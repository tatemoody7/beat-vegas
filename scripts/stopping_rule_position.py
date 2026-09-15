#!/usr/bin/env python
"""Where the registered stopping rule stands (docs/STOPPING_RULE.md).

Reads the locked paper decisions from 2026 week 3 onward (manual_picks: is_paper,
market 1H, graded), computes the two SPRT clocks against the frozen constants in
beatvegas/backtest/stopping.py::REGISTERED, and prints the position. A FAILURE verdict
means real money pauses: run `scripts/rule_pause.py on --note "..."` and review.
Nothing here writes.

    PYTHONPATH=. python scripts/stopping_rule_position.py --out reports/stopping
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from residual_gate import append_step_summary, report_paths  # noqa: E402

from beatvegas.backtest import stopping as S  # noqa: E402
from beatvegas.db.models import ManualPick  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports/stopping")
    return ap.parse_args(argv)


def load_observations(session):
    """(units, favourable clv) per locked paper decision from the registered start,
    in placed order. Favourable clv = -(stored clv): stored is closing - bet."""
    start = S.REGISTERED["start"]
    rows = (
        session.query(ManualPick)
        .filter(
            ManualPick.is_paper.is_(True),
            ManualPick.season >= start["season"],
            ManualPick.graded.is_(True),
        )
        .order_by(ManualPick.placed_at, ManualPick.id)
        .all()
    )
    units, clv = [], []
    for p in rows:
        if (p.market or "1H") != "1H":
            continue
        if p.season == start["season"] and (p.week or 0) < start["week"]:
            continue
        if p.units is None:
            continue
        units.append(float(p.units))
        clv.append(float("nan") if p.clv is None else -float(p.clv))
    return units, clv


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[stopping] DB unreachable — skipped.")
        return 0
    with session_scope() as s:
        units, clv = load_observations(s)
    pos = S.registered_position(units, clv)
    md = S.render_position(pos)
    md_path, json_path, _csv = report_paths(args.out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)
    json_path.write_text(json.dumps(pos, indent=1, default=str))
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
