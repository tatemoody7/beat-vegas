"""The weather source had NO tests, and carried a three-year clock bug.

Both writers asked Open-Meteo for `timezone=auto` and then indexed the resulting
LOCAL hourly array at the UTC kickoff hour, so every stored reading was displaced
by the venue's UTC offset -- 4 to 10 hours for US venues, onto the wrong calendar
day for a late kickoff. Measured before the fix: LA Coliseum 2023-08-27T00:00Z
stored 63.2F (local midnight) against 78.1F at the real 5pm PDT kickoff.

The first two tests are the regression guard for exactly that. The rest pin what
the old module could not express at all: a rate limit is distinguishable from a
venue with no data, and a near-kickoff reading can never be mistaken for a
forecast we could have acted on.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import requests

from beatvegas.sources import weather as W
from beatvegas.sources._http import MAX_RETRY_AFTER


class _Resp:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload if payload is not None else {"hourly": {}}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def _day(hours, **series):
    """A one-day hourly payload keyed by UTC hour."""
    return {
        "hourly": dict(
            time=[f"2024-10-12T{h:02d}:00" for h in hours],
            **series,
        )
    }


class _Recorder(list):
    """The calls made, with the queue of canned responses hanging off it."""

    queue: list = []


@pytest.fixture
def calls(monkeypatch):
    """Record every outbound call; replay a queue of responses."""
    seen, queue = _Recorder(), []

    def fake_get(url, params=None, timeout=None):
        seen.append({"url": url, "params": params})
        item = queue.pop(0) if queue else _Resp(200, _day(range(24), temperature_2m=[50.0] * 24))
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(W.requests, "get", fake_get)
    monkeypatch.setattr(W.time, "sleep", lambda s: seen.append({"slept": s}))
    seen.queue = queue
    return seen


# --------------------------------------------------------------------------- #
# The regression guard
# --------------------------------------------------------------------------- #
def test_every_source_asks_for_utc(calls):
    """`timezone=auto` is what broke this. A local series cannot be keyed by UTC."""
    for source, lead in [
        (W.SOURCE_NEAR_KICKOFF, 0),
        (W.SOURCE_FORECAST, 0),
        (W.SOURCE_ACTUAL, 0),
        (W.SOURCE_DECISION, 24),
    ]:
        W.fetch_hourly_series(
            30.0, -96.0, "2024-10-12", "2024-10-12", source=source, lead_hours=lead
        )
    tz = [c["params"]["timezone"] for c in calls if "params" in c]
    assert tz == ["UTC"] * 4


def test_lookup_takes_the_utc_hour_not_a_positional_guess(calls):
    """Kickoff 17:00Z must read the 17:00Z value, whatever else is in the series.

    The series deliberately starts at 12:00, so a naive `temps[hour]` -- the old
    behaviour -- would return the 05:00 reading instead.
    """
    hours = list(range(12, 24))
    temps = [60.0 + h for h in hours]  # 17:00 -> 77.0
    calls.queue.append(_Resp(200, _day(hours, temperature_2m=temps)))
    got = W.fetch_weather(30.0, -96.0, datetime(2024, 10, 12, 17, 0), source=W.SOURCE_NEAR_KICKOFF)
    assert got["temperature_f"] == 77.0


# --------------------------------------------------------------------------- #
# Source selection
# --------------------------------------------------------------------------- #
def test_past_kickoffs_use_near_kickoff_and_future_use_forecast(calls, monkeypatch):
    now = datetime(2024, 10, 12, 12, 0)
    monkeypatch.setattr(W, "_today", lambda: now)
    W.fetch_weather(30.0, -96.0, now - timedelta(days=3))
    W.fetch_weather(30.0, -96.0, now + timedelta(days=3))
    urls = [c["url"] for c in calls if "url" in c]
    assert urls == [W._NEAR_KICKOFF_URL, W._FORECAST_URL]


def test_beyond_the_forecast_horizon_returns_none_without_calling(calls, monkeypatch):
    now = datetime(2024, 10, 12, 12, 0)
    monkeypatch.setattr(W, "_today", lambda: now)
    assert W.fetch_weather(30.0, -96.0, now + timedelta(days=40)) is None
    assert not [c for c in calls if "url" in c]


def test_decision_source_renames_variables_and_passes_the_model(calls):
    W.fetch_hourly_series(
        30.0,
        -96.0,
        "2024-10-12",
        "2024-10-12",
        source=W.SOURCE_DECISION,
        lead_hours=72,
        models="icon_seamless",
    )
    p = calls[0]["params"]
    assert p["models"] == "icon_seamless"
    assert set(p["hourly"].split(",")) == {
        "temperature_2m_previous_day3",
        "wind_speed_10m_previous_day3",
        "wind_gusts_10m_previous_day3",
        "precipitation_previous_day3",
    }


@pytest.mark.parametrize("lead", [12, 36, 0, 192])
def test_a_decision_lead_must_be_a_whole_day_within_range(lead):
    with pytest.raises(ValueError):
        W.fetch_hourly_series(
            30.0, -96.0, "2024-10-12", "2024-10-12", source=W.SOURCE_DECISION, lead_hours=lead
        )


# --------------------------------------------------------------------------- #
# A rate limit is not "no data"
# --------------------------------------------------------------------------- #
def test_429_honours_retry_after_then_succeeds(calls):
    calls.queue.extend(
        [
            _Resp(429, headers={"Retry-After": "7"}),
            _Resp(200, _day([17], temperature_2m=[71.0])),
        ]
    )
    got = W.fetch_weather(30.0, -96.0, datetime(2024, 10, 12, 17, 0), source=W.SOURCE_NEAR_KICKOFF)
    assert got["temperature_f"] == 71.0
    assert [c["slept"] for c in calls if "slept" in c] == [7.0]


def test_retry_after_is_capped(calls):
    calls.queue.extend([_Resp(429, headers={"Retry-After": "99999"}), _Resp(200)])
    W.fetch_hourly_series(30.0, -96.0, "2024-10-12", "2024-10-12")
    assert [c["slept"] for c in calls if "slept" in c] == [float(MAX_RETRY_AFTER)]


def test_exhausted_retries_raise_rather_than_returning_empty(calls):
    """647 venues were silently lost because this used to return {}."""
    calls.queue.extend([_Resp(429) for _ in range(4)])
    with pytest.raises(W.WeatherUnavailable):
        W.fetch_hourly_series(30.0, -96.0, "2024-10-12", "2024-10-12")


def test_a_bad_request_is_not_retried(calls):
    calls.queue.append(_Resp(404))
    with pytest.raises(requests.HTTPError):
        W.fetch_hourly_series(30.0, -96.0, "2024-10-12", "2024-10-12")
    assert len([c for c in calls if "url" in c]) == 1


def test_timeouts_ride_the_backoff_ladder(calls):
    calls.queue.extend([requests.Timeout("slow"), requests.ConnectionError("reset"), _Resp(200)])
    W.fetch_hourly_series(30.0, -96.0, "2024-10-12", "2024-10-12")
    assert [c["slept"] for c in calls if "slept" in c] == [5, 20]


# --------------------------------------------------------------------------- #
# The anti-look-ahead guard
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "source,lead,expected",
    [
        (W.SOURCE_NEAR_KICKOFF, 0, False),  # tracks actuals; never a decision-time read
        (W.SOURCE_FORECAST, 0, False),
        (W.SOURCE_ACTUAL, 0, False),
        (W.SOURCE_DECISION, 0, False),
        (W.SOURCE_DECISION, 24, True),
        (W.SOURCE_DECISION, 72, True),
    ],
)
def test_decision_safe_is_true_only_for_a_real_fixed_lead(source, lead, expected):
    assert W.decision_safe(source, lead) is expected


def test_there_is_no_helper_that_derives_a_run_time_from_the_lead():
    """`valid_time - lead_hours` is the NOMINAL horizon, which lead_hours already
    carries. A run initialises at one time and becomes usable at another, and
    Open-Meteo states neither for the `_previous_dayN` variables. A helper that
    manufactures one invites `available_at <= decision_time` to look tested when
    it is not, so it does not exist."""
    assert not hasattr(W, "forecast_asof")


def test_missing_coordinates_are_not_a_request(calls):
    assert W.fetch_hourly_series(None, -96.0, "2024-10-12", "2024-10-12") == {}
    assert W.fetch_weather(30.0, None, datetime(2024, 10, 12, 19, 0)) is None
    assert not [c for c in calls if "url" in c]
