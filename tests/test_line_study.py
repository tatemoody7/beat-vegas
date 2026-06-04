from datetime import datetime

import pandas as pd

from beatvegas.analysis.line_study import (
    assign_opening_line,
    bucket_under_rates,
)


def test_bucket_under_rates_math_and_sort():
    df = pd.DataFrame(
        {
            "line": [24.0, 24.0, 24.0, 24.0, 28.5, 28.5, 28.5, 28.5],
            "line_source": ["proxy"] * 8,
            # 24.0 bucket: 1 under, 1 push(=24), 2 over -> decided=3, under_pct=33.3
            "first_half_total": [
                20,
                24,
                30,
                31,
                # 28.5 bucket: 3 under, 1 over -> 75.0
                20,
                21,
                22,
                35,
            ],
        }
    )
    out = bucket_under_rates(df, min_games=4)
    # higher under% first
    assert list(out["line"]) == [28.5, 24.0]
    top = out.iloc[0]
    assert top["games"] == 4 and top["under"] == 3 and top["under_pct"] == 75.0
    low = out.iloc[1]
    assert low["push"] == 1 and low["under_pct"] == 33.3  # 1 of 3 decided


def test_bucket_min_games_filter():
    df = pd.DataFrame(
        {
            "line": [24.5, 24.5, 30.5],
            "line_source": ["proxy"] * 3,
            "first_half_total": [10, 12, 40],
        }
    )
    out = bucket_under_rates(df, min_games=2)
    assert list(out["line"]) == [24.5]  # 30.5 bucket dropped (1 < 2)


def test_assign_opening_line_prefers_real_then_proxy():
    games = pd.DataFrame(
        {
            "id": [1, 2],
            "full_game_total": [47.0, 60.0],  # proxy: 24.5, 31.0
            "first_half_total": [20, 33],
        }
    )
    # game 1 has snapshots (two books), game 2 has none
    snaps = pd.DataFrame(
        {
            "game_id": [1, 1, 1, 1],
            "book": ["dk", "dk", "fd", "fd"],
            "line": [23.0, 24.0, 24.0, 25.0],  # dk open 23.0, fd open 24.0
            "captured_at": [
                datetime(2025, 10, 1, 9),
                datetime(2025, 10, 3, 9),
                datetime(2025, 10, 1, 9),
                datetime(2025, 10, 3, 9),
            ],
        }
    )
    out = assign_opening_line(games, snaps).set_index("id")
    # game1 real consensus opening = median(23.0, 24.0) = 23.5
    assert out.loc[1, "line"] == 23.5 and out.loc[1, "line_source"] == "real_open"
    # game2 falls back to proxy 0.52*60 = 31.2 -> 31.0
    assert out.loc[2, "line"] == 31.0 and out.loc[2, "line_source"] == "proxy"


def test_assign_opening_line_empty_snapshots_all_proxy():
    games = pd.DataFrame({"id": [1], "full_game_total": [47.0], "first_half_total": [20]})
    out = assign_opening_line(games, pd.DataFrame())
    assert out.loc[0, "line_source"] == "proxy"
    assert out.loc[0, "line"] == 24.5  # 0.52*47=24.44 -> 24.5
