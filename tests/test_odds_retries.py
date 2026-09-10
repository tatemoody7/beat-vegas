"""Retries on the PAID Odds API.

The free CFBD client retried and the paid Odds API client did not, so a single
transient 429 or 5xx mid-sweep failed the run — and because card.yml's sweep
step had no continue-on-error, that meant NO card was built at all on the most
likely degraded-card trigger. These tests pin the retry envelope and, just as
importantly, pin what must NOT be retried: a 404 is how the API says "this event
has no first-half market", and a 401 is a bad key.
"""

from __future__ import annotations

import pytest
import requests

from beatvegas.sources import odds as odds_mod
from beatvegas.sources.odds import OddsAPIClient


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.headers = {
            "x-requests-remaining": "999",
            "x-requests-used": "1",
            "x-requests-last": "1",
        }
        self._payload = payload if payload is not None else {"bookmakers": []}
        self.request = None

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for url: x?apiKey=SECRET")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(odds_mod.time, "sleep", lambda _s: None)


def _client(monkeypatch, responses):
    """A client whose transport replays `responses` (a Response or an Exception)."""
    monkeypatch.setattr(
        odds_mod, "load_config", lambda: {"odds_api": {"regions": "us", "bookmakers_1h": []}}
    )
    seq = list(responses)
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(odds_mod.requests, "get", fake_get)
    return OddsAPIClient(api_key="k"), calls


def test_a_timeout_then_success_is_one_successful_call(monkeypatch):
    c, calls = _client(monkeypatch, [requests.Timeout("timed out"), _Resp(200)])
    assert c.event_first_half_totals("e1") == {"bookmakers": []}
    assert len(calls) == 2


def test_a_429_is_retried(monkeypatch):
    c, calls = _client(monkeypatch, [_Resp(429), _Resp(200)])
    c.event_first_half_totals("e1")
    assert len(calls) == 2


def test_a_500_is_retried(monkeypatch):
    c, calls = _client(monkeypatch, [_Resp(503), _Resp(200)])
    c.event_first_half_totals("e1")
    assert len(calls) == 2


def test_it_gives_up_after_three_attempts_and_raises(monkeypatch):
    c, calls = _client(monkeypatch, [_Resp(503), _Resp(503), _Resp(503)])
    with pytest.raises(requests.HTTPError):
        c.event_first_half_totals("e1")
    assert len(calls) == 3


def test_a_404_is_NOT_retried_and_reads_as_no_first_half_market(monkeypatch):
    """event_first_half_totals returns {} on a 404; retrying would spend the
    sweep's wall clock on every unpriced event in the window."""
    c, calls = _client(monkeypatch, [_Resp(404)])
    assert c.event_first_half_totals("e1") == {}
    assert len(calls) == 1


def test_a_401_is_NOT_retried(monkeypatch):
    """A bad key is not transient."""
    c, calls = _client(monkeypatch, [_Resp(401)])
    with pytest.raises(requests.HTTPError):
        c.event_first_half_totals("e1")
    assert len(calls) == 1


def test_the_key_stays_redacted_through_a_retry_exhaustion(monkeypatch):
    """The whole point of the original _get: no apiKey in a CI traceback."""
    boom = requests.ConnectionError("failed for url: https://x?apiKey=SUPERSECRET&y=1")
    c, _ = _client(monkeypatch, [boom, boom, boom])
    with pytest.raises(requests.ConnectionError) as ei:
        c.event_first_half_totals("e1")
    assert "SUPERSECRET" not in str(ei.value)
    assert "apiKey=***" in str(ei.value)
