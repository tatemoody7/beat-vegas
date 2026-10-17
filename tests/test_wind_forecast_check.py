"""H-WX-ICON-BIAS: scripts/wind_forecast_check.py (read-only wind forecast check)."""

from __future__ import annotations

from datetime import datetime

import pytest
from conftest import _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.db.models import BuildForecast, Game, Venue, WeatherActual, WeatherObs


@pytest.fixture
def C(load_script):
    return load_script("wind_forecast_check")


def test_the_zone_is_stored_first_then_an_exact_state_or_city_rule(C):
    assert C.venue_zone("America/Chicago", "PA", "State College") == "America/Chicago"
    assert C.venue_zone(None, "MS", "Hattiesburg") == "America/Chicago"
    assert C.venue_zone("", "PA", "") == "America/New_York"
    assert C.venue_zone(None, "TX", "El Paso") == "America/Denver"
    assert C.venue_zone(None, "TX", "Austin") == "America/Chicago"
    assert C.venue_zone(None, "NV", "Las Vegas") == "America/Los_Angeles"
    # multi-zone states without a stored zone stay unknown, never guessed
    for st in ("TN", "KY", "FL", "IN", "MI", "OR", "ID", "KS", "NE", "ND", "SD"):
        assert C.venue_zone(None, st, "Somewhere") is None, st
    assert C.venue_zone(None, None, None) is None


def test_bands_are_half_open_on_the_frozen_edges(C):
    assert [C.hour_band(h) for h in (12.0, 15.99, 16.0, 18.99, 19.0, 22.5)] == [
        "day",
        "day",
        "evening",
        "evening",
        "night",
        "night",
    ]
    assert C.hour_band(None) is None
    assert [C.obs_band(x) for x in (0.0, 4.9, 5.0, 9.99, 10.0, 15.0, 30.0)] == [
        "0-5",
        "0-5",
        "5-10",
        "5-10",
        "10-15",
        "15+",
        "15+",
    ]
    assert C.ratio_band(8.6, 24.0) == "2+"  # Arkansas State @ Southern Miss, 2026-10-17
    assert C.ratio_band(10.0, 15.0) == "1.5-2"
    assert C.ratio_band(10.0, 14.9) == "0-1.5"
    assert C.ratio_band(0.0, 5.0) is None and C.ratio_band(5.0, None) is None


def _game(kick, local_hour=13.0, dome=False):
    return {"kickoff": kick, "dome": dome, "local_hour": local_hour, "season": 2024}


def test_pair_drops_domes_indoor_readings_and_missing_winds(C):
    k = datetime(2024, 10, 5, 19, 30)
    games = {1: _game(k), 2: _game(k, dome=True), 3: _game(k), 4: _game(k), 5: _game(k)}
    fc = {
        1: {"wind": 8.0, "gust": 20.0, "dome": False},
        2: {"wind": 8.0, "gust": 20.0, "dome": False},
        3: {"wind": 8.0, "gust": 20.0, "dome": True},
        4: {"wind": None, "gust": 20.0, "dome": False},
        5: {"wind": 8.0, "gust": None, "dome": False},
    }
    truth = {
        1: {"wind": 12.0, "indoors": False},
        2: {"wind": 12.0, "indoors": False},
        3: {"wind": 12.0, "indoors": False},
        4: {"wind": 12.0, "indoors": False},
        5: {"wind": 3.0, "indoors": True},
    }
    rows = C.pair(fc, truth, games)
    assert [r["game_id"] for r in rows] == [1]
    assert rows[0]["date"] == "2024-10-05" and rows[0]["forecast"] - rows[0]["observed"] == -4.0


def test_summarize_signs_bias_as_forecast_minus_observed_and_counts_crossings(C):
    rows = [
        {"date": "d1", "forecast": 8.0, "observed": 12.0},  # missed windy, -4
        {"date": "d1", "forecast": 11.0, "observed": 9.0},  # false windy, +2
        {"date": "d2", "forecast": 5.0, "observed": 5.0},  # 0
        {"date": "d3", "forecast": 10.0, "observed": 10.0},  # both windy, 0
    ]
    s = C.summarize(rows)
    assert s["n"] == 4 and s["dates"] == 3
    assert s["bias_mean"] == pytest.approx(-0.5)
    assert s["bias_median"] == pytest.approx(0.0)
    assert s["mae"] == pytest.approx(1.5)
    assert (s["missed_windy"], s["false_windy"]) == (1, 1)
    assert (s["obs_windy"], s["fc_windy"]) == (2, 2)
    lo, hi = s["bias_ci95"]
    assert lo <= s["bias_mean"] <= hi
    assert C.summarize([]) == {"n": 0}


def test_splits_put_every_row_in_each_dimension_once(C):
    rows = [
        {"date": "d", "forecast": 8.6, "gust": 24.0, "observed": 13.0, "local_hour": 18.0},
        {"date": "d", "forecast": 6.0, "gust": 7.0, "observed": 4.0, "local_hour": None},
        {"date": "e", "forecast": 12.0, "gust": None, "observed": 16.0, "local_hour": 12.0},
    ]
    sp = C.splits(rows)
    assert sp["all"]["n"] == 3
    hour = [k for k in sp if k.startswith("kickoff")]
    obs = [k for k in sp if k.startswith("observed")]
    ratio = [k for k in sp if k.startswith("gust ratio")]
    for keys in (hour, obs, ratio):
        assert sum(sp[k]["n"] for k in keys) == 3, keys
    assert sp["kickoff evening"]["n"] == 1 and sp["kickoff zone unknown"]["n"] == 1
    assert sp["gust ratio 2+"]["n"] == 1 and sp["gust ratio n/a"]["n"] == 1


def test_the_loaders_read_the_newest_icon_rows_and_only_pre_kickoff_builds(C):
    eng, scope = _sqlite_scope()
    kick = datetime(2026, 10, 17, 23, 0)
    with Session(eng) as s:
        s.add_all(
            [
                Venue(id=1, name="M.M. Roberts", state="MS", city="Hattiesburg", dome=False),
                Venue(id=2, name="Somewhere", state="TN", city="Memphis", dome=False),
                Game(
                    id=10,
                    season=2026,
                    week=8,
                    start_date=kick,
                    venue_id=1,
                    home_team="Southern Miss",
                    away_team="Arkansas State",
                ),
                Game(
                    id=11,
                    season=2026,
                    week=8,
                    start_date=kick,
                    venue_id=2,
                    home_team="Memphis",
                    away_team="Tulane",
                ),
                Game(  # FCS opponent: out of the universe
                    id=12,
                    season=2026,
                    week=8,
                    start_date=kick,
                    venue_id=1,
                    home_team="Southern Miss",
                    away_team="Nowhere State",
                ),
            ]
        )
        for i, (fetched, wind, model) in enumerate(
            [
                (datetime(2026, 10, 15, 20), 7.0, "icon_seamless"),
                (datetime(2026, 10, 17, 12), 8.6, "icon_seamless"),  # newest pre-kickoff
                (datetime(2026, 10, 17, 23, 30), 14.0, "icon_seamless"),  # after kickoff
                (datetime(2026, 10, 17, 13), 15.0, "gfs_seamless"),  # wrong model
            ]
        ):
            s.add(
                BuildForecast(
                    id=100 + i,
                    game_id=10,
                    fetched_at=fetched,
                    kickoff=kick,
                    wind_mph=wind,
                    wind_gust_mph=24.0,
                    dome=False,
                    weather_model=model,
                )
            )
        for i, (ret, wind) in enumerate([(datetime(2026, 9, 1), 5.0), (datetime(2026, 9, 2), 6.0)]):
            s.add(
                WeatherObs(
                    id=200 + i,
                    game_id=10,
                    lead_hours=24,
                    decision_safe=True,
                    wind_mph=wind,
                    wind_gust_mph=12.0,
                    weather_model="icon_seamless",
                    retrieved_at=ret,
                )
            )
        s.add(
            WeatherObs(
                id=210,
                game_id=11,
                lead_hours=24,
                decision_safe=False,  # not decision-safe: never read
                wind_mph=9.0,
                weather_model="icon_seamless",
                retrieved_at=datetime(2026, 9, 1),
            )
        )
        for i, (src, ver, ret, wind) in enumerate(
            [
                ("open_meteo_era5_archive", "v1", datetime(2026, 10, 20), 11.0),
                ("open_meteo_era5_archive", "v2", datetime(2026, 10, 21), 13.0),
                ("cfbd_games_weather", "v1", datetime(2026, 10, 20), 14.0),
            ]
        ):
            s.add(
                WeatherActual(
                    id=300 + i,
                    game_id=10,
                    source=src,
                    hour_offset=0,
                    wind_mph=wind,
                    dataset_version=ver,
                    retrieved_at=ret,
                )
            )
        s.commit()

    with scope() as s:
        games = C.load_games(s, (2026,))
        assert set(games) == {10, 11}
        assert games[10]["zone"] == "America/Chicago"
        assert games[10]["local_hour"] == pytest.approx(18.0)  # 23:00Z = 6pm CDT
        assert games[11]["zone"] is None and games[11]["local_hour"] is None
        build = C.load_build_forecasts(s, games)
        assert build == {10: {"wind": 8.6, "gust": 24.0, "dome": False, "lead_hours": None}}
        obs = C.load_obs_forecasts(s, games, 24)
        assert set(obs) == {10} and obs[10]["wind"] == 6.0
        truths = C.load_truths(s, games)
        assert truths[C.ERA5][10]["wind"] == 13.0 and truths[C.CFBD][10]["wind"] == 14.0
        rows = C.pair(build, truths[C.ERA5], games)
        assert len(rows) == 1 and rows[0]["forecast"] - rows[0]["observed"] == pytest.approx(-4.4)


def test_the_script_never_writes():
    from pathlib import Path

    src = (
        Path(__file__).resolve().parent.parent / "scripts" / "wind_forecast_check.py"
    ).read_text()
    for token in ("init_db(", ".add(", ".merge(", "upsert", ".delete(", "INSERT", "UPDATE "):
        assert token not in src, token
