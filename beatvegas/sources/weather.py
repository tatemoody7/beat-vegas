"""Weather by venue lat/long + date via Open-Meteo (free, no key).

Past dates use the archive API; near-future dates use the forecast API. Returns
the conditions nearest kickoff hour. Dome handling lives in the enrich script.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Optional

import requests

_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
_FORECAST = "https://api.open-meteo.com/v1/forecast"
_HOURLY = "temperature_2m,wind_speed_10m,precipitation"


def _today() -> _date:
    return datetime.utcnow().date()


def fetch_weather(lat: float, lon: float, date_str: str, hour: int = 19,
                  timeout: int = 30) -> Optional[dict]:
    """Return {temperature_f, wind_mph, precipitation} near `hour` local, or None.

    Uses the archive API for past dates and the forecast API within its ~16-day
    horizon; returns None for far-future dates (no data yet)."""
    if lat is None or lon is None:
        return None
    try:
        d = datetime.fromisoformat(date_str).date()
    except ValueError:
        return None
    today = _today()
    url = _ARCHIVE if d < today else _FORECAST
    if (d - today).days > 16:
        return None                              # beyond forecast horizon
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": date_str, "end_date": date_str,
        "hourly": _HOURLY, "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph", "precipitation_unit": "inch",
        "timezone": "auto",
    }
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        h = r.json().get("hourly", {})
    except (requests.RequestException, ValueError):
        return None
    temps = h.get("temperature_2m") or []
    winds = h.get("wind_speed_10m") or []
    precs = h.get("precipitation") or []
    if not temps:
        return None
    i = min(max(hour, 0), len(temps) - 1)
    return {
        "temperature_f": temps[i],
        "wind_mph": winds[i] if i < len(winds) else None,
        "precipitation": precs[i] if i < len(precs) else None,
    }


def fetch_weather_series(lat: float, lon: float, start_date: str, end_date: str,
                         timeout: int = 60) -> dict:
    """One ranged archive call → {'YYYY-MM-DDTHH': {temp,wind,precip}} (local).

    Used by the historical backfill to fetch a venue's whole span in one request,
    then slice each game's kickoff hour locally. Returns {} on failure."""
    if lat is None or lon is None:
        return {}
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start_date, "end_date": end_date,
        "hourly": _HOURLY, "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph", "precipitation_unit": "inch", "timezone": "auto",
    }
    try:
        r = requests.get(_ARCHIVE, params=params, timeout=timeout)
        r.raise_for_status()
        h = r.json().get("hourly", {})
    except (requests.RequestException, ValueError):
        return {}
    times = h.get("time") or []
    temps = h.get("temperature_2m") or []
    winds = h.get("wind_speed_10m") or []
    precs = h.get("precipitation") or []
    out = {}
    for i, t in enumerate(times):
        out[t[:13]] = {                      # key 'YYYY-MM-DDTHH'
            "temperature_f": temps[i] if i < len(temps) else None,
            "wind_mph": winds[i] if i < len(winds) else None,
            "precipitation": precs[i] if i < len(precs) else None,
        }
    return out
