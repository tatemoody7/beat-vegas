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
        params = {k: v for k, v in params.items() if v is not None}
        url = f"{self.base_url}{path}"
        for attempt in range(self.max_retries):
            resp = self._session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2**attempt)  # backoff on rate-limit/server error
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return resp.json()

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
