"""The 2026 Statistical Protocol's test (beatvegas/protocol.py, docs/PROTOCOL_2026.md).

The observation is a week's mean line value; these tests pin the boundaries, the
week variance, the 30-readings / 3-weeks guard, every ending, and that the
vectorised simulator decides exactly as `position` does.
"""

from __future__ import annotations

import math
import random

import pytest

from beatvegas import protocol as P


def test_boundaries_and_the_ledger():
    assert P.ALPHA == pytest.approx(0.005)
    assert P.UPPER == pytest.approx(math.log(0.8 / 0.005))
    assert P.LOWER == pytest.approx(math.log(0.2 / 0.995))
    assert P.K_TESTS * P.ALPHA == pytest.approx(0.05)


def test_week_variance_adds_the_shared_move_to_the_bets_noise():
    assert P.week_variance(1) == pytest.approx(0.02**2 + 0.06**2)
    assert P.week_variance(9) == pytest.approx(0.02**2 + 0.06**2 / 9)
    # More bets in a week never shrink its variance below the shared move.
    assert P.week_variance(10_000) > 0.02**2


def test_llr_week_is_zero_at_the_midpoint_and_signed_by_side():
    assert P.llr_week(0.015, 10) == pytest.approx(0.0)
    assert P.llr_week(0.03, 10) > 0 > P.llr_week(0.0, 10)
    # A worked week: 10 bets averaging +0.03 -> 0.03 / (0.0004 + 0.00036) * 0.015.
    assert P.llr_week(0.03, 10) == pytest.approx(0.03 / 0.00076 * 0.015)


def test_weekly_groups_in_order_of_first_appearance():
    assert P.weekly([(6, 0.1), (7, 0.0), (6, 0.3)]) == [(6, 2, pytest.approx(0.2)), (7, 1, 0.0)]


def test_no_decision_before_thirty_readings_over_three_weeks():
    one_week = [(6, 0.30)] * 40  # strong, but a single week
    pos = P.position(one_week)
    assert pos.state == P.RUNNING and pos.weeks == 1 and not pos.can_decide
    two_weeks = [(6, 0.30)] * 20 + [(7, 0.30)] * 20
    assert P.position(two_weeks).state == P.RUNNING
    three = two_weeks + [(8, 0.30)] * 5
    pos = P.position(three)
    assert pos.state == P.PROMOTE and pos.decided_at_week == 8


def test_three_weeks_but_under_thirty_readings_waits():
    thin = [(w, 0.30) for w in (6, 7, 8) for _ in range(5)]  # 15 readings
    assert P.position(thin).state == P.RUNNING


def test_a_losing_arm_stops_as_needs_more_evidence():
    losing = [(w, -0.05) for w in (6, 7, 8) for _ in range(12)]
    pos = P.position(losing)
    assert pos.state == P.STOP and pos.decided_at_week == 8
    assert P.label(pos.state).startswith("NEEDS MORE EVIDENCE")


def test_timeouts_at_the_season_end_and_at_max_readings():
    flat = [(w, 0.015) for w in (6, 7) for _ in range(10)]
    assert P.position(flat).state == P.RUNNING
    assert P.position(flat, season_over=True).state == P.TIMEOUT
    # Exactly the midpoint every week: the LLR never moves, so MAX_OBS ends it.
    many = [(w, 0.015) for w in range(1, 30) for _ in range(10)]
    pos = P.position(many)
    assert pos.state == P.TIMEOUT and pos.n == P.MAX_OBS


def test_the_season_ends_at_the_final_read_by_the_clock():
    """p1.3 (roadmap v2.6, Tate 2026-10-18): the final read is Monday 2026-11-30 and the
    season is over from 12:00 UTC that day, deterministically; the last kickoff is before it."""
    from datetime import datetime

    assert P.PROTOCOL_VERSION == "p1.4"
    assert P.SEASON_LAST_KICKOFF == "2026-11-29T04:00:00" and P.FINAL_READ_DATE == "2026-11-30"
    assert P.SEASON_LAST_KICKOFF < P.FINAL_READ_AT == "2026-11-30T12:00:00"
    assert not P.season_over(datetime(2026, 11, 29, 4, 0))  # the last kickoff itself
    assert not P.season_over(datetime(2026, 11, 30, 11, 59, 59))
    assert P.season_over(datetime(2026, 11, 30, 12, 0, 0))
    assert P.season_over(datetime(2027, 1, 25, 12, 0))  # the read it replaced


def test_observations_from_rows_counts_exclusions():
    class R:
        def __init__(self, week, ev):
            self.week, self.ev_cons = week, ev

    obs, excluded = P.observations_from_rows([R(6, 0.01), R(6, None), R(7, -0.02)])
    assert obs == [(6, 0.01), (7, -0.02)] and excluded == 1


def test_the_simulator_makes_the_same_decisions_as_position():
    """simulate() is vectorised over weeks; hold it to position() path by path."""
    import numpy as np

    rng = np.random.default_rng(5)
    per_week, weeks = 9, 10
    for mu in (-0.02, 0.015, 0.04):
        x = rng.normal(mu, 0.05, size=(300, weeks, per_week))
        means = x.mean(axis=2)
        llr = np.cumsum(P.llr_week(means, per_week), axis=1)
        k = np.arange(1, weeks + 1)
        ok = (k * per_week >= P.MIN_OBS) & (k >= P.MIN_WEEKS)
        up = (llr >= P.UPPER) & ok
        dn = (llr <= P.LOWER) & ok
        for r in range(300):
            fu = up[r].argmax() if up[r].any() else 10**6
            fd = dn[r].argmax() if dn[r].any() else 10**6
            vec = P.PROMOTE if fu < fd else P.STOP if fd < fu else P.RUNNING
            obs = [(w, float(v)) for w in range(weeks) for v in x[r, w]]
            pos = P.position(obs)
            assert vec == (P.RUNNING if pos.state == P.TIMEOUT else pos.state)


def test_simulate_keeps_a_no_edge_arm_inside_its_budget():
    for per_week in (8, 15):
        r = P.simulate(0.0, 0.05, per_week, 10, week_shock_sd=0.02, reps=20000)
        assert r["promote"] + r["stop"] + r["timeout"] == pytest.approx(1.0)
        assert r["promote"] < P.ALPHA


def test_variance_components_recover_a_known_week_effect():
    rnd = random.Random(1)
    groups = []
    for _ in range(300):
        shock = rnd.gauss(0, 0.02)
        groups.append([shock + rnd.gauss(0, 0.05) for _ in range(15)])
    vc = P.variance_components(groups)
    assert vc["between"] == pytest.approx(0.02, abs=0.004)
    assert vc["within"] == pytest.approx(0.05, abs=0.003)
    lo, _, _, hi = P.bootstrap_between(groups, reps=300)
    assert lo < 0.02 < hi


def test_variance_components_with_no_week_effect_reads_near_zero():
    rnd = random.Random(2)
    groups = [[rnd.gauss(0, 0.05) for _ in range(12)] for _ in range(200)]
    assert P.variance_components(groups)["between"] < 0.006
    assert P.variance_components([[1.0]])["between"] is None
