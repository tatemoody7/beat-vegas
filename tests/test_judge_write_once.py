"""The judge's columns are write-once (beatvegas/picks.py::apply_judge_reading;
final-2026 plan PR-01, 2026-10-18).

The first reading of a pick -- `ev_cons` and the `cons_*` columns -- is the
programme's evidence. Three paths used to overwrite it in place: `grade_pick`
at grading time (after `consensus_backfill` had usually read the pick an hour
past kickoff), `pick.py grade --regrade`, and `consensus_backfill --write`
without `--missing-only`. Now a recomputation that differs lands in
`judge_reading_audit` and the pick keeps its first reading; an identical
recomputation writes nothing. These tests work each path on an in-memory
SQLite with the real models, the real judge and the real grader.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from conftest import _load_script, _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.challenger_picks import grade_challenger_picks
from beatvegas.db.models import ChallengerPick, Game, JudgeReadingAudit, ManualPick, OddsSnapshot
from beatvegas.picks import JUDGE_FIELDS, apply_judge_reading, grade_pick

KICK = datetime(2026, 10, 10, 19, 30)
GAME_ID = 401
BOOKS = ("draftkings", "fanduel", "caesars")  # three counted books: the judge's minimum


def _game() -> Game:
    return Game(
        id=GAME_ID,
        season=2026,
        week=7,
        season_type="regular",
        start_date=KICK,
        home_team="Home",
        away_team="Away",
        home_points=20,
        away_points=14,
        first_half_total=17,
        first_half_source="linescores",
    )


def _snaps(line: float, minutes_before: int = 30) -> list:
    return [
        OddsSnapshot(
            game_id=GAME_ID,
            book=b,
            market="1H_total",
            line=line,
            over_price=-110,
            under_price=-110,
            captured_at=KICK - timedelta(minutes=minutes_before),
        )
        for b in BOOKS
    ]


def _manual() -> ManualPick:
    return ManualPick(
        game_id=GAME_ID,
        season=2026,
        week=7,
        side="under",
        market="1H",
        line=27.5,
        price=-110,
        stake=1.0,
        book="hardrockbet",
        is_paper=True,
        arm="H-ARM-1HU",
        placed_at=KICK - timedelta(days=2),
    )


def _challenger() -> ChallengerPick:
    return ChallengerPick(
        arm="H-ARM-1HO",
        game_id=GAME_ID,
        season=2026,
        week=7,
        side="over",
        market="1H",
        line=27.5,
        price=-110,
        stake=1.0,
        book="hardrockbet",
        placed_at=KICK - timedelta(days=2),
    )


@pytest.fixture
def db():
    """One finished game with a three-book close at 27.5, 30 minutes before kickoff."""
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(_game())
        s.add_all(_snaps(27.5))
        s.commit()
    return eng, scope


def _judge(p) -> dict:
    return {k: getattr(p, k) for k in JUDGE_FIELDS}


def test_the_first_grade_writes_the_reading_and_audits_nothing(db):
    eng, _ = db
    with Session(eng) as s:
        p = _manual()
        s.add(p)
        s.commit()
        assert grade_pick(s, p, s.get(Game, GAME_ID)) is True
        s.commit()
        assert p.graded is True
        assert p.cons_version == "cv1"
        assert p.cons_books == 3
        assert p.cons_line == 27.5
        assert p.ev_cons is not None
        assert s.query(JudgeReadingAudit).count() == 0


def test_a_regrade_that_disagrees_is_audited_and_the_reading_is_kept(db, monkeypatch):
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)  # by hand: the run id reads '-'
    eng, _ = db
    with Session(eng) as s:
        p = _manual()
        s.add(p)
        s.commit()
        grade_pick(s, p, s.get(Game, GAME_ID))
        s.commit()
        first = _judge(p)
        # Newer rows from the same books at 26.5: a recomputation now reads a
        # different close (one point off the wager, still convertible).
        s.add_all(_snaps(26.5, minutes_before=10))
        s.commit()

        assert grade_pick(s, p, s.get(Game, GAME_ID), judge_reason="regrade") is True
        s.commit()

        assert _judge(p) == first, "the first reading must survive a regrade byte for byte"
        rows = s.query(JudgeReadingAudit).all()
        assert len(rows) == 1
        a = rows[0]
        assert (a.ledger, a.pick_id, a.reason) == ("manual", p.id, "regrade")
        assert a.run_id == "-"
        changed = a.changed.split(",")
        assert "cons_line" in changed and "ev_cons" in changed
        assert json.loads(a.stored_json)["cons_line"] == 27.5
        assert json.loads(a.computed_json)["cons_line"] == 26.5
        assert json.loads(a.stored_json)["ev_cons"] == pytest.approx(first["ev_cons"])


def test_an_identical_recomputation_writes_nothing(db):
    eng, _ = db
    with Session(eng) as s:
        p = _manual()
        s.add(p)
        s.commit()
        grade_pick(s, p, s.get(Game, GAME_ID))
        s.commit()
        first = _judge(p)
        assert grade_pick(s, p, s.get(Game, GAME_ID), judge_reason="regrade") is True
        s.commit()
        assert _judge(p) == first
        assert s.query(JudgeReadingAudit).count() == 0


def test_apply_judge_reading_returns_each_outcome(db):
    eng, _ = db
    with Session(eng) as s:
        p = _manual()
        s.add(p)
        s.commit()
        fields = {k: None for k in JUDGE_FIELDS}
        fields.update({"cons_version": "cv1", "cons_books": 3, "cons_line": 27.5, "ev_cons": -0.04})
        assert apply_judge_reading(s, p, fields, reason="grade") == "written"
        assert p.ev_cons == -0.04
        assert apply_judge_reading(s, p, dict(fields), reason="backfill") == "same"
        moved = dict(fields, ev_cons=-0.01)
        assert apply_judge_reading(s, p, moved, reason="backfill", run_id="12345") == "audited"
        assert p.ev_cons == -0.04
        a = s.query(JudgeReadingAudit).one()
        assert (a.changed, a.run_id, a.reason) == ("ev_cons", "12345", "backfill")


def test_an_unknown_reason_is_refused():
    with pytest.raises(ValueError):
        apply_judge_reading(None, ManualPick(), {}, reason="whatever")


def test_a_challenger_regrade_is_audited_under_its_own_ledger(db):
    eng, _ = db
    with Session(eng) as s:
        c = _challenger()
        s.add(c)
        s.commit()
        assert grade_challenger_picks(s, 2026) == 1
        s.commit()
        first = _judge(c)
        s.add_all(_snaps(26.5, minutes_before=10))
        s.commit()
        assert grade_challenger_picks(s, 2026, regrade=True) == 1
        s.commit()
        assert _judge(c) == first
        a = s.query(JudgeReadingAudit).one()
        assert (a.ledger, a.pick_id, a.reason) == ("challenger", c.id, "regrade")


def test_the_backfill_fills_unread_rows_and_audits_read_ones(db, tmp_path, monkeypatch):
    eng, scope = db
    with Session(eng) as s:
        read, unread = _manual(), _challenger()
        s.add_all([read, unread])
        s.commit()
        grade_pick(s, read, s.get(Game, GAME_ID))
        s.commit()
        first_ev = read.ev_cons
        read_id, unread_id = read.id, unread.id
        s.add_all(_snaps(26.5, minutes_before=10))
        s.commit()

    mod = _load_script("consensus_backfill")
    monkeypatch.setattr(mod, "session_scope", scope)
    monkeypatch.setattr(mod, "try_init_db", lambda: True)
    # --write WITHOUT --missing-only: the path that used to overwrite every row.
    assert mod.main(["--write", "--out", str(tmp_path)]) == 0

    with Session(eng) as s:
        kept = s.get(ManualPick, read_id)
        assert kept.ev_cons == pytest.approx(first_ev)
        assert kept.cons_line == 27.5
        filled = s.get(ChallengerPick, unread_id)
        assert filled.cons_version == "cv1"
        assert filled.cons_line == 26.5  # its first reading is the newest close
        audits = s.query(JudgeReadingAudit).all()
        assert [(a.ledger, a.pick_id, a.reason) for a in audits] == [
            ("manual", read_id, "backfill")
        ]
    report = json.loads(next(tmp_path.glob("consensus_backfill_*.json")).read_text())
    assert (report["written"], report["kept"], report["audited"]) == (1, 0, 1)
