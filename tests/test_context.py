"""etl/context.py: per-game board context for rows the model cannot score.

Every game card — including the derived_lines rows of weeks 1-2 and FBS-vs-FCS
games — must carry real factor values (pace, weather, prior-season efficiency,
situational numbers, 1H scoring priors), never NaN in JSON."""

from __future__ import annotations

import json
import math
from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, TeamTempo, Venue, Weather
from beatvegas.etl import context as ctx_mod
from beatvegas.etl.context import (
    context_for_games,
    fh_priors_for_games,
    json_safe,
    prior_season_efficiency,
)

SEASON, WEEK = 2026, 1


def _engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


def _seed(s: Session) -> None:
    s.add_all(
        [
            Venue(id=10, latitude=39.19, longitude=-96.58),  # Manhattan, KS
            Venue(id=20, latitude=38.96, longitude=-95.25),  # Lawrence, KS
            Venue(id=30, latitude=29.65, longitude=-82.35),  # Gainesville, FL
        ]
    )
    # Prior season (2025): played games with 1H points.
    s.add_all(
        [
            Game(
                id=1,
                season=2025,
                week=1,
                start_date=datetime(2025, 8, 30, 19),
                home_team="Kansas State",
                away_team="Kansas",
                venue_id=10,
                home_points=31,
                away_points=17,
                home_first_half_points=14,
                away_first_half_points=7,
                first_half_total=21,
            ),
            Game(
                id=2,
                season=2025,
                week=2,
                start_date=datetime(2025, 9, 6, 19),
                home_team="Kansas",
                away_team="Florida",
                venue_id=20,
                home_points=20,
                away_points=28,
                home_first_half_points=10,
                away_first_half_points=21,
                first_half_total=31,
            ),
            Game(
                id=3,
                season=2025,
                week=3,
                start_date=datetime(2025, 9, 13, 19),
                home_team="Florida",
                away_team="Kansas State",
                venue_id=30,
                home_points=24,
                away_points=27,
                home_first_half_points=3,
                away_first_half_points=20,
                first_half_total=23,
            ),
        ]
    )
    # Upcoming week 1 of 2026: unplayed; one FBS-vs-FCS game (no prior data for FCS).
    s.add_all(
        [
            Game(
                id=100,
                season=SEASON,
                week=WEEK,
                start_date=datetime(2026, 8, 29, 23),  # 23:00 UTC -> ~16:35 local at -96.58
                home_team="Kansas State",
                away_team="Kansas",
                venue_id=10,
                full_game_total=50.5,
                spread=-6.5,
            ),
            Game(
                id=101,
                season=SEASON,
                week=WEEK,
                start_date=datetime(2026, 8, 29, 16),
                home_team="Florida",
                away_team="Long Island",
                venue_id=30,
                full_game_total=58.0,
                spread=-40.0,
            ),
            # Kansas plays at home in 2026 too (their home base for travel math).
            Game(
                id=102,
                season=SEASON,
                week=2,
                start_date=datetime(2026, 9, 5, 16),
                home_team="Kansas",
                away_team="Florida",
                venue_id=20,
                full_game_total=55.0,
            ),
        ]
    )
    s.add_all(
        [
            TeamTempo(
                season=SEASON,
                week=WEEK,
                team="Kansas State",
                seconds_per_play=28.0,
                plays_per_game=70,
            ),
            TeamTempo(
                season=SEASON, week=WEEK, team="Kansas", seconds_per_play=24.0, plays_per_game=76
            ),
            # Florida has pace; Long Island (FCS) has none.
            TeamTempo(
                season=SEASON, week=WEEK, team="Florida", seconds_per_play=26.0, plays_per_game=72
            ),
        ]
    )
    s.add_all(
        [
            Weather(game_id=100, temperature_f=88.0, wind_mph=12.0, precipitation=0.0, dome=False),
            Weather(game_id=101, temperature_f=91.0, wind_mph=5.0, precipitation=0.3, dome=False),
        ]
    )
    s.commit()


@pytest.fixture
def session():
    eng = _engine()
    with Session(eng) as s:
        _seed(s)
        yield s


def test_pace_and_weather_from_tables(session):
    out = context_for_games(session, SEASON, WEEK, [100, 101])
    g = out[100]
    assert g["combined_sec_play"] == pytest.approx(26.0)
    assert g["combined_plays"] == pytest.approx(146.0)
    assert g["wx_temp"] == 88.0 and g["wx_wind"] == 12.0 and g["wx_precip"] == 0.0
    assert g["dome"] is False and g["wx_dome"] == 0.0
    # FBS-vs-FCS: pace falls back to the one side we have; weather is per game.
    f = out[101]
    assert f["combined_sec_play"] == pytest.approx(26.0)
    assert f["combined_plays"] == pytest.approx(72.0)
    assert f["wx_precip"] == 0.3


def test_situational_numbers_are_explicit(session):
    out = context_for_games(session, SEASON, WEEK, [100, 101])
    g = out[100]
    # Week-1 openers: no prior game this season -> rest days unknown (None, not NaN).
    assert g["home_rest_days"] is None and g["away_rest_days"] is None
    # Kansas (home base Lawrence) -> Manhattan is a short hop.
    assert 50 < g["away_travel_dist"] < 90
    assert abs(g["away_tz_shift"]) < 0.2
    assert 15 < g["kickoff_local_hour"] < 18
    assert isinstance(g["spot"], str) and "trav" in g["spot"]
    # FCS visitor with no home base in our tables -> travel unknown, kickoff known.
    f = out[101]
    assert f["away_travel_dist"] is None
    assert f["kickoff_local_hour"] is not None


def test_prior_season_fh_priors_before_week_3(session):
    out = fh_priors_for_games(
        session, SEASON, WEEK, {100: ("Kansas State", "Kansas"), 101: ("Florida", "Long Island")}
    )
    g = out[100]
    # Kansas State 2025: 1H for 14, 20 -> 17; allowed 7, 3 -> 5
    assert g["home_fh_pf"] == pytest.approx(17.0)
    assert g["home_fh_pa"] == pytest.approx(5.0)
    # Kansas 2025: for 7, 10 -> 8.5; allowed 14, 21 -> 17.5
    assert g["away_fh_pf"] == pytest.approx(8.5)
    assert g["away_fh_pa"] == pytest.approx(17.5)
    assert g["fh_prior_source"] == "prior_season"
    assert g["combined_fh_offense"] == pytest.approx(25.5)
    assert g["combined_fh_defense"] == pytest.approx(22.5)
    # FCS side: nothing in our tables -> None, the FBS side still resolves.
    f = out[101]
    assert f["home_fh_pf"] == pytest.approx(12.0)  # Florida 21, 3
    assert f["away_fh_pf"] is None and f["away_fh_pa"] is None
    assert f["combined_fh_offense"] is None
    assert f["fh_prior_source"] == "prior_season"


def test_season_to_date_priors_from_week_3(session):
    # Play 2026 wk1 + wk2 for Kansas, then ask about a wk3 game.
    session.get(Game, 100).home_first_half_points = 17
    session.get(Game, 100).away_first_half_points = 10
    session.get(Game, 100).first_half_total = 27
    session.get(Game, 102).home_first_half_points = 14
    session.get(Game, 102).away_first_half_points = 24
    session.get(Game, 102).first_half_total = 38
    session.add(
        Game(
            id=103,
            season=SEASON,
            week=3,
            home_team="Kansas",
            away_team="Long Island",
            full_game_total=60.0,
        )
    )
    session.commit()
    out = fh_priors_for_games(session, SEASON, 3, {103: ("Kansas", "Long Island")})
    g = out[103]
    assert g["home_fh_pf"] == pytest.approx(12.0)  # (10 + 14) / 2
    assert g["home_fh_pa"] == pytest.approx(20.5)  # (17 + 24) / 2
    # Long Island never played an FBS game we track -> None either way.
    assert g["away_fh_pf"] is None
    assert g["fh_source_home"] == "season_to_date"
    assert g["fh_source_away"] is None
    assert g["fh_prior_source"] == "season_to_date"


def test_prior_season_efficiency_reuses_cfbd_join(monkeypatch):
    # Stub the CFBD-backed quality frame (features.py's season+1 join helper).
    def fake_quality(client, seasons):
        assert seasons == [SEASON - 1]
        return pd.DataFrame(
            {
                "season": [2025, 2025],
                "team": ["Kansas State", "Kansas"],
                "off_ppa": [0.35, 0.28],
                "def_ppa": [0.22, 0.31],
                "join_season": [SEASON, SEASON],
            }
        )

    monkeypatch.setattr(ctx_mod, "quality_prior_frame", fake_quality)
    eff = prior_season_efficiency(SEASON, client=object())
    assert eff["Kansas State"]["off_ppa"] == 0.35
    assert eff["Kansas"]["def_ppa"] == 0.31


def test_prior_season_efficiency_is_fail_soft(monkeypatch):
    def boom(client, seasons):
        raise RuntimeError("CFBD 503")

    monkeypatch.setattr(ctx_mod, "quality_prior_frame", boom)
    assert prior_season_efficiency(SEASON, client=object()) == {}


def test_context_merges_efficiency_when_given(session):
    eff = {
        "Kansas State": {"off_ppa": 0.35, "def_ppa": 0.22},
        "Kansas": {"off_ppa": 0.28, "def_ppa": 0.31},
    }
    out = context_for_games(session, SEASON, WEEK, [100, 101], efficiency=eff)
    g = out[100]
    assert g["combined_off_ppa"] == pytest.approx(0.63)
    assert g["combined_def_ppa"] == pytest.approx(0.53)
    assert g["home_off_ppa"] == 0.35 and g["away_def_ppa"] == 0.31
    # Half-missing (FCS) -> combined is None, the known side is kept.
    f = out[101]
    assert f["combined_off_ppa"] is None
    assert f["home_off_ppa"] is None  # Florida absent from this stub map
    # No efficiency map at all -> the keys are simply absent (not NaN).
    bare = context_for_games(session, SEASON, WEEK, [100])
    assert "combined_off_ppa" not in bare[100]


def test_context_json_round_trip_has_no_nan(session):
    out = context_for_games(session, SEASON, WEEK, [100, 101])
    text = json.dumps(json_safe(out))
    assert "NaN" not in text and "Infinity" not in text
    back = json.loads(text)
    assert back["100"]["combined_sec_play"] == 26.0
    for g in back.values():
        for v in g.values():
            assert not (isinstance(v, float) and math.isnan(v))


def test_json_safe_scrubs_nested_nan_and_numpy():
    import numpy as np

    d = {"a": float("nan"), "b": [1.0, float("inf"), np.float64(2.5)], "c": {"d": np.int64(3)}}
    out = json_safe(d)
    assert out == {"a": None, "b": [1.0, None, 2.5], "c": {"d": 3}}
    assert isinstance(out["c"]["d"], int)


def test_json_safe_dates_to_iso_and_arrays_to_lists():
    """The one json_safe: dates/datetimes -> ISO strings, numpy arrays -> lists
    (model/artifacts.py fingerprints carry both), NaT -> None."""
    import datetime as dt

    import numpy as np
    import pandas as pd

    out = json_safe(
        {
            "d": dt.date(2025, 9, 6),
            "ts": dt.datetime(2025, 9, 6, 19, 30),
            "pd_ts": pd.Timestamp("2025-09-06 19:30"),
            "nat": pd.NaT,
            "arr": np.array([1, 2, 3]),
            "arr_f": np.array([0.5, float("nan")]),
        }
    )
    assert out["d"] == "2025-09-06"
    assert out["ts"] == "2025-09-06T19:30:00"
    assert out["pd_ts"] == "2025-09-06T19:30:00"
    assert out["nat"] is None
    assert out["arr"] == [1, 2, 3]
    assert out["arr_f"] == [0.5, None]
    json.dumps(out)  # never raises


def test_unknown_game_ids_are_skipped(session):
    out = context_for_games(session, SEASON, WEEK, [100, 999])
    assert set(out) == {100}
