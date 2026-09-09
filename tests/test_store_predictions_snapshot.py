"""store_predictions(snapshot=...) (beatvegas/model/score.py): the predictions
rows always land; the immutable pre-kickoff GameRecords are frozen by default
and NOT on a retrospective re-score (rescore.yml passes --no-snapshot through
weekly_update.py, because a record written after kickoff is not a pre-game
record). Offline: in-memory SQLite, snapshot_slate replaced by a counter."""

from __future__ import annotations

import pandas as pd
import pytest
from conftest import _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.db.models import Game, Prediction
from beatvegas.model import score


def _scored() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": 1,
                "season": 2026,
                "week": 1,
                "rank": 1,
                "under_prob": 0.58,
                "under_score": 58,
                "line": 24.5,
                "line_kind": "hr_1h",
                "proj_1h_total": 22.0,
                "bv_line": 22.0,
                "bv_gap": 2.5,
                "bv_gap_z": 0.2,
                "bv_lo": 10.0,
                "bv_hi": 34.0,
                "bv_sigma": 12.0,
            }
        ]
    )


@pytest.fixture
def wired(monkeypatch):
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=1, home_team="H", away_team="A"))
        s.commit()
    monkeypatch.setattr(score, "init_db", lambda: None)
    monkeypatch.setattr(score, "session_scope", scope)
    monkeypatch.setattr(score, "load_ledger", lambda session: {})
    monkeypatch.setattr(score, "slate_context", lambda session, scored: ({}, {}))
    calls = []
    monkeypatch.setattr(
        score, "snapshot_slate", lambda s, scored, mv, now: calls.append((mv, len(scored))) or 1
    )
    return eng, calls


def test_default_freezes_one_snapshot_per_store(wired):
    eng, calls = wired
    assert score.store_predictions(_scored(), model_version="gbm_test") == 1
    assert calls == [("gbm_test", 1)]
    with Session(eng) as s:
        (row,) = s.query(Prediction).all()
        assert row.game_id == 1 and row.model_version == "gbm_test" and row.line_used == 24.5


def test_snapshot_false_writes_predictions_but_never_a_record(wired):
    eng, calls = wired
    assert score.store_predictions(_scored(), model_version="gbm_test", snapshot=False) == 1
    assert calls == []
    with Session(eng) as s:
        assert s.query(Prediction).count() == 1
