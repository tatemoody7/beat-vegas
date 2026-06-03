import numpy as np
import pandas as pd

from beatvegas.etl.features import FEATURE_COLS
from beatvegas.model.bv_line import (
    apply_bias, bias_corrections, bv_line_for_slate, oof_residuals,
    residual_band, residual_report,
)


def _synthetic_frame(seasons=range(2015, 2025), per_season=300, low_bias=0.0,
                     seed=7):
    """A frame where first_half_total is a clean function of two features plus
    an optional per-era additive shift, so we can assert bias correction works."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        for _ in range(per_season):
            row = {c: 0.0 for c in FEATURE_COLS}
            x1 = rng.normal(0, 1)
            x2 = rng.normal(0, 1)
            row["combined_off_ppa"] = x1
            row["combined_def_ppa"] = x2
            row["combined_sec_play"] = rng.uniform(20, 32)
            row["wx_dome"] = float(rng.integers(0, 2))
            row["era_post2023"] = 1.0 if s >= 2023 else 0.0
            era_shift = low_bias if s >= 2023 else 0.0
            row["first_half_total"] = (
                24 + 3 * x1 - 2 * x2 + era_shift + rng.normal(0, 1.5))
            row["season"] = s
            rows.append(row)
    return pd.DataFrame(rows)


def test_oof_residuals_are_low_bias_on_clean_data():
    df = _synthetic_frame()
    res = oof_residuals(df)
    assert not res.empty
    # A well-specified regressor should be ~unbiased out of fold.
    assert abs(res["residual"].mean()) < 0.5


def test_residual_report_surfaces_first_postera_bias():
    # Honest limit: the FIRST post-2023 season can't be de-biased from data that
    # doesn't exist yet. With only 2023 as the post-era season, the OOF report
    # must SURFACE a large positive post-2023 residual so a human sees it.
    df = _synthetic_frame(seasons=range(2015, 2024), low_bias=4.0)
    report = residual_report(df)
    assert "post2023" in report["by_era"]
    assert report["by_era"]["post2023"]["mean_residual"] > 2.0   # flagged, not hidden


def test_apply_bias_shifts_by_global():
    frame = pd.DataFrame({"era_post2023": [0.0, 1.0]})
    out = apply_bias(np.array([10.0, 10.0]), frame, {"global": 2.0})
    assert out[0] == 12.0
    assert out[1] == 12.0


def test_bv_line_is_clean_floats():
    df = _synthetic_frame()
    train = df[df["season"] < 2024]
    target = df[df["season"] == 2024].copy()
    bv = bv_line_for_slate(train, target)
    assert bv.dtype == float
    assert not np.isnan(bv).any()


def test_empty_slate_returns_empty():
    df = _synthetic_frame()
    assert len(bv_line_for_slate(df, df.iloc[0:0])) == 0
    assert len(bv_line_for_slate(df.iloc[0:0], df)) == 0


def test_residual_band_is_ordered_and_positive_sigma():
    df = _synthetic_frame()
    band = residual_band(df)
    assert band["sigma"] > 0
    assert band["lo_off"] < 0 < band["hi_off"]      # lo below, hi above the line
    # Synthetic noise is N(0, 1.5) → 80% band ≈ ±1.9; sanity bound.
    assert 0.5 < band["sigma"] < 4.0
