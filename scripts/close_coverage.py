#!/usr/bin/env python
"""Write the close-window coverage gauge (beatvegas/coverage.py -> app_settings
`close_coverage_pct`): the share of last Saturday's Hard-Rock-priced games with a
first-half snapshot inside the registered 2-hour close window. Read by the board
banner and /api/health (web/lib/boardHealth.ts, warns under CLOSE_COVERAGE_MIN).

    python scripts/close_coverage.py

Runs at the end of every Saturday close poll (lines_watch.yml) and daily after
grading (grade.yml). Never fails a run: no database, or no Saturday game in the
look-back, prints and exits 0 with the gauge untouched.
"""

from __future__ import annotations

from beatvegas.coverage import close_window_coverage
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.ops import CLOSE_COVERAGE_PCT, record_gauge


def main() -> None:
    if not try_init_db():
        print("[coverage] DB unreachable -- gauge untouched.")
        return
    with session_scope() as s:
        r = close_window_coverage(s)
    if r is None:
        print("[coverage] no Hard-Rock-priced Saturday game in the look-back -- gauge untouched.")
        return
    note = f"sat={r['date']} games={r['games']} covered={r['covered']}"
    written = record_gauge(CLOSE_COVERAGE_PCT, f"{r['share']:.3f}", note=note)
    print(
        f"[coverage] {r['covered']}/{r['games']} Hard-Rock-priced games on Sat {r['date']} "
        f"had a 1H snapshot inside the close window ({r['share']:.0%}); gauge "
        f"{'written' if written else 'NOT written'}"
    )


if __name__ == "__main__":
    main()
