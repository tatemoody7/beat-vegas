#!/usr/bin/env python
"""Score the upcoming slate and log the model's picks (predictions).

Builds features, scores each game's 1H-under probability + 0-100 score, and
stores predictions with the ranking line as `line_used` (proxy fallback when no
line is posted yet). Auto-detects the current week.

The ranking line's basis follows the engine (config model.engine / BV_ENGINE):
the incumbent bv_line ranks against the **opening consensus** 1H line; the
residual engine conditions on the **current** line (Hard Rock's latest 1H
number, else the books' latest consensus, else derived from the full-game
opener) and is handed the training rows' REAL 1H closes.

    python scripts/weekly_update.py                 # current season, auto week
    python scripts/weekly_update.py --season 2025 --week 8
    python scripts/weekly_update.py --line-basis current   # force the basis
    python scripts/weekly_update.py --if-engine residual   # card-day re-score:
        # no-op (exit 0, no DB work) unless config model.engine is `residual`

When the engine hands back a fitted model (score_slate attrs["engine_artifact"],
residual engine only) the run persists it with its training fingerprint
(model_artifacts + a model_runs row) and prints one `fingerprint ...` line
naming what moved since the previous fit, so a mid-season change to the
training history is visible in the job log. The incumbent writes nothing new.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import datetime
from typing import Dict, Optional, Tuple

import pandas as pd

from beatvegas.config import engine_name
from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.features import apply_min_games, build_feature_frame
from beatvegas.etl.proxy_line import proxy_total
from beatvegas.hardrock import HR_BOOK_KEY
from beatvegas.lines import (
    REAL_1H_CLOSE_WINDOW_H,
    consensus_open_close,
    pre_kickoff,
    real_closes,
)
from beatvegas.model.artifacts import (
    fingerprint_changed,
    latest_artifact,
    persist_artifact,
)
from beatvegas.model.score import score_slate, store_predictions
from beatvegas.season import current_season, detect_week
from beatvegas.sources import rotowire


def _full_game_opener(snaps: list) -> Tuple[Optional[float], Optional[float]]:
    """(opener_total, opener_spread): median across books of each book's FIRST
    full-game snapshot (the Sunday opener)."""
    by_book: Dict[str, list] = {}
    for sn in snaps:
        by_book.setdefault(sn.book, []).append(sn)
    totals, spreads = [], []
    for book_snaps in by_book.values():
        first = sorted(book_snaps, key=lambda s: s.captured_at)[0]
        if first.line is not None:
            totals.append(first.line)
        if first.spread is not None:
            spreads.append(first.spread)
    open_total = statistics.median(totals) if totals else None
    open_spread = statistics.median(spreads) if spreads else None
    return open_total, open_spread


LINE_BASES = ("opener", "current")


def resolve_basis(basis: str, engine: str) -> str:
    """`auto` -> the basis the engine expects: the residual engine conditions
    on the line you can bet NOW, the incumbent ranks against the opener."""
    if basis == "auto":
        return "current" if engine == "residual" else "opener"
    return basis


def _latest(snaps: list):
    return sorted(snaps, key=lambda s: s.captured_at)[-1]


def ranking_line_lookup(
    season: int, week: int, basis: str = "opener"
) -> Tuple[Dict[int, float], Dict[int, str]]:
    """Per-game ranking line + provenance for the week.

    basis="opener": an OBSERVED retail 1H opener (consensus of each book's first
    snapshot; kind 'observed_1h'); else a 1H number DERIVED from the captured
    full-game opener via the spread-adjusted multiplier (kind 'derived_fg') —
    which on Sunday is every game, before the retail 1H market posts.
    basis="current": Hard Rock's LATEST PRE-KICKOFF 1H line (kind 'hr_1h'); else
    the median of each book's latest pre-kick 1H line ('observed_1h'); else
    'derived_fg' as above. A game whose only 1H captures are in-play has no
    bettable 1H number and falls through to derived_fg too.
    Games with none are left to score_slate's internal proxy."""
    if basis not in LINE_BASES:
        raise ValueError(f"unknown line basis {basis!r}; expected one of {LINE_BASES}")
    lines: Dict[int, float] = {}
    kinds: Dict[int, str] = {}
    with session_scope() as s:
        rows = (
            s.query(
                OddsSnapshot.game_id,
                OddsSnapshot.book,
                OddsSnapshot.line,
                OddsSnapshot.spread,
                OddsSnapshot.market,
                OddsSnapshot.captured_at,
                Game.start_date,
            )
            .join(Game, Game.id == OddsSnapshot.game_id)
            .filter(
                Game.season == season,
                Game.week == week,
                OddsSnapshot.market.in_(("1H_total", "full_game_total")),
            )
            .all()
        )
    h1: Dict[int, list] = {}
    fg: Dict[int, list] = {}
    kickoffs: Dict[int, object] = {}
    for gid, book, line, spread, market, cap, start_date in rows:
        snap = type("S", (), {"book": book, "line": line, "spread": spread, "captured_at": cap})
        (h1 if market == "1H_total" else fg).setdefault(gid, []).append(snap)
        kickoffs[gid] = start_date

    for gid, snaps in h1.items():
        if basis == "current":
            # A midweek re-run can catch in-play snapshots (poll_lines defaults
            # to --hours-back 24, well past kickoff for games already underway).
            # Never condition the residual model on a live line.
            kick = kickoffs.get(gid)
            snaps = pre_kickoff(snaps, kick)
            # lines.pre_kickoff hands back EVERY snapshot when none is pre-kick,
            # so for a game we only ever caught in-play the filter is a no-op and
            # the "latest" line would be a LIVE number. Skip its 1H market
            # outright: the loop below derives a 1H line from the full-game opener.
            if kick is not None and not any(
                sn.captured_at is None or sn.captured_at <= kick for sn in snaps
            ):
                continue
            hr = [sn for sn in snaps if sn.book == HR_BOOK_KEY and sn.line is not None]
            if hr:
                lines[gid], kinds[gid] = float(_latest(hr).line), "hr_1h"
                continue
            line = consensus_open_close(snaps)[1]  # median of each book's LATEST
            kind = "observed_1h"
        else:
            line = consensus_open_close(snaps)[0]  # median of each book's FIRST
            kind = "observed_1h"
        if line is not None:
            lines[gid], kinds[gid] = line, kind
    for gid, snaps in fg.items():
        if gid in lines:
            continue  # a posted 1H line wins
        open_total, open_spread = _full_game_opener(snaps)
        if open_total is not None:
            lines[gid] = proxy_total(open_total, spread=open_spread)
            kinds[gid] = "derived_fg"
    return lines, kinds


def opening_line_lookup(season: int, week: int) -> Tuple[Dict[int, float], Dict[int, str]]:
    """The incumbent lookup: ranking_line_lookup(basis="opener")."""
    return ranking_line_lookup(season, week, basis="opener")


def training_real_closes(frame: pd.DataFrame, season: int) -> Dict[int, float]:
    """game_id -> REAL pre-kick 1H close for the residual engine's training rows
    (prior seasons only, within REAL_1H_CLOSE_WINDOW_H of kickoff). Rows with
    no known kickoff are skipped: without one the window cannot be enforced
    and a stale opener could masquerade as a close."""
    train = frame[frame["season"] < season]
    kick = pd.to_datetime(train["start_date"], errors="coerce")
    ok = kick.notna()
    kickoffs = {int(g): k.to_pydatetime() for g, k in zip(train.loc[ok, "id"], kick[ok])}
    if not kickoffs:
        return {}
    with session_scope() as s:
        return real_closes(
            s, list(kickoffs), kickoffs, "1H_total", within_hours=REAL_1H_CLOSE_WINDOW_H
        )


def persist_engine_artifact(
    scored: pd.DataFrame, *, engine: str, season: int, week: int, now: Optional[datetime] = None
) -> Optional[str]:
    """Store the fitted model score_slate attached (attrs["engine_artifact"]) as
    one model_artifacts row and return the log line
    `fingerprint <hash> n_rows=<n> max_game_date=<d> changed=<...>` — comparing
    against the previous artifact for this engine, so a mid-season data
    correction shows in the job log. `changed=first_fit` when there is no
    previous artifact for the engine (distinct from `changed=[]`, same history
    as last time). Returns None (and writes NOTHING) when the frame carries no
    artifact: the incumbent engine, or a demoted residual run.

    No model_runs row is written. model_runs is retrain.py's run log; the
    Research page (web/lib/research.ts) reads the NEWEST FIVE rows looking for
    `bv_residual` calibration metrics, so a per-scoring-run row without them
    would blank that panel within a week of the engine being on and pad the
    "Model runs over time" table. Everything a run-log row would have carried
    (fingerprint, sigma, n_train, fallback) sits on the artifact row —
    fingerprint_json + metrics_json — and each game's factors_json carries the
    fingerprint too."""
    artifact = scored.attrs.get("engine_artifact") or {}
    model = artifact.get("model")
    if model is None:
        return None
    fp = artifact.get("fingerprint") or {}
    now = now or datetime.utcnow()
    metrics = {
        "sigma": artifact.get("sigma"),
        "n_train": fp.get("n_rows"),
        "n_rows_residual": artifact.get("n_rows_residual"),
        "n_rows_fallback": artifact.get("n_rows_fallback"),
        "fallback": scored.attrs.get("engine_fallback"),
    }
    with session_scope() as s:
        prev = latest_artifact(s, engine)
        changed = "first_fit" if prev is None else str(fingerprint_changed(prev, fp))
        persist_artifact(
            s,
            engine=engine,
            model=model,
            fingerprint=fp,
            season=season,
            week=week,
            metrics=metrics,
            now=now,
        )
    return (
        f"fingerprint {fp.get('feature_hash')} n_rows={fp.get('n_rows')} "
        f"max_game_date={fp.get('max_game_date')} changed={changed}"
    )


def _enrich_qb_out(scored) -> None:
    """Forward-only: tag the upcoming slate with live 'QB OUT' flags from the
    Rotowire injury report (ESPN publishes no college injuries).

    ONE report call for the whole slate, matched to our school names the same
    way scripts/research_preview.py does. Display only, unofficial, fail-silent
    — never a model feature, never backfilled. Mutates `scored` in place, adding
    qb_out_home/away/detail which store_predictions persists into factors_json."""
    report = rotowire.fetch_injury_report()
    if not report:
        print("[rotowire] WARNING: injury report empty/unreachable — qb-out flags all False")
    schools = sorted(set(scored["home_team"]) | set(scored["away_team"]))
    inj_by_school = rotowire.by_school(report, schools) if report else {}

    homes, aways, details = [], [], []
    for _, r in scored.iterrows():
        parts = []
        flags = {}
        for side, school in (("home", r["home_team"]), ("away", r["away_team"])):
            d = rotowire.qb_out_detail(inj_by_school.get(school, []))
            flags[side] = d is not None
            if d:
                parts.append(f"{school}: {d}")
        homes.append(flags["home"])
        aways.append(flags["away"])
        details.append(" · ".join(parts) or None)
    scored["qb_out_home"] = homes
    scored["qb_out_away"] = aways
    # object dtype keeps None as None across pandas versions (newer pandas
    # coerces a list with None into NaN, which is not a str for factors_json).
    scored["qb_out_detail"] = pd.Series(details, index=scored.index, dtype="object")
    flagged = sum(1 for h, a in zip(homes, aways) if h or a)
    print(f"qb-out flags: {flagged}/{len(scored)} games (live Rotowire, unofficial)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int)
    ap.add_argument("--min-games", type=int, default=0)
    ap.add_argument(
        "--line-basis",
        choices=("auto", *LINE_BASES),
        default="auto",
        help="ranking line: opener (incumbent), current (HR latest > consensus latest > "
        "derived), auto = current for the residual engine else opener",
    )
    ap.add_argument(
        "--if-engine",
        metavar="NAME",
        help="only run when config model.engine is NAME; otherwise print one line and "
        "exit 0 without touching the database (the card-day re-score step)",
    )
    args = ap.parse_args()
    engine = engine_name()
    if args.if_engine and engine != args.if_engine:
        print(f"engine is {engine!r}, not {args.if_engine!r}: nothing to re-score")
        return
    basis = resolve_basis(args.line_basis, engine)
    if not try_init_db():
        return

    week = args.week or detect_week(args.season)
    if week is None:
        print(
            f"Could not detect an active week for {args.season}. "
            "Pass --week explicitly (offseason has no upcoming games)."
        )
        return

    # Build WITHOUT the min_games cut so we can tell "nothing eligible yet" from
    # "scoring broke": the frame keeps every game with a full-game total
    # (including the unplayed target week), and the cut is applied here.
    frame = build_feature_frame(min_games=0)
    in_week = (frame["season"] == args.season) & (frame["week"] == week)
    n_with_total = int(in_week.sum())
    df = apply_min_games(frame, args.min_games)
    n_eligible = int(((df["season"] == args.season) & (df["week"] == week)).sum())

    lines, kinds = ranking_line_lookup(args.season, week, basis=basis)
    # The residual engine can only learn from games with a REAL close; the
    # incumbent never looks (no behaviour change, no extra query).
    closes = training_real_closes(frame, args.season) if engine == "residual" else None
    scored = score_slate(
        args.season,
        target_week=week,
        line_lookup=lines,
        line_kind_lookup=kinds,
        df=df,
        engine=engine,
        real_closes=closes,
    )
    if scored.empty:
        if n_with_total == 0:
            print(
                f"{args.season} wk{week}: no games with a full-game total yet — "
                "nothing to score (the opener capture fills Game.full_game_total)."
            )
            return
        if n_eligible == 0:
            print(
                f"No scorable games for {args.season} wk{week}: {n_with_total} have a total "
                f"but none clear the cut (need >= {args.min_games} games played by both teams)."
            )
            return
        # Eligible rows existed and still nothing came back — that is a bug or
        # missing training data, not an empty week. Fail so the workflow shows red.
        print(
            f"ERROR: {n_eligible} eligible games for {args.season} wk{week} "
            "but score_slate returned no rows (no prior-season training data?)."
        )
        sys.exit(1)
    _enrich_qb_out(scored)
    n = store_predictions(scored)
    fp_line = persist_engine_artifact(scored, engine=engine, season=args.season, week=week)
    if fp_line:
        print(fp_line)
    hr = sum(1 for k in kinds.values() if k == "hr_1h")
    obs = sum(1 for k in kinds.values() if k == "observed_1h")
    der = sum(1 for k in kinds.values() if k == "derived_fg")
    fallback = scored.attrs.get("engine_fallback")
    # Prefer the ROWS THE MODEL ACTUALLY TRAINED ON (score_slate's residual
    # branch, via the fingerprint it stamps into engine_artifact) over
    # len(closes): closes is computed off the pre-apply_min_games frame, so it
    # can count games score_slate's min-games/training cut later drops.
    artifact = scored.attrs.get("engine_artifact") or {}
    fingerprint = artifact.get("fingerprint") or {}
    n_train = fingerprint.get("n_rows")
    train_rows = n_train if n_train is not None else len(closes or {})
    # The residual only runs on rows with a REAL posted 1H line; the rest keep
    # the incumbent's number. Say how the board actually split.
    split = ""
    if engine == "residual":
        n_resid = artifact.get("n_rows_residual", 0)
        split = f" rows_residual={n_resid} rows_fallback={artifact.get('n_rows_fallback', n)}"
    print(
        f"scored {n} games for {args.season} wk{week} "
        f"({hr} Hard Rock 1H, {obs} observed 1H, {der} derived-from-full-game, rest proxy) "
        f"engine={engine} basis={basis} train_rows_with_close={train_rows}{split}"
        + (f" FALLBACK={fallback}" if fallback else "")
    )
    top = scored.head(5)
    for _, r in top.iterrows():
        print(
            f"  #{int(r['rank'])} score {int(r['under_score'])}  "
            f"{r['away_team']} @ {r['home_team']}  line {r['line']:g}"
        )


if __name__ == "__main__":
    main()
