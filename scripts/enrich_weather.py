#!/usr/bin/env python
"""Populate the weather table for a week's games via Open-Meteo + venue coords.

Dome venues are recorded as dome (no wind/precip effect). Outdoor venues get
temp/wind/precip near kickoff.

    python scripts/enrich_weather.py --season 2025 --week 8
"""

from __future__ import annotations

import argparse
import sys
import time

from beatvegas import ci
from beatvegas.db.models import Game, Venue, Weather
from beatvegas.db.store import session_scope, try_init_db, upsert
from beatvegas.sources.weather import fetch_weather

PER_CALL_TIMEOUT_S = 8
MAX_CONSECUTIVE_FAILURES = 15


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()
    if not try_init_db():
        return

    # Read, then fetch OUTSIDE any session: hundreds of Open-Meteo calls inside
    # one transaction trip Neon's idle-in-transaction timeout and lose the batch.
    with session_scope() as s:
        games = [
            (g.id, g.venue_id, g.start_date)
            for g in s.query(Game).filter(Game.season == args.season, Game.week == args.week)
        ]
        venues = {v.id: (v.dome, v.latitude, v.longitude) for v in s.query(Venue).all()}
    rows, fetched, domes, skipped = [], 0, 0, 0
    # Open-Meteo rate-limits shared runners (GHA): a blocked call would otherwise
    # sit out the full timeout, ~450 times. Short per-call timeout, and bail out
    # after a run of failures — whatever was fetched still gets stored.
    consecutive_failures = 0
    for gid, vid, start in games:
        v = venues.get(vid)
        if start is None or v is None:
            skipped += 1
            continue
        dome, lat, lon = v
        if dome:
            rows.append(
                {
                    "game_id": gid,
                    "temperature_f": 72.0,
                    "wind_mph": 0.0,
                    "precipitation": 0.0,
                    "dome": True,
                }
            )
            domes += 1
            continue
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            skipped += 1
            continue
        w = fetch_weather(
            lat, lon, start.date().isoformat(), hour=start.hour or 19, timeout=PER_CALL_TIMEOUT_S
        )
        time.sleep(0.15)  # be polite to the free API
        if w is None:
            skipped += 1
            consecutive_failures += 1
            if consecutive_failures == MAX_CONSECUTIVE_FAILURES:
                ci.warn(
                    f"{MAX_CONSECUTIVE_FAILURES} forecast calls failed in a row "
                    "(rate limit / outage?) — skipping the rest of the slate"
                )
            continue
        consecutive_failures = 0
        rows.append(
            {
                "game_id": gid,
                "temperature_f": w["temperature_f"],
                "wind_mph": w["wind_mph"],
                "precipitation": w["precipitation"],
                "dome": False,
            }
        )
        fetched += 1
    with session_scope() as s:
        n = upsert(s, Weather, rows, ["game_id"])
    print(
        f"weather: {n} games stored ({fetched} fetched, {domes} domes, "
        f"{skipped} skipped) for {args.season} wk{args.week}"
    )
    if fetched == 0 and skipped > 0:
        # Every outdoor game was skipped (outage/rate limit): flip the step's
        # outcome so sunday.yml's "scored WITHOUT weather" warning fires.
        ci.warn("enrich_weather fetched 0 forecasts — board will score without weather")
        sys.exit(3)


if __name__ == "__main__":
    main()
