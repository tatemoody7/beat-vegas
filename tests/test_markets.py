"""beatvegas/markets.py and the market-aware harness (2026-10-06, Track A):
the first-half default is byte-identical to before; the full-game market
grades at its own window, fits its own target and can count the over."""

import numpy as np
import pandas as pd
import pytest
from test_harness import PRE_ROW, const, first_game_id, hand_frame, spec_for
from test_residual_gate import _frame as residual_frame

from beatvegas import markets as M
from beatvegas.backtest import harness as H
from beatvegas.lines import REAL_1H_CLOSE_WINDOW_H, REAL_FG_CLOSE_WINDOW_H
from beatvegas.model.bv_line import TARGET, bv_line_for_slate
from beatvegas.model.fg_line import bv_fg_line_for_slate


def test_by_key_and_descriptors():
    assert M.by_key("1h") is M.FIRST_HALF and M.by_key("fg") is M.FULL_GAME
    assert M.FIRST_HALF.close_window_h == REAL_1H_CLOSE_WINDOW_H == 2.0
    assert M.FULL_GAME.close_window_h == REAL_FG_CLOSE_WINDOW_H == 3.0
    assert M.FULL_GAME.snapshot_market == "full_game_total" and M.FULL_GAME.ledger_market == "full"
    with pytest.raises(ValueError):
        M.by_key("2h")


def test_actuals_full_game_is_home_plus_away_and_first_half_is_the_trusted_total():
    df = pd.DataFrame(
        {
            "first_half_total": [24.0, 0.0, np.nan],
            "home_points": [30, 14, np.nan],
            "away_points": [20, 10, 7],
            "first_half_source": ["pbp", None, None],
        }
    )
    fg = M.actuals(df, M.FULL_GAME)
    assert fg.tolist()[:2] == [50.0, 24.0] and np.isnan(fg.iloc[2])
    fh = M.actuals(df, M.FIRST_HALF)
    assert fh.iloc[0] == 24.0 and np.isnan(fh.iloc[2])
    out = M.with_target(df, M.FULL_GAME)
    assert out[M.FG_ACTUAL_COL].tolist()[:2] == [50.0, 24.0]
    assert M.with_target(df, M.FIRST_HALF) is df  # nothing added for the champion


def test_grading_takes_the_markets_window_and_refuses_another():
    assert H.Grading(closes={}).window_h == 2.0
    assert H.Grading(closes={}, market=M.FULL_GAME).window_h == 3.0
    assert H.Grading(closes={}, window_h=3.0, market=M.FULL_GAME).window_h == 3.0
    with pytest.raises(H.HarnessRefusal) as e:
        H.Grading(closes={}, window_h=2.0, market=M.FULL_GAME)
    assert "REAL_FG_CLOSE_WINDOW_H" in str(e.value)
    with pytest.raises(H.HarnessRefusal):
        H.Grading(closes={}, window_h=None, market=M.FULL_GAME)


def test_incumbent_arm_per_market_and_identity_for_the_champion():
    assert H.incumbent_arm().scorer is bv_line_for_slate
    assert H.incumbent_arm(M.FIRST_HALF).scorer is bv_line_for_slate
    assert H.incumbent_arm(M.FULL_GAME).scorer is bv_fg_line_for_slate


def test_spec_refuses_an_unknown_side_and_run_refuses_a_market_mismatch():
    with pytest.raises(H.HarnessRefusal):
        H.HarnessSpec(
            row_id="x", arms=(H.Arm("i", const(1), True),), test_seasons=(2025,), side="middle"
        )
    frame, closes = hand_frame()
    spec = H.HarnessSpec(
        row_id=PRE_ROW.id,
        arms=(H.Arm("incumbent", const(27.0), True),),
        test_seasons=(2024, 2025),
        market=M.FULL_GAME,
    )
    with pytest.raises(H.HarnessRefusal, match="full-game"):
        H.run(frame, H.Grading(closes=closes), spec, PRE_ROW, {})


def test_side_over_flips_the_gap_sign_and_counts_the_over_as_the_win():
    frame, closes = hand_frame()
    g1 = first_game_id(frame, 2024, 5)
    grading = H.Grading(closes=closes, hr_closes={g1: 30.5}, hr_prices={g1: -115})
    under = H.run(frame, grading, spec_for(PRE_ROW), PRE_ROW, {})
    over = H.run(frame, grading, spec_for(PRE_ROW, side="over"), PRE_ROW, {})
    pu, po = under.per_game, over.per_game
    assert np.allclose(po["gap_incumbent"], -pu["gap_incumbent"])
    assert (po["outcome"] == pu["outcome"]).all()  # the OUTCOME is the same fact
    u_all = under.report["arms"]["incumbent"]["pooled"]["record_all"]
    o_all = over.report["arms"]["incumbent"]["pooled"]["record_all"]
    assert (u_all["wins"], u_all["losses"]) == (o_all["losses"], o_all["wins"])
    assert over.report["spec"]["side"] == "over" and under.report["spec"]["side"] == "under"
    # favourable line value flips with the side
    assert H.favourable_clv(30.0, 29.0) == 1.0 and H.favourable_clv(30.0, 29.0, "over") == -1.0


def test_full_game_market_grades_home_plus_away_at_the_three_hour_window():
    frame, closes = hand_frame()
    # the hand frame: home 30 + away 20 = 50 on every row; close it at 49 -> every under loses
    fg_closes = {g: 49.0 for g in closes}
    spec = H.HarnessSpec(
        row_id=PRE_ROW.id,
        arms=(H.Arm("incumbent", const(45.0), True),),
        test_seasons=(2024, 2025),
        market=M.FULL_GAME,
    )
    res = H.run(frame, H.Grading(closes=fg_closes, market=M.FULL_GAME), spec, PRE_ROW, {})
    pg = res.per_game
    assert (pg["actual"] == 50.0).all() and (pg["close"] == 49.0).all()
    rec = res.report["arms"]["incumbent"]["pooled"]["record_all"]
    assert rec["wins"] == 0 and rec["losses"] == len(pg)
    assert res.report["grading"]["close_window_h"] == 3.0
    assert res.report["spec"]["market"]["key"] == "fg"
    assert "full-game" in res.report["data_basis"]["close_rule"]


def test_regressor_target_keyword_keeps_the_champion_identical_and_fits_the_full_game():
    df, _ = residual_frame()
    df["h_games_played"] = 5
    df["a_games_played"] = 5
    df["home_points"] = 30
    df["away_points"] = 20
    train, test = df[df["season"] < 2025], df[df["season"] == 2025]
    a = bv_line_for_slate(train, test)
    b = bv_line_for_slate(train, test, target=TARGET)
    assert np.array_equal(a, b)  # the default IS the champion's target
    fg = bv_fg_line_for_slate(train, test)
    assert fg.shape == a.shape and np.all(np.isfinite(fg))
    assert float(np.mean(fg)) == pytest.approx(50.0, abs=1.0)  # every full game is 50 here
    assert not np.allclose(fg, a)
