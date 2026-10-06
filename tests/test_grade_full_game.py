"""Full-game market ledger: grade_market_fg vs the realized full-game total."""

import importlib.util
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, OddsSnapshot, Result

_ROOT = Path(__file__).resolve().parent.parent


def _load(script_name: str):
    path = _ROOT / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(script_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_grade_market_fg_full_game():
    grade = _load("grade")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=1,
                home_team="LSU",
                away_team="Clemson",
                start_date=datetime(2026, 9, 1, 12),
                home_points=21,
                away_points=20,  # realized full-game total = 41
            )
        )
        # full-game opener 52.0 (a week out), close 50.0 captured 2 h before
        # kickoff -- inside REAL_FG_CLOSE_WINDOW_H (3 h)
        s.add(
            OddsSnapshot(
                game_id=1,
                book="hardrockbet",
                market="full_game_total",
                line=52.0,
                captured_at=datetime(2026, 8, 25, 12),
            )
        )
        s.add(
            OddsSnapshot(
                game_id=1,
                book="hardrockbet",
                market="full_game_total",
                line=50.0,
                captured_at=datetime(2026, 9, 1, 10),
            )
        )
        s.commit()

        closings = grade._closings_fg(s, 2026)
        n = grade.grade_market_fg(s, closings)
        s.commit()
        assert n == 1

        r = s.query(Result).filter(Result.model_version == "market_fg").one()
        assert r.market == "full"
        assert r.line_used == 50.0  # closing
        assert r.actual_first_half_total == 41  # full-game total stored here
        assert r.under_hit is True  # 41 < 50
        assert r.clv == -2.0  # closing - opening = 50 - 52


def test_grade_market_fg_skips_unfinished():
    grade = _load("grade")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            Game(
                id=2,
                season=2026,
                week=1,
                home_team="A",
                away_team="B",
                start_date=datetime(2026, 9, 1, 12),
                home_points=None,
                away_points=None,
            )
        )
        s.commit()
        closings = grade._closings_fg(s, 2026)
        assert grade.grade_market_fg(s, closings) == 0  # no final score


def test_grade_market_fg_removes_a_stale_row_when_the_close_is_gone():
    """grade_market deletes BEFORE the skip so a re-grade cleans up;
    grade_market_fg skipped first, so a full-game row whose close later failed
    the window kept its stale graded row forever."""
    grade = _load("grade")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            Game(
                id=3,
                season=2026,
                week=1,
                home_team="A",
                away_team="B",
                start_date=datetime(2026, 9, 1, 12),
                home_points=21,
                away_points=20,
            )
        )
        s.add(
            Result(
                game_id=3,
                model_version="market_fg",
                market="full",
                actual_first_half_total=41,
                line_used=50.0,
                line_kind="real",
                under_hit=True,
                closing_line=50.0,
                units=0.9,
            )
        )
        s.commit()
        # No full-game snapshot at all now -> the close is None for game 3.
        closings = grade._closings_fg(s, 2026)
        closings.setdefault(3, (s.get(Game, 3), (None, None), None, (None, None)))
        assert grade.grade_market_fg(s, closings) == 0
        s.commit()
        assert s.query(Result).filter(Result.model_version == "market_fg").count() == 0


def _game_and_snap(s, captured_at, last_seen_at=None):
    s.add(
        Game(
            id=7,
            season=2026,
            week=6,
            home_team="A",
            away_team="B",
            start_date=datetime(2026, 10, 10, 19, 30),
            home_points=24,
            away_points=20,
        )
    )
    s.add(
        OddsSnapshot(
            game_id=7,
            book="draftkings",
            market="full_game_total",
            line=51.5,
            captured_at=captured_at,
            last_seen_at=last_seen_at,
        )
    )
    s.commit()


def test_a_sunday_only_snapshot_is_an_opener_and_grades_nothing():
    """Before 2026-10-06 the full-game ledger applied no window and graded
    Sunday's opener as the close (9 of 380 graded 2026 rows had a snapshot
    inside 3 h). The close must be captured or re-seen inside
    REAL_FG_CLOSE_WINDOW_H."""
    grade = _load("grade")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        _game_and_snap(s, captured_at=datetime(2026, 10, 4, 18, 0))  # Sunday
        closings = grade._closings_fg(s, 2026)
        assert grade.grade_market_fg(s, closings) == 0
        assert closings[7][1] == (51.5, None)  # opener known, no close


def test_a_sunday_snapshot_re_seen_inside_three_hours_is_the_close():
    grade = _load("grade")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        _game_and_snap(
            s,
            captured_at=datetime(2026, 10, 4, 18, 0),
            last_seen_at=datetime(2026, 10, 10, 17, 0),  # 2.5 h before kick
        )
        closings = grade._closings_fg(s, 2026)
        assert grade.grade_market_fg(s, closings) == 1
        assert closings[7][1] == (51.5, 51.5)
        assert closings[7][2] == datetime(2026, 10, 10, 17, 0)
