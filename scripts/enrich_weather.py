#!/usr/bin/env python
"""Populate the weather table for a week's games via Open-Meteo + venue coords.

Dome venues are recorded as dome with NULL temp/wind/precip (there is no
weather to model; a fake 72F/0mph placeholder would teach the model that "72
and calm" means dome). Outdoor venues get temp/wind/precip near kickoff.

FBS-vs-FBS only by default (2026-09-16): the model scores only games where both
teams were FBS that season (etl/fbs.py), but this step fetched a forecast for
every game in the week -- week 3 of 2026 was 311 games for 57 scored, ~290
sequential Open-Meteo calls and 8 of the Sunday job's 11 minutes, four fifths of
it for games nothing reads. `--all-divisions` restores the old behaviour.

    python scripts/enrich_weather.py --season 2025 --week 8
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Dict, List, Tuple

import pandas as pd

from beatvegas import ci
from beatvegas.db.models import Game, Venue, Weather
from beatvegas.db.store import session_scope, try_init_db, upsert
from beatvegas.etl.fbs import FbsMap, filter_fbs_games, load_fbs_teams
from beatvegas.sources.weather import WeatherUnavailable, fetch_weather

PER_CALL_TIMEOUT_S = 8
MAX_CONSECUTIVE_FAILURES = 15

GAME_KEYS = ("id", "venue_id", "start_date", "season", "home_team", "away_team")


def select_games(
    games: List[Dict], fbs: FbsMap, all_divisions: bool = False
) -> Tuple[List[Dict], int]:
    """(games to fetch weather for, games dropped). Pure. Reuses etl.fbs's
    filter -- the same rule build_feature_frame applies -- so the weather rows
    written are exactly the ones the scorer can read. Raises like the filter
    when the FBS snapshot has no entry for a season (loud, never silent)."""
    if all_divisions or not games:
        return list(games), 0
    df = pd.DataFrame(games, columns=list(GAME_KEYS))
    kept = filter_fbs_games(df, fbs)
    return kept.to_dict("records"), len(df) - len(kept)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument(
        "--all-divisions",
        action="store_true",
        help="fetch for every game in the week, not just FBS-vs-FBS (the scored set)",
    )
    args = ap.parse_args()
    if not try_init_db():
        return

    # Read, then fetch OUTSIDE any session: hundreds of Open-Meteo calls inside
    # one transaction trip Neon's idle-in-transaction timeout and lose the batch.
    with session_scope() as s:
        all_games = [
            {
                "id": g.id,
                "venue_id": g.venue_id,
                "start_date": g.start_date,
                "season": g.season,
                "home_team": g.home_team,
                "away_team": g.away_team,
            }
            for g in s.query(Game).filter(Game.season == args.season, Game.week == args.week)
        ]
        venues = {v.id: (v.dome, v.latitude, v.longitude) for v in s.query(Venue).all()}
    fbs = {} if args.all_divisions else load_fbs_teams()
    selected, non_fbs = select_games(all_games, fbs, all_divisions=args.all_divisions)
    games = [(g["id"], g["venue_id"], g["start_date"]) for g in selected]
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
                    "temperature_f": None,
                    "wind_mph": None,
                    "precipitation": None,
                    "dome": True,
                }
            )
            domes += 1
            continue
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            skipped += 1
            continue
        # `start` is naive UTC and goes in whole; passing a date plus an hour is
        # what let a UTC hour index a local-time array for three years.
        try:
            w = fetch_weather(lat, lon, start, timeout=PER_CALL_TIMEOUT_S)
        except WeatherUnavailable:
            w = None  # rate limited or down -- counts as a failure, same as no data
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
        f"{skipped} skipped, {non_fbs} non-FBS not fetched) for {args.season} wk{args.week}"
    )
    if fetched == 0 and skipped > 0:
        # Every outdoor game was skipped (outage/rate limit): flip the step's
        # outcome so sunday.yml's "scored WITHOUT weather" warning fires.
        ci.warn("enrich_weather fetched 0 forecasts — board will score without weather")
        sys.exit(3)


if __name__ == "__main__":
    main()
