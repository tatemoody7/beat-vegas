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
_BACKOFF_SECONDS = (2, 4)  # between attempts 1->2 and 2->3


class CFBDClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
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
        """GET with retries: up to `max_retries` attempts (default 3) on a
        timeout / connection error / 429 / 5xx, sleeping 2s then 4s between
        them. Other 4xx (bad key, bad params) raise immediately. The final
        failure is re-raised as-is so the caller sees the real cause."""
        params = {k: v for k, v in params.items() if v is not None}
        url = f"{self.base_url}{path}"
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
            except _RETRY_EXC as e:
                last_exc = e
            else:
                if resp.status_code != 429 and resp.status_code < 500:
                    resp.raise_for_status()
                    return resp.json()
                last_exc = requests.HTTPError(f"CFBD {resp.status_code} for {path}", response=resp)
            if attempt < self.max_retries - 1:
                time.sleep(_BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)])
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
