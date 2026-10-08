"""The 2026 Statistical Protocol's test (beatvegas/protocol.py, docs/PROTOCOL_2026.md)."""

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


def test_llr_step_is_zero_at_the_midpoint_and_signed_by_side():
    assert P.llr_step(0.015) == pytest.approx(0.0)
    assert P.llr_step(0.03) > 0 > P.llr_step(0.0)


def test_no_decision_before_thirty_observations_over_three_weeks():
    strong = [(w, 0.20) for w in (1, 1, 1) for _ in range(10)]  # 30 strong bets, one week
    pos = P.position(strong)
    assert pos.state == P.RUNNING and pos.weeks == 1 and not pos.can_decide
    spread = [(1 + i // 10, 0.20) for i in range(30)]  # 30 strong bets over 3 weeks
    pos = P.position(spread)
    assert pos.state == P.PROMOTE and pos.decided_at == 30


def test_a_losing_arm_stops_and_a_timeout_spends_the_alpha():
    losing = [(1 + i // 10, -0.05) for i in range(40)]
    pos = P.position(losing)
    assert pos.state == P.STOP and pos.decided_at == 30
    assert P.label(pos.state).startswith("NEEDS MORE EVIDENCE")
    flat = [(1 + i // 10, 0.015) for i in range(20)]
    assert P.position(flat).state == P.RUNNING
    assert P.position(flat, season_over=True).state == P.TIMEOUT


def test_max_observations_times_out():
    # Exactly the midpoint every time: the LLR never moves, so only MAX_OBS ends it.
    obs = [(1 + i // 10, 0.015) for i in range(P.MAX_OBS + 5)]
    pos = P.position(obs)
    assert pos.state == P.TIMEOUT and pos.decided_at == P.MAX_OBS


def test_observations_from_rows_counts_exclusions():
    class R:
        def __init__(self, week, ev):
            self.week, self.ev_cons = week, ev

    obs, excluded = P.observations_from_rows([R(6, 0.01), R(6, None), R(7, -0.02)])
    assert obs == [(6, 0.01), (7, -0.02)] and excluded == 1


def test_the_simulator_makes_the_same_decisions_as_position():
    """simulate() is vectorised; hold it to position() path by path."""
    import numpy as np

    rng = np.random.default_rng(5)
    per_week, weeks = 12, 10
    n = per_week * weeks
    for mu in (-0.02, 0.015, 0.04):
        x = rng.normal(mu, 0.06, size=(200, n))
        wk = np.arange(n) // per_week
        llr = np.cumsum(P.llr_step(x), axis=1)
        nn = np.arange(1, n + 1)
        ok = (nn >= P.MIN_OBS) & ((wk + 1) >= P.MIN_WEEKS)
        up = (llr >= P.UPPER) & ok
        dn = (llr <= P.LOWER) & ok
        for r in range(200):
            fu = up[r].argmax() if up[r].any() else 10**6
            fd = dn[r].argmax() if dn[r].any() else 10**6
            vec = P.PROMOTE if fu < fd else P.STOP if fd < fu else P.RUNNING
            pos = P.position(zip(wk.tolist(), x[r].tolist()))
            expect = P.RUNNING if pos.state == P.TIMEOUT else pos.state
            assert vec == expect


def test_simulate_reports_rates_that_sum_to_one():
    r = P.simulate(0.0, 0.06, 15, 10, reps=2000)
    assert r["promote"] + r["stop"] + r["timeout"] == pytest.approx(1.0)
    assert r["promote"] < 0.02  # a no-edge arm is rarely promoted


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
