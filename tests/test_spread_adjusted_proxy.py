"""Spread-adjusted 1H multiplier: flat fallback, spread sensitivity, clamps, fit."""

import numpy as np
import pytest

from beatvegas.etl import proxy_line
from beatvegas.etl.proxy_line import (
    DEFAULT_SHARE,
    SHARE_CLAMP,
    fh_share,
    fit_share,
    proxy_total,
)


def test_no_spread_is_always_flat():
    # No spread -> flat, regardless of whether a fitted curve exists.
    assert fh_share(None) == DEFAULT_SHARE
    assert fh_share(None, coeffs={"a": 0.50, "b": 0.003}) == DEFAULT_SHARE


def test_flat_fallback_when_no_fitted_curve(monkeypatch):
    # With no fitted curve on disk, even a spread falls back to flat. Hermetic:
    # force the loader to None so the test doesn't depend on data/multiplier.json.
    monkeypatch.setattr(proxy_line, "_load_share_coeffs", lambda: None)
    assert fh_share(10.0) == DEFAULT_SHARE
    assert fh_share(10.0, coeffs=None) == DEFAULT_SHARE


def test_share_rises_with_spread_magnitude():
    c = {"a": 0.50, "b": 0.003}
    assert fh_share(0.0, coeffs=c) == 0.50
    assert fh_share(10.0, coeffs=c) == 0.53
    assert fh_share(-10.0, coeffs=c) == 0.53  # uses |spread|


def test_clamps_hold():
    hi = fh_share(100.0, coeffs={"a": 0.50, "b": 0.01})
    lo = fh_share(100.0, coeffs={"a": 0.40, "b": -0.01})
    assert hi == SHARE_CLAMP[1]
    assert lo == SHARE_CLAMP[0]


def test_proxy_total_flat_default_matches_legacy():
    # 60*0.52 = 31.2 -> 31.0 ; 47*0.52 = 24.44 -> 24.5 (legacy line_study values).
    assert proxy_total(60.0) == 31.0
    assert proxy_total(47.0, ratio=0.52) == 24.5


def test_proxy_total_spread_adjusted_is_higher_for_big_favorite():
    c = {"a": 0.50, "b": 0.003}
    flat = proxy_total(60.0)  # 31.0
    big = proxy_total(60.0, spread=20.0, coeffs=c)  # share clamps to 0.56 -> 33.5
    assert big > flat
    assert big == 33.5


def test_fit_share_recovers_coefficients():
    rng = np.arange(0.0, 28.0, 0.5)
    full = np.full_like(rng, 60.0)
    share = 0.50 + 0.002 * np.abs(rng)
    fh = full * share
    out = fit_share(full, rng, fh)
    assert abs(out["a"] - 0.50) < 1e-6
    assert abs(out["b"] - 0.002) < 1e-6


# --- step-shaped share (FBS-only finding: flat ~0.51 below a blowout cut, higher above) ---

STEP = {"kind": "step", "base": 0.51, "blowout": 0.54, "cut": 21.0}


def test_step_share_is_base_below_cut_and_blowout_at_or_above_cut():
    assert fh_share(0.0, coeffs=STEP) == 0.51
    assert fh_share(20.5, coeffs=STEP) == 0.51
    assert fh_share(21.0, coeffs=STEP) == 0.54
    assert fh_share(-35.0, coeffs=STEP) == 0.54  # uses |spread|


def test_step_share_without_a_spread_uses_the_base_not_the_legacy_flat():
    # A fitted base is the best no-spread guess; the legacy linear kind keeps flat.
    assert fh_share(None, coeffs=STEP) == 0.51
    assert fh_share(None, coeffs={"a": 0.50, "b": 0.003}) == DEFAULT_SHARE


def test_step_share_clamps_hold():
    assert (
        fh_share(30.0, coeffs={"kind": "step", "base": 0.40, "blowout": 0.70, "cut": 21})
        == (SHARE_CLAMP[1])
    )


def test_fit_share_step_recovers_mae_optimal_bucket_shares():
    from beatvegas.etl.proxy_line import fit_share_step

    spread = np.array([3.0, 7.0, 10.0, 14.0, 24.0, 28.0, 35.0, 42.0])
    full = np.full_like(spread, 50.0)
    # below the cut the half lands at exactly 0.51*50, above at 0.54*50
    fh = np.where(np.abs(spread) >= 21, 27.0, 25.5)
    out = fit_share_step(full, spread, fh, cut=21.0)
    assert out["kind"] == "step"
    assert out["cut"] == 21.0
    assert abs(out["base"] - 0.51) < 0.0026  # grid resolution 0.0025
    assert abs(out["blowout"] - 0.54) < 0.0026


def test_load_games_frame_filters_to_fbs_by_default(monkeypatch):
    import pandas as pd

    raw = pd.DataFrame(
        {
            "id": [1, 2],
            "season": [2024, 2024],
            "week": [3, 3],
            "home_team": ["Alabama", "Alabama"],
            "away_team": ["Georgia", "Furman"],
            "first_half_total": [24.0, 30.0],
            "full_game_total": [50.0, 55.0],
            "home_points": [27, 40],
            "away_points": [20, 10],
            "neutral_site": [0, 0],
            "spread": [-3.0, -30.0],
        }
    )
    monkeypatch.setattr(proxy_line, "_query_games_frame", lambda seasons=None: raw)
    monkeypatch.setattr(proxy_line, "load_fbs_teams", lambda: {2024: {"Alabama", "Georgia"}})
    assert proxy_line.load_games_frame()["id"].tolist() == [1]
    assert proxy_line.load_games_frame(fbs_only=False)["id"].tolist() == [1, 2]


@pytest.mark.real_multiplier
def test_adopted_multiplier_on_disk_is_the_fbs_step_model():
    """Documents the adopted state: data/multiplier.json is a step model fitted on
    FBS-vs-FBS games whose base sits below the legacy flat 0.52."""
    proxy_line._load_share_coeffs.cache_clear()
    c = proxy_line._load_share_coeffs()
    assert c is not None and c["kind"] == "step"
    assert c["cut"] == 21.0
    assert c["base"] < DEFAULT_SHARE < c["blowout"]
    assert fh_share(None) == c["base"]
    assert fh_share(-28.0) == c["blowout"]
