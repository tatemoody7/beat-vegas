"""beatvegas/coverage.py -- the close-window coverage share (2026-09-28).

The `close` gauge stayed fresh through a Saturday on which GitHub's cron fired 3
of 18 close slots and only 18 of 57 Hard-Rock-priced games got any first-half
snapshot inside the 2-hour close window. This share is what says so."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from beatvegas import coverage
from beatvegas.db.models import Game, OddsSnapshot
from tests.conftest import _sqlite_scope

# Saturday 2026-09-26: 16:00Z (noon ET) and 23:30Z (7:30pm ET) kickoffs; Sunday
# 2026-09-27 01:00Z is still Saturday 9pm ET; Friday 2026-09-25 23:00Z is Friday.
SAT_NOON = datetime(2026, 9, 26, 16, 0)
SAT_EVE = datetime(2026, 9, 26, 23, 30)
SAT_LATE_UTC_SUNDAY = datetime(2026, 9, 27, 1, 0)
FRI = datetime(2026, 9, 25, 23, 0)
NOW = datetime(2026, 9, 28, 12, 0)


def _seed(s: Session):
    games = [
        Game(id=1, season=2026, week=4, start_date=SAT_NOON, home_team="A", away_team="B"),
        Game(id=2, season=2026, week=4, start_date=SAT_EVE, home_team="C", away_team="D"),
        Game(
            id=3, season=2026, week=4, start_date=SAT_LATE_UTC_SUNDAY, home_team="E", away_team="F"
        ),
        Game(id=4, season=2026, week=4, start_date=FRI, home_team="G", away_team="H"),
        # Hard Rock never priced this one: not in the universe.
        Game(id=5, season=2026, week=4, start_date=SAT_NOON, home_team="I", away_team="J"),
    ]
    s.add_all(games)
    hr = lambda gid, at, seen=None: OddsSnapshot(  # noqa: E731
        game_id=gid,
        book="hardrockbet",
        market="1H_total",
        line=24.5,
        captured_at=at,
        last_seen_at=seen,
    )
    dk = lambda gid, at: OddsSnapshot(  # noqa: E731
        game_id=gid, book="draftkings", market="1H_total", line=24.5, captured_at=at
    )
    s.add_all(
        [
            # game 1: priced Friday, re-seen 90 min before kickoff -> covered by last_seen_at
            hr(1, FRI - timedelta(hours=3), seen=SAT_NOON - timedelta(minutes=90)),
            # game 2: priced Saturday morning only (the sat_am sweep) -> not covered
            hr(2, datetime(2026, 9, 26, 11, 52)),
            # game 3: another book captured inside the window -> covered
            hr(3, datetime(2026, 9, 26, 11, 52)),
            dk(3, SAT_LATE_UTC_SUNDAY - timedelta(minutes=30)),
            # game 4 is Friday: priced and covered, but not a Saturday game
            hr(4, FRI - timedelta(minutes=30)),
            # game 5: draftkings only
            dk(5, SAT_NOON - timedelta(minutes=30)),
            # a full-game row inside the window must not count
            OddsSnapshot(
                game_id=2,
                book="draftkings",
                market="full_game_total",
                line=50.5,
                captured_at=SAT_EVE - timedelta(minutes=30),
            ),
        ]
    )


def test_last_saturday_share_counts_captured_or_reseen_inside_the_window():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        _seed(s)
        s.commit()
    with scope() as s:
        r = coverage.close_window_coverage(s, NOW)
    assert r == {"date": "2026-09-26", "games": 3, "covered": 2, "share": 2 / 3}


def test_a_saturday_afternoon_call_judges_only_the_games_that_have_kicked_off():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        _seed(s)
        s.commit()
    with scope() as s:
        r = coverage.close_window_coverage(s, SAT_NOON + timedelta(hours=1))
    assert r == {"date": "2026-09-26", "games": 1, "covered": 1, "share": 1.0}


def test_no_saturday_game_in_the_lookback_is_none_not_zero():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(Game(id=9, season=2026, week=4, start_date=FRI, home_team="A", away_team="B"))
        s.add(
            OddsSnapshot(
                game_id=9,
                book="hardrockbet",
                market="1H_total",
                line=20.5,
                captured_at=FRI - timedelta(hours=2),
            )
        )
        s.commit()
    with scope() as s:
        assert coverage.close_window_coverage(s, NOW) is None
        # And a Saturday game nobody priced is no universe at all.
        s.add(Game(id=10, season=2026, week=4, start_date=SAT_NOON, home_team="C", away_team="D"))
        s.flush()
        assert coverage.close_window_coverage(s, NOW) is None


def test_the_health_check_judges_saturday_runs_only(monkeypatch):
    from beatvegas import health

    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        _seed(s)
        s.commit()
    with scope() as s:
        weekday = health.Ctx(session=s, now=NOW, job="lines_watch", run_started_at=NOW)
        r = health.lines_watch_close_window_coverage(weekday)
        assert r.ok and "n/a" in r.detail
        sat = health.Ctx(
            session=s,
            now=datetime(2026, 9, 27, 2, 0),
            job="lines_watch",
            run_started_at=datetime(2026, 9, 27, 2, 0),
        )
        r = health.lines_watch_close_window_coverage(sat)
        assert not r.ok and "2/3" in r.detail and "floor 80%" in r.detail


def test_the_gauge_writer_records_share_and_note(monkeypatch, capsys):
    from beatvegas.db import store

    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        _seed(s)
        s.commit()
    import scripts.close_coverage as script

    monkeypatch.setattr(script, "try_init_db", lambda: True)
    monkeypatch.setattr(script, "session_scope", scope)
    monkeypatch.setattr(store, "session_scope", scope)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(script, "record_gauge", lambda k, v, note=None: (k, v, note) and True)
    script.main()
    out = capsys.readouterr().out
    assert "on Sat 2026-09-26" in out and "gauge written" in out
