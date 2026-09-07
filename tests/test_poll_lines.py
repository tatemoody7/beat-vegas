"""scripts/poll_lines.py on the paid Odds API tier: capture EVERY Hard Rock 1H
line. Fake client, throwaway SQLite. The flags under test are the ones the
lines_watch.yml slots pass (opener sweep, per-game close, full refresh)."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, OddsSnapshot
from beatvegas.sources.odds import Credits

SEASON = 2026
NOW = datetime(2026, 9, 19, 15, 0)  # Sat 11am ET, week 3


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _event(eid, home, away, kick):
    return {"id": eid, "home_team": home, "away_team": away, "commence_time": _iso(kick)}


def _payload(ev, line=24.5, over=-110, under=-110, book="hardrockbet"):
    return {
        **ev,
        "bookmakers": [
            {
                "key": book,
                "markets": [
                    {
                        "key": "totals_h1",
                        "outcomes": [
                            {"name": "Over", "price": over, "point": line},
                            {"name": "Under", "price": under, "point": line},
                        ],
                    }
                ],
            }
        ],
    }


class FakeClient:
    """list_events is free (carries the credit headers); each per-event call
    costs 2 credits (totals_h1 x us,us2)."""

    cost = 2

    def __init__(self, events, payloads, remaining=60000):
        self.events = events
        self.payloads = payloads
        self.calls = []
        self.used = 100
        self.remaining = remaining
        self.last_credits = None

    def list_events(self):
        self.last_credits = Credits(self.remaining, self.used, 0)
        return self.events

    def event_first_half_totals(self, event_id):
        self.calls.append(event_id)
        self.used += self.cost
        self.remaining -= self.cost
        self.last_credits = Credits(self.remaining, self.used, self.cost)
        return self.payloads.get(event_id, {})

    def credits_low(self, floor):
        c = self.last_credits
        return floor > 0 and c is not None and c.remaining is not None and c.remaining <= floor


@pytest.fixture
def env(monkeypatch):
    mod = _load_script("poll_lines")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    mod.session_scope = scope
    mod.try_init_db = lambda: True
    mod.load_config = lambda: {"odds_api": {}}

    class _Now(datetime):
        @classmethod
        def utcnow(cls):
            return NOW

    monkeypatch.setattr(mod, "datetime", _Now)
    return mod, eng


def _run(mod, monkeypatch, client, *args):
    mod.OddsAPIClient = lambda: client
    monkeypatch.setattr(sys, "argv", ["poll_lines.py", "--season", str(SEASON), *args])
    mod.main()


def _seed(eng, games, hr_fg_for=(), hr_1h_for=()):
    with Session(eng) as s:
        for gid, home, away, kick in games:
            s.add(
                Game(id=gid, season=SEASON, week=3, home_team=home, away_team=away, start_date=kick)
            )
        for gid in hr_fg_for:
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book="hardrockbet",
                    market="full_game_total",
                    line=50.5,
                    captured_at=NOW - timedelta(days=5),
                )
            )
        for gid in hr_1h_for:
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book="hardrockbet",
                    market="1H_total",
                    line=24.5,
                    over_price=-110,
                    under_price=-110,
                    captured_at=NOW - timedelta(days=1),
                )
            )
        s.commit()


GAMES = [
    (1, "Missouri", "Kansas", NOW + timedelta(minutes=40)),
    (2, "Florida", "Kansas State", NOW + timedelta(hours=5)),
    (3, "Akron", "Toledo", NOW + timedelta(days=2)),
]
EVENTS = [_event(f"e{g[0]}", g[1], g[2], g[3]) for g in GAMES]
PAYLOADS = {e["id"]: _payload(e) for e in EVENTS}


def _snaps(eng, market="1H_total"):
    with Session(eng) as s:
        return s.query(OddsSnapshot).filter(OddsSnapshot.market == market).all()


def test_default_is_unlimited_events_and_writes_every_hr_line(env, monkeypatch, capsys):
    mod, eng = env
    _seed(eng, GAMES, hr_fg_for=(1, 2, 3))
    client = FakeClient(EVENTS, PAYLOADS)
    _run(mod, monkeypatch, client, "--hours-back", "0", "--days-ahead", "3")
    assert client.calls == ["e1", "e2", "e3"]  # no --max-events cap by default
    assert sorted(sn.game_id for sn in _snaps(eng)) == [1, 2, 3]
    out = capsys.readouterr().out
    assert "credits_spent=6" in out and "calls_404=0" in out


def test_kickoff_within_min_polls_only_imminent_games(env, monkeypatch):
    mod, eng = env
    _seed(eng, GAMES, hr_fg_for=(1, 2, 3))
    client = FakeClient(EVENTS, PAYLOADS)
    _run(mod, monkeypatch, client, "--hours-back", "0", "--kickoff-within-min", "75")
    assert client.calls == ["e1"]


def test_missing_hr_only_skips_games_hard_rock_already_priced(env, monkeypatch):
    mod, eng = env
    _seed(eng, GAMES, hr_fg_for=(1, 2, 3), hr_1h_for=(1,))
    client = FakeClient(EVENTS, PAYLOADS)
    _run(mod, monkeypatch, client, "--hours-back", "0", "--days-ahead", "6", "--missing-hr-only")
    assert client.calls == ["e2", "e3"]


def test_hr_universe_keeps_only_hard_rock_priced_games(env, monkeypatch, capsys):
    mod, eng = env
    _seed(eng, GAMES, hr_fg_for=(2,))
    client = FakeClient(EVENTS, PAYLOADS)
    _run(mod, monkeypatch, client, "--hours-back", "0", "--days-ahead", "6", "--hr-universe")
    assert client.calls == ["e2"]
    assert "::warning::" not in capsys.readouterr().out


def test_hr_universe_falls_back_loudly_when_sunday_capture_is_missing(env, monkeypatch, capsys):
    mod, eng = env
    _seed(eng, GAMES)  # no Hard Rock full-game rows at all
    client = FakeClient(EVENTS, PAYLOADS)
    _run(mod, monkeypatch, client, "--hours-back", "0", "--days-ahead", "6", "--hr-universe")
    assert client.calls == ["e1", "e2", "e3"]
    assert "::warning::" in capsys.readouterr().out


def test_unchanged_line_touches_last_seen_at_without_a_new_row(env, monkeypatch):
    mod, eng = env
    _seed(eng, GAMES, hr_fg_for=(1,), hr_1h_for=(1,))  # 24.5 -110/-110 already stored
    client = FakeClient(EVENTS[:1], {"e1": _payload(EVENTS[0])})
    _run(mod, monkeypatch, client, "--hours-back", "0", "--kickoff-within-min", "75")
    rows = _snaps(eng)
    assert len(rows) == 1  # no duplicate row
    assert rows[0].last_seen_at == NOW  # but the pre-kick confirmation is recorded
    assert rows[0].captured_at == NOW - timedelta(days=1)


def test_max_credits_per_run_stops_the_loop_and_warns(env, monkeypatch, capsys):
    mod, eng = env
    _seed(eng, GAMES, hr_fg_for=(1, 2, 3))
    client = FakeClient(EVENTS, PAYLOADS)
    _run(
        mod,
        monkeypatch,
        client,
        "--hours-back",
        "0",
        "--days-ahead",
        "6",
        "--max-credits-per-run",
        "4",
    )
    assert client.calls == ["e1", "e2"]
    out = capsys.readouterr().out
    assert "::warning::" in out and "credits_spent=4" in out


def test_no_odds_yet_is_counted_not_billed_as_a_snapshot(env, monkeypatch, capsys):
    mod, eng = env
    _seed(eng, GAMES, hr_fg_for=(1, 2, 3))
    client = FakeClient(EVENTS, {"e1": _payload(EVENTS[0])})  # e2/e3 -> {} (404)
    _run(mod, monkeypatch, client, "--hours-back", "0", "--days-ahead", "6")
    assert len(_snaps(eng)) == 1
    assert "calls_404=2" in capsys.readouterr().out
