"""The Odds API v4 client for college-football first-half totals (totals_h1).

Free tier = 500 requests/month. Additional markets like totals_h1 cost credits
per region, so we surface the credit headers on every call. The normalizer turns
the nested events->bookmakers->markets->outcomes JSON into flat snapshot rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from ..config import load_config, odds_api_key


@dataclass
class Credits:
    remaining: Optional[int]
    used: Optional[int]
    last_cost: Optional[int]


class OddsAPIClient:
    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        cfg = load_config().get("odds_api", {}) or {}
        self.api_key = api_key or odds_api_key()
        self.base_url = (cfg.get("base_url") or "https://api.the-odds-api.com/v4").rstrip("/")
        self.sport = cfg.get("sport", "americanfootball_ncaaf")
        self.regions = cfg.get("regions", "us")
        self.markets = cfg.get("markets", "totals_h1")
        self.odds_format = cfg.get("odds_format", "american")
        self.timeout = timeout
        self.last_credits: Optional[Credits] = None

    def _credits(self, resp: requests.Response) -> Credits:
        def _int(h):
            v = resp.headers.get(h)
            return int(v) if v is not None and v != "" else None

        c = Credits(
            remaining=_int("x-requests-remaining"),
            used=_int("x-requests-used"),
            last_cost=_int("x-requests-last"),
        )
        self.last_credits = c
        return c

    def list_full_game_totals(self, regions: Optional[str] = None) -> List[Dict[str, Any]]:
        """Full-game `totals` for every book in `regions`, from the BULK /odds
        endpoint. `totals` is a FEATURED market, so this costs (1 x n_regions)
        credits TOTAL for the whole slate — cheap vs the per-event 1H calls.

        Hard Rock's LIVE book key is `hardrockbet` (the docs' FL-specific
        `hardrockbet_fl` has not appeared in responses; hardrock.py accepts
        both). It lives in the `us2` region only — verified empirically — so
        pass regions='us,us2' to capture it alongside the rest of the market."""
        url = f"{self.base_url}/sports/{self.sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions or self.regions,
            "markets": "totals",
            "oddsFormat": self.odds_format,
            "dateFormat": "iso",
        }
        resp = requests.get(url, params=params, timeout=self.timeout)
        self._credits(resp)
        resp.raise_for_status()
        return resp.json()

    def list_events(self) -> List[Dict[str, Any]]:
        """Upcoming events for the sport. FREE (0 credits). Each has id,
        commence_time, home_team, away_team — but no odds."""
        url = f"{self.base_url}/sports/{self.sport}/events"
        resp = requests.get(
            url, params={"apiKey": self.api_key, "dateFormat": "iso"}, timeout=self.timeout
        )
        self._credits(resp)
        resp.raise_for_status()
        return resp.json()

    def event_first_half_totals(self, event_id: str) -> Dict[str, Any]:
        """totals_h1 odds for one event. Costs (markets x regions) credits.

        Additional markets like totals_h1 are ONLY served on this per-event
        endpoint, not the bulk /odds endpoint."""
        url = f"{self.base_url}/sports/{self.sport}/events/{event_id}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": self.regions,
            "markets": self.markets,
            "oddsFormat": self.odds_format,
            "dateFormat": "iso",
        }
        resp = requests.get(url, params=params, timeout=self.timeout)
        self._credits(resp)
        if resp.status_code == 404:
            return {}  # event has no odds posted yet
        resp.raise_for_status()
        return resp.json()

    # --- historical (paid backfill / coverage gate, plan Phase 0) -------------
    def list_historical_events(self, date_iso: str) -> List[Dict[str, Any]]:
        """Events as of a past timestamp. The historical envelope wraps the list
        in `data`. Cheap (no odds)."""
        url = f"{self.base_url}/historical/sports/{self.sport}/events"
        resp = requests.get(
            url,
            params={"apiKey": self.api_key, "date": date_iso, "dateFormat": "iso"},
            timeout=self.timeout,
        )
        self._credits(resp)
        resp.raise_for_status()
        return _unwrap_historical(resp.json()) or []

    def historical_event_first_half_totals(self, event_id: str, date_iso: str) -> Dict[str, Any]:
        """totals_h1 odds for one event as of a past timestamp. Historical
        snapshots cost more per market than live calls — probe sparingly."""
        url = f"{self.base_url}/historical/sports/{self.sport}/events/{event_id}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": self.regions,
            "markets": self.markets,
            "oddsFormat": self.odds_format,
            "dateFormat": "iso",
            "date": date_iso,
        }
        resp = requests.get(url, params=params, timeout=self.timeout)
        self._credits(resp)
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return _unwrap_historical(resp.json()) or {}


def _unwrap_historical(payload: Dict[str, Any]):
    """Pull `data` out of a historical snapshot envelope (list of events, or a
    single event-odds object). Returns None when absent."""
    return payload.get("data")


def _rows_for_market(
    events: List[Dict[str, Any]], market_key: str, books: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Flatten events into one row per (event, book) for a totals market.

    Each row: event_id, commence_time, home_team, away_team, book, line,
    over_price, under_price, last_update."""
    book_filter = set(books) if books else None
    # Keyed by (event, book): with several regions requested the API can list
    # the same bookmaker key twice for one event, and two rows sharing
    # (game_id, book, market, captured_at) violate uq_odds_snapshot on insert.
    # Keep the freshest quote (latest last_update).
    by_key: Dict[tuple, Dict[str, Any]] = {}
    for ev in events:
        for bm in ev.get("bookmakers", []):
            if book_filter and bm.get("key") not in book_filter:
                continue
            for mkt in bm.get("markets", []):
                if mkt.get("key") != market_key:
                    continue
                over_price = under_price = line = None
                for oc in mkt.get("outcomes", []):
                    name = (oc.get("name") or "").lower()
                    if name == "over":
                        over_price, line = oc.get("price"), oc.get("point")
                    elif name == "under":
                        under_price, line = oc.get("price"), oc.get("point")
                if line is None:
                    continue
                row = {
                    "event_id": ev.get("id"),
                    "commence_time": ev.get("commence_time"),
                    "home_team": ev.get("home_team"),
                    "away_team": ev.get("away_team"),
                    "book": bm.get("key"),
                    "line": float(line),
                    "over_price": over_price,
                    "under_price": under_price,
                    "last_update": mkt.get("last_update") or bm.get("last_update"),
                }
                key = (row["event_id"], row["book"])
                prev = by_key.get(key)
                if prev is None or (row["last_update"] or "") >= (prev["last_update"] or ""):
                    by_key[key] = row
    return list(by_key.values())


def normalize_first_half(
    events: List[Dict[str, Any]], books: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """One row per (event, book) for the first-half totals_h1 market."""
    return _rows_for_market(events, "totals_h1", books)


def normalize_full_game(
    events: List[Dict[str, Any]], books: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """One row per (event, book) for the full-game `totals` market. Same shape as
    sources.draftkings.normalize_full_game (spread is None — the totals market
    carries no spread), so scripts/poll_full_game.py consumes either source."""
    rows = _rows_for_market(events, "totals", books)
    for r in rows:
        r["spread"] = None
    return rows
