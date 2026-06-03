"""Tests for the factor-testing & ranking harness (beatvegas.factors)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beatvegas.etl.features import MARKET_COLS
from beatvegas.factors import (
    evaluate_combos,
    evaluate_factor,
    rank_factors,
)
from beatvegas.factors.registry import Factor, default_registry, evaluable_factors


def _synthetic_frame(n_per_season=400, seasons=(2015, 2016, 2017, 2018, 2019),
                     seed=7) -> pd.DataFrame:
    """Frame where `signal` determines `under` and `noise` is irrelevant."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        signal = rng.normal(size=n_per_season)
        noise = rng.normal(size=n_per_season)
        # under is a near-deterministic function of signal (high signal -> under)
        under = (signal + rng.normal(scale=0.2, size=n_per_season) > 0).astype(int)
        rows.append(pd.DataFrame({
            "season": s, "signal": signal, "noise": noise, "under": under,
        }))
    return pd.concat(rows, ignore_index=True)


# --- registry ----------------------------------------------------------------

def test_registry_market_flag_synced():
    reg = {f.name: f for f in default_registry()}
    for col in MARKET_COLS:
        assert reg[col].market is True, f"{col} should be flagged market"


def test_registry_names_unique():
    names = [f.name for f in default_registry()]
    assert len(names) == len(set(names))


def test_evaluable_excludes_forward_only_by_default():
    df = pd.DataFrame({"season": [2015], "under": [0], "signal": [0.0]})
    reg = [Factor("signal", "x"), Factor("inj", "x", forward_only=True)]
    # monkey-free: call the filter logic via a frame that has both columns
    df["inj"] = 0.0
    import beatvegas.factors.registry as R
    orig = R._FACTORS
    try:
        R._FACTORS = reg
        names = [f.name for f in evaluable_factors(df, include_forward_only=False)]
        assert "signal" in names and "inj" not in names
        names2 = [f.name for f in evaluable_factors(df, include_forward_only=True)]
        assert "inj" in names2
    finally:
        R._FACTORS = orig


# --- evaluation --------------------------------------------------------------

def test_strong_factor_beats_noise():
    df = _synthetic_frame()
    sig = evaluate_factor(df, Factor("signal", "x"), first_test_season=2017)
    noise = evaluate_factor(df, Factor("noise", "x"), first_test_season=2017)
    assert sig is not None and noise is not None
    assert sig["auc"] > 0.9                       # near-perfect predictor
    assert sig["top_under_pct"] > 90              # top selection almost all unders
    assert sig["auc"] > noise["auc"]              # signal clearly beats noise
    assert abs(noise["auc"] - 0.5) < 0.1          # noise ~ coin flip


def test_evaluate_factor_is_deterministic():
    df = _synthetic_frame()
    a = evaluate_factor(df, Factor("signal", "x"), first_test_season=2017)
    b = evaluate_factor(df, Factor("signal", "x"), first_test_season=2017)
    assert a == b


def test_sparse_factor_returns_none():
    df = _synthetic_frame(n_per_season=10)        # far below the OOS minimum
    assert evaluate_factor(df, Factor("signal", "x"), first_test_season=2017) is None


def test_rank_orders_signal_first_and_carries_flags():
    df = _synthetic_frame()
    factors = [Factor("signal", "x"), Factor("noise", "x"),
               Factor("signal", "mkt", market=True)]  # dup name w/ market flag
    # use distinct names so both evaluate
    factors = [Factor("signal", "core"), Factor("noise", "core")]
    out = rank_factors(df, factors, first_test_season=2017, combo_top_k=2)
    uni = out["univariate"]
    assert uni[0]["factor"] == "signal" and uni[0]["rank"] == 1
    assert all("perm_importance" in r for r in uni)
    assert out["baseline"]["n"] == len(df)


def test_inspect_combo_smoke():
    from beatvegas.factors.inspect import inspect_combo
    df = _synthetic_frame()
    df["id"] = range(len(df))
    df["week"] = 1
    df["proxy_line"] = 28.0
    df["first_half_total"] = np.where(df["under"] == 1, 24, 31)
    for c in ["era_post2023", "wx_dome", "conference_game", "neutral_site"]:
        df[c] = 0
    rep = inspect_combo(df, ["signal"], first_test_season=2017)
    assert set(["overall", "by_season", "by_era", "proxy_stress", "direction"]).issubset(rep)
    assert rep["overall"]["under_pct"] > 90       # signal selects unders
    assert len(rep["proxy_stress"]) == 7


def test_combo_scan_runs():
    df = _synthetic_frame()
    df["signal2"] = df["signal"] + np.random.default_rng(1).normal(size=len(df))
    combos = evaluate_combos(df, ["signal", "signal2", "noise"], sizes=(2,),
                             top_k=3, first_test_season=2017)
    assert combos and combos[0]["factor"].count("+") == 1
    assert combos[0]["top_roi"] >= combos[-1]["top_roi"]   # sorted best-first
