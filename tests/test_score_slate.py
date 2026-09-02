"""score_slate must score an UPCOMING week — games that have a full-game total
(the Sunday opener) but no first-half result yet. Before this fix the feature
frame dropped every unplayed game, so the target slice was always empty and
weekly_update printed "no scorable games" for every live week."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from beatvegas.etl.features import FEATURE_COLS, apply_min_games, training_frame
from beatvegas.model import score as score_mod


def _frame(seasons=range(2016, 2026), per_season=80, seed=3) -> pd.DataFrame:
    """Played seasons with a clean 1H target + ONE upcoming 2026 wk5 game with
    first_half_total NaN (unplayed) and a full-game total (opener captured)."""
    rng = np.random.default_rng(seed)
    rows = []
    gid = 1
    for s in seasons:
        for i in range(per_season):
            row = {c: 0.0 for c in FEATURE_COLS}
            x1, x2 = rng.normal(0, 1), rng.normal(0, 1)
            row.update(
                {
                    "id": gid,
                    "season": s,
                    "week": 3 + (i % 10),
                    "home_team": f"H{i}",
                    "away_team": f"A{i}",
                    "combined_off_ppa": x1,
                    "combined_def_ppa": x2,
                    "combined_sec_play": rng.uniform(20, 32),
                    "wx_dome": float(rng.integers(0, 2)),
                    "era_post2023": 1.0 if s >= 2023 else 0.0,
                    "full_game_total": 50.0 + 2 * x1,
                    "spread": -3.0,
                    "h_games_played": 5,
                    "a_games_played": 5,
                }
            )
            fh = 24 + 3 * x1 - 2 * x2 + rng.normal(0, 1.5)
            row["first_half_total"] = fh
            row["proxy_line"] = 0.52 * row["full_game_total"]
            row["under"] = float(fh < row["proxy_line"])
            rows.append(row)
            gid += 1
    df = pd.DataFrame(rows)
    # A played game whose 1H result is missing (e.g. a cancelled game that still
    # carries a total): must be EXCLUDED from training, not treated as an over.
    bad = df.iloc[0].copy()
    bad["id"] = 900_000
    bad["season"] = 2024
    bad["first_half_total"] = np.nan
    bad["under"] = np.nan
    # The upcoming game: full-game total captured, no result yet.
    up = df.iloc[1].copy()
    up["id"] = 999_999
    up["season"] = 2026
    up["week"] = 5
    up["home_team"], up["away_team"] = "Kansas State", "Kansas"
    up["first_half_total"] = np.nan
    up["under"] = np.nan
    up["full_game_total"] = 48.5
    return pd.concat([df, bad.to_frame().T, up.to_frame().T], ignore_index=True).astype(
        {c: float for c in FEATURE_COLS}
    )


def test_score_slate_scores_the_unplayed_target_week(monkeypatch):
    df = _frame()
    seen = {}
    real = score_mod.bv_line_for_slate

    def spy(train_df, target_df):
        seen["train"] = train_df
        return real(train_df, target_df)

    monkeypatch.setattr(score_mod, "bv_line_for_slate", spy)

    out = score_mod.score_slate(2026, target_week=5, df=df)

    assert len(out) == 1
    r = out.iloc[0]
    assert int(r["id"]) == 999_999
    assert pd.isna(r["under"])  # target keeps an undefined outcome
    for col in ("bv_line", "bv_gap", "under_score", "under_prob", "line", "rank"):
        assert pd.notna(r[col]), col
    assert r["line_kind"] == "proxy"
    assert "is_opportunity" not in out.columns  # sigma gate removed (point gates in verdict)
    assert "is_opportunity" not in score_mod._factors(r, float(r["line"]))

    train = seen["train"]
    assert train["under"].notna().all()
    assert train["first_half_total"].notna().all()
    assert 900_000 not in set(train["id"])
    assert (train["season"] < 2026).all()


def test_training_frame_drops_nan_targets_and_casts_under_to_int():
    df = _frame(seasons=range(2020, 2022), per_season=5)
    tf = training_frame(df)
    assert len(tf) == 10
    assert tf["under"].dtype.kind in "iu"
    assert set(tf["under"].unique()) <= {0, 1}


def test_apply_min_games_filters_both_sides():
    df = pd.DataFrame({"h_games_played": [0, 2, 5], "a_games_played": [5, 1, 5]})
    assert apply_min_games(df, 2)["h_games_played"].tolist() == [5]
    assert len(apply_min_games(df, 0)) == 3


# --- weekly_update exit semantics -------------------------------------------


def _wire(monkeypatch, frame, scored_empty=True):
    from conftest import _load_script

    wu = _load_script("weekly_update")
    monkeypatch.setattr(wu, "try_init_db", lambda: True)
    monkeypatch.setattr(wu, "detect_week", lambda season: 5)
    monkeypatch.setattr(wu, "build_feature_frame", lambda min_games=0: frame)
    monkeypatch.setattr(wu, "opening_line_lookup", lambda season, week: ({}, {}))
    if scored_empty:
        monkeypatch.setattr(wu, "score_slate", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(sys, "argv", ["weekly_update.py", "--season", "2026"])
    return wu


def _target_frame(n_played: int) -> pd.DataFrame:
    """Two 2026 wk5 rows: both have a total; `n_played` of them clear min_games=2."""
    return pd.DataFrame(
        {
            "id": [1, 2],
            "season": [2026, 2026],
            "week": [5, 5],
            "full_game_total": [50.0, 52.0],
            "h_games_played": [2 if i < n_played else 1 for i in range(2)],
            "a_games_played": [2, 2],
        }
    )


def test_weekly_update_exits_zero_when_min_games_filters_everything(monkeypatch, capsys):
    wu = _wire(monkeypatch, _target_frame(n_played=0))
    wu.main()  # no SystemExit
    out = capsys.readouterr().out
    assert "need >= 2 games played" in out


def test_weekly_update_exits_zero_when_week_has_no_totals_yet(monkeypatch, capsys):
    frame = _target_frame(n_played=2)
    frame["week"] = 6  # nothing for wk5 at all
    wu = _wire(monkeypatch, frame)
    wu.main()
    assert "no games with a full-game total" in capsys.readouterr().out


def test_weekly_update_fails_loudly_when_eligible_games_score_to_nothing(monkeypatch, capsys):
    wu = _wire(monkeypatch, _target_frame(n_played=2))
    with pytest.raises(SystemExit) as e:
        wu.main()
    assert e.value.code == 1
    assert "ERROR" in capsys.readouterr().out


def test_weekly_update_passes_min_games_frame_to_score_slate(monkeypatch):
    frame = _target_frame(n_played=1)
    wu = _wire(monkeypatch, frame, scored_empty=False)
    got = {}

    def fake_score(season, target_week=None, line_lookup=None, line_kind_lookup=None, df=None):
        got["df"] = df
        return pd.DataFrame()

    monkeypatch.setattr(wu, "score_slate", fake_score)
    with pytest.raises(SystemExit):  # eligible row scored to nothing -> loud failure
        wu.main()
    assert got["df"]["id"].tolist() == [1]  # the under-min_games row was filtered
