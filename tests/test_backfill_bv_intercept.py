"""scripts/backfill_bv_intercept.py -- the one-off repair for rows scored before
`Prediction.bv_intercept` existed. Three guards: it fills ONLY the season's
model rows that are NULL (other seasons, other model versions and rows already
carrying a value are untouched), it never moves `bv_line`, and it refuses to
write when the recomputed intercept disagrees with the recorded live value."""

import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from beatvegas.db.models import Game, Prediction

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import _load_script, _sqlite_scope  # noqa: E402

B = _load_script("backfill_bv_intercept")


def _seed(eng):
    with Session(eng) as s:
        for gid, season in ((1, 2026), (2, 2026), (3, 2026), (4, 2025)):
            s.add(Game(id=gid, season=season, week=1, home_team=f"H{gid}", away_team=f"A{gid}"))
        s.add(Prediction(game_id=1, model_version="gbm_v1", bv_line=24.0, under_score=60, rank=1))
        s.add(Prediction(game_id=2, model_version="gbm_v1", bv_line=25.5, under_score=60, rank=2))
        # Already carries a value (scored after the column shipped): keep it.
        s.add(
            Prediction(
                game_id=3,
                model_version="gbm_v1",
                bv_line=26.0,
                bv_intercept=-1.5,
                under_score=60,
                rank=3,
            )
        )
        # Display-only rows and another season are out of scope.
        s.add(
            Prediction(
                game_id=1, model_version="derived_lines", bv_line=None, under_score=0, rank=0
            )
        )
        s.add(Prediction(game_id=4, model_version="gbm_v1", bv_line=22.0, under_score=60, rank=1))
        s.commit()


def test_dry_run_changes_nothing_and_reports_the_scope():
    eng, scope = _sqlite_scope()
    _seed(eng)
    with scope() as s:
        audit = B.backfill(s, 2026, -1.8092, write=False)
    assert audit["rows_total"] == 3
    assert audit["rows_null_before"] == 2
    assert audit["rows_updated"] == 0
    assert audit["rows_null_after"] == 2
    assert audit["sum_bv_line_before"] == audit["sum_bv_line_after"] == 75.5


def test_write_fills_only_the_null_2026_model_rows():
    eng, scope = _sqlite_scope()
    _seed(eng)
    with scope() as s:
        audit = B.backfill(s, 2026, -1.8092, write=True)
    assert audit["rows_updated"] == 2 and audit["rows_null_after"] == 0
    assert audit["sum_bv_line_before"] == audit["sum_bv_line_after"]
    with Session(eng) as s:
        got = {(p.game_id, p.model_version): p.bv_intercept for p in s.query(Prediction).all()}
    assert got[(1, "gbm_v1")] == pytest.approx(-1.8092)
    assert got[(2, "gbm_v1")] == pytest.approx(-1.8092)
    assert got[(3, "gbm_v1")] == pytest.approx(-1.5), "a row that already had a value is kept"
    assert got[(1, "derived_lines")] is None, "display rows are not model rows"
    assert got[(4, "gbm_v1")] is None, "another season is out of scope"
    with Session(eng) as s:
        lines = sorted(
            p.bv_line for p in s.query(Prediction).filter(Prediction.bv_line.isnot(None))
        )
    assert lines == [22.0, 24.0, 25.5, 26.0], "bv_line never moves"


def test_a_second_write_is_a_no_op():
    eng, scope = _sqlite_scope()
    _seed(eng)
    with scope() as s:
        B.backfill(s, 2026, -1.8092, write=True)
    with scope() as s:
        again = B.backfill(s, 2026, -1.8092, write=True)
    assert again["rows_null_before"] == 0 and again["rows_updated"] == 0


def test_tolerance_guard_refuses_a_mismatched_intercept():
    B.check_tolerance(-1.2360)
    B.check_tolerance(-1.236020)  # what the runner prints, inside 0.001
    with pytest.raises(SystemExit):
        B.check_tolerance(-1.2360 - 0.002)
    with pytest.raises(SystemExit):
        B.check_tolerance(-1.8092)  # the Mac's number: refused on the runner
    with pytest.raises(SystemExit):
        B.check_tolerance(0.0)


def test_recorded_value_matches_the_doc():
    """The guard's anchor is the number docs/MODEL_LEVEL_2026.md records for the
    live board; if the doc is corrected, this constant must move with it."""
    doc = (Path(__file__).resolve().parent.parent / "docs" / "MODEL_LEVEL_2026.md").read_text()
    assert (
        f"{B.RECORDED_INTERCEPT:.4f}".replace("-", "−") in doc
        or f"{B.RECORDED_INTERCEPT:.4f}" in doc
    )


def test_compare_stored_reads_a_constant_offset_as_the_intercept_difference():
    stored = {1: 24.0, 2: 25.5, 3: 30.0}
    same = B.compare_stored({1: 24.0, 2: 25.5, 3: 30.0, 9: 1.0}, stored)
    assert same["n"] == 3 and same["mean_signed"] == 0.0 and same["within_0_01"] == 3
    shifted = B.compare_stored({1: 24.57, 2: 26.07, 3: 30.57}, stored)
    assert shifted["mean_signed"] == pytest.approx(0.57)
    assert shifted["max_abs"] == pytest.approx(0.57) and shifted["within_0_01"] == 0
    assert B.compare_stored({}, stored) == {"n": 0}
