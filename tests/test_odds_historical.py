"""Historical Odds-API responses wrap the payload in a snapshot envelope.

The historical endpoints return {timestamp, previous_timestamp, next_timestamp,
data: ...} where `data` is a list (events) or a single object (event odds). The
unwrap helper pulls `data` out so the existing normalizer can be reused as-is.
"""

from __future__ import annotations

from beatvegas.sources.odds import _unwrap_historical


def test_unwrap_historical_events_list():
    payload = {"timestamp": "2023-10-07T16:00:00Z", "data": [{"id": "a"}, {"id": "b"}]}
    assert _unwrap_historical(payload) == [{"id": "a"}, {"id": "b"}]


def test_unwrap_historical_single_event_odds():
    payload = {"timestamp": "t", "data": {"id": "a", "bookmakers": []}}
    assert _unwrap_historical(payload) == {"id": "a", "bookmakers": []}


def test_unwrap_historical_missing_data_is_none():
    assert _unwrap_historical({}) is None
