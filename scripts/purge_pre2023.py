"""Hard-delete all data before a season floor (default 2023) from whatever DB
DATABASE_URL points at (local SQLite or Neon Postgres).

IRREVERSIBLE. Dry-run by default — prints the row counts it WOULD delete.
Pass --execute to actually delete. FK-safe order (children before parents) so
it works on Postgres (FK enforced) and SQLite alike.

Leaves reference tables (teams, venues) and non-season-scoped metadata
(factor_scores, factor_ledger, model_runs) untouched — those hold no pre-floor
data to remove.

Usage:
    python scripts/purge_pre2023.py                 # dry-run on local SQLite
    python scripts/purge_pre2023.py --execute       # delete on local SQLite
    DATABASE_URL=<neon> python scripts/purge_pre2023.py --execute   # Neon
"""

import argparse
import sys

from beatvegas.config import database_url
from beatvegas.db import models as M
from beatvegas.db.store import init_db, session_scope

FLOOR_DEFAULT = 2023

# Game-linked tables (no own season col): deleted by joining to games.id.
GAME_LINKED = [
    M.Result,
    M.Prediction,
    M.OddsSnapshot,
    M.BvAdjustment,
    M.Weather,
]
# Tables with their own season column: deleted by season directly.
SEASON_SCOPED = [
    M.ManualPick,
    M.GameRecord,
    M.FhTeamGame,
    M.TeamWeekFeature,
    M.TeamTempo,
]
# Deleted last (parent).
PARENT = M.Game


def _mask(url: str) -> str:
    if "@" in url:
        head, tail = url.split("@", 1)
        scheme = head.split("://", 1)[0]
        return f"{scheme}://***@{tail}"
    return url


def purge(floor: int, execute: bool) -> int:
    init_db()
    total = 0
    with session_scope() as s:
        game_ids = [
            gid for (gid,) in s.query(M.Game.id).filter(M.Game.season < floor).all()
        ]
        print(f"games with season < {floor}: {len(game_ids)}")

        # Children first (FK-safe). Game-linked tables join via game_id.
        for model in GAME_LINKED:
            q = s.query(model).filter(
                model.game_id.in_(s.query(M.Game.id).filter(M.Game.season < floor))
            )
            n = q.count()
            total += n
            print(f"  {model.__tablename__:20s} (via game_id): {n}")
            if execute and n:
                q.delete(synchronize_session=False)

        # Season-scoped tables delete by their own season column.
        for model in SEASON_SCOPED:
            q = s.query(model).filter(model.season < floor)
            n = q.count()
            total += n
            print(f"  {model.__tablename__:20s} (via season):  {n}")
            if execute and n:
                q.delete(synchronize_session=False)

        # Parent last.
        pq = s.query(PARENT).filter(PARENT.season < floor)
        n = pq.count()
        total += n
        print(f"  {PARENT.__tablename__:20s} (parent):       {n}")
        if execute and n:
            pq.delete(synchronize_session=False)

        if not execute:
            # session_scope commits on exit; nothing was changed in dry-run.
            pass
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", type=int, default=FLOOR_DEFAULT, help="delete season < FLOOR")
    ap.add_argument("--execute", action="store_true", help="actually delete (default: dry-run)")
    args = ap.parse_args()

    print(f"DB: {_mask(database_url())}")
    print(f"mode: {'EXECUTE (irreversible)' if args.execute else 'DRY-RUN'}  floor: {args.floor}")
    total = purge(args.floor, args.execute)
    verb = "deleted" if args.execute else "would delete"
    print(f"\n{verb} {total} rows across all tables (season < {args.floor}).")
    if not args.execute:
        print("Re-run with --execute to delete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
