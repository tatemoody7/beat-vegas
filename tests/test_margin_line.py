"""H-MARGIN (2026-10-07): the margin regressor's target, the Vegas sign, the
Pick'em measures on a hand-worked example, and the walk-forward on synthetic
data (no network, no DB)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from beatvegas.model.bv_line import BV_FEATURE_COLS
from beatvegas.model.margin_line import (
    MARGIN_ACTUAL_COL,
    MARGIN_MODEL_VERSION,
    bv_margin_for_slate,
    margin_metrics,
    played_margin,
    vegas_margin,
    with_margin,
)
from beatvegas.model.score import CHAMPION_READ_VERSIONS

_ROOT = Path(__file__).resolve().parent.parent


def test_target_is_home_minus_away_and_unplayed_rows_drop():
    df = pd.DataFrame({"home_points": [31, 10, None], "away_points": [24, 17, 3]})
    m = with_margin(df)
    assert m[MARGIN_ACTUAL_COL].tolist()[:2] == [7.0, -7.0]
    assert np.isnan(m[MARGIN_ACTUAL_COL].iloc[2])
    assert len(played_margin(df)) == 2


def test_vegas_margin_is_minus_the_home_relative_spread():
    # CFBD: negative spread = home favored; -7 means home by 7.
    assert vegas_margin(pd.Series([-7.0, 3.5])).tolist() == [7.0, -3.5]


def test_the_margin_model_is_never_a_champion_read():
    assert MARGIN_MODEL_VERSION == "bv_margin_v1"
    assert MARGIN_MODEL_VERSION not in CHAMPION_READ_VERSIONS


def test_metrics_on_a_hand_worked_example():
    # game 1: model home by 10, Vegas home by 7, actual home by 14 -> model closer,
    #         both right straight up, model took home ATS and home covered.
    # game 2: model away by 3 (-3), Vegas home by 2, actual away by 4 (-4) ->
    #         model right SU, Vegas wrong; model took away ATS and away covered.
    m = margin_metrics([10.0, -3.0], [14.0, -4.0], [7.0, 2.0], n_boot=200)
    assert m["n"] == 2
    assert m["model"]["mae"] == pytest.approx((4 + 1) / 2)
    assert m["vegas"]["mae"] == pytest.approx((7 + 6) / 2)
    assert m["model"]["su"]["pct"] == 1.0 and m["vegas"]["su"]["pct"] == 0.5
    assert m["model"]["ats"]["pct"] == 1.0
    assert m["mae_diff"]["mean"] == pytest.approx(2.5 - 6.5)


def test_metrics_skip_rows_missing_any_value_and_ties():
    m = margin_metrics([5.0, 0.0, np.nan], [3.0, 7.0, 1.0], [5.0, 1.0, 2.0], n_boot=50)
    assert m["n"] == 2  # the NaN row is dropped
    # row 1: model == Vegas -> no ATS side; row 2: model 0 -> no SU call.
    # ATS counts row 2 only: model 0 vs Vegas home by 1 -> away side; home won by
    # 7 -> home covered -> a loss, 0 of 1.
    assert m["model"]["ats"]["pct"] == 0.0
    assert m["model"]["su"]["pct"] == 1.0  # only row 1 called: home by 5, home won by 3


def _synthetic(seasons=(2022, 2023, 2024, 2025), per=60, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    gid = 0
    for s in seasons:
        for _ in range(per):
            gid += 1
            feats = {c: rng.normal() for c in BV_FEATURE_COLS}
            strength = feats[BV_FEATURE_COLS[0]] * 6
            margin = strength + rng.normal(0, 3)
            hp = 28 + margin / 2
            rows.append(
                {
                    "id": gid,
                    "season": s,
                    "week": 5,
                    "home_points": hp,
                    "away_points": hp - margin,
                    "spread": -(strength + rng.normal(0, 1)),
                    **feats,
                }
            )
    return pd.DataFrame(rows)


def test_walk_forward_learns_a_margin_from_prior_seasons_only():
    df = _synthetic()
    train, test = df[df["season"] < 2025], df[df["season"] == 2025]
    pred = bv_margin_for_slate(train, test)
    assert len(pred) == len(test)
    actual = with_margin(test)[MARGIN_ACTUAL_COL]
    assert np.corrcoef(pred, actual)[0, 1] > 0.6  # it found the planted signal


def _load_backtest():
    spec = importlib.util.spec_from_file_location(
        "margin_backtest", _ROOT / "scripts" / "margin_backtest.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backtest_reports_each_test_season_and_pooled():
    mod = _load_backtest()
    res = mod.backtest(_synthetic(), seasons=(2024, 2025))
    rows = res.pop("_rows")
    assert res["2024"]["n"] == 60 and res["2025"]["n"] == 60 and res["pooled"]["n"] == 120
    assert res["2025"]["train_seasons"] == "2022-2024"
    assert set(rows.columns) >= {"pred", "vegas", MARGIN_ACTUAL_COL}
    assert "| pooled | 120 |" in mod.render(res, "fp")
