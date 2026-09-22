"""H-NEGGAP-L arithmetic (beatvegas/backtest/neggap_level.py). Measurement only;
these pin the sign of the arm gap, the band counting, the flips, and the anchor
build choice, so a later edit cannot quietly change what the row measures."""

from datetime import datetime, timedelta

import pytest

from beatvegas.backtest import neggap_level as N
from beatvegas.challenger import arm_label

T0 = datetime(2026, 9, 24, 20, 0)


def _item(gid, gap, hr_line=30.0, basis="hardrock"):
    return {
        "game_id": gid,
        "gap": gap,
        "gap_basis": basis,
        "hr_line": hr_line,
        "bv_line": hr_line - gap,
        "away": f"A{gid}",
        "home": f"H{gid}",
    }


def test_arm_gap_sign_a_more_negative_intercept_raises_the_gap():
    # champion applied -1.8; an arm applying -0.5 LIFTS its number by 1.3, so
    # its gap is 1.3 points smaller. An arm applying -3.0 lowers it and raises the gap.
    assert N.arm_gap(2.0, c_prior=-1.8, c_t=-0.5) == pytest.approx(0.7)
    assert N.arm_gap(2.0, c_prior=-1.8, c_t=-3.0) == pytest.approx(3.2)
    assert N.arm_gap(2.0, c_prior=-1.8, c_t=-1.8) == pytest.approx(2.0)


def test_outcome_against_hard_rocks_line():
    assert N.outcome(27, 30.5) == "under"
    assert N.outcome(31, 30.5) == "over"
    assert N.outcome(30, 30.0) == "push"
    assert N.outcome(None, 30.0) is None and N.outcome(20, None) is None


def test_arm_intercepts_without_context_measure_the_champion_only():
    cs = N.arm_intercepts(None)
    assert cs[N.CHAMPION] is None
    assert all(cs[arm_label(k)] is None for k in (25.0, 50.0, 100.0, 200.0))
    cs = N.arm_intercepts({"c_prior": -1.8, "c_season": 1.0, "in_season_n": 100})
    assert cs[N.CHAMPION] == -1.8
    # w = 100/125 = 0.8 at k=25: 0.2*-1.8 + 0.8*1.0 = 0.44
    assert cs["k25"] == pytest.approx(0.44)
    # n=0 is the champion on every arm
    cs0 = N.arm_intercepts({"c_prior": -1.8, "c_season": None, "in_season_n": 0})
    assert all(cs0[arm_label(k)] == -1.8 for k in (25.0, 50.0, 100.0, 200.0))


def test_band_counts_and_flips():
    build = {
        "built_at": T0,
        "slot": "fri_pm",
        "week": 4,
        "context": {"c_prior": -1.8, "c_season": 1.0, "in_season_n": 100},  # k25 -> +0.44
        "items": [
            _item(1, -0.5),  # champion negative; k25 gap = -0.5 - 2.24 = -2.74, still negative
            _item(2, 1.0),  # champion positive; k25 gap = -1.24 -> flips negative
            _item(3, 3.0),  # stays positive under every arm
            _item(4, -1.0, basis="market"),  # not Hard Rock priced: excluded
            _item(5, -2.0),  # ungraded: excluded
        ],
    }
    finals = {1: 34, 2: 35, 3: 20, 4: 35, 5: None}
    rows = N.game_rows(build, finals)
    assert [r["game_id"] for r in rows] == [1, 2, 3]
    champ = N.band_counts(rows, N.CHAMPION)
    assert (champ["n"], champ["over"], champ["under"]) == (1, 1, 0)
    k25 = N.band_counts(rows, "k25")
    assert (k25["n"], k25["over"], k25["under"]) == (2, 2, 0)
    assert k25["over_rate"] == 1.0 and k25["over_ci"][0] < 1.0
    fl = N.flips(rows, "k25")
    assert [f["game_id"] for f in fl] == [2]
    assert fl[0]["champion_gap"] == 1.0 and fl[0]["arm_gap"] == pytest.approx(-1.24)


def test_anchor_build_prefers_the_earliest_friday_with_context():
    ctx = {"c_prior": -1.8, "c_season": 0.0, "in_season_n": 10}
    tue = {"built_at": T0 - timedelta(days=3), "slot": "tue_pm", "items": [], "context": ctx}
    fri_a = {"built_at": T0, "slot": "fri_pm", "items": [], "context": ctx}
    fri_b = {"built_at": T0 + timedelta(hours=1), "slot": "fri_pm", "items": [], "context": ctx}
    sat = {"built_at": T0 + timedelta(hours=16), "slot": "sat_am", "items": [], "context": ctx}
    assert N.anchor_build([sat, fri_b, tue, fri_a]) is fri_a
    # no Friday with context: latest build WITH context
    fri_noctx = dict(fri_a, context=None)
    assert N.anchor_build([tue, fri_noctx]) is tue
    # no context anywhere: latest build, champion-only measurement
    assert N.anchor_build([dict(tue, context=None), fri_noctx]) is fri_noctx
    assert N.anchor_build([]) is None


def test_evaluate_reports_unmeasured_arms_when_no_build_has_context():
    weeks = {3: [{"built_at": T0, "slot": "fri_pm", "items": [_item(1, -1.0)], "context": None}]}
    r = N.evaluate(weeks, {1: 40})
    assert r["pooled"][N.CHAMPION]["n"] == 1 and r["pooled"][N.CHAMPION]["over"] == 1
    assert r["pooled"]["k25"]["measured"] is False
    md = N.render_markdown(r)
    assert "not measurable" in md and "None yet." in md
