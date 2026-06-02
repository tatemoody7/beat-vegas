from datetime import datetime

import pandas as pd

from beatvegas.etl.situational import _flag, _rest_days, haversine


def test_haversine_known_distance():
    # NYC -> LA is ~2450 miles
    d = haversine(40.71, -74.00, 34.05, -118.24)
    assert 2400 < d < 2500


def test_haversine_missing_returns_none():
    assert haversine(None, -74, 34, -118) is None
    assert haversine(40, float("nan"), 34, -118) is None


def test_flag():
    assert _flag(4, lambda x: x < 6) == 1     # short week
    assert _flag(7, lambda x: x < 6) == 0
    assert _flag(None, lambda x: x < 6) is None


def test_rest_days_uses_only_prior_game():
    games = pd.DataFrame({
        "id": [1, 2, 3],
        "season": [2025, 2025, 2025],
        "start_date": pd.to_datetime(
            ["2025-09-06", "2025-09-13", "2025-09-20"]),
        "home_team": ["Iowa", "Iowa", "Ohio State"],
        "away_team": ["Utah State", "Iowa State", "Iowa"],
    })
    rest = _rest_days(games).set_index(["id", "team"])["rest_days"]
    assert pd.isna(rest[(1, "Iowa")])              # first game, no prior
    assert rest[(2, "Iowa")] == 7                  # 9/13 - 9/6
    assert rest[(3, "Iowa")] == 7                  # 9/20 - 9/13 (away game)
