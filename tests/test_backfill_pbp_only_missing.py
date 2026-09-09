"""Cheap daily grading (2026-09-09): backfill_pbp.py --only-missing fetches CFBD
/plays only for the weeks that still hold a FINISHED FBS-vs-FBS game with no
fh_team_game rows, instead of all 20 weeks on every grade.yml run."""

from contextlib import contextmanager

from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, FhTeamGame, Game
from beatvegas.sources import cfbpbp

mod = _load_script("backfill_pbp")
SEASON = 2026
FBS = {"Kansas State", "Kansas", "Missouri", "Florida", "LSU", "Clemson"}


def _sqlite_scope():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    return eng, scope


def _game(gid, week, home, away, finished=True):
    return Game(
        id=gid,
        season=SEASON,
        week=week,
        home_team=home,
        away_team=away,
        home_points=24 if finished else None,
        away_points=17 if finished else None,
    )


def _fh(gid, week, off, de):
    return FhTeamGame(
        game_id=gid, season=SEASON, week=week, off_team=off, def_team=de, is_home=True
    )


def _seed(eng):
    with Session(eng) as s:
        s.add_all(
            [
                _game(1, 1, "Kansas State", "Kansas"),  # finished, has rows
                _fh(1, 1, "Kansas State", "Kansas"),
                _fh(1, 1, "Kansas", "Kansas State"),
                _game(2, 2, "Missouri", "Florida"),  # finished, NO rows -> week 2
                _game(3, 3, "LSU", "Clemson", finished=False),  # not over yet
                _game(4, 4, "Florida", "Furman"),  # finished, FCS visitor -> never has PBP
            ]
        )
        s.commit()


def test_weeks_missing_pbp_is_only_the_finished_fbs_week_without_rows(monkeypatch):
    eng, scope = _sqlite_scope()
    _seed(eng)
    monkeypatch.setattr(mod, "load_fbs_teams", lambda: {SEASON: FBS})
    with scope() as s:
        assert mod._weeks_missing_pbp(s, SEASON) == [2]


def test_a_week_with_some_rows_still_comes_back_for_its_other_finished_games(monkeypatch):
    """Per game, not per week: Thursday's game aggregated on Friday must not
    hide Saturday's games in the same week from Sunday's run."""
    eng, scope = _sqlite_scope()
    _seed(eng)
    with Session(eng) as s:
        s.add(_game(5, 1, "LSU", "Clemson"))  # week 1, finished, no rows
        s.commit()
    monkeypatch.setattr(mod, "load_fbs_teams", lambda: {SEASON: FBS})
    with scope() as s:
        assert mod._weeks_missing_pbp(s, SEASON) == [1, 2]


def test_fbs_filter_is_skipped_when_the_snapshot_lacks_the_season(monkeypatch):
    eng, scope = _sqlite_scope()
    _seed(eng)
    monkeypatch.setattr(mod, "load_fbs_teams", lambda: {SEASON - 1: FBS})
    with scope() as s:
        assert mod._weeks_missing_pbp(s, SEASON) == [2, 4]

    def missing():
        raise FileNotFoundError("no snapshot")

    monkeypatch.setattr(mod, "load_fbs_teams", missing)
    with scope() as s:
        assert mod._weeks_missing_pbp(s, SEASON) == [2, 4]


class _Client:
    def __init__(self):
        self.calls = []

    def plays(self, year, week, season_type="regular"):
        self.calls.append((year, week))
        return []


def test_load_plays_week_list_calls_plays_once_per_listed_week():
    client = _Client()
    assert SEASON > cfbpbp.PARQUET_MAX_YEAR
    df = cfbpbp.load_plays(SEASON, client=client, week_list=[2])
    assert client.calls == [(SEASON, 2)]
    assert df.empty
    client = _Client()
    cfbpbp.load_plays(SEASON, client=client, weeks=3)
    assert client.calls == [(SEASON, 1), (SEASON, 2), (SEASON, 3)]


def test_backfill_season_only_missing_fetches_the_missing_week_or_nothing(monkeypatch):
    eng, scope = _sqlite_scope()
    _seed(eng)
    monkeypatch.setattr(mod, "session_scope", scope)
    monkeypatch.setattr(mod, "load_fbs_teams", lambda: {SEASON: FBS})
    client = _Client()
    assert mod.backfill_season(SEASON, client, only_missing=True) == 0  # no plays returned
    assert client.calls == [(SEASON, 2)]
    # Once week 2 has rows there is nothing to fetch: no CFBD call at all.
    with Session(eng) as s:
        s.add(_fh(2, 2, "Missouri", "Florida"))
        s.commit()
    client = _Client()
    assert mod.backfill_season(SEASON, client, only_missing=True) == 0
    assert client.calls == []
