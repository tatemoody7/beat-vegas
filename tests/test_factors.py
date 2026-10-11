"""Tests for the factor-testing & ranking harness (beatvegas.factors)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from beatvegas.etl.features import MARKET_COLS
from beatvegas.factors.registry import Factor, default_registry, evaluable_factors


def _synthetic_frame(
    n_per_season=400, seasons=(2015, 2016, 2017, 2018, 2019), seed=7
) -> pd.DataFrame:
    """Frame where `signal` determines `under` and `noise` is irrelevant."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        signal = rng.normal(size=n_per_season)
        noise = rng.normal(size=n_per_season)
        # under is a near-deterministic function of signal (high signal -> under)
        under = (signal + rng.normal(scale=0.2, size=n_per_season) > 0).astype(int)
        rows.append(
            pd.DataFrame(
                {
                    "season": s,
                    "signal": signal,
                    "noise": noise,
                    "under": under,
                }
            )
        )
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
