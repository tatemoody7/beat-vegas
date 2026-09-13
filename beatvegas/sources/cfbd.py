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

# CFBD reports the calls left in the MONTHLY budget on every response, including
# the 429 that says the budget is gone. Nothing read it until 2026-09-13, which
# is why the quota ran out mid-season with no warning and grading was dead for
# two days before anyone noticed. `CFBDClient.calls_remaining` now carries the
# last value seen, every run prints it once, and dropping under the threshold
# raises a GitHub annotation while there is still time to act.
_CALLS_REMAINING_HEADER = "x-calllimit-remaining"
_LOW_CALLS_WARN = 200  # on any tier this is days, not weeks, of headroom


class CFBDQuotaExceeded(requests.HTTPError):
    """The MONTHLY call budget is spent — not a rate limit, and not transient.

    An HTTPError subclass so every existing `except requests.HTTPError` /
    `except Exception` path keeps working; the distinct type is there so a
    caller that wants to degrade (rather than fail) can tell "we are out of
    budget until the month rolls over" from "CFBD hiccuped"."""


def _calls_remaining(resp: requests.Response) -> Optional[int]:
    """Calls left in the monthly budget per CFBD's own header, or None."""
    raw = resp.headers.get(_CALLS_REMAINING_HEADER)
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def _is_quota_exhausted(resp: requests.Response) -> bool:
    """True when a 429 means the MONTHLY budget is gone rather than "slow down".

    Two independent tells, either of which is enough. CFBD sends
    `x-calllimit-remaining: 0` on the refusal itself, and the body reads
    "Monthly call quota exceeded." — verified live against an exhausted key on
    2026-09-13, which also sent NO Retry-After, so the caller would otherwise
    spend the whole 5/20/60s ladder and three more calls waiting for a month to
    end."""
    if resp.status_code != 429:
        return False
    if _calls_remaining(resp) == 0:
        return True
    try:
        body = resp.text[:200].lower()
    except Exception:  # noqa: BLE001 - a body we cannot read is not proof of anything
        return False
    return "quota" in body


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
        # Calls left in CFBD's monthly budget as of the last response (None
        # until the first one). Read it after a run to see the tank draining.
        self.calls_remaining: Optional[int] = None
        self._reported_calls = False  # print the budget once per client, not per call
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            }
        )

    def _note_budget(self, resp: requests.Response) -> None:
        """Record CFBD's monthly-budget header, print it once, and annotate the
        run when it gets low. This is the only warning the system gets before
        every endpoint starts refusing."""
        remaining = _calls_remaining(resp)
        if remaining is None:
            return
        self.calls_remaining = remaining
        if self._reported_calls:
            return
        self._reported_calls = True
        print(f"[cfbd] {remaining} calls left in this month's budget")
        if remaining <= _LOW_CALLS_WARN:
            from ..ci import warn

            warn(
                f"CFBD monthly budget down to {remaining} calls. When it reaches zero every "
                "endpoint 429s until the month rolls over — scores fall back to ESPN "
                "(sources/espn_scores.py) but talent, SP+ and returning production do not. "
                "Raise the tier at https://collegefootballdata.com/api-tiers"
            )

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        """GET with retries: up to `max_retries` attempts (default 4) on a
        timeout / connection error / 429 / 5xx, sleeping 5s, 20s then 60s
        between them. A 429 carrying `Retry-After` waits that long instead,
        capped at `_MAX_RETRY_AFTER`. Other 4xx (bad key, bad params) raise
        immediately. The final failure is re-raised as-is so the caller sees
        the real cause.

        An EXHAUSTED MONTHLY BUDGET is the exception: it raises
        `CFBDQuotaExceeded` on the spot. Retrying it cannot succeed — the wait
        is the rest of the calendar month — and CFBD sends no Retry-After with
        it, so the old path spent the full 85-second ladder and three more
        calls against a budget that was already gone, on every single call of
        every job."""
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
                self._note_budget(resp)
                if _is_quota_exhausted(resp):
                    raise CFBDQuotaExceeded(
                        f"CFBD monthly call quota exhausted (429 for {path}); it resets at the "
                        "start of next month. Raise the tier at "
                        "https://collegefootballdata.com/api-tiers",
                        response=resp,
                    )
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
