"""config_return_series: per-config return matrix feeding the overfitting controls."""

import pandas as pd

from beatvegas.backtest.engine import WIN_PROFIT, config_return_series


def test_top_fraction_selection_and_returns():
    pg = pd.DataFrame(
        [
            {"season": 2024, "gap": 3.0, "under": 1},  # selected, win
            {"season": 2024, "gap": 2.0, "under": 0},  # selected, loss
            {"season": 2024, "gap": 1.0, "under": 1},  # not selected -> 0
            {"season": 2024, "gap": 0.0, "under": 0},  # not selected -> 0
        ]
    )
    matrix, bets = config_return_series(pg, "gap", "under", [0.5])
    assert len(matrix) == 4 and len(matrix[0]) == 1  # T x N(=1 config)
    col = [row[0] for row in matrix]
    assert col[0] == WIN_PROFIT and col[1] == -1.0
    assert col[2] == 0.0 and col[3] == 0.0  # unselected games contribute nothing
    assert bets[0] == [WIN_PROFIT, -1.0]  # bet-only returns for DSR


def test_per_season_selection_and_multiple_configs():
    pg = pd.DataFrame(
        [
            {"season": 2023, "gap": 5.0, "under": 1},
            {"season": 2023, "gap": 4.0, "under": 0},
            {"season": 2024, "gap": 9.0, "under": 0},
            {"season": 2024, "gap": 8.0, "under": 1},
        ]
    )
    matrix, bets = config_return_series(pg, "gap", "under", [0.5, 1.0])
    assert len(matrix[0]) == 2  # two configs
    # frac=0.5 -> 1 bet per season (the higher gap); frac=1.0 -> both per season.
    assert len(bets[0]) == 2 and len(bets[1]) == 4
