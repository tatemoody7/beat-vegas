"""Monday's CFBD upsert must not clobber the total/spread a live source (Odds API
/ DK) captured. The guard strips those keys from the CFBD row BEFORE upsert (which
overwrites any non-None value) and tags CFBD-sourced values as 'cfbd'."""

from __future__ import annotations

from contextlib import contextmanager

from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game
from beatvegas.line_sources import LIVE_LINE_SOURCES, strip_protected_line_fields

ROW = {
    "id": 1,
    "season": 2026,
    "week": 3,
    "home_team": "LSU",
    "full_game_total": 60.5,
    "full_game_total_book": "consensus",
    "spread": -10.0,
}


def test_live_sources_are_oddsapi_and_dk():
    assert LIVE_LINE_SOURCES == frozenset({"oddsapi", "dk"})


def test_oddsapi_total_and_spread_are_stripped():
    out = strip_protected_line_fields(ROW, "oddsapi", "oddsapi")
    assert "full_game_total" not in out and "full_game_total_book" not in out
    assert "spread" not in out
    assert "full_game_total_source" not in out and "spread_source" not in out
    assert out["id"] == 1 and out["week"] == 3 and out["home_team"] == "LSU"


def test_dk_counts_as_live_too():
    out = strip_protected_line_fields(ROW, "dk", "dk")
    assert "full_game_total" not in out and "spread" not in out


def test_fields_are_protected_independently():
    out = strip_protected_line_fields(ROW, "oddsapi", None)
    assert "full_game_total" not in out
    assert out["spread"] == -10.0 and out["spread_source"] == "cfbd"
    out = strip_protected_line_fields(ROW, None, "dk")
    assert out["full_game_total"] == 60.5 and out["full_game_total_source"] == "cfbd"
    assert "spread" not in out and "spread_source" not in out


def test_cfbd_or_untagged_rows_get_tagged_cfbd():
    for fg, sp in ((None, None), ("cfbd", "cfbd")):
        out = strip_protected_line_fields(ROW, fg, sp)
        assert out["full_game_total"] == 60.5 and out["spread"] == -10.0
        assert out["full_game_total_source"] == "cfbd" and out["spread_source"] == "cfbd"


def test_no_tag_when_the_row_carries_no_value():
    out = strip_protected_line_fields(
        {"id": 1, "full_game_total": None, "spread": None}, None, None
    )
    assert "full_game_total_source" not in out and "spread_source" not in out
    out = strip_protected_line_fields({"id": 1}, None, None)
    assert out == {"id": 1}


def test_input_row_is_not_mutated():
    row = dict(ROW)
    strip_protected_line_fields(row, "oddsapi", "oddsapi")
    assert row == ROW


# ---------------------------------------------------------------- backfill.py


class _CFBD:
    def __init__(self, ou=60.5, sp=-10.0):
        self.ou, self.sp = ou, sp

    def games(self, year, season_type):
        return [
            {
                "id": gid,
                "season": year,
                "week": 3,
                "seasonType": season_type,
                "startDate": "2026-09-19T19:30:00.000Z",
                "homeTeam": home,
                "awayTeam": away,
                "homeId": 10 * gid,
                "awayId": 10 * gid + 1,
            }
            for gid, home, away in ((1, "LSU", "Clemson"), (2, "Kansas", "Missouri"))
        ]

    def lines(self, year, season_type):
        return [
            {
                "id": gid,
                "lines": [{"provider": "consensus", "overUnder": self.ou, "spread": self.sp}],
            }
            for gid in (1, 2)
        ]

    def plays(self, **kw):  # pragma: no cover - unplayed games never reach PBP
        raise AssertionError("plays() must not be called for unplayed games")


def _sqlite_scope():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    return eng, scope


def test_backfill_season_keeps_live_captured_total_and_spread(monkeypatch):
    mod = _load_script("backfill")
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(mod, "session_scope", scope)
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=3,
                home_team="LSU",
                away_team="Clemson",
                full_game_total=55.5,
                full_game_total_book="draftkings",
                full_game_total_source="oddsapi",
                spread=-7.5,
                spread_source="oddsapi",
            )
        )
        s.commit()

    stats = mod.backfill_season(_CFBD(), 2026, "regular", use_pbp=False)
    assert stats["games"] == 2

    with Session(eng) as s:
        g1 = s.get(Game, 1)
        assert g1.full_game_total == 55.5 and g1.full_game_total_book == "draftkings"
        assert g1.full_game_total_source == "oddsapi"
        assert g1.spread == -7.5 and g1.spread_source == "oddsapi"
        assert g1.home_team_id == 10  # non-line fields still refresh
        g2 = s.get(Game, 2)  # brand-new game: CFBD numbers land, tagged cfbd
        assert g2.full_game_total == 60.5 and g2.full_game_total_source == "cfbd"
        assert g2.spread == -10.0 and g2.spread_source == "cfbd"


# --------------------------------------------------------- backfill_spread.py


def _seed_spread_game(eng, source):
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=3,
                home_team="LSU",
                away_team="Clemson",
                spread=-7.5,
                spread_source=source,
            )
        )
        s.commit()


def test_backfill_spread_skips_live_sourced_games_unless_forced(monkeypatch):
    mod = _load_script("backfill_spread")
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(mod, "session_scope", scope)
    _seed_spread_game(eng, "oddsapi")

    assert mod.backfill_season(_CFBD(), 2026, "regular") == 0
    with Session(eng) as s:
        assert s.get(Game, 1).spread == -7.5

    assert mod.backfill_season(_CFBD(), 2026, "regular", force=True) == 1
    with Session(eng) as s:
        g = s.get(Game, 1)
        assert g.spread == -10.0 and g.spread_source == "cfbd"


def test_backfill_spread_updates_cfbd_or_untagged_games(monkeypatch):
    mod = _load_script("backfill_spread")
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(mod, "session_scope", scope)
    _seed_spread_game(eng, None)

    assert mod.backfill_season(_CFBD(), 2026, "regular") == 1
    with Session(eng) as s:
        g = s.get(Game, 1)
        assert g.spread == -10.0 and g.spread_source == "cfbd"
