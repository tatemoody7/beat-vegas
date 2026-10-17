"""scripts/research_preview.py --status-file: the health file the card reads.

The QB-out gate on the card reads whatever game_previews says. An EMPTY
Rotowire injury feed writes blanks, which makes that gate pass every game
silently — so `ok` tracks the injury feed only. ESPN news is display-only: an
empty news feed is recorded but never flips `ok`.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime

import pytest
from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, GamePreview, Team

SEASON, WEEK = 2026, 3
NOW = datetime(2026, 9, 19, 12, 40)

ROWS = [{"team": "Missouri", "player": "QB Someone", "position": "QB", "status": "Out"}]


@pytest.fixture
def env(monkeypatch):
    """The script bound to a throwaway SQLite DB with one game, both unofficial
    sources stubbed."""
    mod = _load_script("research_preview")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=SEASON, week=WEEK, home_team="Missouri", away_team="Kansas"))
        s.add_all([Team(school="Missouri"), Team(school="Kansas")])
        s.commit()

    @contextmanager
    def scope():
        with Session(eng) as sess:
            yield sess
            sess.commit()

    mod.session_scope = scope
    mod.try_init_db = lambda: True
    monkeypatch.setattr(mod.rotowire, "fetch_injury_report", lambda: list(ROWS))
    monkeypatch.setattr(mod.rotowire, "by_school", lambda report, schools: {})
    monkeypatch.setattr(mod, "teams_available", lambda: True)
    monkeypatch.setattr(mod, "espn_team_id", lambda school: None)
    monkeypatch.setattr(mod, "team_news", lambda eid: [])
    return mod, eng


def _run(mod, monkeypatch, *args):
    import sys

    monkeypatch.setattr(
        sys, "argv", ["research_preview.py", "--season", str(SEASON), "--week", str(WEEK), *args]
    )
    mod.main()


def _status(path):
    return json.loads(path.read_text())


def test_a_healthy_run_reports_ok(env, monkeypatch, tmp_path):
    mod, eng = env
    out = tmp_path / "preview.json"
    _run(mod, monkeypatch, "--status-file", str(out))
    assert _status(out) == {
        "ok": True,
        "reason": None,
        "rotowire_rows": 1,
        "espn_ok": True,
        "games": 1,
        "qb_outs": 0,
    }
    with Session(eng) as s:
        assert s.query(GamePreview).count() == 1


def test_every_run_freezes_the_whole_injury_report_with_its_slot(env, monkeypatch, tmp_path):
    """2026-10-04: one injury_snapshots row per run -- the raw report, the
    season/week it fed and the card slot (SLOT env from card.yml, or --slot).
    game_previews is overwritten every build; this is the only record of what
    the QB-out gate read at THIS build."""
    from beatvegas.db.models import InjurySnapshot

    mod, eng = env
    monkeypatch.setenv("SLOT", "tue_pm")
    _run(mod, monkeypatch, "--status-file", str(tmp_path / "a.json"))
    monkeypatch.delenv("SLOT", raising=False)
    _run(mod, monkeypatch, "--slot", "fri_pm")
    # an empty feed still leaves its row: [] is the evidence of the outage
    monkeypatch.setattr(mod.rotowire, "fetch_injury_report", lambda: [])
    _run(mod, monkeypatch)
    with Session(eng) as s:
        rows = s.query(InjurySnapshot).order_by(InjurySnapshot.id).all()
    assert [r.slot for r in rows] == ["tue_pm", "fri_pm", None]
    assert all((r.season, r.week, r.source) == (SEASON, WEEK, "rotowire") for r in rows)
    assert json.loads(rows[0].report_json) == ROWS and json.loads(rows[2].report_json) == []
    assert all(r.captured_at is not None for r in rows)


def test_an_empty_injury_feed_is_not_ok_but_still_writes_the_slate(env, monkeypatch, tmp_path):
    """ESPN is up, so the run is not fatal and the previews are written — but the
    QB read behind them is blank, and the status says so."""
    mod, eng = env
    monkeypatch.setattr(mod.rotowire, "fetch_injury_report", lambda: [])
    out = tmp_path / "preview.json"
    _run(mod, monkeypatch, "--status-file", str(out))
    st = _status(out)
    assert st["ok"] is False and st["reason"] == "rotowire_empty"
    assert st["rotowire_rows"] == 0 and st["espn_ok"] is True and st["games"] == 1


def test_an_empty_espn_news_feed_alone_stays_ok(env, monkeypatch, tmp_path):
    """News is display-only: it must never flip the card into degraded."""
    mod, eng = env
    monkeypatch.setattr(mod, "teams_available", lambda: False)
    out = tmp_path / "preview.json"
    _run(mod, monkeypatch, "--status-file", str(out))
    st = _status(out)
    assert st["ok"] is True and st["reason"] is None and st["espn_ok"] is False


def test_both_sources_empty_writes_the_status_before_the_fatal_exit(env, monkeypatch, tmp_path):
    mod, eng = env
    monkeypatch.setattr(mod.rotowire, "fetch_injury_report", lambda: [])
    monkeypatch.setattr(mod, "teams_available", lambda: False)
    out = tmp_path / "preview.json"
    with pytest.raises(SystemExit) as exc:
        _run(mod, monkeypatch, "--status-file", str(out))
    assert exc.value.code == 3
    assert _status(out) == {
        "ok": False,
        "reason": "both_empty",
        "rotowire_rows": 0,
        "espn_ok": False,
        "games": 0,
        "qb_outs": 0,
    }
    with Session(eng) as s:
        assert s.query(GamePreview).count() == 0  # nothing written


def test_an_unreachable_database_is_not_ok(env, monkeypatch, tmp_path):
    """Symmetric with poll_lines: nothing was written, so the card must not read
    this exit as a healthy QB read. Before, it wrote ok True."""
    mod, eng = env
    mod.try_init_db = lambda: False
    out = tmp_path / "preview.json"
    _run(mod, monkeypatch, "--status-file", str(out))
    assert _status(out) == {
        "ok": False,
        "reason": "db_unreachable",
        "rotowire_rows": 1,
        "espn_ok": True,
        "games": 0,
        "qb_outs": 0,
    }
    with Session(eng) as s:
        assert s.query(GamePreview).count() == 0


def test_no_status_file_flag_writes_nothing(env, monkeypatch, tmp_path):
    mod, _ = env
    _run(mod, monkeypatch)
    assert list(tmp_path.iterdir()) == []


def test_an_uncovered_game_is_marked_not_covered_and_its_qb_unknown(env, monkeypatch):
    """2026-10-17 audit: Rotowire's public feed is a ~5-row teaser of that day's
    games, so a game the pull does not name has NO injury read. It is stored
    covered=False with qb_out NULL (unknown), never as an empty "all clear"."""
    mod, eng = env  # by_school is stubbed to match nothing
    _run(mod, monkeypatch)
    with Session(eng) as s:
        p = s.query(GamePreview).one()
        assert json.loads(p.injuries_json) == {"home": [], "away": [], "covered": False}
        assert p.qb_out is None


def test_a_covered_game_keeps_its_rows_and_a_listed_qb_is_out(env, monkeypatch):
    mod, eng = env
    qb = {
        "player": "QB Someone",
        "position": "QB",
        "IR": "Out",
        "injury_type": "Knee",
        "team": "Missouri",
        "RotoSchoolName": "Missouri",
    }
    monkeypatch.setattr(mod.rotowire, "by_school", lambda report, schools: {"Missouri": [qb]})
    monkeypatch.setattr(
        mod.rotowire, "qb_out_detail", lambda rows: "QB Someone — Out" if rows else ""
    )
    _run(mod, monkeypatch)
    with Session(eng) as s:
        p = s.query(GamePreview).one()
        inj = json.loads(p.injuries_json)
        assert inj["covered"] is True and len(inj["home"]) == 1 and inj["away"] == []
        assert p.qb_out is True and "QB Someone" in p.qb_out_detail
