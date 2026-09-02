#!/usr/bin/env python
"""Score the upcoming slate and log the model's picks (predictions).

Builds features, scores each game's 1H-under probability + 0-100 score, and
stores predictions with the current **opening consensus** line as `line_used`
(proxy fallback when no line is posted yet). Auto-detects the current week.

    python scripts/weekly_update.py                 # current season, auto week
    python scripts/weekly_update.py --season 2025 --week 8
"""

from __future__ import annotations

import argparse
import statistics
import sys
from typing import Dict, Optional, Tuple

from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.features import apply_min_games, build_feature_frame
from beatvegas.etl.proxy_line import proxy_total
from beatvegas.lines import consensus_open_close
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


def opening_line_lookup(season: int, week: int) -> Tuple[Dict[int, float], Dict[int, str]]:
    """Per-game ranking line + provenance.

    Prefers an OBSERVED retail 1H opener (kind 'observed_1h'); else DERIVES a 1H
    number from the captured full-game opener via the spread-adjusted multiplier
    (kind 'derived_fg') — which on Sunday is every game, before the retail 1H
    market posts. Games with neither are left to score_slate's internal proxy."""
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
    for gid, book, line, spread, market, cap in rows:
        snap = type("S", (), {"book": book, "line": line, "spread": spread, "captured_at": cap})
        (h1 if market == "1H_total" else fg).setdefault(gid, []).append(snap)

    for gid, snaps in h1.items():
        opening = consensus_open_close(snaps)[0]
        if opening is not None:
            lines[gid], kinds[gid] = opening, "observed_1h"
    for gid, snaps in fg.items():
        if gid in lines:
            continue  # observed 1H opener wins
        open_total, open_spread = _full_game_opener(snaps)
        if open_total is not None:
            lines[gid] = proxy_total(open_total, spread=open_spread)
            kinds[gid] = "derived_fg"
    return lines, kinds


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
    scored["qb_out_detail"] = details
    flagged = sum(1 for h, a in zip(homes, aways) if h or a)
    print(f"qb-out flags: {flagged}/{len(scored)} games (live Rotowire, unofficial)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int)
    ap.add_argument("--min-games", type=int, default=2)
    args = ap.parse_args()
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

    lines, kinds = opening_line_lookup(args.season, week)
    scored = score_slate(
        args.season, target_week=week, line_lookup=lines, line_kind_lookup=kinds, df=df
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
    obs = sum(1 for k in kinds.values() if k == "observed_1h")
    der = sum(1 for k in kinds.values() if k == "derived_fg")
    print(
        f"scored {n} games for {args.season} wk{week} "
        f"({obs} observed 1H, {der} derived-from-full-game, rest proxy)"
    )
    top = scored.head(5)
    for _, r in top.iterrows():
        print(
            f"  #{int(r['rank'])} score {int(r['under_score'])}  "
            f"{r['away_team']} @ {r['home_team']}  line {r['line']:g}"
        )


if __name__ == "__main__":
    main()
