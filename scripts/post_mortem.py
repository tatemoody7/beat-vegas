#!/usr/bin/env python
"""Post-mortem: every rated game vs its outcome, written to Neon + docs/POST_MORTEM.md.

Two scopes (beatvegas/postmortem.py):
- hist: the stored walk-forward gbm_v1 ratings for 2023-25, regraded at the flat
  0.52 proxy they were rated against AND at the fair step proxy, FBS-only and all
  divisions, under every policy rule (gap >= 1.75, cap 5/week, gap >= 3, ...).
- live: the built cards for the current season (Hard Rock price reads) graded at
  Hard Rock's number, the consensus number and the consensus close.

Delete-then-insert per scope into postmortem_runs / postmortem_buckets /
postmortem_games, so the Results page reads one live run per scope. Spends no
API credits; reads only what grading already wrote.

    python scripts/post_mortem.py --dry-run --md docs/POST_MORTEM.md
    python scripts/post_mortem.py --write            # what grade.yml runs
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from beatvegas import postmortem as pm
from beatvegas import snapshots
from beatvegas.config import REPO_ROOT
from beatvegas.db.models import (
    Card,
    Game,
    PostMortemBucket,
    PostMortemGame,
    PostMortemRun,
    Prediction,
    Result,
    TeamTempo,
    Weather,
)
from beatvegas.db.store import resync_table_sequence, session_scope, try_init_db
from beatvegas.etl.fbs import load_fbs_teams
from beatvegas.etl.proxy_line import _load_share_coeffs
from beatvegas.lines import (
    REAL_1H_CLOSE_WINDOW_H,
    REAL_FG_CLOSE_WINDOW_H,
    real_closes,
)
from beatvegas.model.score import MODEL_VERSION
from beatvegas.season import current_season

MODEL_MARKET = "market"  # grade.py's consensus-close ledger tag
DERIVED_VERSION = "derived_lines"  # post_derived_lines.py display rows
DEFAULT_MD = REPO_ROOT / "docs" / "POST_MORTEM.md"
CHUNK = 500  # Neon pooler stalls on one giant insert (deploy_neon.py)


# ---------------------------------------------------------------- loaders


def load_step_coeffs() -> Optional[Dict[str, float]]:
    c = _load_share_coeffs()
    if c and c.get("kind") == "step":
        return c
    print(
        "[post_mortem] data/multiplier.json is not a step fit; step column skipped", file=sys.stderr
    )
    return None


def _tempo_lookup(session, seasons: Sequence[int]) -> Dict[Tuple[int, int, str], float]:
    rows = (
        session.query(TeamTempo.season, TeamTempo.week, TeamTempo.team, TeamTempo.seconds_per_play)
        .filter(TeamTempo.season.in_(list(seasons)), TeamTempo.seconds_per_play.isnot(None))
        .all()
    )
    return {
        (int(s), int(w), t): float(spp) for s, w, t, spp in rows if s is not None and w is not None
    }


def load_hist_predictions(session, seasons: Sequence[int], model_version: str) -> List[Dict]:
    """predictions ⋈ games (+ weather, team_tempo fallbacks) as plain dicts."""
    q = (
        session.query(Prediction, Game, Weather)
        .join(Game, Game.id == Prediction.game_id)
        .outerjoin(Weather, Weather.game_id == Game.id)
        .filter(Prediction.model_version == model_version, Game.season.in_(list(seasons)))
    )
    tempo = _tempo_lookup(session, seasons)
    rows = q.all()
    ids = [g.id for _, g, _ in rows]
    kicks = {g.id: g.start_date for _, g, _ in rows}
    closes = real_closes(session, ids, kicks, within_hours=REAL_1H_CLOSE_WINDOW_H)
    fg_closes = real_closes(
        session, ids, kicks, market="full_game_total", within_hours=REAL_FG_CLOSE_WINDOW_H
    )
    out: List[Dict] = []
    for p, g, w in rows:
        spp_vals = [
            tempo.get((g.season, g.week, t))
            for t in (g.home_team, g.away_team)
            if g.week is not None and tempo.get((g.season, g.week, t)) is not None
        ]
        out.append(
            {
                "game_id": g.id,
                "season": g.season,
                "week": g.week,
                "home_team": g.home_team,
                "away_team": g.away_team,
                "start_date": g.start_date,
                "neutral_site": g.neutral_site,
                "spread": g.spread,
                "full_game_total": g.full_game_total,
                "first_half_total": g.first_half_total,
                "first_half_source": g.first_half_source,
                "home_points": g.home_points,
                "away_points": g.away_points,
                "bv_line": p.bv_line,
                "under_score": p.under_score,
                "line_used": p.line_used,
                "factors_json": p.factors_json,
                "wx_temp": w.temperature_f if w else None,
                "wx_wind": w.wind_mph if w else None,
                "wx_dome": (1.0 if w.dome else 0.0) if (w and w.dome is not None) else None,
                "tempo_spp": (sum(spp_vals) / len(spp_vals)) if spp_vals else None,
                "close_line": closes.get(g.id),
                "fg_close": fg_closes.get(g.id),
            }
        )
    return out


def _hr_closes(session, game_ids: Sequence[int], kickoffs: Dict[int, datetime]) -> Dict[int, float]:
    """game_id -> Hard Rock's OWN pre-kickoff 1H close. Lives in
    beatvegas/snapshots.py since 2026-09-15 so the studies share it; kept here by
    name for the existing callers and tests."""
    return snapshots.hr_closes(session, game_ids, kickoffs)


def load_live(
    session, season: int
) -> Tuple[
    List[Dict], Dict[int, Dict], Dict[int, float], Dict[int, float], Dict[int, Optional[str]]
]:
    """Every rated game across the season's cards (newest card wins per game,
    so a game only the morning build carried still counts); games for those
    ids; consensus closes; Hard Rock's own pre-kick closes; and the engine tag
    each stored prediction carries (factors_json.engine, None before the field
    existed) — an added split beside the model_version tag, not a replacement."""
    cards = session.query(Card).filter(Card.season == season).order_by(Card.built_at.desc()).all()
    items: List[Dict] = []
    seen_games = set()
    for c in cards:
        try:
            payload = json.loads(c.payload)
        except (TypeError, ValueError):
            continue
        for it in payload.get("items") or []:
            gid = it.get("game_id")
            if gid is None or gid in seen_games:
                continue
            seen_games.add(gid)
            items.append(it)
    ids = sorted({int(it["game_id"]) for it in items if it.get("game_id") is not None})
    games: Dict[int, Dict] = {}
    kickoffs: Dict[int, datetime] = {}
    if ids:
        derived = {
            pr.game_id: pr.line_used
            for pr in session.query(Prediction)
            .filter(Prediction.model_version == DERIVED_VERSION, Prediction.game_id.in_(ids))
            .all()
        }
        for g in session.query(Game).filter(Game.id.in_(ids)).all():
            if g.start_date is not None:
                kickoffs[g.id] = g.start_date
            games[g.id] = {
                "season": g.season,
                "week": g.week,
                "first_half_total": g.first_half_total,
                "first_half_source": g.first_half_source,
                "home_points": g.home_points,
                "away_points": g.away_points,
                "spread": g.spread,
                "full_game_total": g.full_game_total,
                "derived_line": derived.get(g.id),
            }
    closes: Dict[int, float] = {}
    if ids:
        for r in (
            session.query(Result)
            .filter(Result.model_version == MODEL_MARKET, Result.game_id.in_(ids))
            .all()
        ):
            line = r.closing_line if r.closing_line is not None else r.line_used
            if line is not None:
                closes[r.game_id] = float(line)
    hr_closes = _hr_closes(session, ids, kickoffs) if ids else {}
    engines: Dict[int, Optional[str]] = {}
    if ids:
        rows = (
            session.query(Prediction)
            .filter(Prediction.model_version == MODEL_VERSION, Prediction.game_id.in_(ids))
            .all()
        )
        for pr in sorted(rows, key=pm.created_order):  # newest row wins; NULL = oldest
            engines[pr.game_id] = pm.engine_of(pr.factors_json)
    return items, games, closes, hr_closes, engines


# ---------------------------------------------------------------- writer


def _json_clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _model_rows(model, rows: List[Dict], computed_at: datetime) -> List[Dict]:
    cols = {c.name for c in model.__table__.columns} - {"id"}
    out = []
    for r in rows:
        row = {k: _json_clean(v) for k, v in r.items() if k in cols}
        if "computed_at" in cols:
            row["computed_at"] = computed_at
        out.append(row)
    return out


def _chunked_insert(session, model, rows: List[Dict], chunk: int = CHUNK) -> None:
    for i in range(0, len(rows), chunk):
        session.bulk_insert_mappings(model, rows[i : i + chunk])
        session.commit()


def _resync_sequence(session, model) -> None:
    """Bring the id sequence up to MAX(id) — never down — via the shared store
    rule (Neon tables seeded or partially written by earlier runs can leave the
    sequence behind the data; a concurrent writer may be ahead of it)."""
    resync_table_sequence(session, model.__tablename__)


def write_run(session, out: Dict[str, Any], computed_at: datetime, params: Dict[str, Any]) -> None:
    """Replace one scope's post-mortem: delete, then insert.

    KNOWN NOT ATOMIC, deliberately. The delete commits before the inserts do,
    and the inserts commit per chunk, so a crash in between leaves the scope
    empty or half-filled until the next run — and grade.yml runs this twice a
    day, which widens the window.

    The obvious fix (one transaction around the lot) is the one thing that must
    NOT be done here: a single large bulk_insert_mappings STALLS the Neon pooler
    indefinitely, which is why _chunked_insert exists at all (see
    deploy_neon.py::_chunked_insert and the CLAUDE.md gotcha). Trading a rare
    empty /proof section for a hung daily grading job is the wrong way round.

    What makes it tolerable: the only consumer is /proof, a read-only page, and
    web/lib/postmortem.ts already degrades to "Not computed yet" rather than
    erroring. The real fix is to write under a new run_id and flip a pointer,
    which is a schema change — raised, not smuggled in here.
    """
    scope = out["scope"]
    for model in (PostMortemBucket, PostMortemGame, PostMortemRun):
        session.query(model).filter(model.scope == scope).delete(synchronize_session=False)
    session.commit()
    if session.bind.dialect.name == "postgresql":
        for model in (PostMortemBucket, PostMortemGame, PostMortemRun):
            _resync_sequence(session, model)
        session.commit()
    buckets = _model_rows(PostMortemBucket, out["buckets"] + out["contrasts"], computed_at)
    games = _model_rows(PostMortemGame, out["games"], computed_at)
    session.add(
        PostMortemRun(
            run_id=out["run_id"],
            computed_at=computed_at,
            scope=scope,
            params_json=json.dumps(_json_clean(params)),
            notes_json=json.dumps(_json_clean(out["notes"])),
            dropped_json=json.dumps(_json_clean(out["notes"].get("dropped", {}))),
            n_games=len(games),
            n_buckets=len(buckets),
        )
    )
    session.commit()
    _chunked_insert(session, PostMortemBucket, buckets)
    _chunked_insert(session, PostMortemGame, games)


# ---------------------------------------------------------------- main


def _headline(out: Dict[str, Any], selection: str, segment: str, proxy: str) -> str:
    for b in out["buckets"]:
        if (
            b["dimension"] == "all"
            and b["selection"] == selection
            and b["segment"] == segment
            and b["proxy_kind"] == proxy
        ):
            pct = "—" if b["under_pct"] is None else f"{100 * b['under_pct']:.1f}%"
            return f"{selection}/{segment}/{proxy}: {b['unders']}-{b['overs']}-{b['pushes']}P {pct} units {b['units']:+.1f}"
    return f"{selection}/{segment}/{proxy}: n/a"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--scope", choices=("live", "hist", "both"), default="both")
    ap.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024, 2025])
    ap.add_argument("--live-season", type=int, default=None)
    ap.add_argument("--model-version", default=MODEL_VERSION)
    ap.add_argument("--cap", type=int, default=pm.WEEKLY_CAP)
    ap.add_argument(
        "--md",
        type=str,
        default=str(DEFAULT_MD),
        help="markdown report path; pass '' to skip the report",
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="write the postmortem_* tables")
    g.add_argument("--dry-run", action="store_true", help="compute + markdown only (default)")
    args = ap.parse_args(argv)

    if not try_init_db():
        print("[post_mortem] database unreachable; nothing computed", file=sys.stderr)
        return 0
    now = datetime.utcnow().replace(microsecond=0)
    run_id = pm.run_id_for(now)
    computed_at = now.isoformat() + "Z"
    live_season = args.live_season or current_season()
    outs: List[Dict[str, Any]] = []

    with session_scope() as session:
        if args.scope in ("hist", "both"):
            preds = load_hist_predictions(session, args.seasons, args.model_version)
            df = pm.build_hist_frame(preds, load_step_coeffs(), load_fbs_teams())
            print(
                f"[hist] {len(preds)} predictions -> {len(df)} graded rows; dropped {df.attrs.get('dropped')}"
            )
            if not df.empty:
                out = pm.compute_hist(df, run_id=run_id, computed_at=computed_at, cap=args.cap)
                out["run_id"] = run_id
                outs.append(out)
        if args.scope in ("live", "both"):
            items, games, closes, hr_closes, engines = load_live(session, live_season)
            ldf = pm.build_live_frame(items, games, closes, hr_closes, engines=engines)
            print(
                f"[live] season {live_season}: {len(items)} card items, {len(games)} games, {len(closes)} closes"
            )
            if not ldf.empty:
                out = pm.compute_live(
                    ldf, season=live_season, run_id=run_id, computed_at=computed_at
                )
                out["run_id"] = run_id
                outs.append(out)

        params = {
            "seasons": args.seasons,
            "model_version": args.model_version,
            "cap": args.cap,
            "live_season": live_season,
        }
        if args.write:
            for out in outs:
                write_run(session, out, now, params)
                print(
                    f"[write] {out['scope']}: {len(out['buckets']) + len(out['contrasts'])} bucket rows, {len(out['games'])} games"
                )

    runs = [
        {
            "scope": o["scope"],
            "computed_at": computed_at,
            "n_games": len(o["games"]),
            "notes": o["notes"],
        }
        for o in outs
    ]
    md = pm.render_markdown(
        runs,
        [b for o in outs for b in o["buckets"]],
        [c for o in outs for c in o["contrasts"]],
    )
    if args.md.strip():
        md_path = Path(args.md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md)
        print(f"[md] wrote {md_path} ({len(md.splitlines())} lines)")
    else:
        print("[md] skipped (--md '')")

    for o in outs:
        if o["scope"] == pm.HIST_SCOPE:
            kinds = (
                ("real", "step", "flat")
                if o["notes"].get("real_lines", {}).get("n")
                else ("step", "flat")
            )
            for sel in ("cap5", "gap175", "all"):
                for prx in kinds:
                    print("  " + _headline(o, sel, "fbs_only", prx))
        else:
            for sel in ("bet", "price_read", "all_hr"):
                print("  " + _headline(o, sel, "live", "hr"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
