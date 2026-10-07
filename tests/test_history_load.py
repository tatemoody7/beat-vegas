"""The history load (2026-10-06, PR H3): scripts/backfill.py --fbs-only stores
past seasons' FBS-vs-FBS games with pregame Elo, never fails on a retired
venue, and the workflow that runs it follows the dispatch-hygiene rules."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import _load_script, _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.db.models import Game, Venue

ROOT = Path(__file__).resolve().parent.parent
mod = _load_script("backfill")


def _game(gid, home, away, venue=None, elo=(1650.0, 1480.0)):
    return {
        "id": gid,
        "week": 3,
        "completed": True,
        "startDate": "2005-09-17T19:00:00.000Z",
        "homeTeam": home,
        "awayTeam": away,
        "homeId": gid * 10,
        "awayId": gid * 10 + 1,
        "venueId": venue,
        "homePoints": 24,
        "awayPoints": 17,
        "homeLineScores": [7, 7, 3, 7],
        "awayLineScores": [0, 7, 7, 3],
        "homePregameElo": elo[0],
        "awayPregameElo": elo[1],
    }


class _CFBD:
    def __init__(self, games):
        self._games = games

    def games(self, year, season_type):
        return [{**g, "season": year, "seasonType": season_type} for g in self._games]

    def lines(self, year, season_type):
        return []


def _run(monkeypatch, games, fbs_only, season=2005):
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(mod, "session_scope", scope)
    monkeypatch.setattr(mod, "current_season", lambda: 2026)
    monkeypatch.setattr(mod, "load_fbs_teams", lambda: {2005: {"Alabama", "Auburn", "Texas"}})
    with Session(eng) as s:
        s.add(Venue(id=1, name="Bryant-Denny"))
        s.commit()
    stats = mod.backfill_season(_CFBD(games), season, "regular", use_pbp=False, fbs_only=fbs_only)
    return eng, stats


def test_fbs_only_keeps_fbs_vs_fbs_and_stores_pregame_elo(monkeypatch):
    games = [_game(1, "Alabama", "Auburn", venue=1), _game(2, "Texas", "Montana State")]
    eng, stats = _run(monkeypatch, games, fbs_only=True)
    assert stats["games"] == 1 and stats["with_1h"] == 1 and stats["with_elo"] == 1
    with Session(eng) as s:
        g = s.get(Game, 1)
        assert (g.home_pregame_elo, g.away_pregame_elo) == (1650.0, 1480.0)
        assert g.first_half_total == 21 and g.venue_id == 1  # 7+7 home, 0+7 away
        assert s.get(Game, 2) is None


def test_without_fbs_only_every_game_is_stored(monkeypatch):
    games = [_game(1, "Alabama", "Auburn"), _game(2, "Texas", "Montana State")]
    eng, stats = _run(monkeypatch, games, fbs_only=False)
    assert stats["games"] == 2


def test_an_unknown_venue_is_stored_as_null_not_a_failed_insert(monkeypatch):
    eng, _ = _run(monkeypatch, [_game(1, "Alabama", "Auburn", venue=999)], fbs_only=True)
    with Session(eng) as s:
        assert s.get(Game, 1).venue_id is None


def test_a_season_missing_from_the_fbs_list_refuses_to_load(monkeypatch):
    with pytest.raises(ValueError, match="fetch_fbs_teams"):
        _run(monkeypatch, [_game(1, "Alabama", "Auburn")], fbs_only=True, season=1999)


def test_history_workflow_is_dispatch_only_hash_locked_and_in_the_writers_group():
    wf = (ROOT / ".github" / "workflows" / "history_load.yml").read_text()
    assert "workflow_dispatch:" in wf and "schedule:" not in wf
    assert "group: neon-writers" in wf
    assert "--require-hashes" in wf
    assert "--fbs-only" in wf
    assert "${{ inputs." not in wf.split("run: python")[1]  # inputs reach run: only via env
