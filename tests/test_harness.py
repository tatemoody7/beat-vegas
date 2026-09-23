"""beatvegas/backtest/harness.py -- the shared measurement harness.

Every number a deterministic-arm run reports is hand-checked here; the real
incumbent is smoke-tested for shape and for the `plus1 - incumbent == 1.0`
identity only (HistGradientBoosting outputs are platform-dependent and are
never pinned)."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from test_residual_gate import _frame as residual_frame
from test_residual_gate import _hand_frame

from beatvegas import postmortem as pm
from beatvegas import registry as R
from beatvegas import snapshots as SN
from beatvegas.backtest import censoring as C
from beatvegas.backtest import harness as H
from beatvegas.backtest import residual_gate as G
from beatvegas.backtest import stats as S
from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.grading import clv_under, units_won
from beatvegas.lines import REAL_1H_CLOSE_WINDOW_H
from beatvegas.model.bv_line import bv_line_for_slate
from beatvegas.model.score import BET_GAP_PTS

ROOT = R.REPO_ROOT
VECTORS = ROOT / "tests" / "fixtures" / "slate_bar_vectors.json"

PRE_ROW = R.RegistryRow(
    id="H-TEST",
    question="q?",
    status="pre-registered",
    family="fam",
    data="2024-25",
    n="30",
    comparisons="1",
    criterion="PRIMARY: the candidate's pooled MAE is below the incumbent's, paired CI excluding zero.",
    doc="`docs/X.md`",
)
EXP_ROW = R.RegistryRow(
    id="H-EXP",
    question="q?",
    status="exploratory",
    family="exploratory",
    data="2024-25",
    n="30",
    comparisons="n/a",
    criterion="None. Counts and intervals only.",
    doc="`docs/X.md`",
)


def const(value):
    def scorer(train, target):
        return np.full(len(target), float(value))

    scorer.__name__ = f"const_{value}"
    scorer.__qualname__ = scorer.__name__
    return scorer


def spec_for(row, seasons=(2024, 2025), candidates=None, **kw):
    arms = [H.Arm("incumbent", const(27.0), is_incumbent=True)]
    arms += candidates or [H.Arm("plus1", const(28.0))]
    return H.HarnessSpec(row_id=row.id, arms=tuple(arms), test_seasons=tuple(seasons), **kw)


# --- the hand-set frame ---------------------------------------------------------
# Per test season, three weeks of five games. Incumbent predicts 27.0 everywhere,
# the candidate 28.0. Closes / actuals per week (game 1..5):
#   week 5: closes 30 29 28.5 27 26 ; actuals 25 31 28.5 20 33
#   week 6: closes 30 30 28 27 26   ; actuals 32 29 28 27 26
#   week 7: closes 26 26.5 26 25 24 ; actuals 20 30 26 25 24
# Games 1-3 of a week have both teams at 4 games played, games 4-5 at 1 and 4.
WEEKS = {
    5: ([30, 29, 28.5, 27, 26], [25, 31, 28.5, 20, 33]),
    6: ([30, 30, 28, 27, 26], [32, 29, 28, 27, 26]),
    7: ([26, 26.5, 26, 25, 24], [20, 30, 26, 25, 24]),
}


def hand_frame():
    rows, closes = [], {}
    gid = 1000
    # training season, ten played rows, all before any test kickoff
    for i in range(10):
        rows.append(
            {
                "id": gid,
                "season": 2023,
                "week": 5 + i % 3,
                "start_date": datetime(2023, 10, 1) + timedelta(days=i),
                "home_team": f"H{gid}",
                "away_team": f"A{gid}",
                "first_half_total": 24.0 + i,
                "home_points": 30,
                "away_points": 20,
                "first_half_source": "pbp",
                "h_games_played": 4,
                "a_games_played": 4,
                "under": 1.0,
                "proxy_line": 26.0,
                "full_game_total": 52.0,
            }
        )
        gid += 1
    for season in (2024, 2025):
        for week, (cl, ac) in WEEKS.items():
            for j in range(5):
                rows.append(
                    {
                        "id": gid,
                        "season": season,
                        "week": week,
                        "start_date": datetime(season, 9, 28)
                        + timedelta(days=7 * (week - 5), hours=j),
                        "home_team": f"H{gid}",
                        "away_team": f"A{gid}",
                        "first_half_total": float(ac[j]),
                        "home_points": 30,
                        "away_points": 20,
                        "first_half_source": "pbp",
                        "h_games_played": 4 if j < 3 else 1,
                        "a_games_played": 4,
                        "under": 1.0,
                        "proxy_line": 26.0,
                        "full_game_total": 52.0,
                    }
                )
                closes[gid] = float(cl[j])
                gid += 1
    return pd.DataFrame(rows), closes


def first_game_id(frame, season, week):
    return int(frame[(frame["season"] == season) & (frame["week"] == week)]["id"].iloc[0])


@pytest.fixture
def hand():
    frame, closes = hand_frame()
    g1 = first_game_id(frame, 2024, 5)
    grading = H.Grading(
        closes=closes,
        hr_closes={g1: 30.5},
        hr_prices={g1: -115},
        decision_lines={g1: 31.0},
        decision_rule="consensus_as_of(fri_pm)",
    )
    return frame, grading, g1


@pytest.fixture
def hand_result(hand, tmp_path):
    frame, grading, _ = hand
    return H.run(frame, grading, spec_for(PRE_ROW), PRE_ROW, {"rows": len(frame), "path": "x"})


# --- 4. Grading window -------------------------------------------------------------


@pytest.mark.parametrize("window", [None, 3.0, 1.0, 2.5])
def test_grading_refuses_any_window_but_the_real_close_window(window):
    with pytest.raises(H.HarnessRefusal) as e:
        H.Grading(closes={}, window_h=window)
    assert "REAL_1H_CLOSE_WINDOW_H" in str(e.value)


def test_grading_default_window_is_the_real_close_window():
    assert H.Grading(closes={}).window_h == REAL_1H_CLOSE_WINDOW_H == 2.0


def test_spec_needs_exactly_one_incumbent_and_unique_names():
    with pytest.raises(H.HarnessRefusal):
        H.HarnessSpec(row_id="x", arms=(H.Arm("a", const(1)),), test_seasons=(2025,))
    with pytest.raises(H.HarnessRefusal):
        H.HarnessSpec(
            row_id="x",
            arms=(H.Arm("a", const(1), True), H.Arm("a", const(2))),
            test_seasons=(2025,),
        )
    assert H.incumbent_arm().scorer is bv_line_for_slate and H.incumbent_arm().is_incumbent


# --- 5. a season with no real close ------------------------------------------------


def test_a_season_with_zero_real_closes_is_not_evaluable_and_names_the_season(hand):
    frame, grading, _ = hand
    only_2024 = {g: c for g, c in grading.closes.items() if g < first_game_id(frame, 2025, 5)}
    g2 = H.Grading(closes=only_2024)
    with pytest.raises(G.GateNotEvaluable) as e:
        H.run(frame, g2, spec_for(PRE_ROW), PRE_ROW, {})
    assert "2025" in str(e.value) and "zero real 1H closes" in str(e.value)
    assert "proxy" in str(e.value)


def test_no_proxy_derived_column_reaches_the_graded_frame(hand_result, hand):
    frame, _, _ = hand
    assert "proxy_line" in frame.columns and "full_game_total" in frame.columns
    for c in H.PROXY_COLS:
        assert c not in hand_result.per_game.columns
    bad = pd.DataFrame({"game_id": [1], "season": [2025], "proxy_line": [26.0]})
    with pytest.raises(H.HarnessRefusal):
        H.attach_closes(bad, H.Grading(closes={1: 27.0}), spec_for(PRE_ROW))


# --- 6. deterministic arms, hand-checked -------------------------------------------


def test_deterministic_arms_reproduce_the_hand_arithmetic(hand_result):
    pg, rep = hand_result.per_game, hand_result.report
    assert len(pg) == 30
    assert (pg["pred_incumbent"] == 27.0).all() and (pg["pred_plus1"] == 28.0).all()
    assert np.allclose(pg["gap_incumbent"], pg["close"] - 27.0)
    assert np.allclose(pg["gap_plus1"], pg["close"] - 28.0)
    inc, cand = rep["arms"]["incumbent"], rep["arms"]["plus1"]
    s24 = inc["seasons"]["2024"]
    assert s24["n"] == 15
    assert s24["mae"] == pytest.approx(45.5 / 15)
    assert s24["bias_actual_minus_pred"] == pytest.approx(-0.5 / 15)
    assert s24["bias_pred_minus_actual"] == pytest.approx(0.5 / 15)
    assert cand["seasons"]["2024"]["mae"] == pytest.approx(46.5 / 15)
    assert cand["seasons"]["2024"]["bias_actual_minus_pred"] == pytest.approx(-15.5 / 15)
    # selection: k = 1 per five-game slate; week 6 ties at the bar both qualify,
    # week 7's gaps are all <= 0 so nothing qualifies
    assert s24["share_pct"] == pytest.approx(3 / 15)
    assert s24["share_const"] == pytest.approx(4 / 15)
    r = s24["record_pct"]
    assert (r["n"], r["wins"], r["losses"], r["pushes"]) == (3, 2, 1, 0)
    assert r["hit_rate"] == pytest.approx(2 / 3)
    u = units_won(25, 30) * 2 - 1.0
    assert r["units"] == pytest.approx(u) and r["roi"] == pytest.approx(u / 3)
    assert s24["record_cap"] == s24["record_pct"]
    a = s24["record_all"]
    assert (a["n"], a["wins"], a["losses"], a["pushes"]) == (15, 4, 4, 7)
    assert a["hit_rate"] == pytest.approx(0.5)
    # the candidate selects the same three games (a constant shift cannot reorder a slate)
    assert cand["seasons"]["2024"]["record_pct"] == r
    assert cand["seasons"]["2024"]["overlap_vs_incumbent"]["pct"]["both"] == 3
    # pooled = two identical seasons
    p = inc["pooled"]["record_pct"]
    assert (p["n"], p["wins"], p["losses"], p["units"]) == (6, 4, 2, pytest.approx(2 * u))
    assert p["roi"] == pytest.approx(u / 3)
    # money population split: every pick is a game with both teams at >= 2 games
    split = s24["by_games_played"]
    assert split["ge2"]["n"] == 9 and split["lt2"]["n"] == 6
    assert split["ge2"]["record_pct"]["n"] == 3 and split["lt2"]["record_pct"]["n"] == 0
    # market benchmark on the same rows
    assert rep["market"]["seasons"]["2024"]["close_mae"] == pytest.approx(
        (5 + 2 + 0 + 7 + 7 + 2 + 1 + 0 + 0 + 0 + 6 + 3.5 + 0 + 0 + 0) / 15
    )


def test_deterministic_bias_difference_is_exactly_minus_one_and_flagged(hand_result):
    pair = hand_result.report["comparisons"]["pairs"]["plus1"]
    err = pair["err"]
    assert err["deterministic"] is True
    assert err["mean"] == -1.0 and err["lo"] == -1.0 and err["hi"] == -1.0
    assert err["n"] == 30
    # |err| is not constant (some games sit between 27 and 28), so it is not flagged
    assert pair["abs_err"]["mean"] == pytest.approx((46.5 - 45.5) * 2 / 30)
    assert "deterministic" not in pair["abs_err"]


def test_hr_basis_and_clv_are_reported_where_they_exist(hand_result, hand):
    _, _, g1 = hand
    pg = hand_result.per_game
    row = pg[pg["game_id"] == g1].iloc[0]
    assert row["hr_close"] == 30.5 and row["hr_price"] == -115
    assert row["outcome_hr"] == "under" and row["units_hr"] == pytest.approx(100 / 115)
    assert row["decision_line"] == 31.0 and row["clv_fav_incumbent"] == pytest.approx(1.0)
    s24 = hand_result.report["arms"]["incumbent"]["seasons"]["2024"]
    assert s24["hr"]["n"] == 1 and s24["hr"]["n_priced"] == 1
    assert s24["hr"]["record_all"]["wins"] == 1 and s24["hr"]["record_all"][
        "units"
    ] == pytest.approx(100 / 115)
    assert s24["clv"] == {
        "n_picks": 3,
        "n_with_decision_line": 1,
        "mean_favourable": 1.0,
        "bootstrap": s24["clv"]["bootstrap"],
    }
    assert s24["clv"]["bootstrap"]["n"] == 1
    s25 = hand_result.report["arms"]["incumbent"]["seasons"]["2025"]
    assert s25["hr"] is None and s25["clv"]["n_with_decision_line"] == 0
    cov = hand_result.report["data_basis"]["coverage"]
    assert cov["2024"] == {
        "scoreable": 15,
        "with_close": 15,
        "with_hr_close": 1,
        "with_decision_line": 1,
    }


def test_report_carries_the_fixed_caveats_the_substitution_and_the_verbatim_criterion(hand_result):
    rep = hand_result.report
    assert rep["kind"] == "harness"
    assert list(rep["caveats"]) == list(H.FIXED_CAVEATS)
    assert any("EXHAUSTED" in c for c in rep["caveats"])
    assert any("EV / price gate is NOT reproduced" in c for c in rep["caveats"])
    assert "consensus close stands in for Hard Rock" in rep["data_basis"]["substitution"]
    assert "2024-2025" in rep["data_basis"]["substitution"]
    assert rep["spec"]["min_games_train"] == 0 and rep["spec"]["min_games_score"] == 0
    assert rep["verdict"]["criterion_text"] == PRE_ROW.criterion
    assert rep["data_basis"]["train_seasons_by_test_season"] == {
        "2024": "2023",
        "2025": "2023-2024",
    }
    json.dumps(rep)  # _clean'ed


def test_walk_forward_refuses_a_scorer_that_returns_nan_or_the_wrong_length(hand):
    frame, grading, _ = hand

    def nan_scorer(train, target):
        out = np.full(len(target), 27.0)
        out[0] = np.nan
        return out

    def short_scorer(train, target):
        return np.full(len(target) - 1, 27.0)

    for bad, needle in ((nan_scorer, "non-finite"), (short_scorer, "predictions for")):
        spec = spec_for(PRE_ROW, candidates=[H.Arm("bad", bad)])
        with pytest.raises(ValueError) as e:
            H.run(frame, grading, spec, PRE_ROW, {})
        assert needle in str(e.value)


def test_min_games_knobs_cut_the_two_populations_separately(hand):
    frame, grading, _ = hand
    train_pool, score_pool, drops = H.split_populations(frame, spec_for(PRE_ROW, min_games_score=2))
    assert drops["train"]["min_games"] == 0 and drops["score"]["min_games"] == 2
    assert len(score_pool) == 18  # 3 of 5 games a week clear 2 games played
    assert len(train_pool) == 40  # every played row at 0
    train_pool2, _, _ = H.split_populations(frame, spec_for(PRE_ROW, min_games_train=2))
    assert len(train_pool2) == 10 + 18


# --- 7. the real incumbent: shapes and the +1 identity only ------------------------


def test_real_incumbent_smoke_shapes_and_plus_one_identity():
    df, closes = residual_frame()
    df["h_games_played"] = 5
    df["a_games_played"] = 5
    df["home_points"] = 30
    df["away_points"] = 20

    def plus1(train, target):
        return bv_line_for_slate(train, target) + 1.0

    spec = H.HarnessSpec(
        row_id=PRE_ROW.id,
        arms=(H.incumbent_arm(), H.Arm("plus1", plus1)),
        test_seasons=(2025,),
        n_boot=200,
    )
    res = H.run(df, H.Grading(closes=closes), spec, PRE_ROW, {"rows": len(df)})
    pg = res.per_game
    assert len(pg) == 100 and pg["season"].eq(2025).all()
    for col in ("pred_incumbent", "pred_plus1", "gap_incumbent", "err_plus1", "close", "actual"):
        assert np.isfinite(pg[col]).all(), col
    assert np.allclose(pg["pred_plus1"] - pg["pred_incumbent"], 1.0, atol=1e-9)
    assert np.allclose(pg["gap_incumbent"] - pg["gap_plus1"], 1.0, atol=1e-9)
    inc = res.report["arms"]["incumbent"]["pooled"]
    assert inc["n"] == 100 and inc["mae"] is not None and inc["market_mae"] is not None
    assert res.report["comparisons"]["pairs"]["plus1"]["err"]["deterministic"] is True
    assert res.report["comparisons"]["pairs"]["plus1"]["err"]["mean"] == pytest.approx(-1.0)
    assert res.report["arms"]["incumbent"]["scorer"].endswith("bv_line_for_slate")


# --- 8. CLV sign ----------------------------------------------------------------------


def test_favourable_clv_is_the_one_sign_flip():
    assert clv_under(28.5, 27.5) == -1.0
    assert H.favourable_clv(28.5, 27.5) == 1.0
    assert clv_under(27.5, 28.5) == 1.0
    assert H.favourable_clv(27.5, 28.5) == -1.0
    assert H.favourable_clv(None, 27.5) is None and H.favourable_clv(28.5, None) is None


# --- 9. pushes staked, excluded from the hit rate -----------------------------------


def test_record_pushes_staked_not_counted_default_and_hr_columns():
    df = _hand_frame()
    r = G.record(df, pd.Series(True, index=df.index))
    assert (r["wins"], r["losses"], r["pushes"], r["n"]) == (7, 4, 1, 12)
    assert r["hit_rate"] == pytest.approx(7 / 11)
    assert r["roi"] == pytest.approx(r["units"] / 12)
    df["outcome_hr"] = df["outcome"]
    df["units_hr"] = df["units"]
    df["outcome"] = "over"  # the default columns are now wrong on purpose
    r2 = G.record(
        df, pd.Series(True, index=df.index), outcome_col="outcome_hr", units_col="units_hr"
    )
    assert (r2["wins"], r2["losses"], r2["pushes"]) == (7, 4, 1)
    assert r2["units"] == pytest.approx(r["units"])


# --- 10. slate_bar reproduction --------------------------------------------------------


def test_pct_qualifiers_reproduce_every_golden_vector_case():
    vectors = json.loads(VECTORS.read_text())
    rows = []
    for i, case in enumerate(vectors["cases"]):
        for j, g in enumerate(case["gaps"]):
            rows.append(
                {
                    "season": 2025,
                    "week": i,
                    "game_id": i * 100 + j,
                    "gap": np.nan if g is None else g,
                }
            )
    df = pd.DataFrame(rows)
    q, bar = H.pct_qualifiers(df, "gap", share=vectors["share"], fallback_bar=BET_GAP_PTS)
    for i, case in enumerate(vectors["cases"]):
        sub = df[df["week"] == i]
        if sub.empty:
            continue
        expect = BET_GAP_PTS if case["bar"] is None else case["bar"]
        assert (bar.loc[sub.index] == expect).all(), (i, case)
        gaps = sub["gap"]
        assert (q.loc[sub.index] == (gaps.notna() & (gaps >= expect) & (gaps > 0))).all(), i
    # ties at the bar all qualify (three 3.0s over ten games -> k = 2, bar 3.0)
    ties = df[df["week"] == 6]
    assert q.loc[ties.index].sum() == 3
    # a gap <= 0 never qualifies, even when the bar itself is <= 0
    neg = pd.DataFrame(
        {"season": [2025] * 2, "week": [9, 9], "game_id": [1, 2], "gap": [-2.0, -1.0]}
    )
    qn, bn = H.pct_qualifiers(neg, "gap")
    assert (bn == -1.0).all() and not qn.any()
    # an empty-gap slate takes the fallback
    empty = pd.DataFrame({"season": [2025], "week": [10], "game_id": [1], "gap": [np.nan]})
    qe, be = H.pct_qualifiers(empty, "gap", fallback_bar=1.75)
    assert (be == 1.75).all() and not qe.any()


# --- 11. cap ---------------------------------------------------------------------------


def test_cap_within_takes_the_top_five_by_gap_then_kickoff_then_game_id():
    k = pd.Timestamp("2025-10-04T16:00")
    df = pd.DataFrame(
        {
            "season": 2025,
            "week": 5,
            "game_id": [8, 7, 6, 5, 4, 3, 2, 1],
            "kickoff": [k, k, k, k + pd.Timedelta(hours=1), k, k, k, k],
            "gap": [2.0, 2.0, 2.0, 3.0, 3.0, 1.0, 4.0, 0.5],
        }
    )
    q = pd.Series(True, index=df.index)
    mask = H.cap_within(df, "gap", q, cap=5)
    # 4.0 (id 2) ; 3.0 x2 -> id 4 (earlier kickoff) then id 5 ; 2.0 x3 -> ids 6, 7 by game_id
    assert sorted(df.loc[mask, "game_id"].tolist()) == [2, 4, 5, 6, 7]
    q2 = q.copy()
    q2.loc[df["game_id"] == 2] = False  # not qualifying -> never capped in
    mask2 = H.cap_within(df, "gap", q2, cap=5)
    assert 2 not in df.loc[mask2, "game_id"].tolist() and mask2.sum() == 5
    assert not H.cap_within(df, "gap", pd.Series(False, index=df.index)).any()


# --- 12. Holm across declared arms only --------------------------------------------------


def test_holm_runs_across_the_declared_candidates_only(hand):
    frame, grading, _ = hand
    spec = spec_for(PRE_ROW, candidates=[H.Arm("plus1", const(28.0)), H.Arm("minus1", const(26.0))])
    res = H.run(frame, grading, spec, PRE_ROW, {})
    cmp_ = res.report["comparisons"]
    for fam in ("abs_err", "err", "portfolio_units"):
        assert set(cmp_["holm"][fam]) == {"plus1", "minus1"}
        for name in ("plus1", "minus1"):
            raw = cmp_["pairs"][name][fam]["p"]
            adj = cmp_["holm"][fam][name]
            assert adj is None or raw is None or adj >= raw - 1e-12
    assert cmp_["incumbent"] == "incumbent"
    assert set(cmp_["dsr"]["per_arm"]) == {"incumbent", "plus1", "minus1"}
    assert cmp_["dsr"]["n_trials"] == 3
    # two candidates and 30 games: PBO is computed
    assert cmp_["pbo"] is None or 0.0 <= cmp_["pbo"] <= 1.0
    assert "CSCV" in cmp_["pbo_note"]


def test_pbo_is_none_with_a_note_under_two_candidates(hand_result):
    ov = hand_result.report["overfit"]
    assert ov["pbo"] is None and "needs >= 2 candidate arms" in ov["pbo_note"]


# --- 13. verdict rules -------------------------------------------------------------------


def test_exploratory_row_is_measurement_only_and_refuses_a_criterion_function(hand):
    frame, grading, _ = hand
    res = H.run(frame, grading, spec_for(EXP_ROW), EXP_ROW, {})
    assert res.report["verdict"]["verdict"] == "n/a (exploratory: measurement only)"
    assert res.report["verdict"]["criterion_text"] == EXP_ROW.criterion
    with pytest.raises(H.HarnessRefusal) as e:
        H.run(frame, grading, spec_for(EXP_ROW, criterion=lambda rep: True), EXP_ROW, {})
    assert "exploratory" in str(e.value)


def test_pre_registered_without_a_function_is_not_evaluable_and_quotes_the_text(hand_result):
    v = hand_result.report["verdict"]
    assert v["verdict"].startswith("not evaluable (no criterion function declared")
    assert v["criterion_text"] == PRE_ROW.criterion and v["criterion_fn"] is None
    md = H.render_markdown(hand_result.report)
    assert f"> {PRE_ROW.criterion}" in md


def test_pre_registered_with_a_function_reads_met_not_met_or_not_evaluable(hand):
    frame, grading, _ = hand

    def met(rep):
        return rep["arms"]["plus1"]["pooled"]["mae"] < rep["arms"]["incumbent"]["pooled"]["mae"]

    def undecided(rep):
        return None

    r1 = H.run(frame, grading, spec_for(PRE_ROW, criterion=met), PRE_ROW, {})
    assert r1.report["verdict"]["verdict"] == "not met"  # 28.0 is the worse constant
    assert r1.report["verdict"]["criterion_fn"].endswith("met")
    r2 = H.run(frame, grading, spec_for(PRE_ROW, criterion=lambda rep: True), PRE_ROW, {})
    assert r2.report["verdict"]["verdict"] == "met"
    r3 = H.run(frame, grading, spec_for(PRE_ROW, criterion=undecided), PRE_ROW, {})
    assert r3.report["verdict"]["verdict"] == "not evaluable"
    md = H.render_markdown(r1.report)
    assert "**not met**" in md and "criterion function `" in md


def test_run_refuses_a_row_that_is_not_runnable_or_does_not_match_the_spec(hand):
    frame, grading, _ = hand
    decided = replace(PRE_ROW, status="tested-null")
    with pytest.raises(H.HarnessRefusal):
        H.run(frame, grading, spec_for(decided), decided, {})
    with pytest.raises(H.HarnessRefusal):
        H.run(frame, grading, spec_for(PRE_ROW), EXP_ROW, {})


# --- 14. report triple + step summary -------------------------------------------------------


def test_write_report_writes_the_stamped_triple_and_the_step_summary(
    hand_result, tmp_path, monkeypatch
):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    md, js, csv = H.write_report(
        hand_result, str(tmp_path / "harness_H-TEST"), stamp="20260923T000000Z"
    )
    assert md.name == "harness_H-TEST_20260923T000000Z.md"
    assert js.name.endswith(".json") and csv.name.endswith(".csv")
    assert all(p.exists() and p.stat().st_size > 0 for p in (md, js, csv))
    text = md.read_text()
    assert "# Measurement harness — H-TEST (pre-registered)" in text
    assert "2023-25 EXHAUSTED" in text and "Consensus stands in for Hard Rock" in text
    assert "min_games_train = 0, min_games_score = 0" in text
    assert summary.read_text().startswith("# Measurement harness")
    back = json.loads(js.read_text())
    assert back["registry"]["id"] == "H-TEST"
    pg = pd.read_csv(csv)
    assert len(pg) == 30 and "qual_incumbent" in pg.columns


# --- 15. snapshot re-cut + fingerprint -----------------------------------------------------------


def test_load_frame_recuts_a_declared_snapshot_and_always_writes_the_fingerprint(hand, tmp_path):
    frame, _, _ = hand
    frame.attrs["build"] = {"fbs_only": True, "min_games": 0}
    pkl = tmp_path / "frame.pkl"
    frame.to_pickle(pkl)
    fp_path = tmp_path / "harness_X_frame.json"
    got, fp = H.load_frame(pkl, spec_for(PRE_ROW, min_games_score=2), fp_path)
    assert len(got) == len(frame)  # the cut is applied per population later
    assert fp_path.exists() and fp["rows"] == len(frame)
    assert fp["source"]["snapshot"] == str(pkl) and fp["source"]["build"]["min_games"] == 0
    assert json.loads(fp_path.read_text())["rows"] == len(frame)
    # coarser than the spec's finer knob -> refused
    frame.attrs["build"] = {"fbs_only": True, "min_games": 2}
    frame.to_pickle(pkl)
    with pytest.raises(H.HarnessRefusal) as e:
        H.load_frame(pkl, spec_for(PRE_ROW), tmp_path / "y_frame.json")
    assert "coarser" in str(e.value)
    # no declared build -> refused
    frame.attrs = {}
    frame.to_pickle(pkl)
    with pytest.raises(H.HarnessRefusal) as e2:
        H.load_frame(pkl, spec_for(PRE_ROW), tmp_path / "z_frame.json")
    assert "attrs['build']" in str(e2.value)


def test_load_frame_builds_at_the_finer_knob_when_no_snapshot(hand, tmp_path, monkeypatch):
    frame, _, _ = hand
    calls = {}

    def fake_build(min_games, fbs_only):
        calls["min_games"], calls["fbs_only"] = min_games, fbs_only
        return frame.copy()

    monkeypatch.setattr(H, "build_feature_frame", fake_build)
    got, fp = H.load_frame(
        None, spec_for(PRE_ROW, min_games_train=2, min_games_score=0), tmp_path / "f.json"
    )
    assert calls == {"min_games": 0, "fbs_only": True}
    assert got.attrs["build"] == {"fbs_only": True, "min_games": 0}
    assert (tmp_path / "f.json").exists() and fp["source"]["snapshot"] is None


# --- 16. one Wilson ------------------------------------------------------------------------------


def test_there_is_one_wilson_in_the_repo():
    assert C.wilson is S.wilson
    assert pm.wilson_ci(7, 11) == S.wilson(7, 11, z=1.96)
    assert pm.wilson_ci(0, 0) == (None, None) and S.wilson(0, 0) == (None, None)
    lo, hi = S.wilson(15, 65)
    assert 0.14 < lo < 0.15 and 0.34 < hi < 0.35


# --- decision clock + snapshot readers ----------------------------------------------------------------


def test_decision_instant_is_the_friday_window_open_before_kickoff():
    # Saturday 2026-09-19 15:30 ET (19:30Z) -> Friday 2026-09-18 15:45 ET = 19:45Z
    assert SN.decision_instant(datetime(2026, 9, 19, 19, 30)) == datetime(2026, 9, 18, 19, 45)
    # Saturday 23:30 ET is Sunday 03:30Z: still that week's Friday
    assert SN.decision_instant(datetime(2026, 9, 20, 3, 30)) == datetime(2026, 9, 18, 19, 45)
    # a Friday game kicking off before the window opens has no decision line
    assert SN.decision_instant(datetime(2026, 9, 18, 16, 0)) is None
    # a Friday night game does
    assert SN.decision_instant(datetime(2026, 9, 19, 0, 0)) == datetime(2026, 9, 18, 19, 45)
    # winter (EST): 15:45 ET = 20:45Z
    assert SN.decision_instant(datetime(2026, 11, 28, 20, 0)) == datetime(2026, 11, 27, 20, 45)
    assert SN.decision_instant(None) is None
    assert SN.parse_decision_rule("consensus_as_of(fri_pm)") == "fri_pm"
    with pytest.raises(ValueError):
        SN.parse_decision_rule("closing")


def _seed_snapshots(engine):
    from sqlalchemy.orm import Session

    kick = datetime(2026, 9, 19, 19, 30)
    with Session(engine) as s:
        s.add(Game(id=1, season=2026, week=4, start_date=kick, home_team="H", away_team="A"))
        s.add(Game(id=2, season=2026, week=4, start_date=kick, home_team="H2", away_team="A2"))
        s.add(Game(id=3, season=2026, week=4, start_date=None, home_team="H3", away_team="A3"))
        rows = [
            # game 1: Thursday quotes (before the Friday clock), Friday-evening quotes, close
            ("draftkings", datetime(2026, 9, 17, 12, 0), 30.5, -110, -110),
            ("hardrockbet", datetime(2026, 9, 17, 12, 0), 31.0, -110, -110),
            ("draftkings", datetime(2026, 9, 18, 22, 0), 29.5, -110, -110),
            ("hardrockbet", datetime(2026, 9, 19, 18, 0), 29.0, -105, -115),
            ("draftkings", datetime(2026, 9, 19, 18, 30), 28.5, -110, -110),
            # game 2: only an opener 40 h out -> no real close
            ("draftkings", datetime(2026, 9, 18, 3, 0), 40.5, -110, -110),
        ]
        for gid_book in rows:
            book, at, line, o, u = gid_book
            gid = 2 if line == 40.5 else 1
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book=book,
                    market="1H_total",
                    line=line,
                    over_price=o,
                    under_price=u,
                    captured_at=at,
                )
            )
        # a full-game row must never be read as a 1H line
        s.add(
            OddsSnapshot(
                game_id=1,
                book="hardrockbet",
                market="full_game_total",
                line=55.5,
                over_price=-110,
                under_price=-110,
                captured_at=datetime(2026, 9, 19, 18, 0),
            )
        )
        s.commit()
    return kick


def test_snapshot_readers_against_a_seeded_sqlite():
    from conftest import _sqlite_scope

    eng, scope = _sqlite_scope()
    kick = _seed_snapshots(eng)
    with scope() as s:
        kicks = SN.kickoffs_for(s, [1, 2, 3, 99])
        assert kicks == {1: kick, 2: kick}
        closes = SN.consensus_closes(s, [1, 2], kicks)
        # game 1: HR 29.0 and DK 28.5 inside 2 h -> median 28.75; game 2 opener-only -> absent
        assert closes == {1: 28.75}
        assert SN.hr_closes(s, [1, 2], kicks) == {1: 29.0}
        assert SN.hr_close_prices(s, [1, 2], kicks) == {1: -115}
        # Friday 19:45Z: DK's Thursday 30.5 and HR's Thursday 31.0 are the quotes then;
        # game 2's opener (Friday 03:00Z) was on the board at the clock too -- a decision
        # line exists for it even though no real close ever does
        assert SN.decision_lines(s, [1, 2], kicks) == {1: 30.75, 2: 40.5}
        assert SN.decision_lines(s, [1], {}) == {}  # no kickoff -> no provable clock
        assert SN.decision_lines(s, [], kicks) == {}


# --- CLI refuses before the database -----------------------------------------------------------------


def test_cli_refuses_an_unknown_row_before_touching_the_database(
    load_script, monkeypatch, tmp_path
):
    mod = load_script("harness_report")

    def boom(*a, **k):
        raise AssertionError("try_init_db must not be called for a refused row")

    monkeypatch.setattr(mod, "try_init_db", boom)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "s.md"))
    assert mod.main(["--row", "NOPE"]) == 2
    assert "HARNESS REFUSED" in (tmp_path / "s.md").read_text()
    assert mod.main(["--row", "H-NEGGAP-L"]) == 2  # live-tracking
    assert mod.main(["--row", "H-STOP-2", "--candidate", "os.path:join"]) == 2
    assert mod.main(["--row", "H4G", "--criterion", "beatvegas.grading:under_result"]) == 2
    assert mod.main(["--row", "H-STOP-2", "--decision-rule", "closing"]) == 2


def test_cli_resolves_candidates_only_under_beatvegas(load_script):
    mod = load_script("harness_report")
    fn = mod.resolve_callable("beatvegas.model.bv_line:bv_line_for_slate")
    assert fn is bv_line_for_slate
    with pytest.raises(R.HarnessRefusal):
        mod.resolve_callable("beatvegas.model.bv_line:no_such_function")
    with pytest.raises(R.HarnessRefusal):
        mod.resolve_callable("bv_line_for_slate")
    args = mod.parse_args(["--row", "H-STOP-2"])
    assert args.min_games_train == 0 and args.min_games_score == 0
    assert args.decision_rule == "consensus_as_of(fri_pm)"
    assert os.path.basename(mod.__file__ if hasattr(mod, "__file__") else "harness_report.py")
