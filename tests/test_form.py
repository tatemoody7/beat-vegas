"""etl/form.py: last-3 first-half form + home/away 1H splits per team.

Season-to-date from week 3; before that (or when a team has no played game this
season) the prior season stands in, and the payload says which."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game
from beatvegas.etl.context import json_safe
from beatvegas.etl.form import form_for_games, home_away_split, last_n_form

SEASON = 2026


def _g(gid, season, week, home, away, hfh, afh, day):
    return Game(
        id=gid,
        season=season,
        week=week,
        start_date=datetime(season, 9, day, 19),
        home_team=home,
        away_team=away,
        home_first_half_points=hfh,
        away_first_half_points=afh,
        first_half_total=None if hfh is None else hfh + afh,
    )


@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        # 2025: Kansas plays 5 games (3 home, 2 away).
        s.add_all(
            [
                _g(1, 2025, 1, "Kansas", "A", 14, 7, 1),
                _g(2, 2025, 2, "B", "Kansas", 10, 21, 6),
                _g(3, 2025, 3, "Kansas", "C", 17, 3, 13),
                _g(4, 2025, 4, "D", "Kansas", 24, 6, 20),
                _g(5, 2025, 5, "Kansas", "E", 28, 14, 27),
                # 2026: two played weeks, then the week-3 target (unplayed).
                _g(100, SEASON, 1, "Kansas", "F", 7, 10, 1),
                _g(101, SEASON, 2, "G", "Kansas", 21, 3, 6),
                _g(102, SEASON, 3, "Kansas", "H", None, None, 13),
                # A week-1 2026 game for a team with no 2025 history.
                _g(103, SEASON, 1, "Newcomer", "Kansas State", None, None, 1),
            ]
        )
        s.commit()
        yield s


def test_last_n_form_is_chronological_and_capped():
    rows = [
        {"week": 3, "start_date": datetime(2025, 9, 13), "pf": 17, "pa": 3},
        {"week": 1, "start_date": datetime(2025, 9, 1), "pf": 14, "pa": 7},
        {"week": 5, "start_date": datetime(2025, 9, 27), "pf": 28, "pa": 14},
        {"week": 4, "start_date": datetime(2025, 9, 20), "pf": 6, "pa": 24},
    ]
    f = last_n_form(rows, n=3)
    assert f == {"pf": [17, 6, 28], "pa": [3, 24, 14], "n": 3}  # oldest -> newest
    assert last_n_form([], n=3) is None


def test_home_away_split_averages_by_venue():
    rows = [
        {"is_home": True, "pf": 14, "pa": 7},
        {"is_home": True, "pf": 17, "pa": 3},
        {"is_home": False, "pf": 21, "pa": 10},
    ]
    sp = home_away_split(rows)
    assert sp["at_home"] == {"pf": 15.5, "pa": 5.0, "n": 2}
    assert sp["on_road"] == {"pf": 21.0, "pa": 10.0, "n": 1}
    assert home_away_split([{"is_home": True, "pf": 1, "pa": 2}])["on_road"] is None


def test_form_before_week_3_uses_prior_season(session):
    out = form_for_games(session, SEASON, 1, [100])
    f = out[100]
    fh = f["form_home"]  # Kansas, 2025 last three: wk3 17/3, wk4 6/24, wk5 28/14
    assert fh["pf"] == [17, 6, 28] and fh["pa"] == [3, 24, 14]
    assert fh["n"] == 3 and fh["source"] == "prior_season"
    sp = f["split_home"]
    assert sp["source"] == "prior_season"
    assert sp["at_home"] == {"pf": pytest.approx(59 / 3), "pa": pytest.approx(8.0), "n": 3}
    assert sp["on_road"] == {"pf": 13.5, "pa": 17.0, "n": 2}
    # Opponent "F" has no history anywhere -> None, never NaN.
    assert f["form_away"] is None and f["split_away"] is None


def test_form_from_week_3_uses_season_to_date(session):
    out = form_for_games(session, SEASON, 3, [102])
    f = out[102]
    fh = f["form_home"]
    assert fh == {"pf": [7, 3], "pa": [10, 21], "n": 2, "source": "season_to_date"}
    sp = f["split_home"]
    assert sp["at_home"] == {"pf": 7.0, "pa": 10.0, "n": 1}
    assert sp["on_road"] == {"pf": 3.0, "pa": 21.0, "n": 1}
    assert sp["source"] == "season_to_date"


def test_form_falls_back_to_prior_season_when_no_games_yet(session):
    # Week 3 of 2026, but neither side has played this season: Kansas State only
    # has a 2025 game to lean on, and "Newcomer" has nothing at all.
    session.add(_g(6, 2025, 9, "Kansas State", "Z", 10, 20, 29))
    session.add(_g(104, SEASON, 3, "Newcomer", "Kansas State", None, None, 13))
    session.commit()
    out = form_for_games(session, SEASON, 3, [104])
    f = out[104]
    assert f["form_home"] is None and f["split_home"] is None
    assert f["form_away"] == {"pf": [10], "pa": [20], "n": 1, "source": "prior_season"}
    # Prior-season split for a single home game: road side stays absent, not NaN.
    assert f["split_away"]["at_home"] == {"pf": 10.0, "pa": 20.0, "n": 1}
    assert f["split_away"]["on_road"] is None
    assert f["split_away"]["source"] == "prior_season"


def test_form_payload_is_json_clean(session):
    out = form_for_games(session, SEASON, 1, [100, 103])
    text = json.dumps(json_safe(out))
    assert "NaN" not in text
    back = json.loads(text)
    assert set(back["100"]) == {"form_home", "form_away", "split_home", "split_away"}
