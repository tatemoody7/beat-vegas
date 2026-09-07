"""beatvegas.lines.real_closes: the pre-kickoff consensus close per game, with an
optional 'captured within N hours of kickoff' window so a Sunday opener alone
never masquerades as a real close."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, OddsSnapshot
from beatvegas.lines import REAL_1H_CLOSE_WINDOW_H, REAL_FG_CLOSE_WINDOW_H, real_closes

KICK = datetime(2026, 9, 19, 19, 30)


def _session(snaps):
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = Session(eng)
    for gid, line, hours_before in snaps:
        s.add(
            OddsSnapshot(
                game_id=gid,
                book="hardrockbet",
                market="1H_total",
                line=line,
                captured_at=KICK - timedelta(hours=hours_before),
            )
        )
    s.commit()
    return s


def test_windows_are_two_hours_1h_and_three_hours_fg():
    assert REAL_1H_CLOSE_WINDOW_H == 2.0 and REAL_FG_CLOSE_WINDOW_H == 3.0


def test_opener_plus_close_keeps_the_close():
    s = _session([(1, 24.5, 48), (1, 25.5, 0.5)])
    assert real_closes(s, [1], {1: KICK}, within_hours=2.0) == {1: 25.5}
    assert real_closes(s, [1], {1: KICK}) == {1: 25.5}


def test_opener_alone_is_not_a_real_close_inside_the_window():
    s = _session([(1, 24.5, 48)])
    assert real_closes(s, [1], {1: KICK}, within_hours=2.0) == {}


def test_no_window_keeps_legacy_behavior():
    s = _session([(1, 24.5, 48)])
    assert real_closes(s, [1], {1: KICK}, within_hours=None) == {1: 24.5}


def test_market_filter_and_empty_ids():
    s = _session([(1, 24.5, 0.5)])
    assert real_closes(s, [1], {1: KICK}, market="full_game_total") == {}
    assert real_closes(s, [], {}) == {}
