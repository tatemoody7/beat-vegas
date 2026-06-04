"""Walk-forward backtest of the predict-the-1H-total ENGINE (the pivot's core).

Unlike backtest.engine (a classifier on P(under vs proxy)), this fits the
market-blind BV regressor, predicts the actual 1H total, and ranks the board by
the gap between the line and our number:

    gap = line - bv_line          (+gap = line ABOVE our number = under lean)

Two questions it answers:
  1. Does ranking by this gap select 1H unders at least as well as the classifier
     (graded vs the 0.52x proxy, since real historical 1H lines don't exist)?
  2. MAE of the BV line vs the actual 1H total — and does adding a column family
     (e.g. the PBP factors) improve that accuracy? (the genuine, proxy-immune win)

The proxy grade is still directional; the real test is forward CLV vs DK lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from ..model.bv_line import (
    TARGET,
    _assert_market_blind,
    bv_line_for_slate,
)
from .engine import _roi


@dataclass
class BvBacktestResult:
    per_game: pd.DataFrame
    by_season: pd.DataFrame
    summary: Dict


def run_bv_backtest(
    df: pd.DataFrame, first_test_season: int = 2018, top_frac: float = 0.20, min_train: int = 500
) -> BvBacktestResult:
    """Walk-forward gap ranking + MAE for the BV regressor engine."""
    seasons = sorted(df["season"].unique())
    preds = []
    for ts in [s for s in seasons if s >= first_test_season]:
        train = df[df["season"] < ts]
        target = df[df["season"] == ts]
        if len(train) < min_train or target.empty:
            continue
        bv = bv_line_for_slate(train, target)
        t = target[
            ["id", "season", "week", "proxy_line", "first_half_total", "under", "full_game_total"]
        ].copy()
        t["bv_line"] = bv
        t["gap"] = t["proxy_line"] - t["bv_line"]  # +gap -> under lean
        t["abs_err"] = (t[TARGET].astype(float) - t["bv_line"]).abs()
        preds.append(t)
    per_game = pd.concat(preds, ignore_index=True)

    rows, tops = [], []
    for ts, g in per_game.groupby("season"):
        g = g.sort_values("gap", ascending=False)
        k = max(1, int(len(g) * top_frac))
        top = g.head(k)
        tops.append(top)
        rows.append(
            {
                "season": int(ts),
                "games": len(g),
                "top_under_pct": round(100 * top["under"].mean(), 2),
                "top_roi": round(_roi(int(top["under"].sum()), len(top)), 4),
                "mae": round(float(g["abs_err"].mean()), 3),
            }
        )
    pooled = pd.concat(tops, ignore_index=True)
    summary = {
        "test_seasons": f"{rows[0]['season']}-{rows[-1]['season']}" if rows else "n/a",
        "n_games": int(len(per_game)),
        "baseline_under_pct": round(100 * per_game["under"].mean(), 2),
        "top_under_pct": round(100 * pooled["under"].mean(), 2),
        "top_roi": round(_roi(int(pooled["under"].sum()), len(pooled)), 4),
        "mae": round(float(per_game["abs_err"].mean()), 3),
        "breakeven_pct": 52.4,
    }
    return BvBacktestResult(per_game=per_game, by_season=pd.DataFrame(rows), summary=summary)


def _reg() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_depth=3,
        max_iter=300,
        l2_regularization=1.0,
        min_samples_leaf=40,
        random_state=7,
    )


def mae_ablation(
    df: pd.DataFrame, cols: List[str], first_test_season: int = 2018, min_train: int = 500
) -> float:
    """Walk-forward MAE of a regressor predicting the 1H total on `cols` only.

    Used to ask: does a column family improve 1H-total accuracy? Compare the MAE
    on the full BV feature set vs the set minus that family. Market-blind."""
    _assert_market_blind(cols)
    seasons = sorted(df["season"].unique())
    errs = []
    for ts in [s for s in seasons if s >= first_test_season]:
        train = df[df["season"] < ts]
        target = df[df["season"] == ts]
        if len(train) < min_train or target.empty:
            continue
        m = _reg()
        m.fit(train[cols], train[TARGET])
        pred = m.predict(target[cols])
        errs.append(np.abs(target[TARGET].to_numpy() - pred))
    return float(np.mean(np.concatenate(errs))) if errs else float("nan")
