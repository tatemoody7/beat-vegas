"""The live switch to 2003+ training (Tate, 2026-10-07, after H-HIST met):
the champion and the full-game shadow train on 2003+, seasons CFBD never
priced stay as training rows while every scored row still needs a total, early
folds survive inputs that did not exist yet, and the board's tint anchors and
the serve-skew guard stay on the live era."""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
from test_residual_gate import _frame as residual_frame

from beatvegas.etl import features
from beatvegas.model import bv_line, score

ROOT = Path(__file__).resolve().parent.parent


def test_the_constants_are_tates_calls():
    # 2003 went live 2026-10-07 (H-HIST); H-MODEL-FIX (2026-10-10) moves it to
    # 2015, one of the floors H-HIST passed.
    assert score.CHAMPION_TRAIN_MIN_SEASON == 2015
    assert features.CFBD_TOTALS_FROM == 2013
    assert features.FRAME_MIN_SEASON == 2023  # every other frame is unchanged


def test_rows_to_keep():
    df = pd.DataFrame(
        {
            "season": [2005, 2005, 2015, 2015, 2026],
            "full_game_total": [np.nan, 50.0, np.nan, 48.0, np.nan],
        }
    )
    assert features.rows_to_keep(df).tolist() == [False, True, False, True, False]
    assert features.rows_to_keep(df, total_required_from=2013).tolist() == [
        True,
        True,
        False,
        True,
        False,
    ]  # pre-2013 kept; a 2015 or 2026 row without a total is not
    assert features.rows_to_keep(df, require_total=False).all()


def _frame_with_early_gap():
    df, _ = residual_frame(seasons=range(2016, 2027), per_season=80)
    df["h_games_played"] = 5
    df["a_games_played"] = 5
    col = bv_line.BV_FEATURE_COLS[3]
    df.loc[df["season"] < 2020, col] = np.nan  # an input that did not exist yet
    df.loc[df["season"] == 2026, "first_half_total"] = np.nan  # unplayed target week
    df.loc[df["season"] == 2026, "under"] = np.nan
    return df


def test_score_slate_survives_an_input_missing_from_early_seasons():
    df = _frame_with_early_gap()
    out = score.score_slate(2026, target_week=3, df=df, engine="bv_line")
    assert len(out) > 0 and np.all(np.isfinite(out["bv_line"]))
    assert out["bv_sigma"].notna().all()


def test_factor_refs_are_computed_on_the_live_era_only(monkeypatch):
    seen = {}

    def spy(frame):
        seen["min"] = int(frame["season"].min())
        return {}

    monkeypatch.setattr(score, "factor_references", spy)
    score.score_slate(2026, target_week=3, df=_frame_with_early_gap(), engine="bv_line")
    assert seen["min"] == features.FRAME_MIN_SEASON


def test_live_scorers_read_the_champion_floor_and_guard_the_live_era():
    for name in ("weekly_update.py", "fg_shadow.py"):
        src = (ROOT / "scripts" / name).read_text()
        assert "min_season=CHAMPION_TRAIN_MIN_SEASON" in src, name
        assert "total_required_from=CFBD_TOTALS_FROM" in src, name
        assert 'df["season"] >= FRAME_MIN_SEASON' in src, name
    src = inspect.getsource(score.score_slate)
    assert src.count("drop_all_nan=True") >= 3
