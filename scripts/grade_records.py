#!/usr/bin/env python
"""Fill the real 1H result + outcome on frozen GameRecords (plan Phase 0).

Snapshots are frozen pre-kickoff by store_predictions (our own model-shaped
record). After games finish, this fills each ungraded record's first_half_total,
under_hit, and under/over/push outcome — the only post-kickoff write. Idempotent:
already-graded records are skipped.

    python scripts/grade_records.py

Run it after the weekly score update has landed final 1H totals (e.g. alongside
scripts/grade.py). Pair with scripts/grade_factor_ledger.py to refresh the
factor ledger from the freshly graded real lines.
"""

from __future__ import annotations

from datetime import datetime

from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.game_records import grade_records


def main() -> None:
    if not try_init_db():
        print("[records] DB unreachable — skipped (no traceback).")
        return
    with session_scope() as s:
        n = grade_records(s, datetime.utcnow())
    print(f"[records] graded {n} game record(s).")


if __name__ == "__main__":
    main()
