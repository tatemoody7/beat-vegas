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
        # full-game opener 52.0, close 50.0 (both before kickoff)
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
                captured_at=datetime(2026, 8, 31, 12),
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
