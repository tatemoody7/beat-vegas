"""H-MODEL-FIX (docs/HYPOTHESES.md, Tate 2026-10-10): the bowl-game leak, the
seed's extra season, explicit early stopping and the run record of what the
slate's fit did."""

import numpy as np
import pandas as pd

from beatvegas.backtest import model_fix as MF
from beatvegas.etl import features
from beatvegas.model import bv_line


def _season_with_bowl():
    """One team, one season: week 1 scores 10, week 2 scores 20, week 3 scores 30,
    and a bowl filed as CFBD files it -- week 1, played in December -- scoring 70."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "season": [2019] * 4,
            "week": [1, 2, 3, 1],
            "start_date": pd.to_datetime(["2019-08-31", "2019-09-07", "2019-09-14", "2019-12-28"]),
            "team": ["A"] * 4,
            "fh_pf": [10.0, 20.0, 30.0, 70.0],
            "fh_pa": [0.0] * 4,
            "full_pf": [0.0] * 4,
            "full_pa": [0.0] * 4,
            "season_type": ["regular", "regular", "regular", "postseason"],
        }
    )


def test_the_week_ordered_mean_leaked_the_bowl_into_the_regular_season():
    legacy = features._season_to_date(_season_with_bowl(), by_date=False).set_index("id")
    # Week 2's mean read week 1 AND the December bowl: (10 + 70) / 2.
    assert legacy.loc[2, "fh_pf_std"] == 40.0


def test_the_date_ordered_mean_never_reads_a_later_game():
    fixed = features._season_to_date(_season_with_bowl(), by_date=True).set_index("id")
    assert pd.isna(fixed.loc[1, "fh_pf_std"])
    assert fixed.loc[2, "fh_pf_std"] == 10.0
    assert fixed.loc[3, "fh_pf_std"] == 15.0
    assert fixed.loc[4, "fh_pf_std"] == 20.0  # the bowl reads the whole regular season


def test_postseason_games_leave_the_frame_and_a_fixture_without_a_type_is_kept():
    games = _season_with_bowl()
    assert features._drop_postseason(games)["id"].tolist() == [1, 2, 3]
    assert features._drop_postseason(games.drop(columns="season_type"))["id"].tolist() == [
        1,
        2,
        3,
        4,
    ]


def test_the_seed_reads_one_season_before_the_floor_and_only_with_a_seed():
    assert features._seed_load_from(2015, 3.0) == 2014
    assert features._seed_load_from(2015, 0.0) == 2015
    assert features._seed_load_from(None, 3.0) is None


def test_early_stopping_is_off_and_stated():
    assert bv_line.EARLY_STOPPING is False
    assert bv_line._new_regressor().early_stopping is False


def test_the_slate_fit_records_its_trees_and_early_stopping():
    rng = np.random.default_rng(7)
    n = 240
    frame = pd.DataFrame({c: rng.normal(size=n) for c in bv_line.BV_FEATURE_COLS})
    frame["season"] = np.repeat([2024, 2025], n // 2)
    frame[bv_line.TARGET] = 24 + 3 * frame[bv_line.BV_FEATURE_COLS[0]] + rng.normal(size=n)
    train, target = frame[frame["season"] == 2024], frame[frame["season"] == 2025]
    preds = bv_line.bv_line_for_slate(train, target)
    assert len(preds) == len(target)
    assert bv_line.LAST_FIT["n_iter"] == 300  # every tree grows: no silent early stop
    assert bv_line.LAST_FIT["early_stopping"] == "False"
    assert bv_line.LAST_FIT["train_rows"] == len(train)


# --- the study (scripts/model_fix_study.py, beatvegas/backtest/model_fix.py) ---


def _report(hi):
    return {"comparisons": {"pairs": {MF.CANDIDATE_NAME: {"abs_err": {"hi": hi}}}}}


def test_the_criterion_is_the_frozen_non_inferiority_margin():
    assert MF.NON_INFERIORITY_MARGIN == 0.10
    assert MF.criterion(_report(0.10)) is True
    assert MF.criterion(_report(-0.30)) is True
    assert MF.criterion(_report(0.11)) is False
    assert MF.criterion(_report(None)) is None
    assert MF.criterion({}) is None


def _frame(seasons, n_per=120, seed=7):
    rng = np.random.default_rng(seed)
    n = n_per * len(seasons)
    df = pd.DataFrame({c: rng.normal(size=n) for c in bv_line.BV_FEATURE_COLS})
    df["season"] = np.repeat(seasons, n_per)
    df["id"] = np.arange(1, n + 1)
    df[bv_line.TARGET] = 24 + 3 * df[bv_line.BV_FEATURE_COLS[0]] + rng.normal(size=n)
    df["under"] = 1.0
    return df


def test_the_incumbent_scorer_reads_its_own_frame_with_the_pre_fix_early_stopping():
    legacy = _frame([2023, 2024])
    score = MF.incumbent_scorer(legacy)
    target = legacy[legacy["season"] == 2024].sample(frac=1.0, random_state=1)
    preds = score(None, target[["id", "season"]])
    assert len(preds) == len(target)
    assert bv_line.LAST_FIT["early_stopping"] == "auto"
    assert bv_line.LAST_FIT["train_rows"] == 120  # 2023 only: seasons before the target's
    assert bv_line.EARLY_STOPPING is False  # restored after the fit


def test_the_incumbent_scorer_refuses_a_game_its_frame_lacks():
    score = MF.incumbent_scorer(_frame([2023, 2024]))
    try:
        score(None, pd.DataFrame({"id": [999999], "season": [2024]}))
    except ValueError as e:
        assert "missing from the incumbent's frame" in str(e)
    else:
        raise AssertionError("a game outside the incumbent's frame must be refused")


def test_the_extras_render_the_readings():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "model_fix_study", Path(__file__).resolve().parents[1] / "scripts" / "model_fix_study.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    per_game = pd.DataFrame(
        {
            "game_id": range(1, 21),
            "season": [2026] * 20,
            "week": [6] * 20,
            "home_team": ["H"] * 20,
            "away_team": ["A"] * 20,
            "actual": np.linspace(10, 40, 20),
            "close": np.linspace(20, 30, 20),
            "pred_incumbent": np.linspace(15, 45, 20),
            "pred_model_fix": np.linspace(18, 32, 20),
        }
    )
    legacy = pd.DataFrame({"id": range(1, 21), "proj_1h_total": np.linspace(15, 40, 20)})
    md = mod.extras(per_game, legacy)
    assert "## H-MODEL-FIX readings (reported, never gated)" in md
    assert "### By the raw season-to-date projection" in md
    assert "### Week 6 of 2026, side by side" in md
    assert "more than 6 points from the consensus close" in md
