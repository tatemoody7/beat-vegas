import math
from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, Venue
from beatvegas.etl.situational import (
    _flag,
    _rest_days,
    clock_text,
    haversine,
    kickoff_local_hour,
    situational_frame,
    tz_shift_hours,
)


def test_haversine_known_distance():
    # NYC -> LA is ~2450 miles
    d = haversine(40.71, -74.00, 34.05, -118.24)
    assert 2400 < d < 2500


def test_haversine_missing_returns_none():
    assert haversine(None, -74, 34, -118) is None
    assert haversine(40, float("nan"), 34, -118) is None


def test_flag():
    assert _flag(4, lambda x: x < 6) == 1  # short week
    assert _flag(7, lambda x: x < 6) == 0
    assert _flag(None, lambda x: x < 6) is None


def test_rest_days_uses_only_prior_game():
    games = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "season": [2025, 2025, 2025],
            "start_date": pd.to_datetime(["2025-09-06", "2025-09-13", "2025-09-20"]),
            "home_team": ["Iowa", "Iowa", "Ohio State"],
            "away_team": ["Utah State", "Iowa State", "Iowa"],
        }
    )
    rest = _rest_days(games).set_index(["id", "team"])["rest_days"]
    assert pd.isna(rest[(1, "Iowa")])  # first game, no prior
    assert rest[(2, "Iowa")] == 7  # 9/13 - 9/6
    assert rest[(3, "Iowa")] == 7  # 9/20 - 9/13 (away game)


# --- the kickoff clock (data-bug repair 2026-10-17: the venue's IANA zone, not longitude/15) ---


def test_michigan_1930z_is_3_30pm_local():
    # Penn State @ Michigan 2026-10-17: 19:30Z = 3:30pm EDT. Longitude/15 said ~13:00.
    assert kickoff_local_hour(datetime(2026, 10, 17, 19, 30), "America/Detroit") == 15.5


def test_mountain_time_venue():
    # Boulder 20:00Z in October = 2:00pm MDT (UTC-6).
    assert kickoff_local_hour(datetime(2026, 10, 17, 20, 0), "America/Denver") == 14.0


def test_each_side_of_the_2026_11_01_dst_change():
    # The same 19:30Z kickoff is 3:30pm EDT on Oct 31 and 2:30pm EST on Nov 7.
    assert kickoff_local_hour(datetime(2026, 10, 31, 19, 30), "America/Detroit") == 15.5
    assert kickoff_local_hour(datetime(2026, 11, 7, 19, 30), "America/Detroit") == 14.5


def test_arizona_keeps_mst_all_season():
    # Phoenix never shifts: 19:30Z is 12:30pm on both sides of the change.
    assert kickoff_local_hour(datetime(2026, 10, 31, 19, 30), "America/Phoenix") == 12.5
    assert kickoff_local_hour(datetime(2026, 11, 7, 19, 30), "America/Phoenix") == 12.5
    # A Phoenix visitor at Denver: an hour of change before Nov 1, none after.
    assert tz_shift_hours(datetime(2026, 10, 31, 19), "America/Phoenix", "America/Denver") == 1.0
    assert tz_shift_hours(datetime(2026, 11, 7, 19), "America/Phoenix", "America/Denver") == 0.0


def test_tz_shift_is_whole_hours_east_positive():
    k = datetime(2026, 10, 17, 19, 30)
    assert tz_shift_hours(k, "America/New_York", "America/Detroit") == 0.0  # Penn State @ Michigan
    assert tz_shift_hours(k, "America/Los_Angeles", "America/New_York") == 3.0  # west -> east
    assert tz_shift_hours(k, "America/New_York", "America/Chicago") == -1.0


def test_missing_zone_is_none_never_a_guess():
    k = datetime(2026, 10, 17, 19, 30)
    assert kickoff_local_hour(k, None) is None
    assert kickoff_local_hour(k, float("nan")) is None
    assert kickoff_local_hour(k, "") is None
    assert kickoff_local_hour(k, "Not/AZone") is None
    assert kickoff_local_hour(None, "America/Detroit") is None
    assert tz_shift_hours(k, None, "America/Detroit") is None


def test_clock_text():
    assert clock_text(15.5) == "3:30pm"
    assert clock_text(12.0) == "12:00pm"
    assert clock_text(0.25) == "12:15am"
    assert clock_text(19.0) == "7:00pm"
    assert clock_text(None) is None
    assert clock_text(float("nan")) is None


@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(
            [
                Venue(id=1, latitude=42.27, longitude=-83.75, timezone="America/Detroit"),
                Venue(id=2, latitude=40.81, longitude=-77.86, timezone="America/New_York"),
                Venue(id=3, latitude=41.0, longitude=-80.0, timezone=None),  # CFBD gave none
            ]
        )

        def game(gid, start, venue, home, away):
            return Game(
                id=gid, season=2026, week=7, start_date=start, venue_id=venue,
                home_team=home, away_team=away,
            )  # fmt: skip

        s.add_all(
            [
                game(1, datetime(2026, 9, 5, 16), 2, "Penn State", "Akron"),  # PSU home base
                game(2, datetime(2026, 10, 17, 19, 30), 1, "Michigan", "Penn State"),
                game(3, datetime(2026, 10, 17, 19, 30), 3, "Nowhere", "Penn State"),
            ]
        )
        s.commit()
        yield s


def test_frame_reads_the_venue_zone(session):
    f = situational_frame(session=session, season=2026).set_index("id")
    m = f.loc[2]
    assert m["kickoff_local_hour"] == 15.5
    assert m["away_tz_shift"] == 0.0  # Eastern to Eastern
    assert m["early_kickoff"] == 0.0 and m["night_game"] == 0.0


def test_frame_venue_without_zone_is_nan(session, capsys):
    f = situational_frame(session=session, season=2026).set_index("id")
    n = f.loc[3]
    for col in ("kickoff_local_hour", "away_tz_shift", "early_kickoff", "night_game"):
        assert math.isnan(n[col]), col
    assert "[situational] 1 venue(s) have no time zone" in capsys.readouterr().out
    for col in ("kickoff_local_hour", "away_tz_shift", "early_kickoff", "night_game"):
        assert f[col].dtype == "float64", col
