"""A market-blind full-game MARGIN regressor for the CFBD Model Pick'em
(H-MARGIN, docs/HYPOTHESES.md; Tate's calls 2026-10-07; docs/MARGIN.md).

Exploratory measurement: it licenses nothing. Same 58 market-blind inputs as
the champion (`BV_FEATURE_COLS`: no spread, no market column), same HGB, same
walk-forward global intercept (`bv_line.bv_line_for_slate`); only the target
changes to home points minus away points. Stored, when scored live, as
`predictions.model_version = MARGIN_MODEL_VERSION`, which no champion read
admits (`score.CHAMPION_READ_VERSIONS`).

The benchmark is the Vegas closing spread. `games.spread` is CFBD's
home-relative line (negative = home favored, `sources/cfbd_lines.py`) and for a
PLAYED game it is effectively the close (`beat-vegas-as-of-reads`): never an
input here, only the number the Pick'em scores against, so the implied home
margin is `-spread`.
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

from .bv_line import bv_line_for_slate

MARGIN_ACTUAL_COL = "margin_actual"
MARGIN_MODEL_VERSION = "bv_margin_v1"


def with_margin(df: pd.DataFrame) -> pd.DataFrame:
    """The frame with `margin_actual` = home_points - away_points (NaN when either
    is missing, so unplayed rows never reach a fit)."""
    out = df.copy()
    hp = pd.to_numeric(out.get("home_points"), errors="coerce")
    ap = pd.to_numeric(out.get("away_points"), errors="coerce")
    out[MARGIN_ACTUAL_COL] = (hp - ap).astype(float)
    return out


def played_margin(df: pd.DataFrame) -> pd.DataFrame:
    """Rows with both final scores: everything a margin fit may use (unlike the
    champion's `training_frame`, no first-half result is required)."""
    m = with_margin(df)
    return m[m[MARGIN_ACTUAL_COL].notna()]


def bv_margin_for_slate(
    train_df: pd.DataFrame, target_df: pd.DataFrame, drop_all_nan: bool = False
) -> np.ndarray:
    """Fit on `train_df` (played rows), predict `target_df`, return home-relative
    projected margins (positive = home wins by that many)."""
    return bv_line_for_slate(
        played_margin(train_df),
        with_margin(target_df),
        target=MARGIN_ACTUAL_COL,
        drop_all_nan=drop_all_nan,
    )


def vegas_margin(spread: pd.Series) -> pd.Series:
    """Home-relative implied margin from CFBD's spread (negative = home favored)."""
    return -pd.to_numeric(spread, errors="coerce")


def _wilson(k: int, n: int, z: float = 1.959964) -> Optional[Dict[str, float]]:
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"pct": p, "lo": c - h, "hi": c + h}


def margin_metrics(
    pred: Sequence[float],
    actual: Sequence[float],
    vegas: Sequence[float],
    *,
    n_boot: int = 2000,
    seed: int = 7,
) -> Dict:
    """The Pick'em's four measures for the model and for Vegas on the same games:
    MAE, MSE, straight-up pct (winner called; a predicted or actual tie is not
    counted) and, for the model only, ATS pct (side of the closing spread the
    model's margin implies; pushes and zero disagreements are not counted).
    Plus the paired MAE difference (model minus Vegas) with a bootstrap 95%
    interval. Rows missing any of the three are dropped and n says so."""
    p = np.asarray(pred, float)
    a = np.asarray(actual, float)
    v = np.asarray(vegas, float)
    ok = ~(np.isnan(p) | np.isnan(a) | np.isnan(v))
    p, a, v = p[ok], a[ok], v[ok]
    n = int(len(p))
    if n == 0:
        return {"n": 0}

    def su(x):
        m = (x != 0) & (a != 0)
        k = int((np.sign(x[m]) == np.sign(a[m])).sum())
        return _wilson(k, int(m.sum()))

    # ATS: the model takes home when it projects home to beat the spread's margin.
    side = np.sign(p - v)
    cover = np.sign(a - v)
    m = (side != 0) & (cover != 0)
    ats = _wilson(int((side[m] == cover[m]).sum()), int(m.sum()))

    err_model = np.abs(p - a)
    err_vegas = np.abs(v - a)
    diff = err_model - err_vegas
    rng = np.random.default_rng(seed)
    boots = [float(diff[rng.integers(0, n, n)].mean()) for _ in range(n_boot)]
    return {
        "n": n,
        "model": {
            "mae": float(err_model.mean()),
            "mse": float(((p - a) ** 2).mean()),
            "su": su(p),
            "ats": ats,
        },
        "vegas": {
            "mae": float(err_vegas.mean()),
            "mse": float(((v - a) ** 2).mean()),
            "su": su(v),
        },
        "mae_diff": {
            "mean": float(diff.mean()),
            "lo": float(np.percentile(boots, 2.5)),
            "hi": float(np.percentile(boots, 97.5)),
        },
    }
