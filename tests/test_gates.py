"""H4 arithmetic: each gate judged alone, blocked-alone vs the ladder, the fixed
ceiling, shrunk trust, and the three cap rankings. Exploratory -- the module must not
emit a gate verdict."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from beatvegas.backtest import gates as G

KICK = datetime(2026, 9, 19, 19, 30)


def _row(gid, **kw):
    r = {
        "card_id": 10,
        "built_at": KICK - timedelta(days=1),
        "slot": "fri_pm",
        "status": "final",
        "week": 3,
        "game_id": gid,
        "tier": "BET",
        "blocker": None,
        "paper_blocker": None,
        "gate_blocker": None,
        "hr_line": 45.5,
        "hr_price": -110,
        "market_line": 45.5,
        "ev": -0.02,
        "bv_line": 43.0,
        "gap": 2.5,
        "qb_out": False,
        "games_played": 3,
        "over_cap": False,
        "spread": 10.0,
        "kickoff": KICK,
        "fh": 40.0,
        "hr_close": 45.0,
        "close_line": 45.0,
    }
    r.update(kw)
    return r


def test_primary_cut_takes_the_last_decision_build_and_drops_previews():
    rows = pd.DataFrame(
        [
            _row(1, built_at=KICK - timedelta(days=2), slot="thu_pm"),
            _row(1, built_at=KICK - timedelta(days=1), slot="fri_pm"),
            _row(1, built_at=KICK - timedelta(hours=1), slot="manual", status="preview"),
            _row(2, hr_line=None),
        ]
    )
    cut = G.primary_cut(rows)
    assert len(cut) == 1 and cut.iloc[0].slot == "fri_pm"


def test_flags_judge_each_gate_alone_and_record_provenance():
    rows = pd.DataFrame(
        [
            _row(1),  # clean BET
            _row(2, market_line=46.5),  # off market by 1.0 (HR below the market)
            _row(3, ev=None),  # no fair price
            _row(4, ev=-0.08, hr_price=-125),  # price gate AND fixed ceiling
            _row(5, qb_out=True),
            _row(6, qb_out=None, blocker="qb_out", tier="EDGE"),  # pre-field card
            _row(7, games_played=1),
            _row(8, over_cap=True),
            _row(9, status="degraded"),
            _row(10, bv_line=44.5),  # gap 1.0 -> does not qualify
        ]
    )
    fl = G.flags(rows)
    assert fl["qualifies"].tolist() == [True] * 9 + [False]
    assert fl.loc[1, "f_off_market"] and not fl.loc[0, "f_off_market"]
    assert fl.loc[2, "f_no_fair_price"] and not fl.loc[2, "f_price"]
    assert (
        fl.loc[3, "f_price"] and fl.loc[3, "f_fixed_ceiling"] and not fl.loc[0, "f_fixed_ceiling"]
    )
    assert fl.loc[4, "f_qb_out"] and fl.loc[4, "qb_out_src"] == "field"
    assert fl.loc[5, "f_qb_out"] and "undercounted" in fl.loc[5, "qb_out_src"]
    assert fl.loc[6, "f_early_season"] and fl.loc[6, "early_season_src"] == "field"
    assert fl.loc[7, "f_cap"] and fl.loc[8, "f_degraded"]
    assert fl.loc[0, "n_fails"] == 0 and fl.loc[3, "n_fails"] == 1


def test_gate_records_split_fails_alone_and_passed():
    rows = pd.DataFrame(
        [
            _row(1),
            _row(2, ev=-0.08, fh=50.0),  # price alone, went over
            _row(3, ev=-0.08, market_line=46.5),  # price AND off_market -> not alone
            _row(4, fh=None),  # ungraded clean BET
        ]
    )
    recs = {g["gate"]: g for g in G.gate_records(G.flags(rows), n_boot=50)}
    price = recs["price"]
    assert price["fails"]["n"] == 2 and price["alone"]["n"] == 1 and price["passed"]["n"] == 2
    assert price["alone"]["over"] == 1 and price["alone"]["units"] == pytest.approx(-1.0)
    assert price["passed"]["graded"] == 1  # the ungraded BET counts in n, not in graded
    assert price["fails"]["hit_lo"] is None  # under the Wilson floor: counts only
    assert recs["off_market"]["alone"]["n"] == 0


def test_fixed_ceiling_partition_adds_up():
    rows = pd.DataFrame(
        [_row(1), _row(2, hr_price=-120), _row(3, ev=-0.08), _row(4, ev=-0.08, hr_price=-130)]
    )
    fx = G.fixed_ceiling_records(G.flags(rows), n_boot=20)
    assert (fx["both"], fx["fixed_only"], fx["price_only"], fx["neither"]) == (1, 1, 1, 1)
    assert fx["fails"]["n"] == 2 and fx["passed"]["n"] == 2


def test_trust_shrinks_toward_one_and_is_exactly_one_on_thin_buckets():
    resid = pd.DataFrame(
        {
            "bucket": ["<14"] * 60 + ["28+"] * 5,
            "pred": [0.0] * 65,
            "actual": [1.0] * 60 + [4.0] * 5,  # 28+ four times worse, but n = 5
        }
    )
    tf = G.trust_factors(resid)
    overall = (60 * 1 + 5 * 4) / 65
    ratio = overall / 1.0
    assert tf["<14"]["ratio"] == pytest.approx(ratio)
    assert tf["<14"]["trust"] == pytest.approx((60 * ratio + 30) / 90)
    assert tf["28+"]["trust"] == 1.0 and tf["28+"]["n"] == 5
    assert tf["14-21"]["trust"] == 1.0 and tf["14-21"]["n"] == 0


def test_cap_rankings_reorder_by_trust_and_report_overlap():
    rows = pd.DataFrame(
        [
            _row(1, gap=6.0, spread=30.0),  # biggest gap, 28+ bucket
            _row(2, gap=3.0, spread=5.0),
            _row(3, gap=2.5, spread=6.0),
            _row(4, gap=2.4, spread=7.0),
            _row(5, gap=2.3, spread=8.0),
            _row(6, gap=2.2, spread=9.0),
            _row(7, gap=2.0, spread=25.0, tier="EDGE", blocker="price"),  # not in the pool
        ]
    )
    trusts = {
        "low_28": {
            "28+": {"trust": 0.3},
            "<14": {"trust": 1.0},
            "14-21": {"trust": 1.0},
            "21-28": {"trust": 1.0},
        }
    }
    cap = G.cap_rankings(G.primary_cut(rows), trusts, n_boot=20)
    wk = cap[0]
    assert wk["pool"] == 6
    assert 1 in wk["rankings"]["gap_only"]["games"]
    assert 1 not in wk["rankings"]["low_28"]["games"]  # 6.0 * 0.3 = 1.8 falls out
    assert wk["overlap_with_gap_only"]["low_28"] == 4


def test_module_emits_no_gate_verdict_words():
    src = open(G.__file__).read()
    assert "COSTLY**" not in src and "PROTECTIVE**" not in src
    assert "EXPLORATORY" in G.STATUS


def test_render_markdown_carries_the_status():
    rows = pd.DataFrame([_row(1), _row(2, ev=-0.08)])
    cut = G.primary_cut(rows)
    fl = G.flags(cut)
    trusts = {"trust_2026": G.trust_factors(G.residual_frame_2026(cut))}
    r = {
        "season": 2026,
        "weeks": [3],
        "n_cut": 2,
        "n_qualifying": 2,
        "n_graded": 2,
        "status_word": "EXPLORATORY — no gate verdict",
        "gates": G.gate_records(fl, 20),
        "fixed": G.fixed_ceiling_records(fl, 20),
        "trusts": trusts,
        "cap": G.cap_rankings(cut, trusts, n_boot=20),
        "per_build": G.per_build_alone(fl),
        "generated_at": "now",
    }
    md = G.render_markdown(r)
    assert "## Status: **EXPLORATORY" in md and "| price |" in md and np.isfinite(len(md))
