"""The censoring study: scoring rules, the push audit, and the decision rule.

The study itself is a report, but its arithmetic is load-bearing -- a wrong
Wilson interval or a push mishandled by 0.75 pp is the same size as the effect
it was built to detect.
"""

import numpy as np
import pandas as pd
import pytest

from beatvegas.backtest import censoring as C

# --- scoring rules (none of which existed anywhere in this repo before) ------


def test_brier_and_log_loss_reward_the_better_forecast():
    y = np.array([1.0, 1.0, 0.0, 0.0])
    good = np.array([0.9, 0.8, 0.2, 0.1])
    bad = np.array([0.1, 0.2, 0.8, 0.9])
    assert C.brier(good, y) < C.brier(bad, y)
    assert C.log_loss(good, y) < C.log_loss(bad, y)
    # A coin flip scores exactly 0.25 on Brier whatever the outcomes are.
    assert C.brier(np.full(4, 0.5), y) == pytest.approx(0.25)


def test_log_loss_does_not_explode_on_a_confident_miss():
    """An unclipped log-loss returns inf the first time a forecast says 0.0 and
    the thing happens, which silently poisons every aggregate downstream."""
    v = C.log_loss(np.array([0.0, 1.0]), np.array([1.0, 0.0]))
    assert np.isfinite(v) and v > 10


def test_three_outcome_brier_handles_pushes():
    """The future engine emits P(under)/P(push)/P(over). Writing the binary
    version only would guarantee a rewrite AND make the numbers incomparable."""
    p = np.array([[0.5, 0.05, 0.45], [0.2, 0.10, 0.70]])
    y = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    assert C.brier_multi(p, y) == pytest.approx((0.25 + 0.0025 + 0.2025 + 0.04 + 0.01 + 0.09) / 2)


def test_wilson_is_asymmetric_in_the_tail_where_normal_is_wrong():
    """The 28+ bucket is 65 games. A normal approximation there can put the
    upper bound above 1.0; Wilson cannot."""
    lo, hi = C.wilson(15, 65)
    assert 0 < lo < 15 / 65 < hi < 1
    lo0, hi0 = C.wilson(0, 30)
    assert lo0 == pytest.approx(0.0, abs=1e-9) and 0 < hi0 < 0.2
    assert C.wilson(0, 0) == (None, None)


# --- the push audit ----------------------------------------------------------


def _frame(rows):
    return pd.DataFrame(
        rows, columns=["line_real", "outcome_real", "season", "spread", "spread_abs", "fair_under"]
    )


def test_push_audit_splits_integer_from_half_point_and_sizes_the_bias():
    """A half-point line cannot push; an integer one can. Mixing them and
    leaving pushes in the denominator biases the Under rate silently."""
    rows = (
        [[24.5, "under", 2024, -3, 3, 0.5]] * 3
        + [[24.5, "over", 2024, -3, 3, 0.5]] * 3
        + [[24.0, "under", 2024, -3, 3, 0.5]] * 3
        + [[24.0, "over", 2024, -3, 3, 0.5]] * 2
        + [[24.0, "push", 2024, -3, 3, 0.5]] * 2
    )
    a = C.push_audit(_frame(rows))
    assert a["n"] == 13 and a["pushes"] == 2
    by = {r["line_type"]: r for r in a["by_line_type"]}
    assert by["half-point"]["pushes"] == 0
    assert by["integer"]["pushes"] == 2
    # 6 unders / 13 all vs 6 / 11 decided
    assert a["under_pct_all"] == pytest.approx(100 * 6 / 13)
    assert a["under_pct_decided"] == pytest.approx(100 * 6 / 11)
    assert a["bias_pp_if_ignored"] > 0


# --- the gate ----------------------------------------------------------------


def _synthetic(n=4000, true_coef=0.0, seed=3):
    """Games where the market probability is exactly right, plus an optional
    TRUE spread effect the market has failed to price."""
    rng = np.random.default_rng(seed)
    spread = rng.uniform(0, 35, n)
    p_mkt = np.full(n, 0.5)
    z = np.log(p_mkt / (1 - p_mkt)) + true_coef * (spread - spread.mean())
    y = rng.random(n) < 1 / (1 + np.exp(-z))
    return pd.DataFrame(
        {
            "outcome_real": np.where(y, "under", "over"),
            "fair_under": p_mkt,
            "spread_abs": spread,
            "spread": -spread,
            "season": rng.choice([2023, 2024, 2025], n),
            "line_real": 24.5,
        }
    )


def test_gate_finds_a_real_effect_when_one_is_planted():
    """If this cannot detect a planted effect, a null result means nothing."""
    r = C.spread_residual(_synthetic(true_coef=0.04), n_boot=120)
    assert r["spread_coef"] > 0.02
    assert r["spread_excludes_zero"] is True


def test_gate_reports_no_effect_when_the_market_is_right():
    r = C.spread_residual(_synthetic(true_coef=0.0), n_boot=120)
    assert abs(r["spread_coef"]) < 0.01
    assert r["spread_excludes_zero"] is False
    assert r["market_level_unbiased"] is True


def test_gate_excludes_pushes_from_the_comparison():
    """A de-vigged price carries no push mass, so pushes must not sit in the
    denominator of the rate it is compared against."""
    d = _synthetic(n=400)
    d.loc[d.index[:40], "outcome_real"] = "push"
    r = C.spread_residual(d, n_boot=40)
    assert r["n"] == 360


# --- the decision rule -------------------------------------------------------


def _gate(coef, lo, hi, swing):
    return {
        "spread_coef": coef,
        "spread_ci": [lo, hi],
        "spread_excludes_zero": not (lo <= 0 <= hi),
        "swing_pp_7_to_28": swing,
        "clears_vig": abs(swing) > C.VIG_HURDLE_PP,
        "vig_hurdle_pp": C.VIG_HURDLE_PP,
    }


def _seasons(*coefs):
    return [{"season": 2023 + i, "n": 600, "spread_coef": c} for i, c in enumerate(coefs)]


def test_build_requires_significance_stability_AND_economic_size():
    ok = C.verdict(_gate(0.05, 0.03, 0.07, 8.0), _seasons(0.04, 0.05, 0.06), {})
    assert ok["build"] is True and ok["reasons"] == []

    # Significant and stable, but too small to pay the vig.
    small = C.verdict(_gate(0.004, 0.002, 0.006, 1.9), _seasons(0.003, 0.004, 0.005), {})
    assert small["build"] is False
    assert any("vig hurdle" in r for r in small["reasons"])

    # Big and significant, but the sign flips season to season.
    flip = C.verdict(_gate(0.05, 0.03, 0.07, 8.0), _seasons(0.09, -0.04, 0.08), {})
    assert flip["build"] is False
    assert flip["sign_stable_across_seasons"] is False

    # The interval includes zero.
    null = C.verdict(_gate(0.004, -0.008, 0.016, 1.9), _seasons(0.006, -0.004, 0.009), {})
    assert null["build"] is False
    assert any("includes zero" in r for r in null["reasons"])


def test_test1_is_never_allowed_to_authorize_a_build():
    """Test 1 does not measure market pricing, so it is not an input to the
    decision at all -- verdict() does not even take it as an argument. This
    pins that, because 'huge censoring therefore build' is the exact inference
    the first draft of this plan made and had to retract."""
    import inspect

    assert "zero_mass" not in inspect.signature(C.verdict).parameters
    assert set(inspect.signature(C.verdict).parameters) == {"gate", "seasons", "wf"}


# --- mechanism ---------------------------------------------------------------


def test_zero_mass_identifies_the_dog_by_spread_sign():
    """spread is home-relative and negative means the HOME team is favoured;
    getting this backwards inverts the whole table."""
    df = pd.DataFrame(
        {
            "spread": [-20.0, 20.0],  # home favoured, then away favoured
            "spread_abs": [20.0, 20.0],
            "home_fh": [21.0, 0.0],
            "away_fh": [0.0, 21.0],
        }
    )
    got = C.zero_mass_by_bucket(df)
    assert len(got) == 1
    assert got[0]["dog_shutout_pct"] == pytest.approx(100.0)
    assert got[0]["fav_shutout_pct"] == pytest.approx(0.0)
    assert got[0]["dog_mean"] == pytest.approx(0.0)
    assert got[0]["fav_mean"] == pytest.approx(21.0)
