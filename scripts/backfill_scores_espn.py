#!/usr/bin/env python
"""Fill final scores from ESPN when CFBD cannot supply them.

grade.yml's whole job is turning finals into grades, and until 2026-09-13 that
depended on a single vendor: CFBD exhausted its monthly call quota on Sep 12,
429'd every endpoint, and week 2 sat with 14 of 303 games scored and 0 of 31
picks graded for two days. ESPN's public scoreboard needs no key and has no
quota, and its event ids ARE the ids `games.id` already stores.

Deliberately narrow: this UPDATES scores on games the schedule load already
created and writes nothing else. It never inserts a game, never touches team
names (ESPN spells several differently), and never touches lines. `store.upsert`
never overwrites a column with None, so a game ESPN has no line scores for keeps
whatever it already had.

Usage:
    python scripts/backfill_scores_espn.py --days-back 7
    python scripts/backfill_scores_espn.py --start 2026-09-06 --end 2026-09-13
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from typing import List

from beatvegas.db.models import Game
from beatvegas.db.store import init_db, session_scope, upsert
from beatvegas.etl.first_half import attach_first_half
from beatvegas.sources.espn_scores import final_scores

SCORE_COLS = (
    "home_points",
    "away_points",
    "home_first_half_points",
    "away_first_half_points",
    "first_half_total",
    "first_half_source",
)


def _dates(start: date, end: date) -> List[str]:
    out, d = [], start
    while d <= end:
        out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-back", type=int, default=7, help="days back from today (default 7)")
    ap.add_argument("--start", help="YYYY-MM-DD (overrides --days-back)")
    ap.add_argument("--end", help="YYYY-MM-DD (defaults to today)")
    args = ap.parse_args()

    end = date.fromisoformat(args.end) if args.end else date.today()
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=args.days_back)
    dates = _dates(start, end)

    init_db()

    games = final_scores(dates)
    print(f"espn: {len(games)} final games across {dates[0]}..{dates[-1]}")

    rows = []
    for g in games:
        fh = attach_first_half(g)
        rows.append(
            {
                "id": g["id"],
                "home_points": g["homePoints"],
                "away_points": g["awayPoints"],
                **fh,
            }
        )

    # Only games we already know about. Scores for a game that is not on the
    # schedule would be a new row with no teams, season or kickoff -- worse than
    # the missing score it replaces.
    with session_scope() as s:
        known = {
            gid for (gid,) in s.query(Game.id).filter(Game.id.in_([r["id"] for r in rows])).all()
        }
    rows = [r for r in rows if r["id"] in known]
    with_1h = sum(1 for r in rows if r["first_half_total"] is not None)
    if rows:
        with session_scope() as s:
            upsert(s, Game, rows, "id")
    print(f"updated: {len(rows)} known games, {with_1h} with a first-half total")
    if len(known) < len(games):
        print(f"  [note] {len(games) - len(known)} ESPN finals are not on our schedule; skipped")


if __name__ == "__main__":
    main()
