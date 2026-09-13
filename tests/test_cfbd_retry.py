"""CFBDClient._get retries transient failures: the Aug 30 2026 Sunday run died
on a single requests.ReadTimeout. 4 attempts, backoff 5s/20s/60s, on timeout /
connection error / 429 / 5xx; 4xx (bad key, bad params) raises immediately.

The ladder was (2, 4) until 2026-09-13, which gave a rate limit six seconds to
clear. CFBD 429'd four consecutive grading runs over two days, so a 429 is a
quota window rather than a blip and now waits in minutes-adjacent steps -- or
for exactly as long as the server's Retry-After header asks.

An EXHAUSTED MONTHLY BUDGET is the one 429 that is never retried: the wait is
the rest of the calendar month. CFBD marks it with `x-calllimit-remaining: 0`
and a "Monthly call quota exceeded." body, and sends NO Retry-After -- verified
live against an exhausted key on 2026-09-13.
"""

import pytest
import requests

from beatvegas.sources.cfbd import (
    _LOW_CALLS_WARN,
    _MAX_RETRY_AFTER,
    CFBDClient,
    CFBDQuotaExceeded,
)


class _Resp:
    def __init__(self, status, payload=None, headers=None, text=""):
        self.status_code = status
        self._payload = payload if payload is not None else []
        self.headers = headers or {}
        self.text = text

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


# --- the monthly budget (2026-09-13) ----------------------------------------

_QUOTA_BODY = '{"message":"Monthly call quota exceeded."}'


def test_an_exhausted_monthly_budget_raises_at_once_and_spends_nothing(monkeypatch):
    """The failure that killed grading for two days. Retrying cannot clear it,
    and each retry is another call charged against a budget already at zero."""
    c, sleeps = _client(
        [_Resp(429, headers={"x-calllimit-remaining": "0"}, text=_QUOTA_BODY)] * 4,
        monkeypatch,
    )
    with pytest.raises(CFBDQuotaExceeded) as e:
        c.games(2026)
    assert c._session.calls == 1, "a spent budget must not be retried"
    assert sleeps == []
    assert "resets at the start of next month" in str(e.value)
    assert c.calls_remaining == 0
    # Still an HTTPError, so every existing handler keeps working.
    assert isinstance(e.value, requests.HTTPError)


def test_the_quota_body_alone_is_enough_without_the_header(monkeypatch):
    c, sleeps = _client([_Resp(429, text=_QUOTA_BODY)] * 4, monkeypatch)
    with pytest.raises(CFBDQuotaExceeded):
        c.games(2026)
    assert c._session.calls == 1 and sleeps == []


def test_a_plain_rate_limit_is_still_retried(monkeypatch):
    """A 429 with calls left is "slow down", not "come back next month"."""
    c, sleeps = _client(
        [
            _Resp(429, headers={"x-calllimit-remaining": "812"}),
            _Resp(200, [7], headers={"x-calllimit-remaining": "811"}),
        ],
        monkeypatch,
    )
    assert c.games(2026) == [7]
    assert c._session.calls == 2 and sleeps == [5]
    assert c.calls_remaining == 811


def test_the_budget_is_read_from_every_response_and_printed_once(monkeypatch, capsys):
    c, _ = _client(
        [
            _Resp(200, [1], headers={"x-calllimit-remaining": "900"}),
            _Resp(200, [2], headers={"x-calllimit-remaining": "899"}),
        ],
        monkeypatch,
    )
    c.games(2026)
    c.games(2026)
    assert c.calls_remaining == 899, "the latest value, not the first"
    assert capsys.readouterr().out.count("calls left in this month's budget") == 1


def test_a_low_budget_annotates_the_run(monkeypatch, capsys):
    """The only warning the system gets before every endpoint starts refusing."""
    c, _ = _client(
        [_Resp(200, [1], headers={"x-calllimit-remaining": str(_LOW_CALLS_WARN)})],
        monkeypatch,
    )
    c.games(2026)
    out = capsys.readouterr().out
    assert "::warning::" in out and "collegefootballdata.com/api-tiers" in out
    # One call above the line says nothing.
    c2, _ = _client(
        [_Resp(200, [1], headers={"x-calllimit-remaining": str(_LOW_CALLS_WARN + 1)})],
        monkeypatch,
    )
    c2.games(2026)
    assert "::warning::" not in capsys.readouterr().out


def test_a_missing_or_junk_budget_header_changes_nothing(monkeypatch):
    c, _ = _client(
        [_Resp(200, [1]), _Resp(200, [2], headers={"x-calllimit-remaining": "n/a"})],
        monkeypatch,
    )
    assert c.games(2026) == [1] and c.calls_remaining is None
    assert c.games(2026) == [2] and c.calls_remaining is None
