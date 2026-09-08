"""backtest/residual_gate.py — the one-shot walk-forward gate that decides
whether the residual engine replaces the incumbent. These tests pin the split
guards, the record/cap/overlap arithmetic, the report's must-have lines, and
that the harness can DETECT a planted edge (residual MAE beats the close MAE)
while evaluating the incumbent on the full prior-season set."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beatvegas import postmortem as pm
from beatvegas.backtest import residual_gate as G
from beatvegas.etl.features import FEATURE_COLS
from beatvegas.grading import units_won


def _frame(seasons=range(2016, 2026), per_season=100, seed=11, noise=1.5):
    """fh = close + 2*x - 1 + noise. The residual is a clean function of ONE
    feature (home_fh_off_epa); the close itself is random, so a market-blind
    model cannot recover it but a residual model can."""
    rng = np.random.default_rng(seed)
    rows, closes = [], {}
    gid = 1
    for s in seasons:
        for i in range(per_season):
            row = {c: 0.0 for c in FEATURE_COLS}
            x = rng.normal(0, 1)
            close = float(rng.integers(40, 56)) / 2.0  # 20.0 .. 27.5
            row.update(
                {
                    "id": gid,
                    "season": s,
                    "week": 3 + (i % 10),
                    "start_date": pd.Timestamp(f"{s}-10-01") + pd.Timedelta(days=7 * (i % 10)),
                    "home_team": f"H{gid}",
                    "away_team": f"A{gid}",
                    "home_fh_off_epa": x,
                    "full_game_total": 50.0,
                    "spread": -3.0,
                    "wx_wind_band": float(rng.integers(0, 4)),
                    "era_post2023": 1.0 if s >= 2023 else 0.0,
                    "home_points": 30,
                    "away_points": 20,
                    "first_half_source": "pbp",
                }
            )
            row["first_half_total"] = close + 2 * x - 1 + rng.normal(0, noise)
            row["under"] = int(row["first_half_total"] < close)
            rows.append(row)
            closes[gid] = close
            gid += 1
    return pd.DataFrame(rows), closes


@pytest.fixture(scope="module")
def gate():
    """One evaluate() over the synthetic frame, shared by the report tests."""
    df, closes = _frame()
    stored = {gid: closes[gid] - 1.0 for gid in closes if gid % 2 == 0}  # half the games
    return G.evaluate(df, closes, [2023, 2024], 2025, stored_bv=stored)


# --- walk_forward_split ---------------------------------------------------------


def test_split_partitions_by_season():
    df, _ = _frame(per_season=5)
    train, test = G.walk_forward_split(df, [2023, 2024], 2025)
    assert sorted(train["season"].unique()) == [2023, 2024]
    assert set(test["season"]) == {2025}
    assert not set(train["id"]) & set(test["id"])


def test_split_raises_on_game_id_overlap():
    df, _ = _frame(per_season=5)
    df.loc[df["season"] == 2025, "id"] = df.loc[df["season"] == 2024, "id"].to_numpy()
    with pytest.raises(ValueError, match="game id"):
        G.walk_forward_split(df, [2023, 2024], 2025)


def test_split_raises_when_a_training_kickoff_is_not_before_every_test_kickoff():
    df, _ = _frame(per_season=5)
    # a 2024-tagged row that kicks off during the 2025 test season
    late = df[df["season"] == 2024].index[0]
    df.loc[late, "start_date"] = pd.Timestamp("2025-10-01")  # equal to the first test kick
    with pytest.raises(ValueError, match="kickoff"):
        G.walk_forward_split(df, [2023, 2024], 2025)


def test_split_raises_when_the_test_season_is_empty():
    df, _ = _frame(per_season=5)
    with pytest.raises(ValueError, match="test season"):
        G.walk_forward_split(df, [2023, 2024], 2030)


# --- record / cap_picks / overlap ------------------------------------------------


def _hand_frame():
    """12 games, one week: 7 unders, 4 overs, 1 push at the close."""
    fh = [20, 21, 22, 23, 24, 25, 26, 30, 31, 32, 33, 27.5]
    close = [27.5] * 12
    return pd.DataFrame(
        {
            "game_id": range(1, 13),
            "season": 2025,
            "week": 5,
            "kickoff": pd.to_datetime(["2025-10-04T20:00"] * 12),
            "close": close,
            "actual": fh,
            "outcome": [G.under_result(a, c) for a, c in zip(fh, close)],
            "units": [units_won(a, c) for a, c in zip(fh, close)],
        }
    )


def test_record_math_on_a_hand_built_frame():
    df = _hand_frame()
    r = G.record(df, pd.Series(True, index=df.index))
    assert (r["n"], r["wins"], r["losses"], r["pushes"]) == (12, 7, 4, 1)
    assert r["hit_rate"] == pytest.approx(7 / 11)
    assert r["units"] == pytest.approx(7 * (100 / 110) - 4)
    assert r["roi"] == pytest.approx((7 * (100 / 110) - 4) / 12)
    lo, hi = pm.wilson_ci(7, 11)
    assert (r["ci_lo"], r["ci_hi"]) == (pytest.approx(lo), pytest.approx(hi))


def test_record_empty_mask():
    df = _hand_frame()
    r = G.record(df, pd.Series(False, index=df.index))
    assert r["n"] == 0 and r["hit_rate"] is None and r["roi"] is None
    assert r["ci_lo"] is None and r["units"] == 0.0


def test_cap_picks_top_five_per_week_with_kickoff_then_game_id_tiebreak():
    df = pd.DataFrame(
        {
            "game_id": [1, 2, 3, 4, 5, 6, 7, 8, 9],
            "season": 2025,
            "week": [5] * 7 + [6, 6],
            "kickoff": pd.to_datetime(
                ["2025-10-04T20:00"] * 5
                + ["2025-10-02T20:00", "2025-10-04T20:00"]
                + ["2025-10-11T20:00"] * 2
            ),
            "g": [4.0, 3.0, 2.0, 2.0, 2.0, 2.0, 1.75, 1.8, 1.0],
        }
    )
    picked = set(df.loc[G.cap_picks(df, "g"), "game_id"])
    # week 5: 1, 2, then four games tied at 2.0 for three slots -> the Thursday
    # game (6) first, then ids 3 and 4; game 5 and the 1.75 game (7) drop.
    # week 6: only game 8 clears 1.75.
    assert picked == {1, 2, 6, 3, 4, 8}


def test_cap_picks_ignores_nan_and_sub_threshold_gaps():
    df = pd.DataFrame(
        {
            "game_id": [1, 2, 3],
            "season": 2025,
            "week": 5,
            "kickoff": pd.to_datetime(["2025-10-04"] * 3),
            "g": [np.nan, 1.74, 1.75],
        }
    )
    assert list(G.cap_picks(df, "g")) == [False, False, True]


def test_overlap_counts_and_jaccard():
    a = pd.Series([True, True, True, False, False])
    b = pd.Series([True, False, False, True, False])
    o = G.overlap(a, b)
    assert (o["both"], o["only_a"], o["only_b"]) == (1, 2, 1)
    assert (o["n_a"], o["n_b"]) == (3, 2)
    assert o["jaccard"] == pytest.approx(1 / 4)
    assert G.overlap(pd.Series([False]), pd.Series([False]))["jaccard"] is None


# --- evaluate on planted structure ----------------------------------------------


def test_evaluate_detects_the_planted_edge_and_trains_the_incumbent_on_all_priors(gate):
    rep = gate.report
    res, inc = rep["engines"]["residual"], rep["engines"]["incumbent"]
    # the harness can see an edge when one exists
    assert res["mae"] < rep["close_mae"]
    assert res["mae"] < 0.8 * rep["close_mae"]
    # the residual trained on the 2023-24 real-close rows only ...
    assert res["train_seasons"] == [2023, 2024] and res["n_train"] == 200
    assert rep["fingerprint"]["n_rows"] == 200 and rep["fingerprint"]["seasons"] == [2023, 2024]
    # ... while the incumbent trained on EVERY played prior season, as in production
    assert inc["train_seasons"] == list(range(2016, 2025)) and inc["n_train"] == 900
    assert rep["bv_train_seasons"] == "all"
    # a market-blind model cannot recover a random close: it does not beat the market
    assert inc["mae"] > rep["close_mae"]
    assert rep["test_season"] == 2025 and rep["n_test"] == 100


def test_evaluate_per_game_columns_and_gap_identities(gate):
    pg = gate.per_game
    assert len(pg) == 100 and pg["season"].eq(2025).all()
    for col in (
        "game_id",
        "kickoff",
        "close",
        "actual",
        "outcome",
        "units",
        "pred_resid",
        "gap_resid",
        "pred_bv",
        "gap_bv",
        "pred_stored",
        "gap_stored",
        "cap5_resid",
        "cap5_bv",
        "gap175_resid",
        "gap175_bv",
    ):
        assert col in pg.columns, col
    np.testing.assert_allclose(pg["gap_resid"], pg["close"] - pg["pred_resid"])
    np.testing.assert_allclose(pg["gap_bv"], pg["close"] - pg["pred_bv"])
    # stored predictions were supplied for half the games, at close - 1 -> gap 1.0
    st = pg["gap_stored"].dropna()
    assert len(st) == 50 and np.allclose(st, 1.0)
    # outcome/units come from grading at the close, -110
    assert set(pg["outcome"]) <= {"under", "over", "push"}
    win = pg["outcome"] == "under"
    assert np.allclose(pg.loc[win, "units"], 100 / 110)


def test_evaluate_records_and_caps_are_consistent(gate):
    rep, pg = gate.report, gate.per_game
    for eng in ("residual", "incumbent"):
        sel = rep["engines"][eng]["selections"]
        assert set(sel) == {"all", "gap175", "cap5"}
        assert sel["all"]["n"] == 100
        assert sel["cap5"]["n"] <= sel["gap175"]["n"]
    # stored only covers half the games (planted fixture); its "all" is
    # masked to that coverage subset, not the full 100-game test universe.
    stored_sel = rep["engines"]["stored"]["selections"]
    assert set(stored_sel) == {"all", "gap175", "cap5"}
    assert stored_sel["all"]["n"] == 50
    assert stored_sel["cap5"]["n"] <= stored_sel["gap175"]["n"]
    # cap5 is at most 5 per week
    assert pg.groupby("week")["cap5_resid"].sum().max() <= 5
    assert pg.groupby("week")["cap5_bv"].sum().max() <= 5
    # the market benchmark is the blanket under at the close
    assert rep["engines"]["residual"]["selections"]["all"] == rep["market"]["all"]
    # overlap block names both engines
    assert set(rep["overlap"]) == {"cap5", "gap175"}
    assert rep["overlap"]["cap5"]["a"] == "residual" and rep["overlap"]["cap5"]["b"] == "incumbent"


def test_stored_engine_reports_its_own_coverage(gate):
    rep = gate.report
    st = rep["engines"]["stored"]
    assert st["coverage_n"] == 50 and st["coverage_n_total"] == 100
    # mae/bias/calibration are computed on the covered subset only
    assert sum(c["n"] for c in st["calibration"]) == 50


def test_evaluate_match_trains_the_incumbent_on_the_same_seasons():
    df, closes = _frame(per_season=40)
    rep = G.evaluate(df, closes, [2023, 2024], 2025, bv_train_seasons="match").report
    assert rep["engines"]["incumbent"]["train_seasons"] == [2023, 2024]
    assert rep["engines"]["incumbent"]["n_train"] == 80
    assert rep["bv_train_seasons"] == "match"
    assert "stored" not in rep["engines"]


def test_evaluate_calibration_bands_and_bias(gate):
    res = gate.report["engines"]["residual"]
    labels = [b[2] for b in pm.GAP_BANDS]
    assert res["calibration"] and all(c["band"] in labels for c in res["calibration"])
    assert sum(c["n"] for c in res["calibration"]) == 100
    assert res["bias_train"] is not None and res["bias_test"] is not None
    assert abs(res["bias_test"]) < 1.0  # planted noise is zero-mean


def test_evaluate_report_is_json_serialisable(gate):
    import json

    json.dumps(gate.report)


# --- render_markdown ------------------------------------------------------------


def test_render_markdown_has_both_cap5_lines_the_close_benchmark_and_caveats(gate):
    md = G.render_markdown(gate.report)
    assert "| residual | cap5 |" in md
    assert "| incumbent | cap5 |" in md
    assert "| stored | cap5 |" in md
    assert "Close MAE" in md and "benchmark" in md
    assert "## Caveats" in md
    for phrase in (
        "one-shot",
        "do not tune",
        "us-region consensus",
        "not Hard Rock",
        "every played prior season",
        "2023-24 real-close rows",
        "matching how production refits it",
        # MAE anchoring (fix 1): the residual's MAE is anchored to the close.
        "low bar for the residual",
        "Weight the record comparison",
        # gap scale (fix 3): fixed threshold, different gap spreads.
        "Gap scale differs by construction",
        "not the same bet volume",
        # residual fit floor vs production floor (fix 5).
        "falls back to the incumbent",
        # stored coverage (fix 2), printed in the stored engine's own section.
        "Stored coverage: 50 of 100 test games",
    ):
        assert phrase in md, phrase
    # caveat 3 (asymmetric training) reads as one sentence, not two stacked
    # parentheticals back to back.
    assert "(how production refits it) (" not in md
    assert "## Fingerprint" in md and gate.report["fingerprint"]["feature_hash"] in md


def test_render_markdown_without_stored():
    df, closes = _frame(per_season=40)
    rep = G.evaluate(df, closes, [2023, 2024], 2025).report
    md = G.render_markdown(rep)
    assert "| stored |" not in md and "| residual | cap5 |" in md
