"""Walk-forward evaluation + ranking of factors.

Every metric is out-of-sample: for each test season we train only on prior
seasons, exactly like backtest.engine.run_backtest (whose helpers we reuse).

Per factor (univariate):
  - a single-feature GBM is trained walk-forward and scored on each test season;
  - we report top-fraction under% + ROI (the success metric), ROC AUC, the raw
    Pearson corr(factor, under) over OOS rows, and per-season stability.
Multivariate:
  - permutation importance of every factor inside the full GBM;
  - a combination scan over the strongest univariate factors (2- and 3-way).

Ranking is by out-of-sample top-fraction ROI (ties broken by under% then AUC) —
this matches the project goal of "positive ROI at any volume". Stability and
sample size travel alongside as diagnostics, never as filters.
"""

from __future__ import annotations

from itertools import combinations
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

from ..backtest.engine import WIN_PROFIT, _new_model, _roi
from .registry import Factor

_MIN_OOS = 300  # need this many OOS rows to trust a factor's metrics


def _screen_model() -> HistGradientBoostingClassifier:
    """Lighter GBM for the many screening fits (univariate + combo scan).

    The production engine uses _new_model (300 iters); screening fits thousands
    of small models, so we trade a little fidelity for ~3x speed — fine for
    *ranking* factors relative to each other."""
    return HistGradientBoostingClassifier(
        learning_rate=0.1,
        max_depth=3,
        max_iter=100,
        l2_regularization=1.0,
        min_samples_leaf=40,
        random_state=7,
    )


def _walk_forward(
    df: pd.DataFrame,
    cols: List[str],
    first_test_season: int = 2018,
    min_train: int = 500,
    dropna: bool = False,
) -> Optional[pd.DataFrame]:
    """OOS predictions from a GBM over `cols`, one model per test season.

    Returns a frame with season/under/prob (+ the single factor value when
    len(cols)==1, for correlation). None if nothing could be scored.
    HistGradientBoosting handles NaN natively, so multi-factor scans keep all
    rows; single-factor scans drop NaN to get a clean coverage/correlation read.
    """
    sub = df.dropna(subset=cols) if dropna else df
    sub = sub[sub["under"].notna()]  # played games only (the frame carries the unplayed slate)
    seasons = sorted(sub["season"].unique())
    preds = []
    for ts in [s for s in seasons if s >= first_test_season]:
        train = sub[sub["season"] < ts]
        test = sub[sub["season"] == ts]
        if len(train) < min_train or test.empty or train["under"].nunique() < 2:
            continue
        model = _screen_model()
        model.fit(train[cols], train["under"])
        p = model.predict_proba(test[cols])[:, 1]
        chunk = test[["season", "under"]].copy()
        chunk["prob"] = p
        if "first_half_total" in test.columns:
            chunk["fh_total"] = test["first_half_total"].to_numpy()
        if len(cols) == 1:
            chunk["val"] = test[cols[0]].to_numpy()
        preds.append(chunk)
    if not preds:
        return None
    return pd.concat(preds, ignore_index=True)


def _selection_metrics(pg: pd.DataFrame, top_frac: float) -> Dict:
    """Top-fraction under%/ROI (pooled) + per-season under% for stability."""
    per_season = []
    tops = []
    for _, g in pg.groupby("season"):
        g = g.sort_values("prob", ascending=False)
        k = max(1, int(len(g) * top_frac))
        top = g.head(k)
        tops.append(top)
        per_season.append(100 * top["under"].mean())
    pooled = pd.concat(tops, ignore_index=True)
    return {
        "top_n": int(len(pooled)),
        "top_under_pct": round(100 * pooled["under"].mean(), 2),
        "top_roi": round(_roi(int(pooled["under"].sum()), len(pooled)), 4),
        "per_season_under_pct": [round(x, 1) for x in per_season],
        "stability_std": round(float(np.std(per_season)), 2),
    }


def evaluate_factor(
    df: pd.DataFrame, factor: Factor, top_frac: float = 0.20, first_test_season: int = 2018
) -> Optional[Dict]:
    """Full univariate diagnostic payload for one factor, or None if too sparse."""
    pg = _walk_forward(df, [factor.name], first_test_season, dropna=True)
    if pg is None or len(pg) < _MIN_OOS:
        return None
    auc = (
        round(float(roc_auc_score(pg["under"], pg["prob"])), 4)
        if pg["under"].nunique() > 1
        else None
    )
    corr = pg["val"].astype(float).corr(pg["under"].astype(float))
    # corr to ACTUAL 1H total — the genuine 1H-scoring signal, immune to the
    # proxy artifact that inflates proxy-under ROI. Negative = factor up ->
    # fewer real 1H points (a true under driver).
    corr_1h = (
        pg["val"].astype(float).corr(pg["fh_total"].astype(float))
        if "fh_total" in pg.columns
        else None
    )
    out = {
        "factor": factor.name,
        "family": factor.family,
        "description": factor.description,
        "leak_free": factor.leak_free,
        "market": factor.market,
        "forward_only": factor.forward_only,
        "n": int(len(pg)),
        "auc": auc,
        "corr": round(float(corr), 4) if pd.notna(corr) else None,
        "corr_1h": round(float(corr_1h), 4) if corr_1h is not None and pd.notna(corr_1h) else None,
    }
    out.update(_selection_metrics(pg, top_frac))
    return out


def permutation_importances(
    df: pd.DataFrame, cols: List[str], n_repeats: int = 5, random_state: int = 7
) -> Dict[str, float]:
    """Permutation importance (mean AUC drop) of each col in the full GBM,
    measured on the most recent season held out from training."""
    df = df[df["under"].notna()]  # played games only
    seasons = sorted(df["season"].unique())
    if len(seasons) < 2:
        return {}
    ts = seasons[-1]
    train = df[df["season"] < ts]
    test = df[df["season"] == ts]
    if test.empty or test["under"].nunique() < 2:
        return {}
    model = _new_model()
    model.fit(train[cols], train["under"])
    r = permutation_importance(
        model,
        test[cols],
        test["under"],
        n_repeats=n_repeats,
        random_state=random_state,
        scoring="roc_auc",
    )
    return {c: round(float(v), 5) for c, v in zip(cols, r.importances_mean)}


def evaluate_combos(
    df: pd.DataFrame,
    factor_names: List[str],
    sizes=(2, 3),
    top_k: int = 10,
    top_frac: float = 0.20,
    first_test_season: int = 2018,
) -> List[Dict]:
    """Scan 2- and 3-way combinations of the strongest univariate factors.

    `factor_names` must already be ranked best-first; we take the top_k and try
    every size-`s` combination, reporting the same selection metrics.
    """
    cols = factor_names[:top_k]
    out = []
    for size in sizes:
        for combo in combinations(cols, size):
            pg = _walk_forward(df, list(combo), first_test_season, dropna=False)
            if pg is None or len(pg) < _MIN_OOS:
                continue
            auc = (
                round(float(roc_auc_score(pg["under"], pg["prob"])), 4)
                if pg["under"].nunique() > 1
                else None
            )
            row = {
                "factor": " + ".join(combo),
                "members": list(combo),
                "n": int(len(pg)),
                "auc": auc,
            }
            row.update(_selection_metrics(pg, top_frac))
            out.append(row)
    out.sort(key=lambda r: (r["top_roi"], r["top_under_pct"]), reverse=True)
    return out


def rank_factors(
    df: pd.DataFrame,
    factors: List[Factor],
    top_frac: float = 0.20,
    first_test_season: int = 2018,
    combo_top_k: int = 10,
) -> Dict:
    """Evaluate every factor univariately, attach permutation importance, rank
    by OOS top-fraction ROI, then scan combinations of the strongest. Returns
    {"univariate": [...ranked...], "combos": [...], "baseline": {...}}.
    """
    df = df[df["under"].notna()]  # played games only (baseline n / under% must not see NaN)
    rows = [
        r for f in factors if (r := evaluate_factor(df, f, top_frac, first_test_season)) is not None
    ]

    # Permutation importance over the non-forward-only present columns.
    present = [f.name for f in factors if f.name in df.columns]
    perm = permutation_importances(df, present)
    for r in rows:
        r["perm_importance"] = perm.get(r["factor"])

    rows.sort(key=lambda r: (r["top_roi"], r["top_under_pct"], r["auc"] or 0), reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    ranked_names = [r["factor"] for r in rows if not r["market"]]
    combos = evaluate_combos(
        df, ranked_names, top_k=combo_top_k, top_frac=top_frac, first_test_season=first_test_season
    )
    for i, c in enumerate(combos, 1):
        c["rank"] = i

    baseline = {
        "n": int(len(df)),
        "under_pct": round(100 * df["under"].mean(), 2),
        "breakeven_roi_under_pct": 52.4,
        "win_profit": round(WIN_PROFIT, 4),
        "top_frac": top_frac,
        "first_test_season": first_test_season,
    }
    return {"univariate": rows, "combos": combos, "baseline": baseline}
