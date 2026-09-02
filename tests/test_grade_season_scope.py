"""grade.py --season must grade AND summarize only that season. _summary read
every results row ever written and grade_model walked every prediction, so the
printed record mixed seasons."""

from datetime import datetime

from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, Prediction, Result


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


def test_grade_model_only_touches_the_seasons_predictions():
    grade = _load_script("grade")
    eng = _db()
    with Session(eng) as s:
        for gid in (1, 2):
            s.add(
                Prediction(
                    game_id=gid,
                    model_version=grade.MODEL_VERSION,
                    under_score=60,
                    line_used=24.5,
                    created_at=datetime(2026, 9, 1),
                )
            )
        s.commit()
        # A caller handing over closings for BOTH seasons must still only get
        # the requested season graded.
        closings = {
            gid: (s.get(Game, gid), (25.0, 24.0), datetime(2026, 9, 30), (None, None))
            for gid in (1, 2)
        }
        n = grade.grade_model(s, 2026, closings)
        s.commit()
        assert n == 1
        rows = s.query(Result).filter(Result.model_version == grade.MODEL_VERSION).all()
        assert [r.game_id for r in rows] == [2]
