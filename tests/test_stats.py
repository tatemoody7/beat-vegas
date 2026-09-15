"""The shared bootstrap and Holm helpers behave as the pre-registered rules assume."""

import numpy as np
import pytest

from beatvegas.backtest import stats as S


def test_paired_bootstrap_detects_a_clear_paired_difference():
    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, 400)
    r = S.paired_bootstrap_mean(base + 0.5, base, n_boot=500)
    assert r["n"] == 400 and r["mean"] == pytest.approx(0.5, abs=1e-9)
    assert r["lo"] > 0.4 and r["excludes_zero"] and r["p"] < 0.01


def test_paired_bootstrap_on_noise_spans_zero_and_reports_a_large_p():
    rng = np.random.default_rng(2)
    r = S.paired_bootstrap_mean(rng.normal(0, 1, 200), n_boot=500)
    assert r["lo"] < 0 < r["hi"] and not r["excludes_zero"] and r["p"] > 0.05


def test_paired_bootstrap_drops_nans_and_handles_empty():
    r = S.paired_bootstrap_mean([1.0, float("nan"), 3.0], n_boot=50)
    assert r["n"] == 2 and r["mean"] == pytest.approx(2.0)
    e = S.paired_bootstrap_mean([], n_boot=50)
    assert e["n"] == 0 and e["mean"] is None and not e["excludes_zero"]


def test_paired_bootstrap_requires_equal_lengths():
    with pytest.raises(ValueError):
        S.paired_bootstrap_mean([1, 2, 3], [1, 2])


def test_holm_is_step_down_monotone_and_capped():
    adj = S.holm_adjust([0.01, 0.04, 0.03, 0.20])
    # ranks: 0.01 (x4=0.04), 0.03 (x3=0.09), 0.04 (x2=0.08 -> 0.09 monotone), 0.20 (x1)
    assert adj == pytest.approx([0.04, 0.09, 0.09, 0.20])
    assert S.holm_adjust([0.5, 0.9]) == pytest.approx([1.0, 1.0])


def test_holm_ignores_none_and_reject_uses_family_alpha():
    adj = S.holm_adjust([0.01, None, 0.02])
    assert adj[1] is None and adj[0] == pytest.approx(0.02) and adj[2] == pytest.approx(0.02)
    assert S.holm_reject([0.01, None, 0.02], alpha=0.05) == [True, False, True]
    assert S.holm_reject([0.03, 0.04, 0.05], alpha=0.05) == [False, False, False]
