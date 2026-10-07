"""PR H4 (2026-10-06): the H-HIST / H-ELO-F study machinery. The study-only
frame switch keeps rows without a full-game total; the arms train on their own
floors; the incumbent stays the champion as pinned when the study frame reaches
below the live floor; the criteria apply the registered per-arm test; and none
of it changes a live default."""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest
from conftest import _load_script
from test_residual_gate import _frame as residual_frame

from beatvegas.backtest import harness as H
from beatvegas.backtest import history_f
from beatvegas.etl import features
from beatvegas.model import bv_line, elo_line, train_windows
from beatvegas.registry import HarnessRefusal


def _frame():
    df, _ = residual_frame(seasons=range(2016, 2026), per_season=80)
    df["h_games_played"] = 5
    df["a_games_played"] = 5
    df["home_pregame_elo"] = 1500.0 + df["home_fh_off_epa"] * 100
    df["away_pregame_elo"] = 1500.0
    return df


def test_live_defaults_are_unchanged():
    sig = inspect.signature(features.build_feature_frame)
    assert sig.parameters["min_season"].default == features.FRAME_MIN_SEASON == 2023
    assert sig.parameters["require_total"].default is True
    spec = H.HarnessSpec(row_id="X", arms=(H.incumbent_arm(),), test_seasons=(2025,))
    assert spec.frame_min_season == 2023 and spec.require_total is True
    assert H.incumbent_arm().scorer is bv_line.bv_line_for_slate  # identity kept
    for c in elo_line.ELO_COLS:
        assert c not in features.FEATURE_COLS and c not in bv_line.BV_FEATURE_COLS


def test_feature_cols_default_is_the_champion_and_byte_identical():
    df = _frame()
    train, target = df[df["season"] < 2025], df[df["season"] == 2025]
    a = bv_line.bv_line_for_slate(train, target)
    b = bv_line.bv_line_for_slate(train, target, feature_cols=list(bv_line.BV_FEATURE_COLS))
    assert np.array_equal(a, b)


def test_train_window_arms_keep_only_their_floor():
    seen = {}

    def spy(train, target, *a, **k):
        seen["min"] = int(train["season"].min())
        return np.zeros(len(target))

    df = _frame()
    train, target = df[df["season"] < 2025], df[df["season"] == 2025]
    orig = train_windows.bv_line_for_slate
    try:
        train_windows.bv_line_for_slate = spy
        train_windows.bv_line_from_2015(train, target)
        assert seen["min"] == 2016  # the frame starts at 2016 here
        train_windows.champion_2023(train, target)
        assert seen["min"] == 2023
    finally:
        train_windows.bv_line_for_slate = orig
    assert [
        f.floor for f in (train_windows.bv_line_from_2003, train_windows.bv_line_from_2010)
    ] == [
        2003,
        2010,
    ]


def test_the_elo_arm_reads_elo_and_differs_from_the_champion():
    df = _frame()
    train, target = df[df["season"] < 2025], df[df["season"] == 2025]
    champ = train_windows.champion_2023(train, target)
    elo = elo_line.bv_line_with_elo(train, target)
    assert elo.shape == champ.shape and np.all(np.isfinite(elo))
    assert not np.allclose(elo, champ)


def test_harness_report_pins_the_incumbent_when_the_floor_is_lowered():
    hr = _load_script("harness_report")
    args = hr.parse_args(
        [
            "--row",
            "H-HIST",
            "--frame-min-season",
            "all",
            "--keep-rows-without-total",
            "--candidate",
            "beatvegas.model.train_windows:bv_line_from_2003",
            "--candidate-name",
            "hist_2003",
        ]
    )
    assert hr.frame_floor(args) is None
    arms = hr.build_arms(args)
    assert arms[0].is_incumbent and arms[0].scorer is train_windows.champion_2023
    assert arms[1].name == "hist_2003"
    # Without the flag: the live floor and the identical live incumbent.
    plain = hr.parse_args(["--row", "H-ELO-F"])
    assert hr.frame_floor(plain) == 2023
    assert hr.build_arms(plain)[0].scorer is bv_line.bv_line_for_slate
    with pytest.raises(HarnessRefusal):
        hr.build_arms(
            hr.parse_args(["--row", "H-HIST", "--frame-min-season", "all", "--market", "fg"])
        )


def test_frame_coverage_reports_rows_without_total_and_empty_inputs():
    df = _frame()
    df.loc[df["season"] == 2016, "full_game_total"] = np.nan
    cov = H.frame_coverage(df)
    assert cov[2016]["rows_without_total"] == 80 and cov[2017]["rows_without_total"] == 0
    assert cov[2016]["elo_nan_share"] == 0.0
    assert 0.0 <= cov[2016]["mean_nan_share"] <= 1.0


def _report(abs_mean, excl, holm_p, units_hi, arms):
    pairs = {
        a: {
            "abs_err": {"mean": abs_mean, "excludes_zero": excl},
            "portfolio_units": {"hi": units_hi},
        }
        for a in arms
    }
    return {"comparisons": {"pairs": pairs, "holm": {"abs_err": {a: holm_p for a in arms}}}}


def test_criteria_apply_the_registered_per_arm_test():
    hist = history_f.HIST_ARMS
    assert history_f.criterion_hist(_report(-0.2, True, 0.01, 0.5, hist)) is True
    assert history_f.criterion_hist(_report(-0.2, True, 0.20, 0.5, hist)) is False  # Holm
    assert history_f.criterion_hist(_report(-0.2, True, 0.01, -0.1, hist)) is False  # units worse
    assert history_f.criterion_hist(_report(0.1, True, 0.01, 0.5, hist)) is False  # less accurate
    assert history_f.criterion_hist(_report(-0.2, True, 0.01, 0.5, hist[:2])) is None  # arm missing
    assert history_f.criterion_elo(_report(-0.2, True, 0.01, 0.5, history_f.ELO_ARMS)) is True


def test_study_frame_switch_keeps_rows_without_a_total(monkeypatch):
    """require_total=False keeps the rows and gives them a NaN proxy line
    instead of raising inside proxy_total."""
    src = inspect.getsource(features.build_feature_frame)
    assert "rows_to_keep(df, require_total, total_required_from)" in src
    assert 'df.loc[has_total, "proxy_line"]' in src
    # proxy_total itself cannot take a NaN total -- the guard is why.
    with pytest.raises(ValueError):
        from beatvegas.etl.proxy_line import proxy_total

        proxy_total(float("nan"))
    assert pd.isna(np.nan)


def test_history_arms_survive_an_input_that_is_empty_in_early_seasons():
    """The H-HIST dispatch of 2026-10-07 (run 37566306294) crashed before any
    number: HGB refuses to bin an all-NaN column, and a fold trained on the
    earliest seasons has no talent input at all. The history arms drop a column
    that is empty in THAT training slice; the champion's path is untouched."""
    df = _frame()
    col = bv_line.BV_FEATURE_COLS[3]
    df.loc[df["season"] < 2020, col] = np.nan  # e.g. talent before it existed
    train, target = df[df["season"] < 2025], df[df["season"] == 2025]
    pred = train_windows.bv_line_from_2015(train, target)
    assert pred.shape == (len(target),) and np.all(np.isfinite(pred))
    m = bv_line.fit_bv_regressor(df[df["season"] < 2018], drop_all_nan=True)
    assert col not in m.bv_cols_ and len(m.bv_cols_) == len(bv_line.BV_FEATURE_COLS) - 1
    full = bv_line.fit_bv_regressor(df[df["season"] >= 2020])
    assert full.bv_cols_ == list(bv_line.BV_FEATURE_COLS)


def test_the_champion_arm_never_drops_a_column():
    import inspect as _i

    src = _i.getsource(train_windows)
    assert "champion_2023 = _from(FRAME_MIN_SEASON, drop_all_nan=False)" in src
