"""season.detect_week must land on the UPCOMING week on a Sunday run. The old
tiebreak (most games in [now-2d, now+9d], then nearest kickoff) picked the week
that had just finished on a Sunday 18:00 UTC run — Saturday's slate is 1 day
away and outnumbers a light upcoming week. Offline: the games query is faked."""

from contextlib import contextmanager
from datetime import datetime, timedelta

from beatvegas import season as season_mod

SUNDAY_18Z = datetime(2026, 9, 6, 18, 0)  # the first Sunday-opener run of 2026


def _fake_games(monkeypatch, rows):
    class _Q:
        def filter(self, *a, **k):
            return self

        def all(self):
            return rows

    class _S:
        def query(self, *a, **k):
            return _Q()

    @contextmanager
    def scope():
        yield _S()

    monkeypatch.setattr("beatvegas.db.store.session_scope", scope)


def _slate(week, first_kick, n):
    # n kickoffs spread over ~8 hours (a real Saturday), never spilling into
    # the next day.
    return [(week, first_kick + timedelta(minutes=i * 8)) for i in range(n)]


def test_normal_sunday_picks_the_upcoming_week(monkeypatch):
    rows = _slate(1, datetime(2026, 9, 5, 16, 0), 50)  # Saturday, all played
    rows += _slate(2, datetime(2026, 9, 10, 23, 30), 1)  # Thursday night
    rows += _slate(2, datetime(2026, 9, 12, 16, 0), 48)  # Saturday
    _fake_games(monkeypatch, rows)
    assert season_mod.detect_week(2026, now=SUNDAY_18Z) == 2


def test_light_upcoming_slate_still_wins_on_sunday(monkeypatch):
    rows = _slate(1, datetime(2026, 9, 5, 16, 0), 60)  # big finished week
    rows += _slate(2, datetime(2026, 9, 12, 16, 0), 8)  # light bye-heavy week
    _fake_games(monkeypatch, rows)
    assert season_mod.detect_week(2026, now=SUNDAY_18Z) == 2


def test_labor_day_straggler_does_not_hold_week_one(monkeypatch):
    """Week 1 keeps a Monday-night game after the Sunday run; week 2 is still
    the upcoming week (its openers post that Sunday)."""
    rows = _slate(1, datetime(2026, 9, 5, 16, 0), 50)
    rows += [(1, datetime(2026, 9, 7, 23, 30))]  # Labor Day Monday
    rows += _slate(2, datetime(2026, 9, 12, 16, 0), 48)
    _fake_games(monkeypatch, rows)
    assert season_mod.detect_week(2026, now=SUNDAY_18Z) == 2


def test_saturday_morning_keeps_the_week_in_play(monkeypatch):
    rows = _slate(1, datetime(2026, 9, 3, 23, 30), 4)  # Thu/Fri, played
    rows += _slate(1, datetime(2026, 9, 5, 16, 0), 40)  # today, ahead
    rows += _slate(2, datetime(2026, 9, 12, 16, 0), 48)
    _fake_games(monkeypatch, rows)
    assert season_mod.detect_week(2026, now=datetime(2026, 9, 5, 12, 0)) == 1


def test_no_future_games_keeps_old_behaviour(monkeypatch):
    # Postseason lull: only a finished week inside the window -> still returned.
    rows = _slate(14, datetime(2026, 12, 5, 16, 0), 20)
    _fake_games(monkeypatch, rows)
    assert season_mod.detect_week(2026, now=datetime(2026, 12, 7, 12, 0)) == 14


def test_offseason_is_none(monkeypatch):
    _fake_games(monkeypatch, _slate(1, datetime(2026, 9, 5, 16, 0), 10))
    assert season_mod.detect_week(2026, now=datetime(2026, 6, 1)) is None


def test_active_uses_the_same_rule(monkeypatch):
    rows = _slate(1, datetime(2026, 9, 5, 16, 0), 50) + _slate(2, datetime(2026, 9, 12, 16), 8)
    _fake_games(monkeypatch, rows)
    assert season_mod.active(now=SUNDAY_18Z) == (2026, 2)
