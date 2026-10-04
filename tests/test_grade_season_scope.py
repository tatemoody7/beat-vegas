"""grade.py --season must grade AND summarize only that season. _summary read
every results row ever written, so the printed record mixed seasons. (The
grade_model cases that lived here left with the classifier, 2026-10-04.)"""

from datetime import datetime

from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, Result


def _db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(
            [
                Game(
                    id=1,
                    season=2025,
                    week=5,
                    home_team="A",
                    away_team="B",
                    start_date=datetime(2025, 10, 1),
                    first_half_total=20,
                    home_points=30,
                    away_points=20,
                ),
                Game(
                    id=2,
                    season=2026,
                    week=5,
                    home_team="C",
                    away_team="D",
                    start_date=datetime(2026, 10, 1),
                    first_half_total=20,
                    home_points=30,
                    away_points=20,
                ),
            ]
        )
        s.commit()
    return eng


def test_summary_is_season_scoped(capsys):
    grade = _load_script("grade")
    eng = _db()
    with Session(eng) as s:
        s.add_all(
            [
                Result(
                    game_id=1,
                    model_version=grade.MODEL_MARKET,
                    market="1H",
                    actual_first_half_total=20,
                    line_used=24.5,
                    line_kind="real",
                    under_hit=True,
                    units=0.91,
                ),
                Result(
                    game_id=2,
                    model_version=grade.MODEL_MARKET,
                    market="1H",
                    actual_first_half_total=20,
                    line_used=17.5,
                    line_kind="real",
                    under_hit=False,
                    units=-1.0,
                ),
            ]
        )
        s.commit()
        grade._summary(s, grade.MODEL_MARKET, "MARKET 1H", season=2026)
    out = capsys.readouterr().out
    assert "UNDER 0/1" in out and "units=-1.00" in out  # only the 2026 row
