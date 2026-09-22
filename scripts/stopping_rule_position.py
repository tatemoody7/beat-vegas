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
    ap.add_argument(
        "--clock",
        type=int,
        choices=(1, 2),
        default=2,
        help="1 = H-STOP (closed 2026-09-22 at n=30, superseded; printed for history); "
        "2 = H-STOP-2, the registered clock on the H-PCT rule from 2026 week 5 (default)",
    )
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


def load_observations_2(session):
    """Clock 2 (H-STOP-2): locked paper 1H picks of the H-PCT rule from the
    registered start, in placed order. Returns (units, prices) for the PRICED
    picks and (clv, in_window) for EVERY pick, where in_window says the consensus
    close was confirmed inside REGISTERED_2["close_window_h"] of kickoff -- the
    line-value clock excludes and counts the rest. Unpriced picks stay in the
    clv series (H-STOP dropped them from both clocks; that was a silent
    conditioning of a sequential test)."""
    from datetime import timedelta

    from beatvegas.db.models import Game

    start = S.REGISTERED_2["start"]
    window = timedelta(hours=float(S.REGISTERED_2["close_window_h"]))
    rows = (
        session.query(ManualPick, Game.start_date)
        .join(Game, Game.id == ManualPick.game_id)
        .filter(
            ManualPick.is_paper.is_(True),
            ManualPick.season >= start["season"],
            ManualPick.graded.is_(True),
        )
        .order_by(ManualPick.placed_at, ManualPick.id)
        .all()
    )
    units, prices, clv, in_window = [], [], [], []
    for p, kick in rows:
        if (p.market or "1H") != "1H":
            continue
        if p.season == start["season"] and (p.week or 0) < start["week"]:
            continue
        if p.units is not None and p.price is not None:
            units.append(float(p.units))
            prices.append(float(p.price))
        if p.clv is not None:
            clv.append(-float(p.clv))
            ok = (
                p.closing_captured_at is not None
                and kick is not None
                and (kick - p.closing_captured_at) <= window
                and p.closing_captured_at <= kick
            )
            in_window.append(bool(ok))
    return units, prices, clv, in_window


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[stopping] DB unreachable — skipped.")
        return 0
    if args.clock == 2:
        with session_scope() as s:
            units, prices, clv, in_window = load_observations_2(s)
        pos = S.registered_position_2(units, prices, clv, in_window)
        md = S.render_position_2(pos)
    else:
        with session_scope() as s:
            units, clv = load_observations(s)
        pos = S.registered_position(units, clv)
        md = (
            "> Clock 1 (H-STOP) CLOSED 2026-09-22 at n=30, no boundary crossed; superseded by "
            "Clock 2. Printed for history only.\n\n"
        ) + S.render_position(pos)
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
