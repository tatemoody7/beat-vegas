#!/usr/bin/env python
"""Write one operational gauge (beatvegas/ops.py) from a workflow step.

    python scripts/record_gauge.py --key last_grade_completed_at --now
    python scripts/record_gauge.py --key some_key --value 42

grade.yml calls the first form AFTER its fatal grading steps, so the gauge is a
positive fact that grading itself finished -- the fact the 4-hour probe keys on.
The post-mortem row it used to read is written even when four earlier
continue-on-error steps failed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Optional, Sequence

from beatvegas.db.store import try_init_db
from beatvegas.ops import GAUGE_KEYS, record_gauge


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True, choices=GAUGE_KEYS)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--value")
    g.add_argument("--now", action="store_true", help="the current UTC time, ISO 8601")
    ap.add_argument("--note")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[record_gauge] DB unreachable — skipped.")
        return 0
    value = (
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
        if args.now
        else args.value
    )
    ok = record_gauge(args.key, value, args.note)
    print(f"[record_gauge] {args.key} = {value} ({'written' if ok else 'NOT written'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
