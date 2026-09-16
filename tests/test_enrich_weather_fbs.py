"""enrich_weather fetches forecasts for the games the scorer can read -- FBS vs
FBS -- not the whole division-spanning week. Week 3 of 2026 was 311 games for
57 scored: ~290 sequential Open-Meteo calls and 8 of the Sunday job's 11
minutes, four fifths of them for rows nothing reads."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "enrich_weather", Path(__file__).resolve().parent.parent / "scripts" / "enrich_weather.py"
)
enrich_weather = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enrich_weather)

FBS = {2026: {"Alabama", "Georgia", "Florida State"}}


def _g(gid, home, away, season=2026):
    return {
        "id": gid,
        "venue_id": 10 + gid,
        "start_date": None,
        "season": season,
        "home_team": home,
        "away_team": away,
    }


def test_only_fbs_vs_fbs_games_are_fetched():
    games = [
        _g(1, "Alabama", "Georgia"),  # FBS vs FBS
        _g(2, "Alabama", "Jacksonville State"),  # FBS vs non-FBS
        _g(3, "Valdosta State", "West Georgia"),  # neither
        _g(4, "Florida State", "Georgia"),
    ]
    kept, dropped = enrich_weather.select_games(games, FBS)
    assert [g["id"] for g in kept] == [1, 4]
    assert dropped == 2
    # The rows keep every key main() reads.
    assert set(kept[0]) == set(enrich_weather.GAME_KEYS)


def test_all_divisions_restores_the_old_behaviour():
    games = [_g(1, "Alabama", "Georgia"), _g(2, "Valdosta State", "West Georgia")]
    kept, dropped = enrich_weather.select_games(games, FBS, all_divisions=True)
    assert [g["id"] for g in kept] == [1, 2] and dropped == 0


def test_a_season_missing_from_the_snapshot_fails_loudly():
    with pytest.raises(ValueError):
        enrich_weather.select_games([_g(1, "Alabama", "Georgia", season=2031)], FBS)


def test_empty_week_is_fine():
    assert enrich_weather.select_games([], FBS) == ([], 0)
