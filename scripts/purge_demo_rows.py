#!/usr/bin/env python
"""Remove the demo/simulation rows that leaked into Neon (approved 2026-09-07).

scripts/seed_demo.py synthesizes, for 2025 week 8, 12 games x 3 books x 5 daily
stamps of first-half snapshots (captured_at = base + d days + bi hours, i.e.
12:00 / 13:00 / 14:00 UTC on Oct 13-17 2025) plus 5 manual_picks with note
'demo'. Those 180 + 5 rows were meant for data/demo.db but landed in Neon
(flagged by the 2026-09-01 research swarm, lanes/inhouse.md). They polluted the
historical 'real' grading for those 12 games and the demo picks sit in the
2025 ledger.

    python scripts/purge_demo_rows.py            # dry run: list what WOULD go
    python scripts/purge_demo_rows.py --execute  # delete, with the guard below

GUARD: the snapshot signature must match EXACTLY 12 games x 15 rows = 180 and
the pick signature exactly 5 rows, else nothing is deleted.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime

from sqlalchemy import extract

from beatvegas.db.models import Game, ManualPick, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db

SEASON, WEEK = 2025, 8
BOOKS = ("draftkings", "fanduel", "betmgm")
LO, HI = datetime(2025, 10, 13, 12, 0), datetime(2025, 10, 17, 14, 0)  # stored naive UTC
EXPECT_GAMES, EXPECT_PER_GAME, EXPECT_PICKS = 12, 15, 5


def demo_snapshots(s):
    return (
        s.query(OddsSnapshot)
        .join(Game, Game.id == OddsSnapshot.game_id)
        .filter(
            Game.season == SEASON,
            Game.week == WEEK,
            OddsSnapshot.market == "1H_total",
            OddsSnapshot.book.in_(BOOKS),
            OddsSnapshot.captured_at >= LO,
            OddsSnapshot.captured_at <= HI,
            extract("minute", OddsSnapshot.captured_at) == 0,
            extract("second", OddsSnapshot.captured_at) == 0,
            extract("hour", OddsSnapshot.captured_at).in_([12, 13, 14]),
        )
        .all()
    )


def demo_picks(s):
    return s.query(ManualPick).filter(ManualPick.note == "demo", ManualPick.season == SEASON).all()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="actually delete (default: dry run)")
    args = ap.parse_args()
    if not try_init_db():
        return 1
    with session_scope() as s:
        snaps = demo_snapshots(s)
        picks = demo_picks(s)
        per_game = Counter(sn.game_id for sn in snaps)
        print(
            f"snapshot rows matching the demo signature: {len(snaps)} across {len(per_game)} games"
        )
        for gid, n in sorted(per_game.items()):
            print(f"  game {gid}: {n} rows")
        print(f"manual_picks with note='demo' ({SEASON}): {len(picks)}")
        for p in picks:
            print(
                f"  pick #{p.id}: {p.away_team} @ {p.home_team} wk{p.week} u{p.line} paper={p.is_paper}"
            )
        ok = (
            len(per_game) == EXPECT_GAMES
            and all(n == EXPECT_PER_GAME for n in per_game.values())
            and len(picks) == EXPECT_PICKS
        )
        if not ok:
            print(
                f"GUARD: expected {EXPECT_GAMES} games x {EXPECT_PER_GAME} rows and "
                f"{EXPECT_PICKS} picks — signature does not match, nothing deleted."
            )
            return 2
        if not args.execute:
            print("dry run — pass --execute to delete these rows.")
            return 0
        for sn in snaps:
            s.delete(sn)
        for p in picks:
            s.delete(p)
        s.flush()
        print(f"deleted {len(snaps)} odds_snapshots rows and {len(picks)} manual_picks rows")
    with session_scope() as s:
        print(f"after: {len(demo_snapshots(s))} snapshot rows, {len(demo_picks(s))} picks remain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
