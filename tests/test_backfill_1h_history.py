"""Backfill helpers: target timestamp, idempotent scoping, event matching."""

import importlib.util
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, OddsSnapshot

_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    path = _ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_target_snapshot_ts():
    bf = _load("backfill_1h_history")
    assert bf.target_snapshot_ts(datetime(2024, 9, 1, 19, 0), 30) == datetime(2024, 9, 1, 18, 30)


def test_games_needing_skips_already_captured_and_respects_week_limit():
    bf = _load("backfill_1h_history")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(
            [
                Game(id=1, season=2024, week=8, home_team="Auburn", away_team="Missouri",
                     start_date=datetime(2024, 10, 19, 19, 0)),
                Game(id=2, season=2024, week=8, home_team="Iowa", away_team="Penn State",
                     start_date=datetime(2024, 10, 19, 16, 0)),
                Game(id=3, season=2024, week=9, home_team="Texas", away_team="Vandy",
                     start_date=datetime(2024, 10, 26, 12, 0)),
            ]
        )
        # Game 1 already has a 1H snapshot -> must be skipped (idempotent).
        s.add(OddsSnapshot(game_id=1, book="fanduel", market="1H_total", line=24.5,
                           captured_at=datetime(2024, 10, 19, 18, 0)))
        s.commit()

        wk8 = bf.games_needing_backfill(s, 2024, week=8, limit=0)
        assert [g["id"] for g in wk8] == [2]  # game 1 skipped, ordered by kickoff

        allw = bf.games_needing_backfill(s, 2024, week=None, limit=0)
        assert [g["id"] for g in allw] == [2, 3]  # 1 skipped; sorted by start_date

        capped = bf.games_needing_backfill(s, 2024, week=None, limit=1)
        assert [g["id"] for g in capped] == [2]


def test_match_game_to_event_finds_the_right_event():
    bf = _load("backfill_1h_history")
    game = {"id": 7, "home_team": "Auburn", "away_team": "Missouri",
            "start_date": datetime(2024, 10, 19, 19, 0)}
    events = [
        {"id": "evtX", "home_team": "Georgia Bulldogs", "away_team": "Florida Gators",
         "commence_time": "2024-10-19T16:00:00Z"},
        {"id": "evtY", "home_team": "Auburn Tigers", "away_team": "Missouri Tigers",
         "commence_time": "2024-10-19T19:00:00Z"},
    ]
    event_id, score = bf._match_game_to_event(game, events)
    assert event_id == "evtY"
    assert score > 0


def test_match_game_to_event_no_match():
    bf = _load("backfill_1h_history")
    game = {"id": 7, "home_team": "Auburn", "away_team": "Missouri",
            "start_date": datetime(2024, 10, 19, 19, 0)}
    events = [
        {"id": "evtX", "home_team": "Georgia Bulldogs", "away_team": "Florida Gators",
         "commence_time": "2024-10-19T16:00:00Z"},
    ]
    assert bf._match_game_to_event(game, events) == (None, 0.0)
