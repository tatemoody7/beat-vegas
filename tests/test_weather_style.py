"""Weather x style: leak-free as-of style, the bucket table, the offset logistic
and the pre-registered decision rule."""

import numpy as np
import pandas as pd
import pytest

from beatvegas.backtest import weather_style as W


def test_style_as_of_uses_only_prior_weeks_of_the_same_season():
    fh = pd.DataFrame(
        [
            {"season": 2025, "week": 1, "off_team": "Kansas", "pass_rate": 0.60, "explosive": 0.10},
            {"season": 2025, "week": 2, "off_team": "Kansas", "pass_rate": 0.40, "explosive": 0.20},
            {
                "season": 2025,
                "week": 3,
                "off_team": "Kansas",
                "pass_rate": 0.90,
                "explosive": 0.90,
            },  # the game itself: excluded
            {
                "season": 2024,
                "week": 9,
                "off_team": "Kansas",
                "pass_rate": 0.99,
                "explosive": 0.99,
            },  # last season: excluded
        ]
    )
    s = W.style_as_of(fh, 2025, 3, "Kansas")
    assert (
        s["pass_rate"] == pytest.approx(0.50)
        and s["explosive"] == pytest.approx(0.15)
        and s["n_prior"] == 2
    )
    assert W.style_as_of(fh, 2025, 1, "Kansas")["pass_rate"] is None


def test_attach_style_averages_both_offences_and_needs_both():
    fh = pd.DataFrame(
        [
            {"season": 2025, "week": 1, "off_team": "A", "pass_rate": 0.7, "explosive": 0.1},
            {"season": 2025, "week": 1, "off_team": "B", "pass_rate": 0.3, "explosive": 0.3},
        ]
    )
    games = pd.DataFrame(
        [
            {"season": 2025, "week": 2, "home_team": "A", "away_team": "B"},
            {"season": 2025, "week": 2, "home_team": "A", "away_team": "C"},  # C has no prior game
        ]
    )
    out = W.attach_style(games, fh)
    assert out["pass_rate_asof"].tolist()[0] == pytest.approx(0.5)
    assert pd.isna(out["pass_rate_asof"].tolist()[1])


def test_gust_bands_and_bucket_table_exclude_pushes():
    assert [W.gust_band(g) for g in (0, 9.9, 10, 19.9, 25, 40, None)] == [
        "< 10",
        "< 10",
        "10–15",
        "15–20",
        "25+",
        "25+",
        None,
    ]
    df = pd.DataFrame(
        {
            "gust": [5, 5, 5, 22, 22, 22],
            "pass_heavy": [1, 1, 1, 0, 0, 0],
            "outcome": ["under", "over", "push", "under", "under", "over"],
            "fair_under": [0.5] * 6,
        }
    )
    rows = {(b["style"], b["band"]): b for b in W.buckets(df)}
    ph = rows[("pass-heavy", "< 10")]
    assert ph["n"] == 2 and ph["realized_under"] == 0.5 and ph["diff_pp"] == pytest.approx(0.0)
    ot = rows[("other", "20–25")]
    assert (
        ot["n"] == 3
        and ot["realized_under"] == pytest.approx(2 / 3)
        and ot["diff_pp"] == pytest.approx(100 * (2 / 3 - 0.5))
    )


def test_interaction_fit_recovers_a_planted_interaction():
    rng = np.random.default_rng(3)
    n = 6000
    gust = rng.gamma(4, 4, n)  # mean ~16 mph
    ph = rng.integers(0, 2, n)
    fair = np.clip(rng.normal(0.5, 0.02, n), 0.4, 0.6)
    eta = np.log(fair / (1 - fair)) + 0.0 * gust / 5 + 0.0 * ph + 0.25 * (gust / 5) * ph
    y = np.where(rng.random(n) < 1 / (1 + np.exp(-eta)), "under", "over")
    df = pd.DataFrame(
        {"gust": gust, "pass_heavy": ph, "fair_under": fair, "outcome": y, "season": 2025}
    )
    f = W.interaction_fit(df, n_boot=100)
    assert f["coef"]["gust_x_pass_heavy"] == pytest.approx(0.25, abs=0.08)
    assert f["ci"]["gust_x_pass_heavy"][0] > 0
    assert f["swing_pp_pass_heavy_p10_to_p90_gust"] > W.VIG_HURDLE_PP


def test_verdict_is_the_pre_registered_rule():
    good = {
        "coef": {"gust_x_pass_heavy": 0.2},
        "ci": {"gust_x_pass_heavy": (0.05, 0.35)},
        "swing_pp_pass_heavy_p10_to_p90_gust": 6.0,
    }
    seasons = [{"coef": {"gust_x_pass_heavy": 0.2}}, {"coef": {"gust_x_pass_heavy": 0.1}}]
    assert W.verdict(good, seasons)["signal"] is True
    ci_zero = dict(good, ci={"gust_x_pass_heavy": (-0.05, 0.35)})
    v = W.verdict(ci_zero, seasons)
    assert v["signal"] is False and any("includes zero" in r for r in v["reasons"])
    flip = W.verdict(
        good, [{"coef": {"gust_x_pass_heavy": 0.2}}, {"coef": {"gust_x_pass_heavy": -0.1}}]
    )
    assert flip["signal"] is False and any("changes sign" in r for r in flip["reasons"])
    small = dict(good, swing_pp_pass_heavy_p10_to_p90_gust=1.0)
    v = W.verdict(small, seasons)
    assert v["signal"] is False and any("hurdle" in r for r in v["reasons"])


def test_flag_pass_heavy_is_the_top_third():
    df = pd.DataFrame({"pass_rate_asof": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]})
    out = W.flag_pass_heavy(df)
    assert out["pass_heavy"].sum() == 2 and out.attrs["pass_heavy_cut"] == pytest.approx(0.4333, abs=1e-3)
