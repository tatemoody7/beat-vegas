"""Weather by venue lat/long + kickoff via Open-Meteo (free, no key).

EVERY request asks for `timezone=UTC` and every series is keyed by the UTC hour,
because `Game.start_date` is naive UTC (`scripts/backfill.py::_parse_dt` parses the
offset, then strips tzinfo). Until 2026-09-13 both callers asked for
`timezone=auto` and then indexed the LOCAL hourly array at the UTC position, so
every stored reading was displaced by the venue's UTC offset -- 4 to 10 hours for
US venues, and onto the wrong calendar day for a late kickoff. Measured: LA
Coliseum 2023-08-27T00:00Z stored 63.2F (local midnight) against 78.1F at the
real 5pm PDT kickoff. Do not reintroduce `timezone=auto`; a local-time series
cannot be keyed by a UTC timestamp.

FOUR SOURCES, AND THEY ARE NOT INTERCHANGEABLE:

  NEAR_KICKOFF  the Historical Forecast API, which stitches the first hours of
                successive model runs into a continuous series. It therefore
                tracks what ACTUALLY happened -- measured against the ERA5
                actual on 12 real kickoffs it sits closer (1.82F / 1.55mph mean
                absolute difference) than even a 1-day-lead forecast (2.30F /
                1.67mph). It is NOT "the forecast we would have had", and using
                it for market-edge research is look-ahead bias.

  DECISION      the Previous Runs API, which serves the forecast issued a FIXED
                number of days before the valid time. This is the only source a
                betting-edge study may use. Wind, gusts and precipitation only
                carry data from the 2024 season on (probed null at 2023-11-01
                and 2024-01-15, populated from 2024-03-01); 2023 is temperature
                only. Max lead is 7 days -- `previous_day8` comes back empty.

  FORECAST      the ordinary forecast API, for games that have not kicked off.

  ACTUAL        the ERA5 archive. Kept for validation comparisons only; nothing
                stores it today.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Optional, Sequence

import requests

from ._http import RETRY_EXC, backoff_seconds, retry_after

_NEAR_KICKOFF_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
_DECISION_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_ACTUAL_URL = "https://archive-api.open-meteo.com/v1/archive"

# Stored on every row as provenance, so a value can never be mistaken for one
# from a different source six months later.
SOURCE_NEAR_KICKOFF = "open_meteo_historical_forecast"
SOURCE_DECISION = "open_meteo_previous_runs"
SOURCE_FORECAST = "open_meteo_forecast"
SOURCE_ACTUAL = "open_meteo_era5_archive"

_URLS = {
    SOURCE_NEAR_KICKOFF: _NEAR_KICKOFF_URL,
    SOURCE_DECISION: _DECISION_URL,
    SOURCE_FORECAST: _FORECAST_URL,
    SOURCE_ACTUAL: _ACTUAL_URL,
}

# Open-Meteo's names -> ours. Gusts matter more than mean wind for a passing
# offence, and were never captured before.
_VARS = {
    "temperature_2m": "temperature_f",
    "wind_speed_10m": "wind_mph",
    "wind_gusts_10m": "wind_gust_mph",
    "precipitation": "precipitation",
}

FORECAST_HORIZON_DAYS = 16  # past this the forecast API has nothing
MAX_LEAD_HOURS = 168  # previous_day7; day8 returns empty
_ATTEMPTS = 4


class WeatherUnavailable(RuntimeError):
    """The request could not be completed -- rate limited, or down.

    Deliberately distinct from "this venue has no data": the old module returned
    an empty dict for both, which is exactly how 647 venues were silently lost.
    """


def _today() -> datetime:
    return datetime.utcnow()


def decision_safe(source: str, lead_hours: int) -> bool:
    """True only for a forecast that genuinely existed before the decision time.

    NEAR_KICKOFF is never decision-safe however small its notional lead.
    """
    return source == SOURCE_DECISION and lead_hours >= 24


def _hourly_names(source: str, lead_hours: int) -> Dict[str, str]:
    """Open-Meteo variable name -> our column, for this source."""
    if source != SOURCE_DECISION:
        return dict(_VARS)
    day = lead_hours // 24
    return {f"{k}_previous_day{day}": v for k, v in _VARS.items()}


def _get(url: str, params: dict, timeout: int) -> dict:
    """One Open-Meteo call, with the shared retry ladder.

    A 429 or 5xx is retried (honouring `Retry-After`); any other 4xx is a bad
    request and raises straight away. Exhausting the ladder raises
    `WeatherUnavailable` rather than returning empty, so a caller can tell a rate
    limit from a venue with no data.
    """
    last: Optional[str] = None
    for attempt in range(_ATTEMPTS):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except RETRY_EXC as e:  # noqa: PERF203
            last = f"{type(e).__name__}: {e}"
        else:
            if resp.status_code < 400:
                try:
                    return resp.json().get("hourly", {}) or {}
                except ValueError as e:
                    last = f"bad json: {e}"
            elif resp.status_code == 429 or resp.status_code >= 500:
                last = f"HTTP {resp.status_code}"
                wait = retry_after(resp)
                if wait is None:
                    wait = backoff_seconds(attempt)
                if attempt < _ATTEMPTS - 1:
                    time.sleep(wait)
                continue
            else:
                resp.raise_for_status()
        if attempt < _ATTEMPTS - 1:
            time.sleep(backoff_seconds(attempt))
    raise WeatherUnavailable(f"{url}: {last} after {_ATTEMPTS} attempts")


def fetch_hourly_series(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    *,
    source: str = SOURCE_NEAR_KICKOFF,
    lead_hours: int = 0,
    models: Optional[str] = None,
    timeout: int = 60,
) -> Dict[str, dict]:
    """One ranged call -> {'YYYY-MM-DDTHH' (UTC): {temp, wind, gust, precip}}.

    The backfill fetches a venue's whole season in one request and then slices
    each kickoff hour locally -- hundreds of calls instead of thousands. Hours
    with no data for a variable carry None rather than being dropped, so a caller
    can tell "no gust reading" from "no such hour".
    """
    if lat is None or lon is None:
        return {}
    if source not in _URLS:
        raise ValueError(f"unknown weather source: {source!r}")
    if source == SOURCE_DECISION and not (
        24 <= lead_hours <= MAX_LEAD_HOURS and lead_hours % 24 == 0
    ):
        raise ValueError(f"lead_hours must be a whole number of days in 24..{MAX_LEAD_HOURS}")
    names = _hourly_names(source, lead_hours)
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(names),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC",  # load-bearing -- see the module docstring
    }
    if models:
        params["models"] = models
    h = _get(_URLS[source], params, timeout)
    times: Sequence[str] = h.get("time") or []
    out: Dict[str, dict] = {}
    for i, t in enumerate(times):
        row = {}
        for api_name, col in names.items():
            vals = h.get(api_name) or []
            row[col] = vals[i] if i < len(vals) else None
        out[t[:13]] = row  # key 'YYYY-MM-DDTHH', UTC
    return out


def fetch_weather(
    lat: float,
    lon: float,
    kickoff_utc: datetime,
    *,
    source: Optional[str] = None,
    lead_hours: int = 0,
    timeout: int = 30,
) -> Optional[dict]:
    """Conditions at `kickoff_utc` (naive UTC), or None when there is no data.

    Takes a datetime rather than a date plus an hour on purpose: the old
    signature let a caller pass a UTC date with a local hour, which is precisely
    the bug this module exists to prevent.
    """
    if lat is None or lon is None or kickoff_utc is None:
        return None
    if source is None:
        source = SOURCE_FORECAST if kickoff_utc.date() >= _today().date() else SOURCE_NEAR_KICKOFF
    if source == SOURCE_FORECAST and (kickoff_utc - _today()).days > FORECAST_HORIZON_DAYS:
        return None  # beyond the forecast horizon
    day = kickoff_utc.strftime("%Y-%m-%d")
    series = fetch_hourly_series(
        lat, lon, day, day, source=source, lead_hours=lead_hours, timeout=timeout
    )
    return series.get(kickoff_utc.strftime("%Y-%m-%dT%H"))
