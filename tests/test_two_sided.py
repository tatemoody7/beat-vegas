"""The two-sided diagnostic: bands, follow-the-sign units, symmetry, and the
pre-registered decision rule -- pinned so it cannot be tuned to the numbers."""

import numpy as np
import pandas as pd
import pytest

from beatvegas.backtest import two_sided as T


def test_band_edges_mirror_the_under_ladder():
    assert T.band_of(-3.0) == "<= -3"
    assert T.band_of(-2.99) == "-3 .. -1.75"
    assert T.band_of(-1.75) == "-3 .. -1.75"
    assert T.band_of(-1.74) == "-1.75 .. -1"
    assert T.band_of(-0.5) == "-1 .. 0"
    assert T.band_of(0.0) == "0 .. 1"
    assert T.band_of(1.75) == "1.75 .. 3"
    assert T.band_of(3.0) == ">= 3"
    assert T.band_of(None) is None and T.band_of(float("nan")) is None


def test_follow_sign_units_bets_the_side_the_gap_points_to():
    assert T.follow_sign_units(2.0, "under") == pytest.approx(100 / 110)
    assert T.follow_sign_units(2.0, "over") == -1.0
    assert T.follow_sign_units(-2.0, "over") == pytest.approx(100 / 110)
    assert T.follow_sign_units(-2.0, "under") == -1.0
    assert T.follow_sign_units(-2.0, "push") == 0.0
    assert T.follow_sign_units(0.0, "under") == 0.0


def _frame(
    neg_over: int, neg_under: int, pos_under: int, pos_over: int, seasons=(2023, 2024, 2025)
):
    rows = []
    k = 0
    for _i in range(neg_over):
        rows.append({"gap": -2.5, "outcome": "over", "season": seasons[k % 3], "week": 5})
        k += 1
    for _i in range(neg_under):
        rows.append({"gap": -2.5, "outcome": "under", "season": seasons[k % 3], "week": 5})
        k += 1
    for _i in range(pos_under):
        rows.append({"gap": 2.5, "outcome": "under", "season": seasons[k % 3], "week": 9})
        k += 1
    for _i in range(pos_over):
        rows.append({"gap": 2.5, "outcome": "over", "season": seasons[k % 3], "week": 9})
        k += 1
    rows.append({"gap": 2.5, "outcome": "push", "season": 2023, "week": 9})
    return pd.DataFrame(rows)


def test_ladder_counts_and_excludes_pushes_from_the_rate():
    df = _frame(60, 40, 55, 45)
    rows = {r["band"]: r for r in T.ladder(df, "gap", "outcome")}
    b = rows["1.75 .. 3"]
    assert (b["under"], b["over"], b["push"], b["n"]) == (55, 45, 1, 101)
    assert b["under_rate"] == pytest.approx(0.55)
    assert b["side"] == "under" and b["side_rate"] == pytest.approx(0.55)
    assert b["units_follow_sign"] == pytest.approx(55 * 100 / 110 - 45)
    n = rows["-3 .. -1.75"]
    assert n["side"] == "over" and n["side_rate"] == pytest.approx(0.60)
    assert n["units_follow_sign"] == pytest.approx(60 * 100 / 110 - 40)
    assert rows["<= -3"]["n"] == 0 and rows["<= -3"]["under_rate"] is None


def test_symmetry_reads_over_on_the_left_and_under_on_the_right():
    s = T.symmetry(_frame(60, 40, 55, 45), "gap", "outcome")
    assert s["neg_n"] == 100 and s["neg_over_rate"] == pytest.approx(0.60)
    assert s["pos_n"] == 100 and s["pos_under_rate"] == pytest.approx(0.55)
    assert s["neg_over_ci"][0] < 0.60 < s["neg_over_ci"][1]


def test_verdict_is_the_pre_registered_rule():
    # Strong, replicated, well-powered over signal -> detected.
    strong = _frame(180, 100, 150, 130)
    s = T.symmetry(strong, "gap", "outcome")
    seasons = T.per_group(strong, "gap", "outcome", "season")
    assert T.verdict(s, seasons)["over_side_signal"] is True
    # The same rate on too few games -> not a finding (n < 100).
    small = _frame(18, 10, 15, 13)
    v = T.verdict(
        T.symmetry(small, "gap", "outcome"), T.per_group(small, "gap", "outcome", "season")
    )
    assert v["over_side_signal"] is False and any("needs 100" in r for r in v["reasons"])
    # Beats break-even in the point estimate but the Wilson lower bound spans a coin flip.
    thin = _frame(56, 48, 60, 50)
    v = T.verdict(T.symmetry(thin, "gap", "outcome"), T.per_group(thin, "gap", "outcome", "season"))
    assert v["over_side_signal"] is False and any("coin flip" in r for r in v["reasons"])


def test_verdict_needs_the_sign_in_two_of_three_seasons():
    # 2023 carries all the overs; 2024 and 2025 lean under on negative gaps.
    rows = [{"gap": -2.5, "outcome": "over", "season": 2023, "week": 5}] * 150
    rows += [{"gap": -2.5, "outcome": "under", "season": 2024, "week": 5}] * 30
    rows += [{"gap": -2.5, "outcome": "under", "season": 2025, "week": 5}] * 30
    rows += [{"gap": -2.5, "outcome": "over", "season": 2024, "week": 5}] * 20
    rows += [{"gap": -2.5, "outcome": "over", "season": 2025, "week": 5}] * 20
    df = pd.DataFrame(rows)
    v = T.verdict(T.symmetry(df, "gap", "outcome"), T.per_group(df, "gap", "outcome", "season"))
    assert v["over_side_signal"] is False
    assert any("of 3 seasons" in r for r in v["reasons"])


def test_gap_slope_recovers_a_planted_relationship():
    rng = np.random.default_rng(1)
    gap = rng.normal(0, 2.5, 3000)
    p = 1 / (1 + np.exp(-(0.15 * gap)))
    y = np.where(rng.random(3000) < p, "under", "over")
    g = T.gap_slope(pd.DataFrame({"gap": gap, "outcome": y}), "gap", "outcome", n_boot=100)
    assert g["slope"] == pytest.approx(0.15, abs=0.05)
    assert g["slope_ci"][0] < 0.15 < g["slope_ci"][1]
    assert g["n_negative"] + g["n_positive"] == 3000


def test_week_band_edges():
    assert [T.week_band(w) for w in (1, 2, 3, 4, 5, 8, 9, 12, 13, None)] == [
        "w1-2",
        "w1-2",
        "w3-4",
        "w3-4",
        "w5-8",
        "w5-8",
        "w9-12",
        "w9-12",
        "w13+",
        None,
    ]


def test_render_markdown_smoke():
    df = _frame(60, 40, 55, 45)
    df["week_band"] = df["week"].map(T.week_band)
    sym = T.symmetry(df, "gap", "outcome")
    seasons = T.per_group(df, "gap", "outcome", "season")
    r = {
        "hist_scope": "h",
        "live_scope": "l",
        "hist_n": len(df),
        "live_n": len(df),
        "hist_ladder": T.ladder(df, "gap", "outcome"),
        "hist_symmetry": sym,
        "hist_per_season": seasons,
        "hist_per_week_band": T.per_group(df, "gap", "outcome", "week_band"),
        "hist_slope": T.gap_slope(df, "gap", "outcome", n_boot=20),
        "live_ladder": T.ladder(df, "gap", "outcome"),
        "live_symmetry": sym,
        "verdict": T.verdict(sym, seasons),
        "generated_at": "now",
    }
    md = T.render_markdown(r)
    assert "## Verdict:" in md and "PRE-REGISTERED" in md and "| 1.75 .. 3 |" in md
