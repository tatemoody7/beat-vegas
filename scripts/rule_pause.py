#!/usr/bin/env python
"""Throw or clear the real-money pause (docs/STOPPING_RULE.md).

    python scripts/rule_pause.py on --note "week 6 failure boundary crossed"
    python scripts/rule_pause.py off
    python scripts/rule_pause.py status        # exit 0 = not paused, 2 = paused

While paused, every real-money first-half pick is refused -- POST /api/picks
(web/lib/pickRules.ts, its own 409 reason) and `pick.py add` without --paper, and
--force does not bypass it. Paper picks continue and still count toward the record.
The switch is one row in `app_settings` (key rule_paused); this script is its only
writer. Creating the table is `init_db` (migrate.yml), which `try_init_db` also
runs, so the first `status` on a fresh database creates it.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from beatvegas.db.models import AppSetting
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.picks import RULE_PAUSED_KEY, rule_paused, set_rule_paused


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("action", choices=("on", "off", "status"))
    ap.add_argument("--note", default=None, help="why (shown on the board banner)")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[rule_pause] DB unreachable — nothing changed.", file=sys.stderr)
        return 1
    with session_scope() as s:
        if args.action == "status":
            note = rule_paused(s)
            row = s.get(AppSetting, RULE_PAUSED_KEY)
            since = f" since {row.updated_at:%Y-%m-%d %H:%M} UTC" if row and row.updated_at else ""
            if note is None:
                print("real money: NOT paused" + since)
                return 0
            print(f"real money: PAUSED{since}" + (f" — {note}" if note else ""))
            return 2
        row = set_rule_paused(s, paused=(args.action == "on"), note=args.note)
        s.flush()
        state = "PAUSED" if row.value == "true" else "not paused"
        print(f"real money: {state}" + (f" — {row.note}" if row.note else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
