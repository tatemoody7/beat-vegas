#!/usr/bin/env python
"""Where the H-NEGGAP-P paper-over arms stand (docs/NEGGAP_PAPER.md).

Reads every graded over observation (`challenger_picks`, side='over', arm in
stopping.NEGGAP["arms"]), computes each arm's two SPRT clocks against the frozen
constants in beatvegas/backtest/stopping.py::NEGGAP, and prints the position.
Nothing here writes, and no verdict it prints changes real money.

SIGN: stored clv is closing - bet; for an OVER a RISING line is favourable, so
favourable line value is +clv here -- the reverse of the champion's ledger and
of scripts/challenger_position.py. The line-value clock takes only closes
confirmed inside lines.REAL_1H_CLOSE_WINDOW_H of kickoff and counts the rest.

    PYTHONPATH=. python scripts/neggap_position.py --out reports/neggap
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from residual_gate import append_step_summary, report_paths  # noqa: E402

from beatvegas.backtest import stopping as S  # noqa: E402
from beatvegas.db.models import ChallengerPick, Game  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402
from beatvegas.lines import close_in_window  # noqa: E402


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports/neggap")
    return ap.parse_args(argv)


def load_observations(
    session,
) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, list]]]:
    """One pass over the arms' over rows: (tallies per arm, graded observations
    per arm). Observations are units, prices, favourable clv (+clv for an over)
    and whether the close was inside the window (lines.close_in_window, the same
    rule the champion's clock applies), in placed order. Only the registered
    over arms; the H-INSEASON arms (side under) never enter."""
    rows = (
        session.query(ChallengerPick, Game.start_date)
        .outerjoin(Game, Game.id == ChallengerPick.game_id)
        .filter(ChallengerPick.side == "over", ChallengerPick.arm.in_(list(S.NEGGAP["arms"])))
        .order_by(ChallengerPick.placed_at, ChallengerPick.id)
        .all()
    )
    tallies: Dict[str, Dict[str, int]] = {}
    obs: Dict[str, Dict[str, list]] = {}
    for p, kickoff in rows:
        t = tallies.setdefault(p.arm, {"logged": 0, "graded": 0, "won": 0})
        t["logged"] += 1
        if not p.graded:
            continue
        t["graded"] += 1
        t["won"] += int(p.result == "over")
        o = obs.setdefault(p.arm, {"units": [], "prices": [], "clv": [], "clv_in_window": []})
        o["units"].append(float("nan") if p.units is None else float(p.units))
        o["prices"].append(float("nan") if p.price is None else float(p.price))
        o["clv"].append(float("nan") if p.clv is None else S.NEGGAP["clv_sign"] * float(p.clv))
        o["clv_in_window"].append(close_in_window(p.closing_captured_at, kickoff))
    return tallies, obs


def render(pos: Dict[str, Any], tallies: Dict[str, Dict[str, int]]) -> str:
    r = pos["registered"]
    L = [
        "# H-NEGGAP-P paper overs — running position",
        "",
        f"Design {r['design'].upper()}, total false-decision budget {100 * r['alpha_total']:.0f}% "
        f"split /{len(r['arms'])} across arms ({r['multiplicity']}, "
        f"{100 * r['alpha_arm']:.3f}% each) then /2 across clocks = "
        f"{100 * r['alpha_clock']:.3f}% per arm-clock, power {100 * r['power']:.0f}%. "
        f"Registered {r['registered_on']}. Sigmas {r['sigma']} (the champion's).",
        "",
        "**Paper only.** Nothing here touches real-money selection or H-STOP-2. "
        "Favourable line value for an OVER is +(closing − bet).",
        "",
        "| arm | logged | graded | over (won) |",
        "|---|---|---|---|",
    ]
    for label in r["arms"]:
        t = tallies.get(label, {"logged": 0, "graded": 0, "won": 0})
        L.append(f"| {label} | {t['logged']} | {t['graded']} | {t['won']} |")
    L += [
        "",
        "| arm | clock | n | mean | LLR | A / B | excluded (no close in window) | verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, arm in pos["arms"].items():
        for name, c in arm.get("clocks", {}).items():
            b = c.get("bounds", {})
            mean, llr = c.get("mean"), c.get("llr")
            L.append(
                f"| {label} | {name} | {c.get('n', 0)} | "
                f"{'—' if mean is None else format(mean, '+.4f')} | "
                f"{'—' if llr is None else format(llr, '+.3f')} | "
                f"{b.get('A', float('nan')):.3f} / {b.get('B', float('nan')):.3f} | "
                f"{c.get('excluded_no_close_in_window', 0) if name == 'clv' else '—'} | "
                f"{c.get('verdict') or c.get('status', 'accruing')} |"
            )
    L += ["", "| arm | family verdict |", "|---|---|"]
    for label, arm in pos["arms"].items():
        L.append(f"| {label} | {arm['family_verdict']} |")
    L += [""]
    if pos["passers"]:
        L.append(
            f"**Arms past both boundaries: {', '.join(pos['passers'])}.** A finding for Tate; nothing at real money."
        )
        if not pos["may_name_threshold"]:
            L.append(
                "MORE THAN ONE ARM PASSED, so no threshold is chosen here — that needs its own registered row."
            )
    else:
        L.append("No arm has crossed a boundary. The family accrues.")
    return "\n".join(L) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[neggap] DB unreachable — skipped.")
        return 0
    with session_scope() as s:
        tallies, arms = load_observations(s)
    if not arms:
        print("[neggap] no graded over observations yet — no clock to report.")
        print(json.dumps(tallies, indent=1))
        return 0
    pos = S.neggap_position(arms)
    md = render(pos, tallies)
    md_path, json_path, _csv = report_paths(args.out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)
    json_path.write_text(json.dumps({"position": pos, "tallies": tallies}, indent=1, default=str))
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
