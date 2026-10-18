"""The research_snapshots writer (beatvegas/research_capture.py; final-2026 plan C11).

Research capture lands in its own table so cv1, pv1, the HT1H trigger and the
card keep reading `odds_snapshots` exactly as registered. Live purposes write on
change and bump `last_seen_at`; archive waves write every row as an observation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from conftest import _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas import research_capture as rc
from beatvegas.db.models import ResearchSnapshot

T0 = datetime(2026, 10, 24, 15, 0)


def _row(book="pinnacle", line=52.5, over=-108, under=-104, **extra):
    r = {
        "event_id": "ev1",
        "game_id": 401,
        "book": book,
        "market": "full_game_total",
        "line": line,
        "over_price": over,
        "under_price": under,
        "last_update": "2026-10-24T14:58:00Z",
    }
    r.update(extra)
    return r


@pytest.fixture
def db():
    eng, _ = _sqlite_scope()
    return eng


def test_live_rows_write_on_change_and_reseen_bumps_last_seen(db):
    with Session(db) as s:
        out = rc.write_rows(s, [_row()], purpose="sharp_eu", region="eu", request_id=7, now=T0)
        s.commit()
        assert out == {"written": 1, "reseen": 0}
        out = rc.write_rows(
            s, [_row()], purpose="sharp_eu", region="eu", now=T0 + timedelta(hours=1)
        )
        s.commit()
        assert out == {"written": 0, "reseen": 1}
        rows = s.query(ResearchSnapshot).all()
        assert len(rows) == 1
        r = rows[0]
        assert (r.purpose, r.region, r.request_id, r.source) == ("sharp_eu", "eu", 7, "live")
        assert r.captured_at == T0 and r.last_seen_at == T0 + timedelta(hours=1)
        assert r.feed_updated_at == datetime(2026, 10, 24, 14, 58)
        out = rc.write_rows(
            s, [_row(line=53.5)], purpose="sharp_eu", region="eu", now=T0 + timedelta(hours=2)
        )
        s.commit()
        assert out == {"written": 1, "reseen": 0}
        assert s.query(ResearchSnapshot).count() == 2


def test_purposes_do_not_dedupe_against_each_other(db):
    with Session(db) as s:
        rc.write_rows(s, [_row()], purpose="sharp_eu", region="eu", now=T0)
        out = rc.write_rows(s, [_row()], purpose="fg_midweek", now=T0)
        s.commit()
        assert out["written"] == 1
        assert s.query(ResearchSnapshot).count() == 2


def test_ladder_rungs_and_team_totals_are_distinct_rows(db):
    rungs = [
        _row(book="hardrockbet", market="alt_1H_total", line=ln, over=o, under=u)
        for ln, o, u in ((26.5, -150, 120), (27.5, -115, -105), (28.5, 110, -140))
    ]
    teams = [
        _row(book="draftkings", market="team_total", line=24.5, team="Home"),
        _row(book="draftkings", market="team_total", line=28.5, team="Away"),
    ]
    with Session(db) as s:
        out = rc.write_rows(s, rungs, purpose="hr_ladder_close", region="books", now=T0)
        out2 = rc.write_rows(s, teams, purpose="team_totals", region="books", now=T0)
        s.commit()
        assert (out["written"], out2["written"]) == (3, 2)
        assert {r.team for r in s.query(ResearchSnapshot).filter_by(market="team_total")} == {
            "Home",
            "Away",
        }


def test_archive_waves_keep_every_observation_and_the_envelope_stamp(db):
    wave1 = _row(captured_at=datetime(2026, 9, 12, 18, 0))
    wave2 = _row(captured_at=datetime(2026, 9, 12, 19, 0))  # same price, later wave
    with Session(db) as s:
        out = rc.write_rows(
            s,
            [wave1, wave2],
            purpose="archive_pinnacle_2026",
            region="eu",
            source="historical",
            dedupe=False,
        )
        s.commit()
        assert out == {"written": 2, "reseen": 0}
        rows = s.query(ResearchSnapshot).order_by(ResearchSnapshot.captured_at).all()
        assert [r.captured_at.hour for r in rows] == [18, 19]
        assert all(r.source == "historical" and r.last_seen_at is None for r in rows)


def test_region_falls_back_to_the_book_table(db):
    with Session(db) as s:
        rc.write_rows(
            s,
            [_row(book="pinnacle"), _row(book="kalshi"), _row(book="nobodyknows")],
            purpose="probe",
            now=T0,
        )
        s.commit()
        got = {r.book: r.region for r in s.query(ResearchSnapshot)}
        assert got == {"pinnacle": "eu", "kalshi": "us_ex", "nobodyknows": "unknown"}


def test_unknown_purpose_or_source_is_refused(db):
    with Session(db) as s:
        with pytest.raises(ValueError):
            rc.write_rows(s, [_row()], purpose="whatever")
        with pytest.raises(ValueError):
            rc.write_rows(s, [_row()], purpose="probe", source="guess")


def test_frozen_readers_do_not_import_the_research_writer():
    """cv1, pv1, the HT1H trigger and the card must never see research rows."""
    import importlib
    import sys

    for mod in (
        "beatvegas.consensus",
        "beatvegas.pricing",
        "beatvegas.ht_paper",
        "beatvegas.card",
        "beatvegas.lines",
    ):
        importlib.import_module(mod)
    src_names = {"beatvegas.research_capture"}
    for mod in (
        "beatvegas.consensus",
        "beatvegas.pricing",
        "beatvegas.ht_paper",
        "beatvegas.card",
        "beatvegas.lines",
    ):
        text = open(sys.modules[mod].__file__).read()
        assert "research_capture" not in text and "ResearchSnapshot" not in text, mod
    assert src_names
