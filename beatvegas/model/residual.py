"""The market-residual 1H engine (inactive by default: config `model.engine`).

The incumbent BV line (bv_line.py) is MARKET-BLIND: it predicts the 1H total
from scratch and compares it to Vegas. This engine takes the opposite stance:
the pre-kick 1H line is the best single predictor of the 1H total, so we
CONDITION on it and predict only the part it gets wrong — the residual
`actual − line`. The board's `bv_line` then becomes `line + r̂` and the gap is
`−r̂`. A residual model can only learn from games with a REAL pre-kick close
(no proxy: a 0.52×full-game number would teach it the proxy's error, not the
market's), so its training frame is the subset of history with a captured 1H
close within lines.REAL_1H_CLOSE_WINDOW_H of kickoff.

Leak-freedom: every season-to-date column is already shifted (features.py);
`resid_line` / `implied_1h_share` are functions of the pre-kick close and the
pre-kick full-game total only; the target is never a feature; the caller
trains on `season < target_season` only. `assert_residual_features` guards the
feature list, and pins the INCUMBENT: none of this engine's line-derived
columns may ever leak into bv_line.BV_FEATURE_COLS.
"""

from __future__ import annotations

import hashlib
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold, cross_val_predict

from ..etl.features import FH_FACTOR_COLS
from ..grading import trusted_first_half_total
from .bv_line import BV_FEATURE_COLS

LINE_COL = "resid_line"  # the pre-kick 1H line the model conditions on
TARGET = "resid_target"  # trusted 1H actual − resid_line
MODEL_VERSION_TAG = "resid_v1"
# Below this many training games with a real close, score_slate falls back to
# the incumbent (and says so in attrs["engine_fallback"]).
RESIDUAL_MIN_TRAIN = 300
# The regressor's leaf size, kept as a name because the fit floor is derived
# from it (see RESIDUAL_MIN_FIT_ROWS).
MIN_SAMPLES_LEAF = 30
# The fewest rows fit_residual will accept. A HistGradientBoostingRegressor
# with min_samples_leaf=30 cannot make even ONE split below 2*30 rows: both
# children of the root would have to hold 30 rows. Under the floor the "model"
# is the training mean wearing a regressor's clothes — and newer
# numpy/scikit-learn report that with an opaque binning error rather than
# saying so. RESIDUAL_MIN_TRAIN (300) is the production gate; this is the
# floor for any caller of the public entry point.
RESIDUAL_MIN_FIT_ROWS = 2 * MIN_SAMPLES_LEAF
# A 1H close outside this range is a data error (wrong market / bad parse),
# not a football game.
CLOSE_MIN, CLOSE_MAX = 10.0, 60.0
_BAND_LO, _BAND_HI = 0.1, 0.9  # 80% empirical band, mirrors bv_line.residual_band

# Columns the residual model may see. All pre-kickoff; none derived from the
# OUTCOME. FH_FACTOR_COLS are the 52 season-to-date 1H PBP factors.
RESIDUAL_FEATURE_COLS: List[str] = [
    LINE_COL,
    "implied_1h_share",
    "full_game_total",
    "spread",
    "combined_sec_play",
    "combined_plays",
    "wx_temp",
    "wx_precip",
    "wx_wind_band",
    "wx_dome",
    *FH_FACTOR_COLS,
    "era_post2023",
    "home_rest_days",
    "away_rest_days",
    "home_short_week",
    "away_short_week",
    "home_off_bye",
    "away_off_bye",
    "away_travel_dist",
    "neutral_site",
]

# Names that would make the residual circular or leak the outcome. The second
# block is every OUTCOME column build_feature_frame carries alongside the
# features (final score, the 1H truth and its provenance, and the per-team 1H
# points `home_fh`/`away_fh` those are summed from) — none may ever be a feature.
_FORBIDDEN = {
    "bv_line",
    "bv_gap",
    "line_used",
    "closing_line",
    "proxy_line",
    "under",
    TARGET,
    "home_points",
    "away_points",
    "first_half_total",
    "first_half_source",
    "home_fh",
    "away_fh",
}
# This engine's line-derived columns: the incumbent must never see them.
_LINE_DERIVED = {LINE_COL, "implied_1h_share", "wx_wind_band"}

# The features the residual genuinely needs: the line it conditions on and the
# two market numbers that shape 1H share. The long tail (weather, PBP factors,
# rest) may legitimately be absent on an old frame and is NaN-filled silently;
# these three are not — a residual has little signal to spare, so their absence
# is a loud warning plus fingerprint["missing_features"], not a quiet NaN column.
REQUIRED_FEATURES: Tuple[str, ...] = (LINE_COL, "full_game_total", "spread")


class ResidualFitError(ValueError):
    """The residual model cannot be fitted on what it was handed.

    Raised (never swallowed) so a caller sees a typed, self-describing failure
    instead of an opaque error from deep inside the estimator. score_slate
    catches it and demotes the board to the incumbent with the reason attached
    to attrs["engine_fallback"].
    """


def assert_residual_features(cols) -> None:
    """Guard both engines: the residual list must carry the line and nothing
    outcome/line-derived beyond it; the incumbent must stay market-blind."""
    cols = list(cols)
    if LINE_COL not in cols:
        raise AssertionError(f"residual engine must condition on {LINE_COL!r}")
    leaked = set(cols) & _FORBIDDEN
    if leaked:
        raise AssertionError(f"residual features leak the outcome/line: {sorted(leaked)}")
    cross = set(BV_FEATURE_COLS) & _LINE_DERIVED
    if cross:
        raise AssertionError(f"incumbent bv_line is no longer market-blind: {sorted(cross)}")


def attach_line_features(df: pd.DataFrame, line: pd.Series) -> pd.DataFrame:
    """Copy of `df` with `resid_line` (float) and `implied_1h_share` =
    line / full_game_total (NaN when the total is missing or <= 0)."""
    out = df.copy()
    out[LINE_COL] = pd.to_numeric(pd.Series(line, index=out.index), errors="coerce").astype(float)
    total = pd.to_numeric(out.get("full_game_total"), errors="coerce").astype(float)
    total = total.where(total > 0)
    out["implied_1h_share"] = out[LINE_COL] / total
    return out


def _ensure_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Clean float model columns (NaN, never None/pd.NA/bool); a feature the
    frame does not carry yet becomes a NaN column, as features.py does."""
    for c in RESIDUAL_FEATURE_COLS:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df


def missing_required(df: pd.DataFrame) -> List[str]:
    """REQUIRED_FEATURES that `df` cannot supply — absent, or present but wholly
    NaN (an all-NaN column is as useless to the fit as a missing one)."""
    out: List[str] = []
    for c in REQUIRED_FEATURES:
        if c not in df.columns:
            out.append(c)
            continue
        col = pd.to_numeric(df[c], errors="coerce")
        if len(col) == 0 or bool(col.isna().all()):
            out.append(c)
    return out


def residual_training_frame(df: pd.DataFrame, closes: Dict[int, float]) -> pd.DataFrame:
    """The rows the residual model may train on.

    Keeps games with a real 1H close in [CLOSE_MIN, CLOSE_MAX] whose 1H actual
    passes grading.trusted_first_half_total (rejects the linescore false-zero
    corruption). Attaches the line features and TARGET = actual − close.
    Pushes stay (target 0) — a push is information about the line, not noise.
    """
    cols = list(df.columns) + [LINE_COL, "implied_1h_share", TARGET]
    if df.empty or not closes:
        return pd.DataFrame(columns=cols)
    sub = df[df["id"].isin(list(closes))].copy()
    if sub.empty:
        return pd.DataFrame(columns=cols)
    close = sub["id"].map(closes).astype(float)
    sub = attach_line_features(sub, close)
    fh = pd.to_numeric(sub["first_half_total"], errors="coerce")
    hp = sub["home_points"] if "home_points" in sub.columns else pd.Series(None, index=sub.index)
    ap = sub["away_points"] if "away_points" in sub.columns else pd.Series(None, index=sub.index)
    src = (
        sub["first_half_source"]
        if "first_half_source" in sub.columns
        else pd.Series(None, index=sub.index)
    )

    def _trusted(v, h, a, s):
        if pd.isna(v):
            return np.nan
        t = trusted_first_half_total(
            float(v),
            None if pd.isna(h) else float(h),
            None if pd.isna(a) else float(a),
            s if isinstance(s, str) else None,
        )
        return np.nan if t is None else float(t)

    trusted = pd.Series(
        [_trusted(v, h, a, s) for v, h, a, s in zip(fh, hp, ap, src)], index=sub.index
    )
    keep = trusted.notna() & sub[LINE_COL].between(CLOSE_MIN, CLOSE_MAX)
    sub = sub[keep].copy()
    sub[TARGET] = trusted[keep] - sub[LINE_COL]
    return _ensure_numeric(sub).reset_index(drop=True)


def _new_regressor() -> HistGradientBoostingRegressor:
    # Shallower/fewer trees than bv_line: the residual carries far less signal
    # than the total, and the training set (real closes only) is much smaller.
    return HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_depth=3,
        l2_regularization=1.0,
        max_iter=200,
        min_samples_leaf=MIN_SAMPLES_LEAF,
        random_state=7,
    )


def _require_fit_rows(n: int, what: str = "residual fit") -> None:
    """Refuse a fit that cannot produce a real tree. Names the count and the
    floor, so the job log says which one it was."""
    if n < RESIDUAL_MIN_FIT_ROWS:
        raise ResidualFitError(
            f"{what}: {n} training row(s) is under the floor of "
            f"{RESIDUAL_MIN_FIT_ROWS} (2 x min_samples_leaf={MIN_SAMPLES_LEAF}, "
            "the fewest rows that can make a single split)"
        )


def _fit_matrix(train: pd.DataFrame) -> pd.DataFrame:
    """The feature matrix handed to the estimator at FIT time.

    A wholly-NaN training column carries no information — but scikit-learn's
    binner cannot describe one. It drops the missing values first, so an
    all-NaN column leaves ZERO distinct values and
    `sliding_window_view(distinct, 2)` raises "window shape cannot be larger
    than input array shape" (newer numpy/scikit-learn; older builds happened
    to tolerate it). A CONSTANT column holds exactly the same amount of
    information and bins cleanly, so an all-NaN training column becomes a
    constant 0.0 here.

    Fit time only. Filling NaN at PREDICT time would send a genuinely unknown
    value into a real bin instead of down the model's missing branch, which is
    a different — and wrong — prediction.
    """
    X = train[RESIDUAL_FEATURE_COLS].astype(float)
    dead = [c for c in RESIDUAL_FEATURE_COLS if bool(X[c].isna().all())]
    for c in dead:
        X[c] = 0.0
    return X


def fit_residual(train: pd.DataFrame) -> HistGradientBoostingRegressor:
    """Fit the residual regressor. Raises ResidualFitError below the row floor."""
    assert_residual_features(RESIDUAL_FEATURE_COLS)
    train = _ensure_numeric(train.copy())
    _require_fit_rows(len(train))
    model = _new_regressor()
    model.fit(_fit_matrix(train), train[TARGET].astype(float))
    return model


def predict_residual(model, df: pd.DataFrame) -> np.ndarray:
    """r̂ = predicted (actual − line) for rows that carry the line features."""
    if df.empty:
        return np.array([], dtype=float)
    df = _ensure_numeric(df.copy())
    return np.asarray(model.predict(df[RESIDUAL_FEATURE_COLS]), dtype=float)


def predict_1h_total(model, df: pd.DataFrame) -> np.ndarray:
    """The engine's 1H number: the line it was given + r̂."""
    if df.empty:
        return np.array([], dtype=float)
    line = pd.to_numeric(df[LINE_COL], errors="coerce").astype(float).to_numpy()
    return line + predict_residual(model, df)


def cv_min_rows(k: int = 5) -> int:
    """Rows a k-fold sigma needs. Each fold fits on (k-1)/k of the frame, so
    the FOLD's training split — not the whole frame — must clear the fit floor.
    Below k rows KFold cannot even split."""
    if k < 2:
        return RESIDUAL_MIN_FIT_ROWS
    return max(k, -(-RESIDUAL_MIN_FIT_ROWS * k // (k - 1)))


def residual_sigma(train: pd.DataFrame, k: int = 5) -> Dict:
    """{"sigma", "lo_off", "hi_off"} from k-fold out-of-fold residuals of the
    residual model on TRAIN only (the target slate never enters). Offsets are
    added to the predicted 1H total for an 80% band.

    Guarded like fit_residual, but through the documented sentinel the caller
    already handles rather than an exception: a frame too small for every fold
    to clear RESIDUAL_MIN_FIT_ROWS returns all-None, and score_slate leaves the
    band NaN. Empty-safe."""
    empty = {"sigma": None, "lo_off": None, "hi_off": None}
    if train is None or len(train) < cv_min_rows(k):
        return empty
    train = _ensure_numeric(train.copy())
    y = train[TARGET].astype(float).to_numpy()
    cv = KFold(n_splits=k, shuffle=True, random_state=7)
    oof = cross_val_predict(_new_regressor(), _fit_matrix(train), y, cv=cv)
    err = y - np.asarray(oof, dtype=float)
    if len(err) == 0:
        return empty
    mean = float(err.mean())
    return {
        "sigma": round(float(err.std()), 2),
        "lo_off": round(float(np.quantile(err, _BAND_LO)) - mean, 2),
        "hi_off": round(float(np.quantile(err, _BAND_HI)) - mean, 2),
    }


def _date_str(v) -> Optional[str]:
    if v is None or pd.isna(v):
        return None
    return pd.Timestamp(v).strftime("%Y-%m-%d")


def fingerprint(train: pd.DataFrame, cols) -> Dict:
    """What the fitted model saw — enough to tell two card-day fits apart."""
    cols = list(cols)
    fp: Dict = {
        "model_version": MODEL_VERSION_TAG,
        "n_rows": int(len(train)),
        "seasons": sorted(int(s) for s in train["season"].dropna().unique())
        if "season" in train.columns
        else [],
        "min_game_date": None,
        "max_game_date": None,
        "feature_hash": hashlib.sha256("|".join(cols).encode()).hexdigest()[:16],
        "n_features": len(cols),
        "target_mean": None,
        "target_std": None,
        "sklearn_version": sklearn.__version__,
    }
    if "start_date" in train.columns and len(train):
        dates = pd.to_datetime(train["start_date"], errors="coerce")
        fp["min_game_date"] = _date_str(dates.min())
        fp["max_game_date"] = _date_str(dates.max())
    if TARGET in train.columns and len(train):
        y = pd.to_numeric(train[TARGET], errors="coerce").dropna()
        if len(y):
            fp["target_mean"] = round(float(y.mean()), 4)
            fp["target_std"] = round(float(y.std()), 4)
    return fp


def residual_1h_for_slate(
    train_resid: pd.DataFrame, target: pd.DataFrame, line: pd.Series
) -> Tuple[np.ndarray, object, Dict]:
    """Fit on the residual training frame, predict the slate given its ranking
    line: (predicted 1H total, fitted model, fingerprint). Empty train or slate
    -> (empty array, None, {}), like bv_line_for_slate.

    A REQUIRED_FEATURES column missing from either frame warns (RuntimeWarning)
    and lands in fingerprint["missing_features"]; the long tail stays a silent
    NaN fill. A training frame under RESIDUAL_MIN_FIT_ROWS raises
    ResidualFitError (score_slate demotes the board to the incumbent)."""
    if train_resid is None or train_resid.empty or target.empty:
        return np.array([], dtype=float), None, {}
    model = fit_residual(train_resid)
    slate = attach_line_features(target, line)
    pred = predict_1h_total(model, slate)
    fp = fingerprint(train_resid, RESIDUAL_FEATURE_COLS)
    missing = sorted(set(missing_required(train_resid)) | set(missing_required(slate)))
    if missing:
        warnings.warn(
            f"residual engine: required feature(s) {missing} absent or all-NaN — "
            "the model is conditioning on a NaN column",
            RuntimeWarning,
            stacklevel=2,
        )
    fp["missing_features"] = missing
    return pred, model, fp
