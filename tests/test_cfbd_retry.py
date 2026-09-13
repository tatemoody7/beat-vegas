"""CFBDClient._get retries transient failures: the Aug 30 2026 Sunday run died
on a single requests.ReadTimeout. 4 attempts, backoff 5s/20s/60s, on timeout /
connection error / 429 / 5xx; 4xx (bad key, bad params) raises immediately.

The ladder was (2, 4) until 2026-09-13, which gave a rate limit six seconds to
clear. CFBD 429'd four consecutive grading runs over two days, so a 429 is a
quota window rather than a blip and now waits in minutes-adjacent steps -- or
for exactly as long as the server's Retry-After header asks.
"""

import pytest
import requests

from beatvegas.sources.cfbd import _MAX_RETRY_AFTER, CFBDClient


class _Resp:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload if payload is not None else []
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


class _Session:
    """Scripted session: each call pops the next outcome (exception or _Resp)."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _client(outcomes, monkeypatch):
    sleeps = []
    monkeypatch.setattr("beatvegas.sources.cfbd.time.sleep", lambda s: sleeps.append(s))
    c = CFBDClient(api_key="k", base_url="https://x")
    c._session = _Session(outcomes)
    return c, sleeps


def test_read_timeout_is_retried_with_backoff(monkeypatch):
    c, sleeps = _client(
        [requests.ReadTimeout("t"), requests.ConnectionError("c"), _Resp(200, [{"id": 1}])],
        monkeypatch,
    )
    assert c.games(2026, week=1) == [{"id": 1}]
    assert c._session.calls == 3
    assert sleeps == [5, 20]


def test_5xx_and_429_are_retried(monkeypatch):
    c, sleeps = _client([_Resp(503), _Resp(429), _Resp(200, [7])], monkeypatch)
    assert c.games(2026) == [7]
    assert sleeps == [5, 20]


def test_gives_up_after_four_attempts(monkeypatch):
    c, sleeps = _client([requests.ReadTimeout(str(i)) for i in range(4)], monkeypatch)
    with pytest.raises(requests.ReadTimeout):
        c.games(2026)
    assert c._session.calls == 4
    assert sleeps == [5, 20, 60]  # no sleep after the final failure


def test_persistent_5xx_raises_http_error(monkeypatch):
    c, _ = _client([_Resp(500), _Resp(502), _Resp(503), _Resp(503)], monkeypatch)
    with pytest.raises(requests.HTTPError):
        c.games(2026)
    assert c._session.calls == 4


def test_4xx_is_not_retried(monkeypatch):
    c, sleeps = _client([_Resp(401)], monkeypatch)
    with pytest.raises(requests.HTTPError):
        c.games(2026)
    assert c._session.calls == 1 and sleeps == []


def test_retry_after_overrides_the_ladder(monkeypatch):
    c, sleeps = _client(
        [_Resp(429, headers={"Retry-After": "12"}), _Resp(200, [1])],
        monkeypatch,
    )
    assert c.games(2026) == [1]
    assert sleeps == [12]  # the server's number, not our 5


def test_retry_after_is_capped(monkeypatch):
    c, sleeps = _client(
        [_Resp(429, headers={"Retry-After": "99999"}), _Resp(200, [1])],
        monkeypatch,
    )
    assert c.games(2026) == [1]
    assert sleeps == [_MAX_RETRY_AFTER]


def test_unparseable_retry_after_falls_back_to_the_ladder(monkeypatch):
    # The HTTP-date form is legal and we do not parse it; a bad value must not
    # raise, it must just leave us on our own backoff.
    c, sleeps = _client(
        [_Resp(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), _Resp(200, [1])],
        monkeypatch,
    )
    assert c.games(2026) == [1]
    assert sleeps == [5]
