"""H-INSEASON's gate: the estimator, the as-of rule, and the frozen criterion.

The properties worth pinning are the ones a careless edit would break silently:
the arm must reduce to the incumbent when the season has told it nothing, the
blend must never see a game at or after the one it is scoring, and `c_season`
must come from the RAW prediction -- deriving it from a calibrated one would
re-apply `c_prior` scaled by w, which no number in the report would reveal.
"""

import numpy as np
import pandas as pd
import pytest

from beatvegas.backtest.inseason import (
    INCUMBENT,
    K_GRID,
    _verdict,
    evaluate,
    in_season_shift,
    render_markdown,
    season_fit,
)
from beatvegas.etl.features import FEATURE_COLS, training_frame
from beatvegas.model.bv_line import bv_line_for_slate

# 600 a season so the nested walk-forward inside bias_corrections clears
# oof_residuals' min_train of 500, which is the live board's shape. 2024 as a
# test season has only 2023 behind it, so its c_prior is 0 and its arms are
# in-season ONLY -- kept deliberately, because that is the case H-INTERCEPT
# could not evaluate at all.
PER_SEASON = 600
SEASONS = (2023, 2024, 2025, 2026)
SHIFT = {2023: 0.0, 2024: 1.5, 2025: -2.0, 2026: 2.5}
WEEKS = 12


def _frame(seed=11):
    rng = np.random.default_rng(seed)
    rows = []
    gid = 0
    for s in SEASONS:
        for i in range(PER_SEASON):
            row = {c: 0.0 for c in FEATURE_COLS}
            x1, x2 = rng.normal(0, 1), rng.normal(0, 1)
            row["combined_off_ppa"] = x1
            row["combined_def_ppa"] = x2
            row["combined_sec_play"] = rng.uniform(20, 32)
            row["era_post2023"] = 1.0 if s >= 2023 else 0.0
            row["first_half_total"] = 24 + 3 * x1 - 2 * x2 + SHIFT[s] + rng.normal(0, 1.5)
            row["season"] = s
            row["week"] = 1 + (i % WEEKS)
            row["id"] = gid
            row["under"] = 0
            gid += 1
            rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def frame():
    return _frame()


def test_the_declared_grid_is_the_one_in_the_registry():
    assert tuple(K_GRID) == (25.0, 50.0, 100.0, 200.0)


def test_week_one_is_the_incumbent_exactly():
    """n=0 means w=0: the season has told the arm nothing, so it must not move."""
    week = np.array([1.0, 1.0, 2.0, 2.0])
    raw = np.array([20.0, 22.0, 24.0, 26.0])
    actual = np.array([25.0, 27.0, 29.0, 31.0])
    out = in_season_shift(week, raw, actual, c_prior=-1.8, k=50.0)
    assert out["n_seen"][0] == 0 and out["weight"][0] == 0.0
    assert out["shift"][0] == pytest.approx(-1.8)
    assert out["shift"][1] == pytest.approx(-1.8)


def test_the_window_closes_strictly_before_the_week_being_scored():
    """No game may contribute to its own intercept, nor a later one to an earlier."""
    week = np.array([1.0, 1.0, 2.0, 3.0])
    raw = np.array([20.0, 20.0, 20.0, 20.0])
    actual = np.array([25.0, 25.0, 100.0, 30.0])  # week 2 is an extreme outlier
    out = in_season_shift(week, raw, actual, c_prior=0.0, k=1.0)
    # Week 2's own 80-point error must not touch week 2's shift.
    assert out["n_seen"][2] == 2
    assert out["shift"][2] == pytest.approx((2 / 3) * 5.0)
    # Week 3 sees weeks 1-2, including that outlier.
    assert out["n_seen"][3] == 3
    assert out["shift"][3] == pytest.approx((3 / 4) * ((5 + 5 + 80) / 3))


def test_c_season_comes_from_the_raw_prediction_not_a_calibrated_one():
    """The one arithmetic mistake this design can make, pinned.

    With c_prior non-zero and w=1, the shift must be the RAW residual mean. If
    c_season were computed from `raw + c_prior`, it would come back reduced by
    c_prior and the total would double-count.
    """
    week = np.array([1.0, 2.0])
    raw = np.array([20.0, 20.0])
    actual = np.array([30.0, 30.0])
    # k tiny -> w = 1/(1+k) ~ 1 on week 2, which has seen exactly one game.
    out = in_season_shift(week, raw, actual, c_prior=-5.0, k=1e-9)
    assert out["shift"][1] == pytest.approx(10.0, abs=1e-6)  # the raw residual, not 15.0


def test_the_incumbent_arm_reproduces_the_live_bv_line(frame):
    played = training_frame(frame)
    train = played[played["season"] < 2026]
    test = played[played["season"] == 2026]
    live = pd.DataFrame(
        {"id": test["id"].to_numpy(), "p": np.asarray(bv_line_for_slate(train, test), float)}
    ).sort_values("id")

    res = evaluate(frame, test_seasons=[2026], grid=[50.0], n_boot=200)
    got = res.per_game.sort_values("id")["pred_incumbent"].to_numpy()
    np.testing.assert_allclose(got, live["p"].to_numpy(), rtol=0, atol=1e-9)


def test_a_larger_k_trusts_the_season_less(frame):
    res = evaluate(frame, test_seasons=[2026], grid=[25.0, 200.0], n_boot=200)
    w25 = res.per_game["w_k25"].mean()
    w200 = res.per_game["w_k200"].mean()
    assert 0 < w200 < w25 < 1


def test_2024_has_no_prior_fold_so_its_arms_are_in_season_only(frame):
    """The season H-INTERCEPT could not evaluate is evaluable here."""
    f = season_fit(frame, 2024)
    assert f["c_prior"] == 0.0

    res = evaluate(frame, test_seasons=[2024, 2026], grid=[50.0], n_boot=200)
    arm = next(a for a in res.report["arms"] if not a["is_incumbent"])
    # Unlike H-INTERCEPT, the arms genuinely differ from the incumbent on 2024.
    assert arm["seasons"]["2024"]["bias"] != pytest.approx(
        next(a for a in res.report["arms"] if a["is_incumbent"])["seasons"]["2024"]["bias"]
    )
    assert any("IN-SEASON ONLY" in c for c in res.report["caveats"])


def test_the_estimator_removes_a_level_shift_it_can_see(frame):
    """A sanity check on direction, not an adoption claim.

    2026 carries a +2.5 level shift the training seasons never saw, so the
    incumbent must read low there and an arm that reads the season's own games
    must read less low.
    """
    res = evaluate(frame, test_seasons=[2026], grid=[25.0], n_boot=200)
    inc = next(a for a in res.report["arms"] if a["is_incumbent"])
    arm = next(a for a in res.report["arms"] if not a["is_incumbent"])
    assert arm["seasons"]["2026"]["abs_bias"] < inc["seasons"]["2026"]["abs_bias"]


def test_bootstrap_is_deterministic_under_the_seed(frame):
    a = evaluate(frame, test_seasons=[2026], grid=[50.0], n_boot=200).report
    b = evaluate(frame, test_seasons=[2026], grid=[50.0], n_boot=200).report
    assert a["arms"][0]["aggregate"] == b["arms"][0]["aggregate"]


def _agg(diff, lo, hi, p):
    return {
        "arm": 1.0,
        "incumbent": 1.0 - diff,
        "diff": diff,
        "lo": lo,
        "hi": hi,
        "below_zero": hi < 0,
        "p": p,
    }


def _arm(mean_ci, worst_ci, season_cis, holm_rejects=True):
    return {
        "k": 50.0,
        "label": "k50",
        "is_incumbent": False,
        "mean_abs_bias": 1.0,
        "worst_abs_bias": 1.0,
        "aggregate": {"mean_abs_bias": mean_ci, "worst_abs_bias": worst_ci},
        "seasons": {
            s: {"vs_incumbent": {"mean": v[0], "lo": v[1], "hi": v[2], "worse": v[1] > 0}}
            for s, v in season_cis.items()
        },
        "holm": {"p_raw": 0.01, "p_adjusted": 0.02, "rejects": holm_rejects},
    }


_GOOD = _agg(-0.5, -0.9, -0.1, 0.01)
_STRADDLES = _agg(-0.5, -0.9, +0.2, 0.30)
_TIE = (-0.05, -0.4, +0.3)
_WORSE = (+0.5, +0.2, +0.9)
_BETTER = (-0.5, -0.9, -0.1)


def test_verdict_adopts_when_every_clause_holds():
    arm = _arm(_GOOD, _GOOD, {"2024": _BETTER, "2025": _TIE, "2026": _BETTER})
    v = _verdict(arm)
    # A TIE does not block: that is the clause H-INTERCEPT died on, relaxed here.
    assert v["non_inferior_every_season"] is True
    assert v["adopt"] is True


def test_verdict_refuses_when_a_season_is_entirely_worse():
    arm = _arm(_GOOD, _GOOD, {"2024": _BETTER, "2025": _WORSE, "2026": _BETTER})
    v = _verdict(arm)
    assert v["non_inferior_every_season"] is False and v["adopt"] is False
    assert "entirely above zero" in v["why"]


def test_verdict_refuses_when_an_aggregate_interval_straddles_zero():
    arm = _arm(_GOOD, _STRADDLES, {"2024": _BETTER, "2025": _BETTER, "2026": _BETTER})
    v = _verdict(arm)
    assert v["beats_mean"] is True and v["beats_worst"] is False and v["adopt"] is False


def test_verdict_refuses_when_holm_does_not_reject():
    arm = _arm(
        _GOOD, _GOOD, {"2024": _BETTER, "2025": _BETTER, "2026": _BETTER}, holm_rejects=False
    )
    v = _verdict(arm)
    assert v["adopt"] is False and "Holm" in v["why"]


def test_holm_input_is_the_weaker_of_the_two_required_tests(frame):
    """An arm is only as strong as its weaker required component."""
    res = evaluate(frame, test_seasons=[2025, 2026], grid=[25.0, 200.0], n_boot=200)
    for arm in res.report["arms"]:
        if arm["is_incumbent"]:
            continue
        ps = [arm["aggregate"][n]["p"] for n in ("mean_abs_bias", "worst_abs_bias")]
        assert arm["holm"]["p_raw"] == pytest.approx(max(ps))


def test_the_report_states_the_as_of_rule_and_the_limitation(frame):
    res = evaluate(frame, test_seasons=[2026], grid=[50.0], n_boot=200)
    md = render_markdown(res.report)
    assert "weeks < w" in md
    assert "BETWEEN-season variation" in md
    assert "DEVELOPMENT EVIDENCE" in md
    assert "own registry row and its own clock" in md


def test_a_nonpositive_k_is_refused(frame):
    with pytest.raises(ValueError, match="positive"):
        evaluate(frame, test_seasons=[2026], grid=[0.0], n_boot=50)


def test_incumbent_is_never_adopted(frame):
    res = evaluate(frame, test_seasons=[2026], grid=[50.0], n_boot=200)
    inc = next(a for a in res.report["arms"] if a["is_incumbent"])
    assert inc["verdict"]["adopt"] is False and inc["holm"] is None


def test_the_incumbent_is_k_infinity_so_the_weight_is_zero_at_every_n():
    """Not a special case in the code: w = n/(n+inf) = 0 however much it has seen."""
    week = np.array([1.0, 2.0, 3.0])
    raw = np.array([20.0, 20.0, 20.0])
    actual = np.array([30.0, 30.0, 30.0])
    out = in_season_shift(week, raw, actual, c_prior=-1.8, k=INCUMBENT)
    assert np.all(out["weight"] == 0.0)
    np.testing.assert_allclose(out["shift"], -1.8)
