"""Spread-adjusted 1H multiplier: flat fallback, spread sensitivity, clamps, fit."""

import numpy as np

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
