"""Immutable per-game snapshots (plan Phase 0).

snapshot_slate freezes one GameRecord per game pre-kickoff (features + as-of
line/bv_line/gap); it's idempotent per (game, model) so the first pre-kickoff
capture stands. grade_records fills the real 1H result + outcome afterward — the
only post-kickoff write.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from beatvegas.etl.game_records import grade_records, outcome_of, record_fields, snapshot_slate


def test_outcome_of():
    assert outcome_of(20, 24.5) == (True, "under")
    assert outcome_of(28, 24.5) == (False, "over")
    assert outcome_of(24, 24) == (None, "push")
    assert outcome_of(None, 24.5) == (None, None)
    assert outcome_of(20, None) == (None, None)


def test_record_fields_freezes_features_and_outputs():
    row = pd.Series(
        {
            "id": 7,
            "season": 2025,
            "week": 8,
            "line": 24.5,
            "line_kind": "observed_1h",
            "bv_line": 22.0,
            "bv_gap": 2.5,
            "bv_gap_z": 0.8,
            "under_score": 58,
            "combined_sec_play": 28.0,  # a feature column
        }
    )
    f = record_fields(row, "gbm_v1")
    assert f["game_id"] == 7 and f["season"] == 2025
    assert f["line"] == 24.5 and f["line_kind"] == "observed_1h"
    assert f["bv_line"] == 22.0 and f["under_score"] == 58
    import json

    feats = json.loads(f["features_json"])
    assert feats["combined_sec_play"] == 28.0  # frozen feature vector


def test_snapshot_is_immutable_and_grade_fills_outcome(db):
    from beatvegas.db.models import Game, GameRecord

    store = db
    now = dt.datetime(2025, 10, 1)
    with store.session_scope() as s:
        s.add(Game(id=1, season=2025, week=8, home_team="A", away_team="B", full_game_total=50.0))
    scored = pd.DataFrame(
        [
            {
                "id": 1,
                "season": 2025,
                "week": 8,
                "line": 24.5,
                "line_kind": "observed_1h",
                "bv_line": 22.0,
                "bv_gap": 2.5,
                "bv_gap_z": 0.8,
                "under_score": 58,
            }
        ]
    )
    with store.session_scope() as s:
        assert snapshot_slate(s, scored, "gbm_v1", now) == 1
    with store.session_scope() as s:
        assert snapshot_slate(s, scored, "gbm_v1", now) == 0  # immutable: no overwrite
    with store.session_scope() as s:
        s.get(Game, 1).first_half_total = 20  # under 24.5
    with store.session_scope() as s:
        assert grade_records(s, now) == 1
    with store.session_scope() as s:
        rec = s.query(GameRecord).filter_by(game_id=1).one()
        assert rec.outcome == "under" and rec.under_hit is True
        assert rec.line == 24.5 and rec.first_half_total == 20
