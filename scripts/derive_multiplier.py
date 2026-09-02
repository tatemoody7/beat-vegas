#!/usr/bin/env python
"""Fit the spread-aware 1H share and adopt it ONLY if it beats flat 0.52.

Two candidate shapes, both fitted on realized 1H points of FBS-vs-FBS games with
a known closing spread and scored walk-forward (each season by a fit on PRIOR
seasons only):

  linear  share = a + b*|spread|                      (the original 2026-05 curve)
  step    share = base below |spread| < cut, blowout at/above (FBS-only finding:
          ~0.51 for spreads under 21, ~0.54 in 21+ blowouts — a step, not a slope)

The winner is compared with the flat-0.52 baseline on 1H-line MAE. If — and only
if — it wins by MIN_ADOPT_MARGIN, data/multiplier.json is written and
proxy_line.fh_share() picks it up. Otherwise flat 0.52 stays (zero behaviour
change). Spreads exist only from 2023 (scripts/backfill_spread.py), so the
walk-forward has few test seasons; the margin gate is what keeps this honest.

    python scripts/derive_multiplier.py             # fit, report, write if it wins
    python scripts/derive_multiplier.py --no-write  # report only
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, Optional

import numpy as np
import pandas as pd

from beatvegas.config import REPO_ROOT
from beatvegas.db.store import init_db
from beatvegas.etl.proxy_line import (
    DEFAULT_SHARE,
    SHARE_CLAMP,
    fh_share,
    fit_share,
    fit_share_step,
    load_games_frame,
)

_OUT = REPO_ROOT / "data" / "multiplier.json"

# Adoption is gated on a MEANINGFUL walk-forward win, not any win: a 0.03-MAE
# edge is noise, and adopting it shifts every derived 1H line ~0.3-0.5 pts.
MIN_ADOPT_MARGIN = 0.05
STEP_CUT = 21.0


def _line(full_total, share):
    return np.round(np.asarray(full_total, float) * share * 2) / 2


def _predict_linear(full_total, spread, coeffs):
    share = coeffs["a"] + coeffs["b"] * np.abs(np.asarray(spread, float))
    return _line(full_total, np.clip(share, SHARE_CLAMP[0], SHARE_CLAMP[1]))


def _predict_step(full_total, spread, coeffs):
    share = np.array([fh_share(sp, coeffs=coeffs) for sp in np.asarray(spread, float)])
    return _line(full_total, share)


def _mae(pred, actual):
    return float(np.mean(np.abs(np.asarray(pred, float) - np.asarray(actual, float))))


def walk_forward(df: pd.DataFrame, min_train: int = 200) -> Dict[str, float]:
    """Walk-forward 1H-line MAE for flat 0.52, the linear fit and the step fit.
    `df` needs season, spread, full_game_total, first_half_total."""
    d = df[df["spread"].notna()]
    seasons = sorted(d["season"].unique())
    pred = {"flat": [], "linear": [], "step": []}
    actual = []
    for ts in seasons:
        train, test = d[d["season"] < ts], d[d["season"] == ts]
        if len(train) < min_train or test.empty:
            continue
        ft, sp, fh = (
            train["full_game_total"].to_numpy(),
            train["spread"].to_numpy(),
            train["first_half_total"].to_numpy(),
        )
        lin = fit_share(ft, sp, fh)
        stp = fit_share_step(ft, sp, fh, cut=STEP_CUT)
        tt, tsp = test["full_game_total"].to_numpy(), test["spread"].to_numpy()
        pred["flat"].extend(_line(tt, DEFAULT_SHARE))
        pred["linear"].extend(_predict_linear(tt, tsp, lin))
        pred["step"].extend(_predict_step(tt, tsp, stp))
        actual.extend(test["first_half_total"].to_numpy())
    if not actual:
        return {"flat": np.nan, "linear": np.nan, "step": np.nan, "n": 0}
    return {k: _mae(v, actual) for k, v in pred.items()} | {"n": len(actual)}


def choose_model(maes: Dict[str, float], margin: float = MIN_ADOPT_MARGIN) -> Optional[str]:
    """The best non-flat model, or None if it does not beat flat by `margin`."""
    best = min(("linear", "step"), key=lambda k: maes[k])
    return best if maes[best] < maes["flat"] - margin else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--no-write", action="store_true", help="report only; never persist coefficients"
    )
    ap.add_argument(
        "--all-divisions", dest="fbs_only", action="store_false", help="include non-FBS games"
    )
    args = ap.parse_args()
    init_db()

    df = load_games_frame(fbs_only=args.fbs_only)
    df = df[df["spread"].notna()].copy()
    if len(df) < 200:
        print(
            f"Only {len(df)} games carry a spread — run scripts/backfill_spread.py first. "
            "Aborting (flat 0.52 stays)."
        )
        return

    maes = walk_forward(df)
    if not maes["n"]:
        print("Not enough walk-forward history. Aborting (flat 0.52 stays).")
        return
    seasons = sorted(df["season"].unique())
    print(
        f"games with spread: {len(df)} ({seasons[0]}-{seasons[-1]}, "
        f"{'FBS-vs-FBS' if args.fbs_only else 'all divisions'}); walk-forward test n={maes['n']}"
    )
    print(
        f"walk-forward MAE (1H line vs realized): flat-0.52={maes['flat']:.3f}  "
        f"linear={maes['linear']:.3f}  step={maes['step']:.3f}"
    )

    ft, sp, fh = (
        df["full_game_total"].to_numpy(),
        df["spread"].to_numpy(),
        df["first_half_total"].to_numpy(),
    )
    lin, stp = fit_share(ft, sp, fh), fit_share_step(ft, sp, fh, cut=STEP_CUT)
    print(f"linear (all data): share = {lin['a']:.4f} + {lin['b']:.5f}*|spread|")
    print(
        f"step   (all data): share = {stp['base']:.4f} below |spread|<{STEP_CUT:g}, "
        f"{stp['blowout']:.4f} at/above"
    )

    winner = choose_model(maes)
    if winner is None or args.no_write:
        reason = (
            "(--no-write set)."
            if args.no_write
            else f"(best={min(maes['linear'], maes['step']):.3f} must beat flat by "
            f">{MIN_ADOPT_MARGIN}; margin was {maes['flat'] - min(maes['linear'], maes['step']):+.3f})."
        )
        print("NOT adopted — flat 0.52 stays " + reason)
        return

    payload = dict(lin if winner == "linear" else stp)
    payload.update(
        {
            "walk_forward_mae": maes[winner],
            "flat_mae": maes["flat"],
            "n": maes["n"],
            "fbs_only": bool(args.fbs_only),
            "seasons": f"{seasons[0]}-{seasons[-1]}",
        }
    )
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"ADOPTED {winner} — wrote {_OUT} (beats flat by {maes['flat'] - maes[winner]:.3f}).")


if __name__ == "__main__":
    main()
