#!/usr/bin/env python
"""Write our derived-1H numbers for the posted lines to the board (Neon).

Display-only: for each posted full-game line, compute our spread-adjusted derived
1H total and store a `predictions` row with model_version="derived_lines" and all
MODEL fields NULL (no under_score, no bv_line, no gap). The Opportunities board
renders these as cards labeled "DERIVED — no model pick". Real in-season scoring
(gbm_v1, newer created_at) auto-supersedes them per the season-scoped board query.

Each derived row's factors_json carries the same DRIVER keys a model row does
(pace, weather, prior-season efficiency, situational numbers, 1H scoring priors,
last-3 form + home/away splits, the tinted factor board) via etl/context.py +
etl/form.py — so weeks 1-2 and FBS-vs-FCS cards show real values, not dashes.

The game universe is Hard Rock's: only games with a Hard Rock full-game snapshot
this week are posted (the only book bettable from Florida).

Runs in the cloud (GitHub Actions) against Neon — the Mac can't reach Neon on the
campus network. Idempotent: replaces prior derived_lines rows for the season.

    python scripts/post_derived_lines.py --season 2026 --week 1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set

from beatvegas.db.models import Game, OddsSnapshot, Prediction
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.context import context_for_games, prior_season_efficiency
from beatvegas.etl.form import form_for_games
from beatvegas.etl.match import match_event
from beatvegas.etl.proxy_line import fh_share, proxy_total
from beatvegas.factors.board import historical_references, load_references
from beatvegas.factors.ledger import load_ledger
from beatvegas.hardrock import HR_BOOK_KEY
from beatvegas.model.score import derived_factors
from beatvegas.season import current_season
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.cfbd_lines import full_game_rows as cfbd_full_game_rows
from beatvegas.sources.draftkings import DraftKingsClient, normalize_full_game

MODEL_VERSION = "derived_lines"


def fetch(source: str, season: int):
    """(rows, source_used) — DK first, CFBD fallback (mirrors poll_full_game)."""
    if source in ("dk", "auto"):
        rows = normalize_full_game(DraftKingsClient().fetch_ncaaf())
        if rows or source == "dk":
            return rows, "dk"
    return cfbd_full_game_rows(CFBDClient(), season), "cfbd"


def hardrock_game_ids(session, season: int, week: Optional[int]) -> Set[int]:
    """Games with a Hard Rock full-game snapshot this season(/week) — the site's
    game universe (Hard Rock is the only book bettable from Florida)."""
    q = (
        session.query(OddsSnapshot.game_id)
        .join(Game, Game.id == OddsSnapshot.game_id)
        .filter(
            Game.season == season,
            OddsSnapshot.book == HR_BOOK_KEY,
            OddsSnapshot.market == "full_game_total",
        )
    )
    if week is not None:
        q = q.filter(Game.week == week)
    return {int(gid) for (gid,) in q.distinct().all()}


def build_prediction_rows(
    fetched: List[Dict],
    gmeta: Dict[int, Dict],
    week: Optional[int],
    context: Optional[Dict[int, Dict]] = None,
    form: Optional[Dict[int, Dict]] = None,
    refs: Optional[Dict] = None,
    ledger: Optional[Dict] = None,
) -> List[Dict]:
    """Pure: map posted full-game rows -> derived-1H prediction-row dicts.

    `gmeta`: game_id -> {week, home, away}; games outside it are dropped (so the
    caller restricts the universe by trimming gmeta). `context` / `form` are the
    per-game maps from etl/context.py / etl/form.py (optional; absent -> the
    driver keys are None). Returns dicts ready for the Prediction model (model
    fields omitted = NULL), ranked by lowest derived 1H. Unit-tested without a DB."""
    games = [
        {"id": gid, "home_team": m["home"], "away_team": m["away"], "start_date": None}
        for gid, m in gmeta.items()
    ]
    context = context or {}
    form = form or {}
    out: List[Dict] = []
    for r in fetched:
        gid = r.get("game_id")
        if gid is None:
            gid, _ = match_event(r["home_team"], r["away_team"], r["commence_time"], games)
        if gid is None or gid not in gmeta:
            continue
        if week is not None and gmeta[gid]["week"] != week:
            continue
        total, spread = r["line"], r.get("spread")
        derived = proxy_total(total, spread=spread)
        payload = derived_factors(
            derived,
            total,
            spread,
            round(fh_share(spread), 3),
            context=context.get(gid),
            form=form.get(gid),
            refs=refs,
            ledger=ledger,
        )
        out.append({"game_id": gid, "line_used": derived, "factors_json": json.dumps(payload)})
    out.sort(key=lambda d: d["line_used"])  # lowest derived 1H first
    for i, d in enumerate(out, start=1):
        d["rank"] = i
    return out


def enrich_maps(session, season: int, gmeta: Dict[int, Dict], efficiency=None) -> tuple:
    """(context, form) for every game in gmeta, grouped by week. Fail-soft per
    week: a hiccup in one source leaves those cards without the extra keys."""
    context: Dict[int, Dict] = {}
    form: Dict[int, Dict] = {}
    by_week: Dict[int, List[int]] = {}
    for gid, m in gmeta.items():
        by_week.setdefault(m["week"], []).append(gid)
    for wk, ids in by_week.items():
        try:
            context.update(context_for_games(session, season, wk, ids, efficiency=efficiency))
        except Exception as e:  # noqa: BLE001 - display-only enrichment
            print(f"[derived] wk{wk}: context unavailable ({e!r})")
        try:
            form.update(form_for_games(session, season, wk, ids))
        except Exception as e:  # noqa: BLE001
            print(f"[derived] wk{wk}: form unavailable ({e!r})")
    return context, form


def write_derived_rows(
    session,
    fetched,
    gmeta,
    week,
    now,
    allowed_ids: Optional[Set[int]] = None,
    efficiency: Optional[Dict[str, Dict]] = None,
    refs: Optional[Dict] = None,
) -> int:
    """Build derived-1H rows and persist them, replacing any prior derived_lines
    rows for the season's games (idempotent). Returns the number written.

    `allowed_ids` restricts the POSTED games (the Hard Rock universe); None =
    every game in gmeta. The delete scope stays the full gmeta so a game that
    drops out of the Hard Rock universe loses its stale card too. `efficiency`
    is the prior-season PPA map from prior_season_efficiency (None = skip the PPA
    keys); `refs` the historical factor references for the board tint (None =
    untinted board).

    Refuses to delete when there is nothing to insert: an empty fetch (DK 403,
    CFBD not posted yet) must never blank the board's existing derived cards."""
    delete_ids = list(gmeta.keys())
    if allowed_ids is not None:
        gmeta = {gid: m for gid, m in gmeta.items() if gid in allowed_ids}
    season = next((m["season"] for m in gmeta.values() if "season" in m), None)
    if season is None:
        season = _season_of(session, gmeta)
    context, form = ({}, {})
    if gmeta and season is not None:
        target = {gid: m for gid, m in gmeta.items() if week is None or m["week"] == week}
        context, form = enrich_maps(session, season, target, efficiency=efficiency)
    ledger = load_ledger(session)
    rows = build_prediction_rows(
        fetched, gmeta, week, context=context, form=form, refs=refs, ledger=ledger
    )
    if not rows:
        return 0

    if delete_ids:
        (
            session.query(Prediction)
            .filter(Prediction.model_version == MODEL_VERSION, Prediction.game_id.in_(delete_ids))
            .delete(synchronize_session=False)
        )
    for d in rows:
        session.add(
            Prediction(
                game_id=d["game_id"],
                model_version=MODEL_VERSION,
                line_used=d["line_used"],
                rank=d["rank"],
                factors_json=d["factors_json"],
                created_at=now,
            )
        )
    return len(rows)


def _season_of(session, gmeta: Dict[int, Dict]) -> Optional[int]:
    if not gmeta:
        return None
    gid = next(iter(gmeta))
    row = session.query(Game.season).filter(Game.id == gid).first()
    return int(row[0]) if row else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int, help="filter to one week (e.g. 1)")
    ap.add_argument("--source", choices=("dk", "cfbd", "auto"), default="auto")
    ap.add_argument(
        "--all-books",
        action="store_true",
        help="post every fetched game, not just those with a Hard Rock full-game snapshot",
    )
    ap.add_argument(
        "--no-refs", action="store_true", help="skip the historical factor references (faster)"
    )
    ap.add_argument(
        "--refs",
        metavar="PATH",
        help="read the factor references from this JSON (written by weekly_update.py "
        "--write-refs earlier in the same run) instead of rebuilding the historical frame; "
        "falls back to the rebuild when the file is missing",
    )
    args = ap.parse_args()

    if not try_init_db():
        return

    fetched, source = fetch(args.source, args.season)
    now = datetime.utcnow()
    efficiency = prior_season_efficiency(args.season)  # fail-soft: {} on CFBD trouble
    if args.no_refs:
        refs = {}
    else:
        refs = (load_references(args.refs) if args.refs else None) or historical_references()

    with session_scope() as s:
        gmeta = {
            g.id: {"week": g.week, "home": g.home_team, "away": g.away_team, "season": g.season}
            for g in s.query(Game).filter(Game.season == args.season).all()
        }
        allowed = None if args.all_books else hardrock_game_ids(s, args.season, args.week)
        n_hr = len(allowed) if allowed is not None else len(gmeta)
        n = write_derived_rows(
            s,
            fetched,
            gmeta,
            args.week,
            now,
            allowed_ids=allowed,
            efficiency=efficiency,
            refs=refs,
        )

    print(
        f"source={source} season={args.season} "
        f"week={args.week if args.week is not None else 'all'} "
        f"hardrock_games={n_hr} derived_rows_written={n} "
        f"ppa_teams={len(efficiency)} board_refs={len(refs)}"
    )
    if n == 0:
        # Nothing built (empty/failed fetch, no Hard Rock games, or no matching
        # games): the previous board rows were left untouched, but the run did
        # NOT do its job — fail loudly so the workflow shows red instead of a
        # silent no-op.
        print("[derived] 0 rows built — existing board rows preserved; failing the run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
