"""Thin, robust client for the CollegeFootballData REST API.

We wrap the raw REST endpoints with `requests` rather than the official `cfbd`
PyPI package: the official client's models churn between versions, while the
HTTP surface is stable and transparent. Free key: https://collegefootballdata.com/key
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from ..config import cfbd_api_key, load_config

# Transient failures worth a second look. requests.Timeout covers both
# ConnectTimeout and ReadTimeout (the Aug 30 2026 Sunday run died on ONE
# ReadTimeout); ConnectionError covers resets and DNS blips.
_RETRY_EXC = (requests.Timeout, requests.ConnectionError)
# Between attempts 1->2, 2->3, 3->4. The old (2, 4) ladder gave a rate limit six
# seconds to clear, which it never does: CFBD 429'd every grading run on
# 2026-09-12/13 across four attempts spread over two days. A 429 is a quota
# window, not a blip, so wait in minutes-adjacent steps. Timeouts and connection
# errors ride the same ladder -- they are rare enough that the extra wait costs
# nothing, and the job has no deadline.
_BACKOFF_SECONDS = (5, 20, 60)
_MAX_RETRY_AFTER = 120  # honour the server's Retry-After, but never stall a job on it


def _retry_after(resp: requests.Response) -> Optional[float]:
    """Seconds the server asked us to wait, or None if it did not say.

    Only the delta-seconds form is honoured; the HTTP-date form is rare here and
    a bad parse should fall back to our own ladder rather than raise.
    """
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        secs = float(raw.strip())
    except ValueError:
        return None
    if secs <= 0:
        return None
    return min(secs, _MAX_RETRY_AFTER)


class CFBDClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 4,
    ):
        cfg = load_config().get("cfbd", {}) or {}
        self.api_key = api_key or cfbd_api_key()
        self.base_url = (
            base_url or cfg.get("base_url") or "https://api.collegefootballdata.com"
        ).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }
        )

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        """GET with retries: up to `max_retries` attempts (default 4) on a
        timeout / connection error / 429 / 5xx, sleeping 5s, 20s then 60s
        between them. A 429 carrying `Retry-After` waits that long instead,
        capped at `_MAX_RETRY_AFTER`. Other 4xx (bad key, bad params) raise
        immediately. The final failure is re-raised as-is so the caller sees
        the real cause."""
        params = {k: v for k, v in params.items() if v is not None}
        url = f"{self.base_url}{path}"
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            wait: Optional[float] = None
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
            except _RETRY_EXC as e:
                last_exc = e
            else:
                if resp.status_code != 429 and resp.status_code < 500:
                    resp.raise_for_status()
                    return resp.json()
                last_exc = requests.HTTPError(f"CFBD {resp.status_code} for {path}", response=resp)
                wait = _retry_after(resp)
            if attempt < self.max_retries - 1:
                if wait is None:
                    wait = _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]
                time.sleep(wait)
        assert last_exc is not None
        raise last_exc

    # --- endpoints -------------------------------------------------------
    def games(
        self,
        year: int,
        week: Optional[int] = None,
        season_type: str = "regular",
        division: str = "fbs",
    ) -> List[Dict]:
        """Games incl. final scores and (when present) per-quarter line scores."""
        return self._get(
            "/games",
            {
                "year": year,
                "week": week,
                "seasonType": season_type,
                "division": division,
            },
        )

    def fbs_teams(self, year: int) -> List[Dict]:
        """Teams classified FBS for `year` (each row has `school`, `conference`)."""
        return self._get("/teams/fbs", {"year": year})

    def teams(self, year: int) -> List[Dict]:
        """Every team CFBD knows for `year`, all divisions.

        Wider than `/teams/fbs`: rows carry `id`, `classification` (fbs/fcs/ii/iii)
        and `logos` (CDN URLs). Used by scripts/fetch_team_logos.py.
        """
        return self._get("/teams", {"year": year})

    def plays(self, year: int, week: int, season_type: str = "regular") -> List[Dict]:
        """Play-by-play (fallback path for 1H points; has `period` + scoring)."""
        return self._get(
            "/plays",
            {
                "year": year,
                "week": week,
                "seasonType": season_type,
            },
        )

    def lines(
        self, year: int, week: Optional[int] = None, season_type: str = "regular"
    ) -> List[Dict]:
        """Full-game betting lines (each game has a `lines` list per provider)."""
        return self._get(
            "/lines",
            {
                "year": year,
                "week": week,
                "seasonType": season_type,
            },
        )

    def sp_ratings(self, year: int, team: Optional[str] = None) -> List[Dict]:
        return self._get("/ratings/sp", {"year": year, "team": team})

    def advanced_season_stats(
        self, year: int, team: Optional[str] = None, exclude_garbage_time: bool = True
    ) -> List[Dict]:
        return self._get(
            "/stats/season/advanced",
            {
                "year": year,
                "team": team,
                "excludeGarbageTime": str(exclude_garbage_time).lower(),
            },
        )

    def venues(self) -> List[Dict]:
        return self._get("/venues", {})

    def talent(self, year: int) -> List[Dict]:
        """Recruiting-based team talent composite (preseason-known)."""
        return self._get("/talent", {"year": year})

    def roster(self, year: int, team: Optional[str] = None) -> List[Dict]:
        """Team roster with class `year` (1-4) per player (preseason-known)."""
        return self._get("/roster", {"year": year, "team": team})
