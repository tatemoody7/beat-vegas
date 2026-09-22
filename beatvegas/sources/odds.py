"""The Odds API v4 client for college-football totals (totals_h1 + full-game).

Paid tier = 100K credits/month (2026-09; free tier was 500). A per-event call is
billed (markets x regions), but `bookmakers=` (up to 10 keys) counts as ONE region
and takes priority over `regions` — so the 1H sweep names its ten books and pays
1 credit per event instead of 2 on us,us2 (verified live 2026-09-09). We surface
the credit headers on every call. The normalizers turn the nested
events->bookmakers->markets->outcomes JSON into flat snapshot rows.

The bulk full-game pull asks for BOTH featured markets, `totals,spreads`, so each
(event, book) row carries that book's home-relative spread next to its total
(`spread` is None only when the book posted no spreads market). Featured markets
cost (markets x regions) credits per call, so the whole slate is 4-6 credits.

Every HTTP status error and transport error is re-raised with the `apiKey=`
query value redacted (`redact_key`) so a 401/429 traceback, or a connection
failure/timeout raised by `requests.get` itself, never echoes the key into
CI logs.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..config import load_config, odds_api_key
from ..hardrock import normalize_book

# The Odds API bills every group of 10 named bookmakers as one region, so a
# per-event call naming <= 10 books costs the same as a single-region call.
# Naming an 11th quietly doubles it (see OddsAPIClient.__init__).
MAX_BOOKMAKERS_ONE_REGION = 10

# Retries, mirroring sources/cfbd.py. The FREE data source retried and the PAID
# one did not, so a single transient 429/5xx mid-sweep failed the whole card
# build. Only transport errors, 429 and 5xx are retried: a 404 is meaningful
# here (event_first_half_totals returns {} for an unpriced event) and any other
# 4xx is a bad key or bad params that a retry cannot fix. The Odds API does not
# bill 429s or 5xx, so a retry does not re-spend a credit.
_RETRY_EXC = (requests.Timeout, requests.ConnectionError)
_BACKOFF_SECONDS = (2, 4)  # between attempts 1->2 and 2->3
DEFAULT_MAX_RETRIES = 3


@dataclass
class Credits:
    remaining: Optional[int]
    used: Optional[int]
    last_cost: Optional[int]


_API_KEY_RE = re.compile(r"(apiKey=)[^&\s'\"]+")


def redact_key(text: str) -> str:
    """Mask the `apiKey=` query value anywhere in `text` (URLs in error
    messages, printed request lines). Idempotent."""
    return _API_KEY_RE.sub(r"\1***", text)


def _raise_for_status(resp: requests.Response) -> None:
    """`resp.raise_for_status()` whose HTTPError message has the key redacted:
    requests puts the full request URL (apiKey included) in the message, and
    that string ends up in GitHub Actions logs on a 401/429."""
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise requests.HTTPError(redact_key(str(e)), response=resp, request=resp.request) from None


class OddsAPIClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        cfg = load_config().get("odds_api", {}) or {}
        self.api_key = api_key or odds_api_key()
        self.base_url = (cfg.get("base_url") or "https://api.the-odds-api.com/v4").rstrip("/")
        self.sport = cfg.get("sport", "americanfootball_ncaaf")
        self.regions = cfg.get("regions", "us")
        self.markets = cfg.get("markets", "totals_h1")
        self.odds_format = cfg.get("odds_format", "american")
        self.bookmakers = list(cfg.get("bookmakers_1h") or [])
        self.timeout = timeout
        self.max_retries = max(1, int(max_retries))
        self.last_credits: Optional[Credits] = None

    def _scope_params(self) -> Dict[str, Any]:
        """The ONE billing dimension for a per-event call.

        `bookmakers` (<= 10 keys) is billed as a single region and takes
        priority over `regions` in the API, so we send exactly one of the two,
        never both: sending both still works today but hides a future billing
        change behind the API's precedence rule. An empty list falls back to
        region pricing, which is what `poll_lines.py --regions` forces for the
        A/B probe."""
        if self.bookmakers:
            return {"bookmakers": ",".join(self.bookmakers)}
        return {"regions": self.regions}

    # `bookmakers` is a guarded PROPERTY, not a plain attribute. The check used
    # to live in __init__ only, so `client.bookmakers = [...]` after
    # construction — which is exactly what poll_lines.py --bookmakers does —
    # walked straight past it and would have silently doubled the cost of every
    # per-event call for the whole run. Validating on assignment closes every
    # path at once, including __init__, which now assigns through this setter.
    @property
    def bookmakers(self) -> List[str]:
        return self._bookmakers

    @bookmakers.setter
    def bookmakers(self, keys) -> None:
        keys = list(keys or [])
        if len(keys) > MAX_BOOKMAKERS_ONE_REGION:
            # Not a warning: an 11th key silently DOUBLES every per-event call
            # for the rest of the season, and nothing in the output would say so.
            raise ValueError(
                f"{len(keys)} bookmaker keys given; the Odds API bills one region "
                f"per {MAX_BOOKMAKERS_ONE_REGION} books, so an extra key doubles "
                "the cost of every per-event 1H call"
            )
        self._bookmakers = keys

    def _get(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """`requests.get` with retries, and with the key redacted no matter how
        it fails.

        Retries: up to `max_retries` attempts on a timeout / connection error /
        429 / 5xx, sleeping 2s then 4s between them. A 4xx that is not 429 is
        returned to the caller untouched — `event_first_half_totals` reads a 404
        as "this event has no first-half market", and a 401 is a bad key that no
        retry fixes.

        Redaction: a transport error raised by `get` itself never reaches
        `_raise_for_status` (there is no Response yet), but requests still
        stuffs the full request URL — apiKey included — into the exception
        message. Re-raise the same exception type with that message redacted.
        """
        last_exc: Optional[BaseException] = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, params=params, timeout=self.timeout)
            except _RETRY_EXC as e:
                last_exc = type(e)(redact_key(str(e)))
            except requests.RequestException as e:
                # Not retryable (a malformed URL, too many redirects, ...).
                raise type(e)(redact_key(str(e))) from None
            else:
                # Read the credit headers from every response we get back, so a
                # retried call still reports the API's latest counters.
                self._credits(resp)
                if resp.status_code != 429 and resp.status_code < 500:
                    return resp
                last_exc = requests.HTTPError(
                    redact_key(f"Odds API {resp.status_code} for {url}"), response=resp
                )
            if attempt < self.max_retries - 1:
                nap = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                print(
                    f"[odds] attempt {attempt + 1}/{self.max_retries} failed "
                    f"({last_exc}); retrying in {nap}s"
                )
                time.sleep(nap)
        assert last_exc is not None
        raise last_exc

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
        # The board's gauge (beatvegas/ops.py), recorded on the first priced
        # response of a run: the month's balance, where a reader will see it.
        if c.remaining is not None and not getattr(self, "_gauge_recorded", False):
            self._gauge_recorded = True
            from ..ops import ODDS_CREDITS_REMAINING, record_gauge

            record_gauge(ODDS_CREDITS_REMAINING, c.remaining)
        return c

    def credits_low(self, floor: int) -> bool:
        """True once the month's remaining credits (from the LAST response's
        x-requests-remaining header) are at or below `floor`. Unknown (no call
        yet / header missing) is NOT low; floor <= 0 disables the guard. Call a
        free endpoint (list_events) first to learn the balance."""
        c = self.last_credits
        return floor > 0 and c is not None and c.remaining is not None and c.remaining <= floor

    def list_full_game_odds(
        self, regions: Optional[str] = None, markets: str = "totals,spreads"
    ) -> List[Dict[str, Any]]:
        """Full-game featured markets for every book in `regions`, from the BULK
        /odds endpoint. Featured markets cost (n_markets x n_regions) credits
        TOTAL for the whole slate: the Sunday opener (`us,us2,us_ex`, two
        markets) is 6 credits, a card-day refresh (`us,us2`) is 4 — cheap vs
        the per-event 1H calls. Default `totals,spreads` gives each book's
        total AND its home-relative spread in one call.

        REGIONS, NOT BOOKMAKERS: this is the bulk endpoint, billed
        (markets x regions) for the WHOLE slate, and it needs `us_ex` for the
        exchange fair price on Sundays. Naming books here would cap the slate
        at those ten and buy nothing — tests/test_odds_bookmakers.py pins it.

        Hard Rock's LIVE book key is `hardrockbet` (the docs' FL-specific
        `hardrockbet_fl` has not appeared in responses; hardrock.py accepts
        both). It lives in the `us2` region only — verified empirically — so
        pass regions='us,us2' to capture it alongside the rest of the market."""
        url = f"{self.base_url}/sports/{self.sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions or self.regions,
            "markets": markets,
            "oddsFormat": self.odds_format,
            "dateFormat": "iso",
        }
        resp = self._get(url, params)
        _raise_for_status(resp)
        return resp.json()

    def list_full_game_totals(self, regions: Optional[str] = None) -> List[Dict[str, Any]]:
        """Full-game `totals` only (1 x n_regions credits). Thin alias kept for
        callers that never need the spread; see list_full_game_odds."""
        return self.list_full_game_odds(regions=regions, markets="totals")

    def list_events(self) -> List[Dict[str, Any]]:
        """Upcoming events for the sport. FREE (0 credits). Each has id,
        commence_time, home_team, away_team — but no odds."""
        url = f"{self.base_url}/sports/{self.sport}/events"
        resp = self._get(url, {"apiKey": self.api_key, "dateFormat": "iso"})
        _raise_for_status(resp)
        return resp.json()

    def event_first_half_totals(self, event_id: str) -> Dict[str, Any]:
        """totals_h1 odds for one event. Costs (markets x regions) credits —
        1 when odds_api.bookmakers_1h is set (<= 10 books bill as one region),
        2 on us,us2 when it is empty.

        Additional markets like totals_h1 are ONLY served on this per-event
        endpoint, not the bulk /odds endpoint."""
        url = f"{self.base_url}/sports/{self.sport}/events/{event_id}/odds"
        params = {
            "apiKey": self.api_key,
            "markets": self.markets,
            "oddsFormat": self.odds_format,
            "dateFormat": "iso",
            **self._scope_params(),
        }
        resp = self._get(url, params)
        if resp.status_code == 404:
            return {}  # event has no odds posted yet
        _raise_for_status(resp)
        return resp.json()

    # --- historical (paid backfill / coverage gate, plan Phase 0) -------------
    def list_historical_events(self, date_iso: str) -> List[Dict[str, Any]]:
        """Events as of a past timestamp. The historical envelope wraps the list
        in `data`. Cheap (no odds)."""
        url = f"{self.base_url}/historical/sports/{self.sport}/events"
        resp = self._get(url, {"apiKey": self.api_key, "date": date_iso, "dateFormat": "iso"})
        _raise_for_status(resp)
        return _unwrap_historical(resp.json()) or []

    def historical_bulk_totals(
        self, date_iso: str, regions: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Full-game `totals` for EVERY upcoming event as of a past timestamp, from
        the historical BULK /odds endpoint (one call covers the whole slate that
        commences after `date_iso`). Costs 10 credits x regions x markets — so
        10 with `us` — regardless of how many events come back. Used by
        scripts/backfill_fg_history.py to grade the same picks on the full game."""
        url = f"{self.base_url}/historical/sports/{self.sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions or self.regions,
            "markets": "totals",
            "oddsFormat": self.odds_format,
            "dateFormat": "iso",
            "date": date_iso,
        }
        resp = self._get(url, params)
        _raise_for_status(resp)
        return _unwrap_historical(resp.json()) or []

    def historical_event_first_half_totals(self, event_id: str, date_iso: str) -> Dict[str, Any]:
        """totals_h1 odds for one event as of a past timestamp. Historical
        snapshots cost more per market than live calls — probe sparingly."""
        url = f"{self.base_url}/historical/sports/{self.sport}/events/{event_id}/odds"
        params = {
            "apiKey": self.api_key,
            "markets": self.markets,
            "oddsFormat": self.odds_format,
            "dateFormat": "iso",
            "date": date_iso,
            **self._scope_params(),
        }
        resp = self._get(url, params)
        if resp.status_code == 404:
            return {}
        _raise_for_status(resp)
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
    # Keep the freshest quote (latest last_update). `book` is the canonical
    # key (hardrock.normalize_book), so hardrockbet_fl folds into hardrockbet.
    by_key: Dict[tuple, Dict[str, Any]] = {}
    for ev in events:
        for bm in ev.get("bookmakers", []):
            if book_filter and bm.get("key") not in book_filter:
                continue
            for mkt in bm.get("markets", []):
                if mkt.get("key") != market_key:
                    continue
                over_price = under_price = None
                over_pt = under_pt = None
                for oc in mkt.get("outcomes", []):
                    name = (oc.get("name") or "").lower()
                    if name == "over":
                        over_price, over_pt = oc.get("price"), oc.get("point")
                    elif name == "under":
                        under_price, under_pt = oc.get("price"), oc.get("point")
                # One line per book, over-first (the same tie-break as
                # sources/draftkings.py). A market whose two outcomes sit at
                # DIFFERENT points is alternate rungs, not a centred line, and
                # pairing an over price from one rung with an under price from
                # another would make a number up — skip it rather than guess.
                if (
                    over_pt is not None
                    and under_pt is not None
                    and float(over_pt) != float(under_pt)
                ):
                    continue
                line = over_pt if over_pt is not None else under_pt
                if line is None:
                    continue
                row = {
                    "event_id": ev.get("id"),
                    "commence_time": ev.get("commence_time"),
                    "home_team": ev.get("home_team"),
                    "away_team": ev.get("away_team"),
                    "book": normalize_book(bm.get("key")),
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


def _home_spreads(
    events: List[Dict[str, Any]], books: Optional[List[str]] = None
) -> Dict[Tuple[str, str], float]:
    """(event_id, book) -> home-relative spread (negative = home favored) from
    each book's `spreads` market. The outcome named after `home_team` carries
    the home point; when only the away outcome is present its point is negated.
    Same freshest-`last_update`-wins rule and canonical book key as
    _rows_for_market, so the two dicts line up key for key."""
    book_filter = set(books) if books else None
    by_key: Dict[Tuple[str, str], Tuple[str, float]] = {}
    for ev in events:
        home = ev.get("home_team")
        away = ev.get("away_team")
        for bm in ev.get("bookmakers", []):
            if book_filter and bm.get("key") not in book_filter:
                continue
            for mkt in bm.get("markets", []):
                if mkt.get("key") != "spreads":
                    continue
                home_pt = away_pt = None
                for oc in mkt.get("outcomes", []):
                    try:
                        point = float(oc.get("point"))
                    except (TypeError, ValueError):
                        # One book's malformed outcome (bad/missing point)
                        # shouldn't abort the whole Sunday capture.
                        continue
                    if oc.get("name") == home:
                        home_pt = point
                    elif oc.get("name") == away:
                        away_pt = point
                if home_pt is not None:
                    spread = home_pt
                elif away_pt is not None:
                    spread = -away_pt
                else:
                    continue
                key = (ev.get("id"), normalize_book(bm.get("key")))
                stamp = mkt.get("last_update") or bm.get("last_update") or ""
                prev = by_key.get(key)
                if prev is None or stamp >= prev[0]:
                    by_key[key] = (stamp, spread)
    return {k: v[1] for k, v in by_key.items()}


def normalize_full_game(
    events: List[Dict[str, Any]], books: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """One row per (event, book) for the full-game `totals` market, with that
    book's home-relative `spread` from its `spreads` market (None when the book
    posted no spread — poll_full_game._changed treats None as "unknown", not
    "moved"). Same shape as sources.draftkings.normalize_full_game, so
    scripts/poll_full_game.py consumes either source."""
    rows = _rows_for_market(events, "totals", books)
    spreads = _home_spreads(events, books)
    for r in rows:
        r["spread"] = spreads.get((r["event_id"], r["book"]))
    return rows
