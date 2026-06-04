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


def normalize_first_half(
    events: List[Dict[str, Any]], books: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Flatten events into one row per (event, book) for the totals_h1 market.

    Each row: event_id, commence_time, home_team, away_team, book, line,
    over_price, under_price, last_update."""
    book_filter = set(books) if books else None
    rows: List[Dict[str, Any]] = []
    for ev in events:
        for bm in ev.get("bookmakers", []):
            if book_filter and bm.get("key") not in book_filter:
                continue
            for mkt in bm.get("markets", []):
                if mkt.get("key") != "totals_h1":
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
                rows.append(
                    {
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
                )
    return rows
