"""The frame's season floor (2026-10-06, PR H2): loading 2003-2022 history for
the H-HIST / H-ELO-F studies must change nothing live. The games every frame
reads, the schedule-derived situational columns, and the seasons the site lists
all start at 2023 unless a study opts in; and a past season's load never
rewrites a team's current conference."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from conftest import _load_script, _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.db.models import Game, Team
from beatvegas.etl import features, situational

ROOT = Path(__file__).resolve().parent.parent


def _seed(eng):
    with Session(eng) as s:
        for gid, season in ((1, 2005), (2, 2022), (3, 2024), (4, 2026)):
            s.add(
                Game(
                    id=gid,
                    season=season,
                    week=3,
                    start_date=datetime(season, 9, 20, 19),
                    home_team="Alpha",
                    away_team="Beta",
                    home_points=24,
                    away_points=20,
                )
            )
        s.commit()


def test_the_floor_is_2023_and_the_site_mirrors_it():
    assert features.FRAME_MIN_SEASON == 2023
    src = (ROOT / "web" / "lib" / "model.ts").read_text()
    m = re.search(r"export\s+const\s+SITE_MIN_SEASON\s*=\s*(\d+)\s*;", src)
    assert m and int(m.group(1)) == features.FRAME_MIN_SEASON


def test_query_games_reads_from_the_floor_unless_a_study_opts_out(monkeypatch):
    eng, scope = _sqlite_scope()
    _seed(eng)
    monkeypatch.setattr(features, "session_scope", scope)
    assert sorted(features._query_games()["season"]) == [2024, 2026]
    assert sorted(features._query_games(None)["season"]) == [2005, 2022, 2024, 2026]
    assert sorted(features._query_games(2010)["season"]) == [2022, 2024, 2026]


def test_build_feature_frame_threads_the_floor_to_games_and_situational(monkeypatch):
    """Both readers get the same floor, so rest days and the cross-season
    revenge/rivalry flags never see a game the frame itself excludes. Only the
    H-MODEL-FIX candidate's frame, with a seed, reads one season earlier (its
    floor's first season needs a prior-season mean; that season never becomes
    a row); a seed on the live frame does not move the floor."""
    seen = {}

    def fake_games(fbs_only=True, min_season=features.FRAME_MIN_SEASON):
        seen["games"] = min_season
        raise RuntimeError("stop")  # nothing past the loader is under test

    monkeypatch.setattr(features, "_load_all_games", fake_games)
    for kw, want in (
        ({}, 2023),
        ({"min_season": None}, None),
        ({"min_season": 2003}, 2003),
        ({"prior_weight": 3.0, "min_season": 2015}, 2015),
        ({"prior_weight": 3.0, "min_season": 2015, "model_fix_candidate": True}, 2014),
        ({"prior_weight": 3.0, "min_season": None, "model_fix_candidate": True}, None),
    ):
        try:
            features.build_feature_frame(min_games=0, **kw)
        except RuntimeError:
            pass
        assert seen["games"] == want, kw
    src = Path(features.__file__).read_text()
    assert "situational_frame(min_season=min_season)" in src


def test_situational_frame_honours_the_floor(monkeypatch):
    eng, scope = _sqlite_scope()
    _seed(eng)
    monkeypatch.setattr(situational, "session_scope", scope)
    ids = set(situational.situational_frame(min_season=2023)["id"])
    assert ids == {3, 4}
    assert set(situational.situational_frame()["id"]) == {1, 2, 3, 4}


class _CFBD:
    def __init__(self, conf):
        self.conf = conf

    def games(self, year, season_type):
        return [
            {
                "id": 50 + year % 100,
                "season": year,
                "week": 2,
                "seasonType": season_type,
                "completed": True,
                "startDate": f"{year}-09-12T19:30:00.000Z",
                "homeTeam": "Alpha",
                "awayTeam": "Beta",
                "homeId": 10,
                "awayId": 11,
                "homeConference": self.conf,
                "awayConference": self.conf,
                "homePoints": 21,
                "awayPoints": 14,
                "homeLineScores": [7, 7, 0, 7],
                "awayLineScores": [7, 0, 7, 0],
            }
        ]

    def lines(self, year, season_type):
        return []


def test_a_past_season_load_never_rewrites_a_teams_conference(monkeypatch):
    mod = _load_script("backfill")
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(mod, "session_scope", scope)
    monkeypatch.setattr(mod, "current_season", lambda: 2026)
    with Session(eng) as s:
        s.add_all([Team(id=10, school="Alpha", conference="SEC"), Team(id=11, school="Beta")])
        s.commit()
    mod.backfill_season(_CFBD("Big East"), 2005, "regular", use_pbp=False)
    with Session(eng) as s:
        assert s.get(Team, 10).conference == "SEC"  # untouched by 2005
        assert s.get(Team, 11).conference is None
        assert s.query(Game).filter_by(season=2005).count() == 1
    # The current season still writes today's membership.
    mod.backfill_season(_CFBD("ACC"), 2026, "regular", use_pbp=False)
    with Session(eng) as s:
        assert s.get(Team, 10).conference == "ACC"
