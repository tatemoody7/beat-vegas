#!/usr/bin/env python
"""Where the H-INSEASON challenger family stands (docs/INSEASON_PAPER.md).

Reads every graded challenger observation (`challenger_picks`), computes each
arm's two SPRT clocks against the frozen constants in
beatvegas/backtest/stopping.py::CHALLENGER, and prints the position. Nothing
here writes, and no verdict it prints changes real money: H-STOP is the only
clock attached to the bankroll, and this file cannot reach it.

The arms' alternatives and sds are H-STOP's own, so an arm's numbers read
directly beside the champion's. The error budget is not: 5% total, split /4
across the arms (Bonferroni) and /2 across the clocks, so each arm-clock runs at
0.625%.

    PYTHONPATH=. python scripts/challenger_position.py --out reports/challenger
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from residual_gate import append_step_summary, report_paths  # noqa: E402
from sqlalchemy import func  # noqa: E402

from beatvegas.backtest import stopping as S  # noqa: E402
from beatvegas.db.models import ChallengerPick  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports/challenger")
    return ap.parse_args(argv)


def load_observations(session) -> Dict[str, Dict[str, list]]:
    """Per arm: (units, favourable clv) in placed order.

    Favourable clv = -(stored clv). The stored value is `closing - bet` and for
    an UNDER a line that FALLS is the good one, so the sign flips here exactly
    as it does for the champion. A "fix" to that is a bug -- see
    web/lib/clvDirection.test.ts.
    """
    rows = (
        session.query(ChallengerPick)
        .filter(ChallengerPick.graded.is_(True))
        .order_by(ChallengerPick.placed_at, ChallengerPick.id)
        .all()
    )
    out: Dict[str, Dict[str, list]] = {}
    for p in rows:
        if (p.market or "1H") != "1H" or p.units is None or not p.arm:
            continue
        obs = out.setdefault(p.arm, {"units": [], "clv": []})
        obs["units"].append(float(p.units))
        obs["clv"].append(float("nan") if p.clv is None else -float(p.clv))
    return out


def latest_build_context(session) -> Dict[str, Any]:
    """What the arms saw at the MOST RECENT build: how many completed games fed
    `c_season`, the weight each arm gave it, and the intercept each applied.

    Printed before any clock so the first rows are checkable at a glance --
    `in_season_n = 0` on every arm means the arms were the champion (no
    completed row carried `bv_intercept`, see scripts/backfill_bv_intercept.py),
    not that the season has said nothing.
    """
    latest = session.query(func.max(ChallengerPick.placed_at)).scalar()
    if latest is None:
        return {"placed_at": None, "arms": {}}
    rows = (
        session.query(ChallengerPick)
        .filter(ChallengerPick.placed_at == latest)
        .order_by(ChallengerPick.arm, ChallengerPick.id)
        .all()
    )
    arms: Dict[str, Dict[str, Any]] = {}
    for p in rows:
        a = arms.setdefault(
            p.arm,
            {
                "rows": 0,
                "slot": p.slot,
                "in_season_n": p.in_season_n,
                "in_season_weight": p.in_season_weight,
                "c_prior": p.c_prior,
                "c_season": p.c_season,
            },
        )
        a["rows"] += 1
    total = session.query(func.count(ChallengerPick.id)).scalar() or 0
    return {"placed_at": latest, "arms": arms, "rows_total": int(total)}


def render_context(ctx: Dict[str, Any]) -> str:
    if not ctx.get("arms"):
        return "No challenger observations logged yet.\n"

    def f(v, spec):
        return "—" if v is None else format(v, spec)

    L = [
        f"Latest build {ctx['placed_at']} (slot {next(iter(ctx['arms'].values())).get('slot')}); "
        f"{ctx.get('rows_total', 0)} observations on file.",
        "",
        "| arm | rows at this build | completed games seen (n) | weight w | c_prior | c_season |",
        "|---|---|---|---|---|---|",
    ]
    for label, a in ctx["arms"].items():
        L.append(
            f"| {label} | {a['rows']} | {f(a['in_season_n'], 'd')} | "
            f"{f(a['in_season_weight'], '.3f')} | {f(a['c_prior'], '+.4f')} | "
            f"{f(a['c_season'], '+.4f')} |"
        )
    return "\n".join(L) + "\n"


def render(pos: Dict[str, Any]) -> str:
    r = pos["registered"]
    L = [
        "# H-INSEASON challenger family — running position",
        "",
        f"Design {r['design'].upper()}, total false-decision budget {100 * r['alpha_total']:.0f}% "
        f"split /{len(r['arms'])} across arms ({r['multiplicity']}, "
        f"{100 * r['alpha_arm']:.2f}% each) then /2 across clocks = "
        f"{100 * r['alpha_clock']:.3f}% per arm-clock, power {100 * r['power']:.0f}%. "
        f"Registered {r['registered_on']}.",
        "",
        "**Paper only.** Nothing here touches real-money selection or H-STOP.",
        "",
        "| arm | clock | n | mean | LLR | A / B | verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for label, arm in pos["arms"].items():
        for name, c in arm.get("clocks", {}).items():
            b = c.get("bounds", {})
            mean = c.get("mean")
            llr = c.get("llr")
            L.append(
                f"| {label} | {name} | {c.get('n', 0)} | "
                f"{'—' if mean is None else format(mean, '+.4f')} | "
                f"{'—' if llr is None else format(llr, '+.3f')} | "
                f"{b.get('A', float('nan')):.3f} / {b.get('B', float('nan')):.3f} | "
                f"{c.get('verdict', 'accruing')} |"
            )
    L += ["", "| arm | family verdict |", "|---|---|"]
    for label, arm in pos["arms"].items():
        L.append(f"| {label} | {arm['family_verdict']} |")
    L += [""]
    if pos["passers"]:
        L.append(f"**Arms past both boundaries: {', '.join(pos['passers'])}.**")
        L.append(
            "A k may be named."
            if pos["may_name_k"]
            else "MORE THAN ONE ARM PASSED, so no k is chosen here — that choice needs its "
            "own registered row, written before it is read."
        )
    else:
        L.append("No arm has crossed a boundary. The family accrues.")
    return "\n".join(L) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[challenger] DB unreachable — skipped.")
        return 0
    with session_scope() as s:
        ctx = latest_build_context(s)
        arms = load_observations(s)
    ctx_md = render_context(ctx)
    print(ctx_md)
    if not arms:
        print("[challenger] no graded challenger observations yet — no clock to report.")
        return 0
    pos = S.challenger_position(arms)
    pos["latest_build"] = ctx
    md = render(pos) + "\n" + ctx_md
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
