#!/usr/bin/env python
"""Operating characteristics of the 2026 Statistical Protocol (docs/PROTOCOL_2026.md).

    python scripts/protocol_sim.py            # writes reports/protocol_sim_<UTC>.{md,json}

No database: it simulates arms under the protocol's own rule
(beatvegas.protocol.simulate) across the worlds that matter -- the true spread
of line value per bet (0.045 measured, 0.06 assumed), a shared week-wide shock
(Saturday market moves), each arm's weekly volume, and the true edge -- and
reports how often an arm is promoted, stopped or timed out, and how many bets
and weeks that takes. Deterministic (fixed seed). Tate approves these numbers
before the protocol is frozen.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from beatvegas.protocol import (
    ALPHA,
    BETA,
    LOWER,
    MAX_OBS,
    MIN_OBS,
    MIN_WEEKS,
    MU1,
    PROTOCOL_VERSION,
    SIGMA,
    SIGMA_WEEK,
    UPPER,
    simulate,
)

ROOT = Path(__file__).resolve().parent.parent
SEASON_WEEKS = 10  # weeks 7-15 plus the bowls, from the protocol's start
MEANS = (-0.05, 0.0, 0.01, 0.03, 0.05)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports")
    ap.add_argument("--reps", type=int, default=20000)
    args = ap.parse_args(argv)
    rows = []
    for per_week in (8, 15):
        for true_sd in (0.05, 0.06):
            for shock in (0.0, 0.005, 0.012, 0.02):
                for mu in MEANS:
                    r = simulate(mu, true_sd, per_week, SEASON_WEEKS, shock, reps=args.reps)
                    rows.append(
                        {
                            "per_week": per_week,
                            "true_sd": true_sd,
                            "week_shock_sd": shock,
                            "true_mean_ev": mu,
                            **r,
                        }
                    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    head = (
        f"# Protocol {PROTOCOL_VERSION} simulation ({stamp})\n\n"
        f"Rule: SPRT on WEEKLY mean line value, H0 mean EV 0 vs H1 +{MU1:.2f}; a week of n bets has assumed "
        f"variance {SIGMA_WEEK}^2 + {SIGMA}^2/n; alpha {ALPHA} per arm, "
        f"beta {BETA}; promote at LLR >= {UPPER:.3f}, stop at LLR <= {LOWER:.3f}; no decision before "
        f"{MIN_OBS} observations over {MIN_WEEKS}+ weeks; timeout at {MAX_OBS} or {SEASON_WEEKS} weeks. "
        f"{args.reps} simulated arms per world.\n\n"
        "| bets/week | true spread | true week move | true mean EV | promote | stop | timeout | mean bets | mean weeks |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    body = "".join(
        f"| {r['per_week']} | {r['true_sd']} | {r['week_shock_sd']} | {r['true_mean_ev']:+.2f} | {r['promote']:.4f} | "
        f"{r['stop']:.4f} | {r['timeout']:.4f} | {r['mean_bets']:.0f} | {r['mean_weeks']:.1f} |\n"
        for r in rows
    )
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"protocol_sim_{stamp}.md").write_text(head + body)
    (outdir / f"protocol_sim_{stamp}.json").write_text(
        json.dumps({"version": PROTOCOL_VERSION, "rows": rows}, indent=1)
    )
    print(head + body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
