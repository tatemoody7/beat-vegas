"""The Odds API key rides in the query string, and requests echoes the full URL
in every HTTPError message — which lands in GitHub Actions logs on a 401/429.
Every raise site and every printed fetch error must redact it."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
import requests
from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game
from beatvegas.sources import odds
from beatvegas.sources.odds import Credits, OddsAPIClient, _raise_for_status, redact_key

URL = "https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/events?apiKey=SECRET&dateFormat=iso"


def _resp(status=401, url=URL, reason="Unauthorized"):
    r = requests.Response()
    r.status_code = status
    r.url = url
    r.reason = reason
    r._content = b"{}"
    return r


def test_redact_key_masks_the_query_value_and_is_idempotent():
    once = redact_key(URL)
    assert "SECRET" not in once
    assert "apiKey=***&dateFormat=iso" in once
    assert redact_key(once) == once
    # trailing key, quoted key, key followed by whitespace
    assert redact_key("x?apiKey=abc") == "x?apiKey=***"
    assert redact_key("'x?apiKey=abc' then") == "'x?apiKey=***' then"
    assert redact_key("no key here") == "no key here"


def test_raise_for_status_redacts_the_url_in_the_error():
    with pytest.raises(requests.HTTPError) as ei:
        _raise_for_status(_resp())
    msg = str(ei.value)
    assert "401" in msg and "***" in msg and "SECRET" not in msg
    assert ei.value.response.status_code == 401  # callers still read the status


def test_raise_for_status_is_a_no_op_on_success():
    _raise_for_status(_resp(status=200, reason="OK"))


def test_client_calls_raise_redacted_errors(monkeypatch):
    monkeypatch.setattr(odds, "load_config", lambda: {})
    monkeypatch.setattr(odds.requests, "get", lambda *a, **k: _resp())
    client = OddsAPIClient(api_key="SECRET")
    for call in (
        client.list_events,
        client.list_full_game_totals,
        lambda: client.event_first_half_totals("evt1"),
        lambda: client.list_historical_events("2025-09-06T12:00:00Z"),
        lambda: client.historical_bulk_totals("2025-09-06T12:00:00Z"),
        lambda: client.historical_event_first_half_totals("evt1", "2025-09-06T12:00:00Z"),
    ):
        with pytest.raises(requests.HTTPError) as ei:
            call()
        assert "SECRET" not in str(ei.value), call


def test_client_redacts_transport_errors_too(monkeypatch):
    """requests.get itself can raise (ConnectionError, ReadTimeout, ...) before
    there's ever a Response to call _raise_for_status on. That path used to
    bypass redaction entirely and leak the raw apiKey in the exception."""
    monkeypatch.setattr(odds, "load_config", lambda: {})

    def _boom(*a, **k):
        raise requests.ConnectionError(f"Max retries exceeded with url: {URL}")

    monkeypatch.setattr(odds.requests, "get", _boom)
    client = OddsAPIClient(api_key="SECRET")
    for call in (client.list_events, client.list_full_game_odds):
        with pytest.raises(requests.ConnectionError) as ei:
            call()
        assert "SECRET" not in str(ei.value), call
        assert "***" in str(ei.value), call


def test_poll_lines_fetch_failure_print_lacks_the_key(monkeypatch, capsys):
    mod = _load_script("poll_lines")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    now = datetime(2026, 9, 19, 15, 0)
    kick = now + timedelta(hours=5)
    with Session(eng) as s:
        s.add(
            Game(id=1, season=2026, week=3, home_team="LSU", away_team="Clemson", start_date=kick)
        )
        s.commit()

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    class _Now(datetime):
        @classmethod
        def utcnow(cls):
            return now

    class _Client:
        def __init__(self):
            self.last_credits = None

        def list_events(self):
            self.last_credits = Credits(60000, 100, 0)
            return [
                {
                    "id": "e1",
                    "home_team": "LSU",
                    "away_team": "Clemson",
                    "commence_time": kick.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            ]

        def event_first_half_totals(self, event_id):
            # A transport error bypasses _raise_for_status; requests still puts
            # the full URL (key included) in the message.
            raise requests.ConnectionError(f"Max retries exceeded with url: {URL}")

        def credits_low(self, floor):
            return False

    monkeypatch.setattr(mod, "session_scope", scope)
    monkeypatch.setattr(mod, "try_init_db", lambda: True)
    monkeypatch.setattr(mod, "load_config", lambda: {"odds_api": {}})
    monkeypatch.setattr(mod, "datetime", _Now)
    monkeypatch.setattr(mod, "OddsAPIClient", _Client)
    monkeypatch.setattr(sys, "argv", ["poll_lines.py", "--season", "2026"])
    try:
        mod.main()
    except SystemExit:
        pass  # an incomplete sweep fails the run on purpose
    out = capsys.readouterr().out
    assert "FAILED" in out
    assert "SECRET" not in out and "apiKey=***" in out
