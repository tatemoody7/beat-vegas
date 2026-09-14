#!/usr/bin/env python
"""Backfill `weather_obs` from Open-Meteo: one call per venue-season, resumable.

    python scripts/backfill_weather.py --start 2023 --end 2026 --leads 0,24,72
    python scripts/backfill_weather.py --promote          # staging file -> weather_obs

TWO KINDS OF ROW, AND THEY MUST NEVER BE MIXED:

  lead_hours = 0    the near-kickoff series (Historical Forecast API). It stitches
                    the first hours of successive model runs, so it tracks what
                    ACTUALLY happened -- 1.82F / 1.55mph from the ERA5 actual on a
                    12-kickoff sample, closer than even a 1-day-lead forecast. Good
                    for modelling and data quality. `decision_safe = false`: using
                    it to claim a pregame edge is look-ahead bias.

  lead_hours >= 24  the forecast that genuinely existed that far ahead (Previous
                    Runs API). `decision_safe = true`. 2024+ only -- fixed-lead
                    wind, gusts and precipitation carry no data before the 2024
                    season, so 2023 is skipped for these leads rather than filled
                    with something that looks like data.

The model is PINNED to icon_seamless for the fixed-lead rows. The default blend
(gfs_seamless) returns gusts BELOW the mean wind at 48h and beyond -- physically
impossible, so the two variables are not coming from one run. Measured over 18
venue-hours: gfs 0/18 violations at 24h but 7-9/18 from 48h out, icon 0/18 at
every lead from 24h to 144h, with full coverage on all four variables across
2024-2026. See docs/WEATHER.md.

Writes to a staging JSONL first and only touches the database on --promote, so a
90-minute fetch can be inspected before anything reads it, and a re-run resumes
from where it stopped.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from beatvegas.db.models import Game, Venue, WeatherObs
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.venues import coord_problems
from beatvegas.sources.weather import (
    SOURCE_DECISION,
    SOURCE_NEAR_KICKOFF,
    WeatherUnavailable,
    decision_safe,
    fetch_hourly_series,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGING = REPO_ROOT / "data" / "cache" / "weather_staging.jsonl"
DONE = REPO_ROOT / "data" / "cache" / "weather_staging.done"

DECISION_MODEL = "icon_seamless"  # see the module docstring -- gusts, not preference
DATASET_VERSION = "open_meteo_v1_2026-09-14"  # bump when the fetch methodology changes
DECISION_FIRST_SEASON = 2024  # fixed-lead wind/gust/precip do not exist before this
SLEEP_S = 0.3  # be polite to the free API
MAX_CONSECUTIVE_FAILURES = 10
CHUNK = 500  # a single big bulk_insert stalls the Neon pooler indefinitely


def _plan(start: int, end: int) -> Tuple[Dict[Tuple[int, int], list], Dict[int, dict]]:
    """(venue_id, season) -> [games], plus the venue index. Past kickoffs only."""
    now = datetime.utcnow()
    with session_scope() as s:
        games = [
            (g.id, g.venue_id, g.season, g.start_date)
            for g in s.query(Game)
            .filter(Game.season.between(start, end), Game.start_date.isnot(None))
            .all()
        ]
        venues = {
            v.id: {"dome": bool(v.dome), "lat": v.latitude, "lon": v.longitude, "name": v.name}
            for v in s.query(Venue).all()
        }
    groups: Dict[Tuple[int, int], list] = defaultdict(list)
    for gid, vid, season, start_date in games:
        if vid is None or start_date is None or start_date >= now:
            continue  # upcoming games are the weekly job's business
        groups[(vid, season)].append((gid, start_date))
    return groups, venues


def _row(
    game_id: int,
    lead: int,
    kickoff: datetime,
    source: str,
    model: Optional[str],
    venue: dict,
    vals: Optional[dict],
) -> dict:
    w = vals or {}
    return {
        "game_id": int(game_id),
        "lead_hours": int(lead),
        "valid_time": kickoff.isoformat(),
        # NOT valid_time - lead_hours. That is the nominal horizon, which
        # `lead_hours` already carries; the run's initialisation and the moment it
        # became publicly usable are different times again, and Open-Meteo states
        # neither for the `_previous_dayN` variables. NULL is the honest answer --
        # inventing one would make `available_at <= decision_time` untestable while
        # looking like it had been tested.
        "model_run_time": None,
        "available_at": None,
        "decision_safe": decision_safe(source, lead),
        "temperature_f": w.get("temperature_f"),
        "wind_mph": w.get("wind_mph"),
        "wind_gust_mph": w.get("wind_gust_mph"),
        "precipitation": w.get("precipitation"),
        "dome": bool(venue["dome"]),
        "source": source,
        "weather_model": model,
        "dataset_version": DATASET_VERSION,
        "latitude": venue["lat"],
        "longitude": venue["lon"],
        "retrieved_at": datetime.utcnow().isoformat(),
    }


def _load_done() -> set:
    if not DONE.exists():
        return set()
    return {ln.strip() for ln in DONE.read_text().splitlines() if ln.strip()}


def _check_coords(venues: Dict[int, dict], used: set) -> None:
    """Coordinates before requests: perfect weather for the wrong stadium is the
    one failure here that looks like success all the way down."""
    rows = [
        {"id": vid, "name": v["name"], "latitude": v["lat"], "longitude": v["lon"]}
        for vid, v in venues.items()
        if vid in used and not v["dome"]
    ]
    problems = coord_problems(rows)
    wrong = [(vid, why) for vid, why in problems if why != "missing"]
    missing = [vid for vid, why in problems if why == "missing"]
    if missing:
        print(f"  {len(missing)} venues have no coordinates -- unfetchable, skipped")
    if wrong:
        for vid, why in wrong[:20]:
            print(f"  [BAD COORDS] venue {vid} ({venues[vid]['name']}): {why}")
        raise SystemExit(
            f"{len(wrong)} venues have implausible coordinates. Fix them before "
            "spending an hour of requests on the wrong locations."
        )


def fetch(start: int, end: int, leads: List[int], limit: Optional[int]) -> None:
    groups, venues = _plan(start, end)
    _check_coords(venues, {vid for vid, _ in groups})
    done = _load_done()
    STAGING.parent.mkdir(parents=True, exist_ok=True)

    todo = []
    for (vid, season), games in sorted(groups.items()):
        for lead in leads:
            if lead and season < DECISION_FIRST_SEASON:
                continue  # no fixed-lead wind/gust/precip before 2024
            if f"{vid}|{season}|{lead}" in done:
                continue
            todo.append((vid, season, lead, games))
    if limit:
        todo = todo[:limit]
    print(f"== weather backfill {start}-{end} leads={leads}: {len(todo)} venue-season-leads ==")

    fails = 0
    written = skipped_novenue = 0
    with STAGING.open("a") as out, DONE.open("a") as donef:
        for i, (vid, season, lead, games) in enumerate(todo, 1):
            v = venues.get(vid)
            if v is None:
                skipped_novenue += 1
                continue
            source = SOURCE_NEAR_KICKOFF if lead == 0 else SOURCE_DECISION
            model = None if lead == 0 else DECISION_MODEL

            if v["dome"]:
                # No API call: a dome has no weather, and a 72F/0mph placeholder
                # would teach the model that "72 and calm" means dome.
                rows = [_row(gid, lead, k, source, model, v, None) for gid, k in games]
            elif v["lat"] is None or v["lon"] is None:
                skipped_novenue += 1
                continue
            else:
                lo = min(k for _, k in games).strftime("%Y-%m-%d")
                hi = max(k for _, k in games).strftime("%Y-%m-%d")
                try:
                    series = fetch_hourly_series(
                        v["lat"], v["lon"], lo, hi, source=source, lead_hours=lead, models=model
                    )
                except WeatherUnavailable as e:
                    fails += 1
                    print(f"  [warn] venue {vid} {season} lead{lead}: {e}")
                    if fails >= MAX_CONSECUTIVE_FAILURES:
                        raise SystemExit(
                            f"{MAX_CONSECUTIVE_FAILURES} venue-seasons failed in a row -- "
                            "stopping. Nothing is lost: re-run to resume."
                        ) from e
                    continue
                fails = 0
                rows = []
                for gid, k in games:
                    vals = series.get(k.strftime("%Y-%m-%dT%H"))
                    if not vals or vals.get("temperature_f") is None:
                        continue
                    rows.append(_row(gid, lead, k, source, model, v, vals))
                time.sleep(SLEEP_S)

            for r in rows:
                out.write(json.dumps(r) + "\n")
            written += len(rows)
            out.flush()
            donef.write(f"{vid}|{season}|{lead}\n")
            donef.flush()
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} venue-seasons, {written} rows")
    print(f"staged {written} rows -> {STAGING} ({skipped_novenue} venue-seasons unfetchable)")


def _parse_rows(leads: Optional[List[int]]) -> List[dict]:
    rows = []
    for ln in STAGING.read_text().splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        if leads and r["lead_hours"] not in leads:
            continue
        for k in ("valid_time", "model_run_time", "available_at", "retrieved_at"):
            r[k] = datetime.fromisoformat(r[k]) if r[k] else None
        rows.append(r)
    # Last write wins, so a re-fetched venue-season supersedes its earlier rows.
    # The key mirrors uq_weather_obs_reading exactly -- a different model or run is
    # a DIFFERENT reading to be kept, not a replacement.
    latest = {
        (
            r["game_id"],
            r["lead_hours"],
            r.get("source") or "",
            r.get("weather_model") or "",
            r.get("model_run_time") or "",
        ): r
        for r in rows
    }
    return list(latest.values())


def promote(leads: Optional[List[int]]) -> None:
    rows = _parse_rows(leads)
    present = sorted({r["lead_hours"] for r in rows})
    print(f"promoting {len(rows)} rows, leads {present}")
    with session_scope() as s:
        # Full replace per lead. The staging file is the complete authority for
        # the leads it holds, and nothing reads weather_obs yet, so this is
        # cheaper and more predictable than 40k single-row upserts against Neon.
        s.query(WeatherObs).filter(WeatherObs.lead_hours.in_(present)).delete(
            synchronize_session=False
        )
        s.commit()
        for i in range(0, len(rows), CHUNK):
            s.bulk_insert_mappings(WeatherObs, rows[i : i + CHUNK])
            s.commit()
        total = s.query(WeatherObs).count()
    print(f"weather_obs now holds {total} rows")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--start", type=int, default=2023)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument(
        "--leads", default="0,24,72", help="comma-separated lead hours; 0 = near kickoff"
    )
    ap.add_argument("--limit", type=int, help="stop after N venue-season-leads (smoke test)")
    ap.add_argument(
        "--promote", action="store_true", help="write the staging file into weather_obs"
    )
    args = ap.parse_args()
    leads = [int(x) for x in args.leads.split(",") if x.strip() != ""]
    if not try_init_db():
        return
    if args.promote:
        promote(leads)
    else:
        fetch(args.start, args.end, leads, args.limit)


if __name__ == "__main__":
    main()
