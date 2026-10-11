"""The calibrated, independent "BV line" — our own projected 1H total.

A gradient-boosted *regressor* over the full feature set predicts realized
first-half points directly (vs the classifier in score.py, which only predicts
P(under) against a proxy line). We then compare the BV line to the real Vegas 1H
line and rank by the gap.

Calibration for a regression line means UNBIASEDNESS: E[actual - pred] ~= 0
overall AND within segments (era pre/post-2023 especially). A persistent low
bias would make every game falsely scream "under". We learn a global intercept
from out-of-fold residuals on the training slice only (leak-free) and shift
predictions by it. This is the regression analogue of probability calibration —
calibration_curve / CalibratedClassifierCV apply to probabilities, not to a line.

Era is handled by the `era_post2023` FEATURE (the tree learns era-conditional
scoring once post-2023 seasons are in the training slice), NOT by a per-era
intercept: an additive per-era correction on top of an era-aware model double-
counts, because pooled OOF residuals mix early folds that had no post-2023
training data with the final model that does. We instead REPORT per-era residuals
(see residual_report) so any remaining segment bias is auditable by a human — the
honest limit being that the very first post-2023 season can't be de-biased from
data that doesn't yet exist.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from ..etl.features import (
    BANNED_LINE_COLS,
    FEATURE_COLS,
    LEAKY_WEATHER_COLS,
    MARKET_COLS,
    SERVE_UNAVAILABLE_COLS,
)

TARGET = "first_half_total"
ERA_COL = "era_post2023"
_MIN_SEGMENT = 200  # min rows to report a segment residual

# The BV line is MARKET-BLIND: it sees none of the Vegas-derived inputs. This is
# the whole point — an independent number to compare against Vegas, so the gap
# isn't circular. (The classifier in score.py keeps FEATURE_COLS by design.)
# ...and it never sees the first-half PBP season-to-date columns: they are NaN
# on every row the live model scores and present on every row it trains on
# (features.SERVE_UNAVAILABLE_COLS, B-SERVE 2026-09-22).
# ...nor the legacy weather values, kickoff observations that live serving never
# has (features.LEAKY_WEATHER_COLS, strategic review 2026-10-09).
_EXCLUDED = set(SERVE_UNAVAILABLE_COLS) | set(LEAKY_WEATHER_COLS)
BV_FEATURE_COLS = [c for c in FEATURE_COLS if c not in MARKET_COLS and c not in _EXCLUDED]


# Early stopping, stated rather than left to sklearn's default (2026-10-10).
# 'auto' turns it on above 10,000 training rows, holding out a random 10%
# (random_state=7, so a refit repeats): the 2003+ champion (about 16,700 rows)
# stops early, every smaller fit grows all 300 trees. H-MODEL-FIX tested False
# together with three other changes and the bundle was less accurate
# (docs/MODEL_FIX.md), so 'auto' stays; each refit records the trees it grew.
EARLY_STOPPING: Union[str, bool] = "auto"


def _new_regressor() -> HistGradientBoostingRegressor:
    # The hyperparameters the retired offline backtest engine used (2026-10-11).
    return HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_depth=3,
        max_iter=300,
        l2_regularization=1.0,
        min_samples_leaf=40,
        random_state=7,
        early_stopping=EARLY_STOPPING,
    )


def _assert_market_blind(cols) -> None:
    """Defense in depth: the BV regressor must never train on a Vegas number."""
    leaked = (set(cols) & MARKET_COLS) | (set(cols) & BANNED_LINE_COLS)
    if leaked:
        raise AssertionError(f"BV line must be market-blind; leaked columns: {leaked}")


def _played(df: pd.DataFrame, target: str = TARGET) -> pd.DataFrame:
    """Rows with a realized total for `target` — the frame also carries the
    unplayed upcoming slate (NaN target), which must never reach a fit or a
    residual. `target` defaults to the champion's 1H total; the research-only
    full-game fit passes `markets.FG_ACTUAL_COL` (2026-10-06)."""
    return df[pd.to_numeric(df[target], errors="coerce").notna()]


def fit_bv_regressor(
    train_df: pd.DataFrame,
    target: str = TARGET,
    feature_cols: Optional[Sequence[str]] = None,
    drop_all_nan: bool = False,
) -> HistGradientBoostingRegressor:
    """`feature_cols` (default BV_FEATURE_COLS, the champion's inputs): a study
    arm may add inputs (H-ELO-F); the market-blind assert covers whatever is
    passed.

    `drop_all_nan` (default False, the champion's path): fit only on columns
    with at least one value in THIS training slice. sklearn's HGB refuses to
    bin an all-NaN column (`window shape cannot be larger than input array
    shape`), and an all-NaN column carries no split the model could use, so
    dropping it is the same model. The H-HIST arms need it: a fold trained on
    2003 alone has no talent / returning-production inputs at all. The fitted
    model records the columns it used in `bv_cols_`; every predict reads them."""
    cols = list(BV_FEATURE_COLS if feature_cols is None else feature_cols)
    _assert_market_blind(cols)
    train_df = _played(train_df, target)
    if drop_all_nan:
        cols = [c for c in cols if train_df[c].notna().any()]
    model = _new_regressor()
    model.fit(train_df[cols], train_df[target].astype(float))
    model.bv_cols_ = cols
    return model


def oof_residuals(
    df: pd.DataFrame,
    min_train: int = 500,
    target: str = TARGET,
    feature_cols: Optional[Sequence[str]] = None,
    drop_all_nan: bool = False,
) -> pd.DataFrame:
    """Walk-forward out-of-fold residuals (actual - pred) across seasons.

    For each season, train on all prior seasons and predict it — so no game is
    ever predicted by a model that trained on it. Returns the input rows with a
    `bv_raw` prediction and `residual` column for the seasons that could be
    scored (early seasons with too little prior data are dropped).
    """
    df = _played(df, target)
    seasons = sorted(df["season"].unique())
    out = []
    for ts in seasons:
        train = df[df["season"] < ts]
        test = df[df["season"] == ts]
        if len(train) < min_train or test.empty:
            continue
        model = fit_bv_regressor(train, target, feature_cols, drop_all_nan)
        pred = model.predict(test[model.bv_cols_])
        chunk = test.copy()
        chunk["bv_raw"] = pred
        chunk["residual"] = chunk[target].astype(float) - pred
        out.append(chunk)
    if not out:
        return df.iloc[0:0].assign(bv_raw=[], residual=[])
    return pd.concat(out, ignore_index=True)


def bias_corrections(
    train_df: pd.DataFrame,
    target: str = TARGET,
    feature_cols: Optional[Sequence[str]] = None,
    drop_all_nan: bool = False,
) -> Dict:
    """Global intercept correction learned from OOF residuals on TRAIN only.

    Returns {"global": float}. We deliberately do NOT apply a per-era intercept
    (the era feature handles era; per-era would double-count) — per-era residuals
    are surfaced for auditing via residual_report instead.
    """
    res = oof_residuals(
        train_df, target=target, feature_cols=feature_cols, drop_all_nan=drop_all_nan
    )
    if res.empty:
        return {"global": 0.0}
    return {"global": float(res["residual"].mean())}


def apply_bias(raw_pred: np.ndarray, frame: pd.DataFrame, corrections: Dict) -> np.ndarray:
    """Shift raw predictions by the global intercept correction."""
    global_bias = corrections.get("global", 0.0)
    return np.asarray(raw_pred, dtype=float) + global_bias


def bv_line_for_slate(
    train_df: pd.DataFrame,
    target_df: pd.DataFrame,
    target: str = TARGET,
    feature_cols: Optional[Sequence[str]] = None,
    drop_all_nan: bool = False,
) -> np.ndarray:
    """Fit on train, predict the target slate, return calibrated BV lines.

    Empty train/target yields an empty array. Bias corrections are derived from
    the train slice only (leak-free w.r.t. the target season). `target` is the
    column fitted (default the champion's 1H total; the live path never passes
    anything else -- `model.fg_line` is the full-game caller: research, and the
    H-FG-P shadow `bv_fg_v1`, which no champion read can see).
    """
    if train_df.empty or target_df.empty:
        return np.array([], dtype=float)
    cols = list(BV_FEATURE_COLS if feature_cols is None else feature_cols)
    model = fit_bv_regressor(train_df, target, cols, drop_all_nan)
    # What the slate's fit actually did, for the weekly run record
    # (scripts/weekly_update.py; H-MODEL-FIX: early stopping once hid here).
    LAST_FIT.clear()
    LAST_FIT.update(
        n_iter=int(model.n_iter_),
        early_stopping=str(model.early_stopping),
        train_rows=int(len(_played(train_df, target))),
    )
    raw = model.predict(target_df[model.bv_cols_])
    corrections = bias_corrections(train_df, target, cols, drop_all_nan)
    return apply_bias(raw, target_df, corrections)


# The last bv_line_for_slate fit: trees grown, the early-stopping setting, rows.
LAST_FIT: Dict[str, object] = {}


def residual_band(
    train_df: pd.DataFrame, lo: float = 0.1, hi: float = 0.9, drop_all_nan: bool = False
) -> Dict:
    """Empirical (conformal) prediction band for the BV line.

    Reuses the walk-forward OOF residuals — no extra models. Returns
    {"lo_off", "hi_off", "sigma"}: offsets to add to the calibrated BV line for
    an [lo, hi] interval (default 80%), and the residual std. A raw gap is
    meaningless without this — a 2pt gap is noise if sigma is 7pt.
    """
    res = oof_residuals(train_df, drop_all_nan=drop_all_nan)
    if res.empty or len(res) < _MIN_SEGMENT:
        return {"lo_off": None, "hi_off": None, "sigma": None}
    r = res["residual"]
    # Bias correction already centers residuals near 0; the band is around the
    # calibrated line, so center the quantiles on the mean (the applied shift).
    mean = float(r.mean())
    return {
        "lo_off": round(float(r.quantile(lo)) - mean, 2),
        "hi_off": round(float(r.quantile(hi)) - mean, 2),
        "sigma": round(float(r.std()), 2),
    }


def residual_report(df: pd.DataFrame) -> Dict:
    """Auditable calibration summary for model_runs: mean OOF residual overall
    and per segment (era / tempo tercile / dome). Mean near 0 == well calibrated.
    """
    res = oof_residuals(df)
    if res.empty:
        return {"n": 0}
    report: Dict = {
        "n": int(len(res)),
        "overall_mean_residual": round(float(res["residual"].mean()), 3),
    }

    by_era = {}
    for era_val, grp in res.groupby(ERA_COL):
        label = "post2023" if float(era_val) >= 1.0 else "pre2023"
        by_era[label] = {
            "n": int(len(grp)),
            "mean_residual": round(float(grp["residual"].mean()), 3),
        }
    report["by_era"] = by_era

    if res["combined_sec_play"].notna().sum() >= 3 * _MIN_SEGMENT:
        try:
            res = res.copy()
            res["_tempo_bucket"] = pd.qcut(
                res["combined_sec_play"], 3, labels=["fast", "mid", "slow"]
            )
            report["by_tempo"] = {
                str(b): {"n": int(len(g)), "mean_residual": round(float(g["residual"].mean()), 3)}
                for b, g in res.groupby("_tempo_bucket", observed=True)
            }
        except ValueError:
            pass

    dome = res[res["wx_dome"] == 1]
    outdoor = res[res["wx_dome"] != 1]
    report["by_dome"] = {
        "dome": {
            "n": int(len(dome)),
            "mean_residual": round(float(dome["residual"].mean()), 3) if len(dome) else None,
        },
        "outdoor": {
            "n": int(len(outdoor)),
            "mean_residual": round(float(outdoor["residual"].mean()), 3) if len(outdoor) else None,
        },
    }
    return report
