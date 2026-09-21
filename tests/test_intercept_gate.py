"""H-INTERCEPT's gate: the arithmetic, and the rule applied as registered.

The properties that matter are structural rather than statistical -- every arm
is a constant shift of one fitted model, so lambda=1 must BE the incumbent and
the arms must differ by exactly (lambda - 1) * c. The third block pins the fact
that killed the row: a season whose training window holds no scorable fold gets
an intercept of 0, every arm coincides, and the criterion's every-season clause
cannot be met there for a reason about the test rather than the intercept.
"""

import numpy as np
import pandas as pd
import pytest

from beatvegas.backtest.intercept import (
    INCUMBENT_LAMBDA,
    LAMBDA_GRID,
    STRUCTURAL_TIE,
    _abs_bias_ci,
    _verdict,
    evaluate,
    render_markdown,
    season_predictions,
)
from beatvegas.etl.features import FEATURE_COLS, training_frame
from beatvegas.model.bv_line import bv_line_for_slate

# 600 a season so the nested walk-forward inside bias_corrections clears
# oof_residuals' min_train of 500: with 2023-25 in the window, 2024 and 2025 are
# both scorable, which is the live board's shape. 2024 as a test season has only
# 2023 behind it and is therefore the degenerate case, deliberately.
PER_SEASON = 600
SEASONS = (2023, 2024, 2025, 2026)
SHIFT = {2023: 0.0, 2024: 1.5, 2025: -2.0, 2026: 2.5}


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
            row["week"] = 1 + (i % 12)
            row["id"] = gid
            row["under"] = 0
            gid += 1
            rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def frame():
    return _frame()


def test_the_declared_grid_is_the_one_in_the_registry():
    assert tuple(LAMBDA_GRID) == (0.0, 0.25, 0.5, 0.75, 1.0)
    assert INCUMBENT_LAMBDA in LAMBDA_GRID


def test_lambda_one_reproduces_the_live_bv_line(frame):
    """The incumbent is an ARM, not a re-implementation that might drift."""
    played = training_frame(frame)
    train = played[played["season"] < 2026]
    test = played[played["season"] == 2026]
    live = np.asarray(bv_line_for_slate(train, test), dtype=float)

    res = evaluate(frame, test_seasons=[2026], grid=[0.0, 1.0])
    arm = res.per_game.sort_values("id")["pred_l1.0"].to_numpy()
    expected = pd.DataFrame({"id": test["id"].to_numpy(), "p": live}).sort_values("id")["p"]
    np.testing.assert_allclose(arm, expected.to_numpy(), rtol=0, atol=1e-9)


def test_arms_differ_from_the_incumbent_by_exactly_lambda_times_the_intercept(frame):
    res = evaluate(frame, test_seasons=[2026], grid=list(LAMBDA_GRID))
    pg = res.per_game
    c = float(pg["intercept"].iloc[0])
    assert abs(c) > 1e-6, "2026 must have a real intercept for this assertion to mean anything"
    for lam in LAMBDA_GRID:
        diff = pg[f"pred_l{lam}"] - pg[f"pred_l{INCUMBENT_LAMBDA}"]
        np.testing.assert_allclose(diff.to_numpy(), (lam - INCUMBENT_LAMBDA) * c, atol=1e-9)


def test_a_constant_shift_cannot_reorder_the_board(frame):
    """Why a level deficit breaks the threshold and not the ranking."""
    res = evaluate(frame, test_seasons=[2026], grid=[0.0, 1.0])
    pg = res.per_game
    assert list(pg.sort_values("pred_l0.0")["id"]) == list(pg.sort_values("pred_l1.0")["id"])


def test_2024_has_no_scorable_fold_so_every_arm_coincides(frame):
    """The blocker that has nothing to do with the intercept."""
    f = season_predictions(frame, 2024)
    assert f["intercept"] == 0.0

    res = evaluate(frame, test_seasons=[2024, 2026], grid=list(LAMBDA_GRID))
    meta = {s["season"]: s for s in res.report["seasons"]}
    assert meta[2024]["degenerate"] is True
    assert meta[2026]["degenerate"] is False

    for arm in res.report["arms"]:
        s24 = arm["seasons"]["2024"]
        assert s24["vs_incumbent"]["lo"] == 0.0 and s24["vs_incumbent"]["hi"] == 0.0
        assert s24["vs_incumbent"]["excludes_zero"] is False
        assert arm["verdict"]["adopt"] is False

    challenger = next(a for a in res.report["arms"] if not a["is_incumbent"])
    assert STRUCTURAL_TIE in challenger["verdict"]["why"]
    md = render_markdown(res.report)
    assert STRUCTURAL_TIE in md
    assert "no scorable fold" in md


def test_abs_bias_ci_is_zero_width_when_the_shifts_match():
    raw = np.array([20.0, 25.0, 30.0, 35.0])
    actual = np.array([22.0, 24.0, 31.0, 33.0])
    ci = _abs_bias_ci(raw, actual, 0.0, 0.0)
    assert ci["lo"] == 0.0 and ci["hi"] == 0.0 and ci["excludes_zero"] is False


def test_abs_bias_ci_is_deterministic_and_signs_toward_the_better_arm():
    rng = np.random.default_rng(3)
    actual = rng.normal(28, 10, 400)
    raw = actual - 3.0 + rng.normal(0, 1, 400)  # the model reads 3 points LOW
    # The incumbent shifts it further down; the challenger leaves it alone.
    ci = _abs_bias_ci(raw, actual, 0.0, -2.0)
    assert ci["mean"] < 0 and ci["hi"] < 0 and ci["excludes_zero"] is True
    assert ci == _abs_bias_ci(raw, actual, 0.0, -2.0)


def _arm(lam, biases, cis=None, incumbent=False):
    return {
        "lambda": lam,
        "is_incumbent": incumbent,
        "mean_abs_bias": float(np.mean([abs(b) for b in biases.values()])),
        "worst_abs_bias": float(max(abs(b) for b in biases.values())),
        "seasons": {
            s: {
                "abs_bias": abs(b),
                "degenerate": False,
                "vs_incumbent": (cis or {}).get(s),
            }
            for s, b in biases.items()
        },
    }


_WINS = {"n": 10, "mean": -0.5, "lo": -0.9, "hi": -0.1, "excludes_zero": True}
_TIES = {"n": 10, "mean": 0.0, "lo": -0.4, "hi": 0.4, "excludes_zero": False}


def test_verdict_refuses_an_arm_that_wins_the_aggregates_but_ties_a_season():
    """Mean and worst are not sufficient: the registered rule needs every season."""
    inc = _arm(1.0, {"2024": 1.0, "2025": 1.0, "2026": 3.0}, incumbent=True)
    challenger = _arm(
        0.0,
        {"2024": 0.5, "2025": 0.5, "2026": 1.0},
        {"2024": _WINS, "2025": _TIES, "2026": _WINS},
    )
    v = _verdict(challenger, inc)
    assert v["beats_mean"] and v["beats_worst"]
    assert v["every_season"] is False
    assert v["adopt"] is False
    assert "does not exclude zero" in v["why"]


def test_verdict_adopts_only_when_all_three_conditions_hold():
    inc = _arm(1.0, {"2024": 1.0, "2025": 1.0, "2026": 3.0}, incumbent=True)
    challenger = _arm(
        0.0,
        {"2024": 0.5, "2025": 0.5, "2026": 1.0},
        {"2024": _WINS, "2025": _WINS, "2026": _WINS},
    )
    assert _verdict(challenger, inc)["adopt"] is True


def test_verdict_refuses_an_arm_that_loses_the_worst_season():
    inc = _arm(1.0, {"2024": 1.0, "2025": 1.0, "2026": 1.0}, incumbent=True)
    challenger = _arm(
        0.0,
        {"2024": 0.1, "2025": 0.1, "2026": 2.0},
        {"2024": _WINS, "2025": _WINS, "2026": _WINS},
    )
    v = _verdict(challenger, inc)
    assert v["beats_mean"] is True and v["beats_worst"] is False
    assert v["adopt"] is False


def test_the_incumbent_arm_is_never_adopted(frame):
    res = evaluate(frame, test_seasons=[2026], grid=list(LAMBDA_GRID))
    inc = next(a for a in res.report["arms"] if a["is_incumbent"])
    assert inc["verdict"]["adopt"] is False
    assert "incumbent" in inc["verdict"]["why"]


def test_grid_without_the_incumbent_is_refused(frame):
    with pytest.raises(ValueError, match="incumbent"):
        evaluate(frame, test_seasons=[2026], grid=[0.0, 0.5])


def test_a_constant_shift_gives_a_zero_width_interval_and_says_so():
    """The clause "CI excludes zero" is near-vacuous against a constant shift.

    Both arms differ by a fixed amount, so while a resampled bias keeps its sign
    the difference of absolute means is that same amount every time. Width only
    appears where a resample can cross zero bias.
    """
    rng = np.random.default_rng(5)
    actual = rng.normal(28, 10, 500)
    raw = actual + 4.0 + rng.normal(0, 1, 500)  # bias comfortably away from zero
    ci = _abs_bias_ci(raw, actual, 0.0, -1.0)
    assert ci["deterministic"] is True
    assert ci["hi"] - ci["lo"] < 1e-9
    assert ci["excludes_zero"] is True  # satisfied by construction, not by evidence

    # A bias sitting ON zero is the case where resamples straddle and width appears.
    near_zero = actual + rng.normal(0, 1, 500)
    wide = _abs_bias_ci(near_zero, actual, 0.0, -1.0)
    assert wide["deterministic"] is False
    assert wide["hi"] - wide["lo"] > 1e-6


def test_the_zero_width_caveat_reaches_the_report(frame):
    res = evaluate(frame, test_seasons=[2025, 2026], grid=[0.0, 1.0])
    md = render_markdown(res.report)
    assert "ZERO WIDTH" in md
    assert "close to vacuous" in md
