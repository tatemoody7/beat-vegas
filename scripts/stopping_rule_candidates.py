#!/usr/bin/env python
"""Print the stopping-rule candidate table (docs/STOPPING_RULE.md) from frozen inputs.

    PYTHONPATH=. python scripts/stopping_rule_candidates.py \\
        --breakeven 0.5475 --sd-units 0.924 --sd-clv 1.714 --sigma-outcome 11.26

The inputs are the 2026 weeks 1-2 paper ledger's mean price-implied break-even and the
sample sds of units per bet and favourable line value, plus the model's outcome sd
(bv_sigma). They are frozen at registration; this script does not read them from the
database on purpose, so a later run cannot drift them. Exits 0.
"""

from __future__ import annotations

import argparse
import json
from typing import Optional, Sequence

from beatvegas.backtest import stopping as S


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--breakeven", type=float, required=True)
    ap.add_argument("--sd-units", type=float, required=True)
    ap.add_argument("--sd-clv", type=float, required=True)
    ap.add_argument("--sigma-outcome", type=float, default=11.26)
    ap.add_argument("--edge", type=float, default=0.04)
    ap.add_argument("--power", type=float, default=0.80)
    ap.add_argument("--json", action="store_true")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    a = parse_args(argv)
    t = S.candidate_table(a.breakeven, a.sd_units, a.sd_clv, a.sigma_outcome, a.edge, power=a.power)
    print(json.dumps(t, indent=1) if a.json else S.render_candidates(t))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
