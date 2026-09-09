"""Grading finality (2026-09-09): CFBD returns live points for a game in
progress, and the noon-ET Saturday grading run used to write them straight into
home/away_points and the 1H total — where write-once pick grading would freeze
a partial score. backfill.py now keys finality off CFBD's `completed` flag
(both points present, for older exports without the key) and writes no points
and no first-half columns until the game is final."""

from conftest import _load_script, _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.db.models import Game

mod = _load_script("backfill")

LIVE = {
    "id": 7,
    "week": 2,
    "completed": False,
    "homePoints": 14,
    "awayPoints": 10,
    "homeLineScores": [7, 7],
    "awayLineScores": [3, 7],
}
FINAL = {
    "id": 8,
    "week": 2,
    "completed": True,
    "homePoints": 31,
    "awayPoints": 17,
    "homeLineScores": [14, 3, 7, 7],
    "awayLineScores": [0, 7, 3, 7],
}


def test_completed_flag_wins_when_present():
    assert mod._is_completed(LIVE) is False
    assert mod._is_completed(FINAL) is True
    # completed=True with no points yet is still "final" by CFBD's word.
    assert mod._is_completed({"id": 1, "completed": True}) is True


def test_missing_completed_key_falls_back_to_both_points():
    assert mod._is_completed({"id": 1, "homePoints": 31, "awayPoints": 17}) is True
    assert mod._is_completed({"id": 1, "home_points": 31, "away_points": 17}) is True
    assert mod._is_completed({"id": 1, "homePoints": 31}) is False
    assert mod._is_completed({"id": 1}) is False
    # An explicit null flag is the same as no flag.
    assert mod._is_completed({"id": 1, "completed": None, "homePoints": 3, "awayPoints": 0}) is True


def test_in_progress_game_never_needs_pbp():
    # Live line scores (two quarters) would otherwise fail the trust guard and
    # queue a plays fetch for a game that is not over.
    assert mod._needs_pbp(LIVE) is False
    assert mod._needs_pbp({**LIVE, "homeLineScores": None, "awayLineScores": None}) is False
    assert mod._needs_pbp({**FINAL, "homeLineScores": None, "awayLineScores": None}) is True


class _CFBD:
    def __init__(self, games):
        self._games = games

    def games(self, year, season_type):
        return [
            {
                **g,
                "season": year,
                "seasonType": season_type,
                "startDate": "2026-09-12T19:30:00.000Z",
                "homeTeam": f"Home{g['id']}",
                "awayTeam": f"Away{g['id']}",
                "homeId": 10 * g["id"],
                "awayId": 10 * g["id"] + 1,
            }
            for g in self._games
        ]

    def lines(self, year, season_type):
        return []

    def plays(self, **kw):  # pragma: no cover - a live game never reaches PBP
        raise AssertionError("plays() must not be called for an in-progress game")


def test_backfill_season_writes_no_points_or_first_half_for_a_live_game(monkeypatch):
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(mod, "session_scope", scope)
    stats = mod.backfill_season(_CFBD([LIVE, FINAL]), 2026, "regular", use_pbp=False)
    assert stats["games"] == 2 and stats["with_1h"] == 1
    with Session(eng) as s:
        live = s.get(Game, 7)
        assert live.home_team == "Home7"  # the row itself lands
        assert live.home_points is None and live.away_points is None
        assert live.first_half_total is None and live.first_half_source is None
        final = s.get(Game, 8)
        assert (final.home_points, final.away_points) == (31, 17)
        assert final.first_half_total == 24 and final.first_half_source == "linescores"


def test_a_later_final_fills_the_row_the_live_pass_left_alone(monkeypatch):
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(mod, "session_scope", scope)
    mod.backfill_season(_CFBD([LIVE]), 2026, "regular", use_pbp=False)
    done = {**LIVE, "completed": True, "homePoints": 28, "awayPoints": 24}
    done["homeLineScores"], done["awayLineScores"] = [7, 7, 7, 7], [3, 7, 7, 7]
    mod.backfill_season(_CFBD([done]), 2026, "regular", use_pbp=False)
    with Session(eng) as s:
        g = s.get(Game, 7)
        assert (g.home_points, g.away_points) == (28, 24)
        assert g.first_half_total == 24
