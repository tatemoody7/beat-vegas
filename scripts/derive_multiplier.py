#!/usr/bin/env python
"""Fit the spread-adjusted 1H multiplier and adopt it ONLY if it beats flat 0.52.

The research says the 1H share of the full-game total rises with spread magnitude
(favorites score relatively more early). We fit share = a + b*|spread| on realized
1H points, validate walk-forward (each season scored by a model fit on PRIOR
seasons only), and compare the predicted-1H-line MAE to the flat-0.52 baseline.

If — and only if — the fitted curve wins, we write data/multiplier.json, which
proxy_line.fh_share() then loads. No improvement => no file => flat 0.52 stays
(zero behavior change). Requires Game.spread (run scripts/backfill.py first).

    python scripts/derive_multiplier.py
    python scripts/derive_multiplier.py --write   # persist if it wins (default on)
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from beatvegas.config import REPO_ROOT
from beatvegas.db.store import init_db
from beatvegas.etl.proxy_line import (
    DEFAULT_SHARE, SHARE_CLAMP, fit_share, load_games_frame,
)

_OUT = REPO_ROOT / "data" / "multiplier.json"


def _predict_line(full_total, spread, coeffs):
    share = coeffs["a"] + coeffs["b"] * np.abs(spread)
    share = np.clip(share, SHARE_CLAMP[0], SHARE_CLAMP[1])
    return np.round(full_total * share * 2) / 2


def _mae(pred, actual):
    return float(np.mean(np.abs(np.asarray(pred, float) - np.asarray(actual, float))))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true",
                    help="report only; never persist coefficients")
    args = ap.parse_args()
    init_db()

    df = load_games_frame()
    df = df[df["spread"].notna()].copy()
    if len(df) < 200:
        print(f"Only {len(df)} games carry a spread — run scripts/backfill.py to "
              "populate Game.spread before fitting. Aborting (flat 0.52 stays).")
        return

    seasons = sorted(df["season"].unique())
    fit_pred, flat_pred, actuals = [], [], []
    for ts in seasons:
        train = df[df["season"] < ts]
        test = df[df["season"] == ts]
        if len(train) < 200 or test.empty:
            continue
        coeffs = fit_share(train["full_game_total"].to_numpy(),
                           train["spread"].to_numpy(),
                           train["first_half_total"].to_numpy())
        fit_pred.extend(_predict_line(test["full_game_total"].to_numpy(),
                                      test["spread"].to_numpy(), coeffs))
        flat_pred.extend(np.round(test["full_game_total"].to_numpy()
                                  * DEFAULT_SHARE * 2) / 2)
        actuals.extend(test["first_half_total"].to_numpy())

    if not actuals:
        print("Not enough walk-forward history. Aborting.")
        return

    fit_mae, flat_mae = _mae(fit_pred, actuals), _mae(flat_pred, actuals)
    final = fit_share(df["full_game_total"].to_numpy(), df["spread"].to_numpy(),
                      df["first_half_total"].to_numpy())
    print(f"walk-forward MAE (1H line vs realized): "
          f"spread-adjusted={fit_mae:.3f}  flat-0.52={flat_mae:.3f}  "
          f"n={len(actuals)}")
    print(f"fitted share = {final['a']:.4f} + {final['b']:.5f}*|spread|  "
          f"(clamped to {SHARE_CLAMP})")
    for sp in (0, 7, 14, 21):
        share = min(max(final["a"] + final["b"] * sp, SHARE_CLAMP[0]), SHARE_CLAMP[1])
        print(f"  |spread|={sp:>2}  share={share:.3f}")

    if fit_mae < flat_mae and not args.no_write:
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(
            {"a": final["a"], "b": final["b"],
             "walk_forward_mae": fit_mae, "flat_mae": flat_mae,
             "n": len(actuals)}, indent=2))
        print(f"ADOPTED — wrote {_OUT} (beats flat by {flat_mae - fit_mae:.3f}).")
    else:
        print("NOT adopted — flat 0.52 stays "
              + ("(--no-write set)." if args.no_write else "(no MAE improvement)."))


if __name__ == "__main__":
    main()
