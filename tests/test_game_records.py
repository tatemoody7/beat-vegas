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


# --- the engine dimension --------------------------------------------------
#
# A slate can be produced by EITHER 1H engine, and under the residual engine it
# can be produced by both at once (a row with no real posted 1H line falls back
# to the incumbent). The frozen record has to say which one made it, or the two
# engines' history is one indistinguishable bucket after the fact.


def _sqlite_session():
    """An in-memory records table — the shared PG sandbox is not needed here."""
    from sqlalchemy import create_engine as _ce
    from sqlalchemy.orm import Session

    from beatvegas.db.models import GameRecord

    eng = _ce("sqlite:///:memory:")
    GameRecord.__table__.create(eng)
    return Session(eng)


def _scored(*engines) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": i + 1,
                "season": 2026,
                "week": 5,
                "line": 24.5,
                "line_kind": "hr_1h" if e == "residual" else "derived_fg",
                "bv_line": 22.0,
                "bv_gap": 2.5,
                "bv_gap_z": 0.8,
                "under_score": 58,
                "engine": e,
            }
            for i, e in enumerate(engines)
        ]
    )


def test_record_fields_freezes_the_engine_that_made_the_number():
    row = _scored("residual").iloc[0]
    assert record_fields(row, "gbm_v1")["engine"] == "residual"
    # the model-version tag is an independent dimension, not replaced by it
    assert record_fields(row, "gbm_v1")["model_version"] == "gbm_v1"


def test_record_fields_engine_is_null_for_a_slate_that_predates_the_field():
    row = pd.Series({"id": 1, "season": 2026, "week": 5, "line": 24.5, "under_score": 58})
    assert record_fields(row, "gbm_v1")["engine"] is None


def test_snapshot_freezes_each_row_under_its_own_engine():
    """Under the residual engine a mixed slate splits per row: the game with a
    real posted 1H line is the residual's, the derived/proxy game is the
    incumbent's. Both freeze on the same slate, stamped separately."""
    from beatvegas.db.models import GameRecord

    s = _sqlite_session()
    assert snapshot_slate(s, _scored("residual", "bv_line"), "gbm_v1", dt.datetime(2026, 9, 6)) == 2
    got = {r.game_id: r.engine for r in s.query(GameRecord).all()}
    assert got == {1: "residual", 2: "bv_line"}


def test_snapshot_of_an_incumbent_only_slate_is_stamped_bv_line():
    from beatvegas.db.models import GameRecord

    s = _sqlite_session()
    assert snapshot_slate(s, _scored("bv_line", "bv_line"), "gbm_v1", dt.datetime(2026, 9, 6)) == 2
    assert {r.engine for r in s.query(GameRecord).all()} == {"bv_line"}


def test_migration_adds_the_engine_column_to_a_legacy_records_table():
    from sqlalchemy import create_engine, inspect, text

    from beatvegas.db.store import _MIGRATIONS, _apply_migrations

    assert _MIGRATIONS["game_records"]["engine"] == "VARCHAR"
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE game_records (id INTEGER PRIMARY KEY, game_id INTEGER)"))
    _apply_migrations(eng)
    assert "engine" in {col["name"] for col in inspect(eng).get_columns("game_records")}


# --- the false-zero guard --------------------------------------------------
#
# A LINE-SCORE 0 against a non-zero final is the known corruption (placeholder
# all-zero quarters); 44 such rows were repaired in Neon in 2026-07. Grading one
# books a fabricated UNDER win into the records grid, the credibility ledger and
# bv_line recalibration, so grade_records must route through
# grading.trusted_first_half_total like every other grader.


def _game_and_record(store, **game_kw):
    """One snapshotted record on a game, ready to grade."""
    from beatvegas.db.models import Game

    now = dt.datetime(2026, 10, 1)
    with store.session_scope() as s:
        s.add(Game(id=1, season=2026, week=8, home_team="A", away_team="B", **game_kw))
    scored = pd.DataFrame(
        [
            {
                "id": 1,
                "season": 2026,
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
    return now


def test_a_linescore_false_zero_is_not_graded_as_an_under_win(db):
    """0 at the half with a 45-point final is corruption, not a shutout."""
    from beatvegas.db.models import GameRecord

    store = db
    now = _game_and_record(
        store,
        first_half_total=0,
        first_half_source="linescores",
        home_points=24,
        away_points=21,
    )
    with store.session_scope() as s:
        assert grade_records(s, now) == 0  # skipped, not booked
    with store.session_scope() as s:
        rec = s.query(GameRecord).filter_by(game_id=1).one()
        assert rec.graded_at is None
        assert rec.under_hit is None and rec.outcome is None


def test_a_genuine_scoreless_half_from_pbp_still_grades(db):
    """A PBP zero is verified against the running score — grade it normally."""
    from beatvegas.db.models import GameRecord

    store = db
    now = _game_and_record(
        store, first_half_total=0, first_half_source="pbp", home_points=24, away_points=21
    )
    with store.session_scope() as s:
        assert grade_records(s, now) == 1
    with store.session_scope() as s:
        rec = s.query(GameRecord).filter_by(game_id=1).one()
        assert rec.under_hit is True and rec.outcome == "under"
        assert rec.first_half_total == 0


def test_a_zero_zero_final_grades_from_linescores_too(db):
    """0 at the half in a 0-0 final is consistent, so it is trustworthy."""
    store = db
    now = _game_and_record(
        store, first_half_total=0, first_half_source="linescores", home_points=0, away_points=0
    )
    with store.session_scope() as s:
        assert grade_records(s, now) == 1
