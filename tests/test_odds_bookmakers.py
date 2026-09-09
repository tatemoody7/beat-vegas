"""The 1-credit per-event 1H call.

The Odds API bills a per-event call (markets x regions), and every group of ten
named bookmakers counts as ONE region — `bookmakers` also takes priority over
`regions`. So naming our ten books costs 1 credit per event where `us,us2` cost
2, for the same market read. Verified live on 2026-09-09 against two real
events: `x-requests-last: 1`, and the response carried `hardrockbet` alongside
seven comparison books drawn from both regions.

These tests pin the three ways that saving silently reverts: sending `regions`
instead, sending BOTH (the API's precedence rule would hide it), and letting the
list grow past ten (which doubles every sweep for the rest of the season with
nothing in the output to say so). They also pin that the BULK full-game pull is
left alone — it is billed per region for the whole slate and needs `us_ex`.
"""

from __future__ import annotations

import pytest

from beatvegas.sources import odds as odds_mod
from beatvegas.sources.odds import MAX_BOOKMAKERS_ONE_REGION, OddsAPIClient

TEN = [
    "hardrockbet",
    "draftkings",
    "fanduel",
    "betmgm",
    "williamhill_us",
    "betrivers",
    "ballybet",
    "espnbet",
    "bovada",
    "fliff",
]


class _Resp:
    status_code = 200
    headers = {"x-requests-remaining": "1000", "x-requests-used": "1", "x-requests-last": "1"}

    def json(self):
        return {"bookmakers": []}

    def raise_for_status(self):
        return None


@pytest.fixture
def sent(monkeypatch):
    """Records the params of every request the client makes."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(dict(params or {}))
        return _Resp()

    monkeypatch.setattr(odds_mod.requests, "get", fake_get)
    return calls


def _client(monkeypatch, bookmakers):
    monkeypatch.setattr(
        odds_mod,
        "load_config",
        lambda: {"odds_api": {"regions": "us,us2", "bookmakers_1h": list(bookmakers)}},
    )
    return OddsAPIClient(api_key="k")


def test_per_event_call_names_books_and_never_sends_regions(monkeypatch, sent):
    """The 1-credit path: `bookmakers`, and NOT `regions`. Sending both still
    works today, but then the saving depends on the API's precedence rule
    rather than on what we asked for."""
    c = _client(monkeypatch, TEN)
    c.event_first_half_totals("e1")
    assert sent[0]["bookmakers"] == ",".join(TEN)
    assert "regions" not in sent[0]
    assert sent[0]["markets"] == "totals_h1"


def test_an_empty_list_falls_back_to_region_pricing(monkeypatch, sent):
    """`poll_lines.py --regions` clears the list to force the 2-credit path for
    an A/B probe, so that path has to keep working."""
    c = _client(monkeypatch, [])
    c.event_first_half_totals("e1")
    assert sent[0]["regions"] == "us,us2"
    assert "bookmakers" not in sent[0]


def test_the_historical_endpoint_takes_the_same_cheap_path(monkeypatch, sent):
    """Historical snapshots are billed at a higher multiplier per region, so the
    saving is proportionally the same — and a backfill must compare against the
    same ten-book universe the live sweep sees."""
    c = _client(monkeypatch, TEN)
    c.historical_event_first_half_totals("e1", "2026-09-01T12:00:00Z")
    assert sent[0]["bookmakers"] == ",".join(TEN)
    assert "regions" not in sent[0]


@pytest.mark.parametrize("books", [TEN, []])
def test_the_bulk_full_game_pull_always_prices_by_region(monkeypatch, sent, books):
    """The bulk endpoint is billed (markets x regions) for the WHOLE slate — 4
    credits, or 6 with the exchanges — and the Sunday capture needs `us_ex` for
    the exchange fair price. Naming books here would cap the slate at those ten
    and save nothing, so it must never inherit the per-event scope."""
    c = _client(monkeypatch, books)
    c.list_full_game_odds(regions="us,us2,us_ex")
    assert sent[0]["regions"] == "us,us2,us_ex"
    assert "bookmakers" not in sent[0]


def test_an_eleventh_book_is_refused_at_construction(monkeypatch):
    """Eleven books is a second region: every per-event call silently doubles,
    and nothing in the sweep output would say so. Fail loudly at startup."""
    with pytest.raises(ValueError, match="doubles the cost"):
        _client(monkeypatch, TEN + ["betonlineag"])
    # Exactly at the limit is fine.
    assert len(_client(monkeypatch, TEN).bookmakers) == MAX_BOOKMAKERS_ONE_REGION
