"""Overfitting controls: Deflated Sharpe + PBO (CSCV)."""

import math

from beatvegas.backtest.overfit import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    pbo,
    probabilistic_sharpe_ratio,
    sharpe_ratio,
    sr_variance_across_configs,
)


def test_sharpe_ratio():
    assert sharpe_ratio([1.0, 1.0, 1.0]) == 0.0  # no variance -> 0 by convention
    assert sharpe_ratio([2.0, -1.0, 2.0, -1.0]) > 0  # positive mean


def test_psr_increases_with_sample_and_sr():
    # Same SR, more observations -> more confident it's > 0.
    p_small = probabilistic_sharpe_ratio(0.2, n=20, skew=0.0, kurtosis=3.0)
    p_large = probabilistic_sharpe_ratio(0.2, n=500, skew=0.0, kurtosis=3.0)
    assert 0 < p_small < p_large <= 1


def test_expected_max_sharpe_grows_with_trials():
    # Trying more configs raises the bar a real edge must clear.
    few = expected_max_sharpe(2, sr_variance=0.04)
    many = expected_max_sharpe(100, sr_variance=0.04)
    assert many > few > 0
    assert expected_max_sharpe(1, 0.04) == 0.0  # <2 trials -> no benchmark
    assert expected_max_sharpe(50, 0.0) == 0.0  # no spread -> no benchmark


def test_deflated_sharpe_drops_as_trials_rise():
    # A return series with a real positive mean.
    returns = [0.9, -1.0, 0.9, 0.9, -1.0, 0.9, 0.9, -1.0, 0.9, 0.9] * 5
    var = 0.05
    dsr_few = deflated_sharpe_ratio(returns, n_trials=2, sr_variance=var)
    dsr_many = deflated_sharpe_ratio(returns, n_trials=1000, sr_variance=var)
    assert 0 <= dsr_many <= dsr_few <= 1
    assert dsr_few > dsr_many  # deflation strictly tightens with more trials


def test_pbo_dominant_config_is_zero():
    # Config 0 beats config 1 in EVERY observation -> never overfit -> PBO 0.
    matrix = [[2.0, 0.0] for _ in range(64)]
    assert pbo(matrix, n_splits=8) == 0.0


def test_pbo_in_unit_interval_for_mixed_signal():
    # Two configs that each "win" on alternating observations: no stable edge.
    matrix = []
    for i in range(64):
        matrix.append([1.0, 0.0] if i % 2 == 0 else [0.0, 1.0])
    p = pbo(matrix, n_splits=8)
    assert 0.0 <= p <= 1.0 and not math.isnan(p)


def test_pbo_nan_when_insufficient():
    assert math.isnan(pbo([[1.0, 2.0]], n_splits=16))  # too few rows
    assert math.isnan(pbo([[1.0] for _ in range(64)], n_splits=8))  # only 1 config


def test_sr_variance_across_configs():
    assert sr_variance_across_configs([[1.0, 1.0]]) == 0.0  # <2 usable configs
    v = sr_variance_across_configs([[2.0, -1.0, 2.0, -1.0], [1.0, 1.0, 1.0, 1.0]])
    assert v >= 0.0
