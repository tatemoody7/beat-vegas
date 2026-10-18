#!/usr/bin/env python
"""Where the H-FG-P paper full-game unders stand (docs/FG_MARKET.md).

Reads every `fg_under` observation (`challenger_picks`, market='full',
side='under'), computes the arm's two SPRT clocks against the frozen constants
in beatvegas/backtest/stopping.py::FG, and prints the position. Nothing here
writes, and no verdict it prints changes real money.

SIGN: stored clv is closing - bet; for an UNDER a FALLING line is favourable, so
favourable line value is -clv here. The line-value clock takes only closes
confirmed inside lines.REAL_FG_CLOSE_WINDOW_H (3 h) of kickoff and counts the
rest; until its sigma is frozen (the first two Saturdays) it reports "not
started" and this script prints the (close - build line) spread it will be
frozen from.

    PYTHONPATH=. python scripts/archive/fg_position.py --out reports/fg
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from beatvegas.backtest import stopping as S  # noqa: E402
from beatvegas.backtest.reporting import append_step_summary, report_paths  # noqa: E402
from beatvegas.db.models import ChallengerPick, Game  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402
from beatvegas.lines import REAL_FG_CLOSE_WINDOW_H, close_in_window  # noqa: E402


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports/fg")
    return ap.parse_args(argv)


def load_observations(session) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, list]]]:
    """(tallies per arm, graded observations per arm), placed order. Only the
    registered full-game under arm; no 1H row or over row can enter."""
    rows = (
        session.query(ChallengerPick, Game.start_date)
        .outerjoin(Game, Game.id == ChallengerPick.game_id)
        .filter(
            ChallengerPick.side == S.FG["side"],
            ChallengerPick.market == S.FG["market"],
            ChallengerPick.arm.in_(list(S.FG["arms"])),
        )
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
        t["won"] += int(p.result == "under")
        o = obs.setdefault(
            p.arm, {"units": [], "prices": [], "clv": [], "clv_in_window": [], "move": []}
        )
        o["units"].append(float("nan") if p.units is None else float(p.units))
        o["prices"].append(float("nan") if p.price is None else float(p.price))
        o["clv"].append(float("nan") if p.clv is None else S.FG["clv_sign"] * float(p.clv))
        inside = close_in_window(p.closing_captured_at, kickoff, hours=REAL_FG_CLOSE_WINDOW_H)
        o["clv_in_window"].append(inside)
        # (close - build line), the quantity the line-value sigma freezes from
        if inside and p.clv is not None:
            o["move"].append(float(p.clv))
    return tallies, obs


def render(pos: Dict[str, Any], tallies: Dict[str, Dict[str, int]], obs: Dict) -> str:
    r = pos["registered"]
    L = [
        "# H-FG-P paper full-game unders — running position",
        "",
        f"Design {r['design'].upper()}, total false-decision budget {100 * r['alpha_total']:.0f}% "
        f"split /2 across clocks = {100 * r['alpha_clock']:.1f}% per clock, power "
        f"{100 * r['power']:.0f}%. Registered {r['registered_on']}. Sigmas {r['sigma']}.",
        "",
        "**Paper only.** Nothing here touches real money or H-STOP-2. Favourable line value "
        "for an UNDER is −(closing − bet), against the consensus full-game close inside 3 h.",
        "",
        "| arm | logged | graded | under (won) |",
        "|---|---|---|---|",
    ]
    for label in r["arms"]:
        t = tallies.get(label, {"logged": 0, "graded": 0, "won": 0})
        L.append(f"| {label} | {t['logged']} | {t['graded']} | {t['won']} |")
    L += [
        "",
        "| arm | clock | n | mean | LLR | A / B | excluded (no close in window) | status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for label, arm in pos["arms"].items():
        for name, c in arm["clocks"].items():
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
    if r["sigma"]["clv"] is None:
        L += ["", "Line-value sigma NOT frozen yet (first two Saturdays):"]
        for label, o in obs.items():
            mv = o.get("move", [])
            sd = statistics.stdev(mv) if len(mv) >= 2 else None
            L.append(
                f"- {label}: {len(mv)} in-window (close − build line) moves; "
                f"sd {'—' if sd is None else format(sd, '.3f')}"
            )
    L += [""]
    if pos["passers"]:
        L.append(
            f"**Past both boundaries: {', '.join(pos['passers'])}.** A finding; nothing at real money."
        )
    else:
        L.append("No boundary crossed. The arm accrues.")
    return "\n".join(L) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[fg] DB unreachable — skipped.")
        return 0
    with session_scope() as s:
        tallies, obs = load_observations(s)
    if not obs:
        print("[fg] no graded full-game under observations yet — no clock to report.")
        print(json.dumps(tallies, indent=1))
        return 0
    pos = S.fg_position(obs)
    md = render(pos, tallies, obs)
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
