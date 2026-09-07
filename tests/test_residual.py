"""model/residual.py — the market-residual 1H engine (inactive by default).

It conditions on the pre-kick 1H line and predicts actual − line. These tests
pin the training-frame filters (trusted 1H only, real close in [10, 60],
pushes kept), leak-freedom guards, and that the regressor recovers a planted
residual signal."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beatvegas.etl.features import FEATURE_COLS, FH_FACTOR_COLS
from beatvegas.model import residual as R
from beatvegas.model.bv_line import BV_FEATURE_COLS


def _frame(seasons=range(2016, 2026), per_season=120, seed=11, noise=1.5):
    """fh = close + 2*x - 1 + noise: the residual is a clean function of ONE
    feature (home_fh_off_epa) so the regressor should recover it."""
    rng = np.random.default_rng(seed)
    rows, closes = [], {}
    gid = 1
    for s in seasons:
        for i in range(per_season):
            row = {c: 0.0 for c in FEATURE_COLS}
            x = rng.normal(0, 1)
            close = float(rng.integers(40, 56)) / 2.0  # 20.0 .. 27.5
            row.update(
                {
                    "id": gid,
                    "season": s,
                    "week": 3 + (i % 10),
                    "start_date": pd.Timestamp(f"{s}-10-01") + pd.Timedelta(days=7 * (i % 10)),
                    "home_fh_off_epa": x,
                    "full_game_total": 50.0,
                    "spread": -3.0,
                    "wx_wind_band": float(rng.integers(0, 4)),
                    "era_post2023": 1.0 if s >= 2023 else 0.0,
                    "home_points": 30,
                    "away_points": 20,
                    "first_half_source": "pbp",
                }
            )
            row["first_half_total"] = close + 2 * x - 1 + rng.normal(0, noise)
            row["under"] = float(row["first_half_total"] < close)
            rows.append(row)
            closes[gid] = close
            gid += 1
    return pd.DataFrame(rows), closes


# --- attach_line_features ------------------------------------------------------


def test_attach_line_features_share_nan_on_zero_or_nan_total():
    df = pd.DataFrame({"full_game_total": [50.0, 0.0, np.nan, -5.0]})
    out = R.attach_line_features(df, pd.Series([25.0, 25.0, 25.0, 25.0], index=df.index))
    assert out[R.LINE_COL].tolist() == [25.0, 25.0, 25.0, 25.0]
    assert out[R.LINE_COL].dtype == float
    assert out["implied_1h_share"].iloc[0] == pytest.approx(0.5)
    assert out["implied_1h_share"].iloc[1:].isna().all()


def test_attach_line_features_does_not_mutate_input():
    df = pd.DataFrame({"full_game_total": [50.0]})
    R.attach_line_features(df, pd.Series([25.0]))
    assert R.LINE_COL not in df.columns


# --- residual_training_frame ---------------------------------------------------


def _tiny():
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5, 6, 7],
            "first_half_total": [20.0, 0.0, 0.0, 24.5, 30.0, 25.0, 22.0],
            "home_points": [28, 31, 0, 21, 40, 30, 27],
            "away_points": [14, 10, 0, 17, 35, 20, 20],
            "first_half_source": ["pbp", "linescores", "linescores", "pbp", "pbp", "pbp", "pbp"],
            "full_game_total": [50.0, 52.0, 44.0, 48.0, 70.0, 50.0, 47.0],
        }
    )


def test_training_frame_target_is_fh_minus_close_and_filters():
    closes = {1: 22.5, 2: 24.0, 3: 21.0, 4: 24.5, 5: 65.0, 6: 8.5}  # 7 has no close
    out = R.residual_training_frame(_tiny(), closes)
    ids = out["id"].tolist()
    assert 1 in ids and 4 in ids
    assert 2 not in ids  # linescore false-zero (fh 0, final 41): untrusted
    assert 3 in ids  # genuine 0-0 half in a 0-0 final: trusted
    assert 5 not in ids  # close 65 > 60
    assert 6 not in ids  # close 8.5 < 10
    assert 7 not in ids  # no real close
    by_id = out.set_index("id")
    assert by_id.loc[1, R.TARGET] == pytest.approx(20.0 - 22.5)
    assert by_id.loc[4, R.TARGET] == pytest.approx(0.0)  # push kept, target 0
    assert by_id.loc[1, R.LINE_COL] == 22.5
    assert by_id.loc[1, "implied_1h_share"] == pytest.approx(22.5 / 50.0)


def test_training_frame_empty_closes_is_empty():
    out = R.residual_training_frame(_tiny(), {})
    assert out.empty
    assert R.TARGET in out.columns and R.LINE_COL in out.columns


def test_training_frame_drops_nan_first_half_total():
    df = _tiny()
    df.loc[0, "first_half_total"] = np.nan
    out = R.residual_training_frame(df, {1: 22.5, 4: 24.5})
    assert out["id"].tolist() == [4]


# --- feature guards --------------------------------------------------------------


def test_residual_feature_cols_pass_guard():
    R.assert_residual_features(R.RESIDUAL_FEATURE_COLS)


@pytest.mark.parametrize(
    "bad",
    [
        "bv_line",
        "bv_gap",
        "line_used",
        "closing_line",
        "proxy_line",
        "under",
        R.TARGET,
        # the OUTCOME columns build_feature_frame carries next to the features
        "home_points",
        "away_points",
        "first_half_total",
        "first_half_source",
        "home_fh",
        "away_fh",
    ],
)
def test_guard_trips_on_banned_column(bad):
    with pytest.raises(AssertionError):
        R.assert_residual_features(R.RESIDUAL_FEATURE_COLS + [bad])


def test_guard_requires_the_line_column():
    cols = [c for c in R.RESIDUAL_FEATURE_COLS if c != R.LINE_COL]
    with pytest.raises(AssertionError):
        R.assert_residual_features(cols)


def test_incumbent_bv_line_stays_market_blind():
    # The residual engine's line-derived columns must never leak into the
    # market-blind regressor (its whole point is an independent number).
    assert not set(BV_FEATURE_COLS) & {R.LINE_COL, "implied_1h_share", "wx_wind_band"}


def test_residual_feature_cols_are_unique_and_include_all_fh_factors():
    assert len(R.RESIDUAL_FEATURE_COLS) == len(set(R.RESIDUAL_FEATURE_COLS))
    assert set(FH_FACTOR_COLS) <= set(R.RESIDUAL_FEATURE_COLS)


def test_residual_feature_cols_exist_in_the_feature_frame():
    """Every column is either produced by features.py (FEATURE_COLS, or the
    extra frame columns spread / wx_wind_band) or attached by this module."""
    frame_cols = set(FEATURE_COLS) | {"spread", "wx_wind_band"}
    attached = {R.LINE_COL, "implied_1h_share"}
    missing = set(R.RESIDUAL_FEATURE_COLS) - frame_cols - attached
    assert not missing, missing


# --- fit / predict ------------------------------------------------------------------


def test_regressor_recovers_planted_residual():
    df, closes = _frame()
    train_r = R.residual_training_frame(df[df["season"] < 2025], closes)
    test_r = R.residual_training_frame(df[df["season"] == 2025], closes)
    model = R.fit_residual(train_r)
    r_hat = R.predict_residual(model, test_r)
    signal = (2 * test_r["home_fh_off_epa"] - 1).to_numpy()
    mae_model = np.mean(np.abs(r_hat - signal))
    mae_zero = np.mean(np.abs(signal))  # predicting "no residual" (the market)
    assert mae_model < 0.5 * mae_zero
    assert mae_model < 1.0  # well under the planted signal's scale (~1.6)


def test_predict_1h_total_is_line_plus_residual():
    df, closes = _frame(per_season=60)
    train_r = R.residual_training_frame(df[df["season"] < 2025], closes)
    test_r = R.residual_training_frame(df[df["season"] == 2025], closes)
    model = R.fit_residual(train_r)
    total = R.predict_1h_total(model, test_r)
    np.testing.assert_allclose(
        total, test_r[R.LINE_COL].to_numpy() + R.predict_residual(model, test_r)
    )


def test_residual_sigma_positive_and_ordered():
    df, closes = _frame(per_season=60)
    train_r = R.residual_training_frame(df[df["season"] < 2025], closes)
    band = R.residual_sigma(train_r)
    assert band["sigma"] > 0
    assert band["lo_off"] < 0 < band["hi_off"]


def test_residual_sigma_empty_safe():
    empty = R.residual_training_frame(_tiny(), {})
    assert R.residual_sigma(empty) == {"sigma": None, "lo_off": None, "hi_off": None}


def test_fingerprint_is_stable_and_column_sensitive():
    df, closes = _frame(per_season=40)
    train_r = R.residual_training_frame(df[df["season"] < 2025], closes)
    a = R.fingerprint(train_r, R.RESIDUAL_FEATURE_COLS)
    b = R.fingerprint(train_r, R.RESIDUAL_FEATURE_COLS)
    assert a == b
    assert a["n_rows"] == len(train_r)
    assert a["n_features"] == len(R.RESIDUAL_FEATURE_COLS)
    assert a["seasons"] == list(range(2016, 2025))
    assert a["min_game_date"] == "2016-10-01" and a["max_game_date"] == "2024-12-03"
    assert len(a["feature_hash"]) == 16
    assert isinstance(a["sklearn_version"], str)
    renamed = [c if c != "spread" else "spread_x" for c in R.RESIDUAL_FEATURE_COLS]
    assert R.fingerprint(train_r, renamed)["feature_hash"] != a["feature_hash"]


def test_residual_1h_for_slate_returns_pred_model_fingerprint():
    df, closes = _frame(per_season=60)
    train_r = R.residual_training_frame(df[df["season"] < 2025], closes)
    target = df[df["season"] == 2025].copy()
    line = target["id"].map(closes).astype(float)
    pred, model, fp = R.residual_1h_for_slate(train_r, target, line)
    assert len(pred) == len(target) and pred.dtype == float and not np.isnan(pred).any()
    assert fp["n_rows"] == len(train_r) and fp["model_version"] == R.MODEL_VERSION_TAG
    assert hasattr(model, "predict")


def test_residual_1h_for_slate_empty_safe():
    df, closes = _frame(per_season=20)
    train_r = R.residual_training_frame(df, closes)
    pred, model, fp = R.residual_1h_for_slate(train_r, df.iloc[0:0], pd.Series([], dtype=float))
    assert len(pred) == 0 and model is None and fp == {}
    pred, model, fp = R.residual_1h_for_slate(train_r.iloc[0:0], df, df["id"].map(closes))
    assert len(pred) == 0 and model is None and fp == {}


def test_residual_1h_for_slate_tolerates_missing_frame_columns():
    """A frame that predates a LONG-TAIL feature (wx_wind_band) still scores with
    NaN, not KeyError — the same contract features.py gives FEATURE_COLS. But a
    missing REQUIRED feature (spread) is not a silent NaN fill: it warns and is
    named in the fingerprint, because the residual has little signal to spare."""
    df, closes = _frame(per_season=40)
    df = df.drop(columns=["wx_wind_band", "spread"])
    train_r = R.residual_training_frame(df[df["season"] < 2025], closes)
    target = df[df["season"] == 2025].copy()
    with pytest.warns(RuntimeWarning, match="spread"):
        pred, _, fp = R.residual_1h_for_slate(
            train_r, target, target["id"].map(closes).astype(float)
        )
    assert len(pred) == len(target)
    assert fp["missing_features"] == ["spread"]  # wx_wind_band is long tail, not required


def test_residual_1h_for_slate_does_not_warn_on_a_complete_frame(recwarn):
    df, closes = _frame(per_season=40)
    train_r = R.residual_training_frame(df[df["season"] < 2025], closes)
    target = df[df["season"] == 2025].copy()
    _, _, fp = R.residual_1h_for_slate(train_r, target, target["id"].map(closes).astype(float))
    assert fp["missing_features"] == []
    assert [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)] == []


def test_required_features_all_nan_column_counts_as_missing():
    """A column that is present but entirely NaN is as useless as an absent one."""
    df, closes = _frame(per_season=40)
    df["full_game_total"] = np.nan
    train_r = R.residual_training_frame(df[df["season"] < 2025], closes)
    target = df[df["season"] == 2025].copy()
    with pytest.warns(RuntimeWarning, match="full_game_total"):
        _, _, fp = R.residual_1h_for_slate(train_r, target, target["id"].map(closes).astype(float))
    assert fp["missing_features"] == ["full_game_total"]
