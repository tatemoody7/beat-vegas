"""The stopping rule's arithmetic and, above all, its discipline: a fixed-n design is
one test at n, a sequential design stops on Wald's bounds, and no bootstrap band exists
to be peeked at."""

from __future__ import annotations

import numpy as np
import pytest

from beatvegas.backtest import stopping as S


def test_effect_sizes():
    assert S.edge_to_units(0.04, 0.5) == pytest.approx(0.08)
    assert S.edge_to_units(0.04, 0.5475) == pytest.approx(0.07306, abs=1e-4)
    assert S.edge_to_points(0.04, 11.26) == pytest.approx(1.129, abs=1e-3)
    assert S.breakeven_from_prices([-110, -110]) == pytest.approx(110 / 210)
    assert S.breakeven_from_prices([100]) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        S.edge_to_units(0.04, 1.5)


def test_fixed_n_matches_the_textbook():
    # (1.96 + 0.8416)^2 * sigma^2 / mu1^2
    n = S.fixed_n(0.1, 1.0, 0.05, 0.8)
    assert n == 785
    assert S.fixed_n(0.1, 1.0, 0.025, 0.8) > n  # a tighter per-clock alpha needs more
    assert S.fixed_band(1.0, 0.05, 100) == pytest.approx(0.196, abs=1e-3)


def test_sprt_bounds_and_expected_n_are_walds():
    b = S.sprt_bounds(0.025, 0.2)
    assert b["A"] == pytest.approx(np.log(0.8 / 0.025)) and b["B"] == pytest.approx(
        np.log(0.2 / 0.975)
    )
    e = S.sprt_expected_n(0.0731, 1.0, 0.025, 0.2)
    assert 400 < e["under_h0"] < 700 and 800 < e["under_h1"] < 1100
    assert e["at_midpoint"] > e["under_h0"]


def test_candidate_table_splits_alpha_across_the_two_clocks():
    t = S.candidate_table(0.5475, 0.924, 1.714, 11.26)
    fixed = [r for r in t["rows"] if r["design"] == "fixed-n"]
    assert {r["alpha_clock"] for r in fixed} == {0.025, 0.05}
    profit_5 = next(r for r in fixed if r["clock"] == "profit" and r["alpha_total"] == 0.05)
    assert profit_5["n"] > 1000  # the honest order of magnitude for a 4-pp edge
    clv_5 = [r for r in fixed if r["clock"] == "clv" and r["alpha_total"] == 0.05]
    assert len(clv_5) == 3 and min(r["n"] for r in clv_5) < 100 < max(r["n"] for r in clv_5)


def test_fixed_n_design_is_not_a_test_before_n_and_tests_the_first_n_once():
    mu1, sigma = {"profit": 0.0731, "clv": 1.129}, {"profit": 1.0, "clv": 1.714}
    x = np.full(50, 1.0)  # a clear, deterministic effect on both clocks
    r = S.running_position(x, x, "fixed-n", mu1, sigma, 0.025, n_fixed={"profit": 100, "clv": 30})
    assert (
        r["clocks"]["profit"]["status"] == "not a test" and r["clocks"]["profit"]["verdict"] is None
    )
    c = r["clocks"]["clv"]
    assert c["status"].startswith("tested once") and c["mean_at_n"] == pytest.approx(x[:30].mean())
    assert c["verdict"] == "success" and r["real_money"] == "unchanged"


def test_sprt_stops_on_the_first_crossing_and_a_failure_pauses_real_money():
    mu1, sigma = {"profit": 0.0731, "clv": 1.129}, {"profit": 1.0, "clv": 1.714}
    bad = np.full(3000, -0.15)  # a rule losing 0.15u a bet
    r = S.running_position(bad, np.zeros(3000), "sprt", mu1, sigma, 0.025)
    p = r["clocks"]["profit"]
    assert p["status"] == "stopped" and p["verdict"] == "failure" and p["stopped_at"] < 300
    assert r["real_money"] == "PAUSE"
    good = np.full(3000, 0.15)
    r2 = S.running_position(good, [0.0, 0.0, 0.0], "sprt", mu1, sigma, 0.025)
    assert r2["clocks"]["profit"]["verdict"] == "success" and r2["real_money"] == "unchanged"
    assert r2["clocks"]["clv"]["status"] == "running"  # three flat reads have not reached B


def test_no_bootstrap_band_exists_in_the_module():
    src = open(S.__file__).read()
    assert "bootstrap" not in src.lower().replace("no bootstrap band exists", "").replace(
        "bootstrap band is never", ""
    ).replace("an ordinary confidence band", "")
    with pytest.raises(ValueError):
        S.running_position(
            [1.0], [1.0], "peek", {"profit": 1, "clv": 1}, {"profit": 1, "clv": 1}, 0.05
        )


def test_render_candidates_names_both_clocks_and_designs():
    md = S.render_candidates(S.candidate_table(0.5475, 0.924, 1.714, 11.26))
    assert "| profit | +0.073 | fixed-n |" in md and "| clv | +1.129 | SPRT |" in md
    assert "| clv | +0.500 | fixed-n |" in md and "mu1" in md


def test_registered_rule_is_the_one_tate_chose():
    r = S.REGISTERED
    assert r["design"] == "sprt" and r["alpha_total"] == 0.05 and r["alpha_clock"] == 0.025
    assert r["mu1"]["profit"] == pytest.approx(0.0731, abs=1e-4) and r["mu1"]["clv"] == 0.50
    assert r["start"] == {"season": 2026, "week": 3}
    pos = S.registered_position([], [])
    assert pos["design"] == "sprt" and pos["real_money"] == "unchanged"
    assert "Stopping rule" in S.render_position(pos)


def test_position_script_filters_to_locked_paper_decisions_from_week_3(monkeypatch):
    from contextlib import contextmanager
    from datetime import datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from beatvegas.db.models import Base, ManualPick
    from tests.conftest import _load_script

    mod = _load_script("stopping_rule_position")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(
            [
                ManualPick(
                    season=2026,
                    week=2,
                    is_paper=True,
                    market="1H",
                    graded=True,
                    units=0.9,
                    clv=-1.0,
                    placed_at=datetime(2026, 9, 11),
                ),
                ManualPick(
                    season=2026,
                    week=3,
                    is_paper=True,
                    market="1H",
                    graded=True,
                    units=-1.0,
                    clv=0.5,
                    placed_at=datetime(2026, 9, 18),
                ),
                ManualPick(
                    season=2026,
                    week=3,
                    is_paper=False,
                    market="1H",
                    graded=True,
                    units=0.9,
                    clv=0.0,
                    placed_at=datetime(2026, 9, 18),
                ),
                ManualPick(
                    season=2026,
                    week=3,
                    is_paper=True,
                    market="1H",
                    graded=False,
                    placed_at=datetime(2026, 9, 19),
                ),
            ]
        )
        s.commit()

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s

    with scope() as s:
        units, clv = mod.load_observations(s)
    assert units == [-1.0] and clv == [-0.5]  # week 2 out, real out, ungraded out; clv sign flipped
