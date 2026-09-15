"""A retro-scored week's predictions become GameRecords that declare themselves
retro (captured_at after kickoff), grade like any other, and never duplicate."""

import importlib.util
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, GameRecord, Prediction
from beatvegas.etl.game_records import grade_records

_ROOT = Path(__file__).resolve().parent.parent


def _load():
    path = _ROOT / "scripts" / "backfill_game_records.py"
    spec = importlib.util.spec_from_file_location("backfill_game_records", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _seed(s):
    s.add(
        Game(
            id=1,
            season=2026,
            week=1,
            home_team="Kansas",
            away_team="Fresno State",
            start_date=datetime(2026, 8, 29, 23),
            home_points=31,
            away_points=7,
            first_half_total=20,
            first_half_source="linescores",
        )
    )
    s.add(
        Prediction(
            game_id=1,
            model_version="gbm_v1",
            under_score=75,
            bv_line=21.15,
            bv_gap=2.35,
            bv_sigma=11.26,
            line_used=23.5,
            rank=23,
            factors_json=json.dumps(
                {
                    "line_kind": "observed_1h",
                    "engine": "bv_line",
                    "proj_1h_total": 24.1,
                    "not_a_feature": 1,
                }
            ),
            created_at=datetime(2026, 9, 10, 21, 45),  # eleven days AFTER kickoff
        )
    )
    s.commit()


def test_retro_week_freezes_self_declaring_records_and_grades_them():
    mod = _load()
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        _seed(s)
        recs = mod.backfill_records(s, 2026, 1, "gbm_v1")
        assert len(recs) == 1
        r = recs[0]
        assert r.captured_at == datetime(2026, 9, 10, 21, 45)  # after start_date: retro
        assert r.line == 23.5 and r.line_kind == "observed_1h" and r.engine == "bv_line"
        assert r.bv_line == 21.15 and r.bv_gap == 2.35 and r.bv_gap_z == round(2.35 / 11.26, 4)
        assert r.under_score == 75
        assert json.loads(r.features_json) == {"proj_1h_total": 24.1}  # FEATURE_COLS only
        s.add(r)
        s.flush()
        assert grade_records(s, datetime(2026, 9, 15)) == 1
        s.commit()
        got = s.query(GameRecord).one()
        assert got.first_half_total == 20 and got.outcome == "under" and got.under_hit is True
        # idempotent: the game now carries a record, so nothing is proposed again
        assert mod.backfill_records(s, 2026, 1, "gbm_v1") == []


def test_prediction_without_a_number_is_skipped():
    mod = _load()
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        _seed(s)
        s.query(Prediction).update({"bv_line": None})
        s.commit()
        assert mod.backfill_records(s, 2026, 1, "gbm_v1") == []
