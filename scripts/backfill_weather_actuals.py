#!/usr/bin/env python
"""Backfill `weather_actuals`: OBSERVED weather around played FBS-vs-FBS games.

    python scripts/backfill_weather_actuals.py --start 2013 --end 2026 --sources era5,cfbd
    python scripts/backfill_weather_actuals.py --check     # sanity + ERA5-vs-CFBD agreement
    python scripts/backfill_weather_actuals.py --promote   # staging file -> weather_actuals

A STUDY TABLE, NOT A MODEL INPUT (Tate's calls, 2026-10-08, roadmap v1.3): the data
behind the Salaga & Howley history look (docs/LITERATURE.md) -- wind and rain
averaged over the game, temperature and humidity at kickoff. Nothing reads
`weather_actuals` but that look, so filling it cannot move the champion (which reads
`weather`) or a frozen study (which reads `weather_obs`). These are what the
conditions WERE; none of it was knowable before kickoff, so none of it is
decision-safe.

TWO SOURCES, SIDE BY SIDE (a cross-check, never blended):
  era5  Open-Meteo's ERA5 archive, `models=era5` pinned so 2013 and 2026 come from
        the same reanalysis. One call per game for the day(s) spanning the kickoff
        hour -1 to +4, so each call is one unit of the free quota (~10,000 a day:
        a full 2013-2026 pass spans two UTC days and resumes where it stopped).
        `timezone=UTC` as everywhere (docs/WEATHER.md section 1). ERA5 lags real
        time by about five days, so games newer than ERA5_LAG_DAYS are left for a
        later run. Domed venues are skipped -- no call, no row.
  cfbd  CFBD /games/weather, one reading per game (provider unnamed), two calls a
        season (regular + postseason) against a 75,000-a-month quota. Stored at
        hour_offset 0 as reported.

Writes a staging JSONL first and touches the database only on --promote, so a
two-day fetch can be inspected (--check) before anything is written, and a re-run
skips every game already staged.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beatvegas.sources.weather import (  # noqa: E402
    ACTUAL_VARS,
    SOURCE_ACTUAL,
    WeatherUnavailable,
    fetch_hourly_series,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGING = REPO_ROOT / "data" / "cache" / "weather_actuals_staging.jsonl"
DONE = REPO_ROOT / "data" / "cache" / "weather_actuals_staging.done"

SOURCE_ERA5 = SOURCE_ACTUAL  # "open_meteo_era5_archive"
SOURCE_CFBD = "cfbd_games_weather"
SOURCES = {"era5": SOURCE_ERA5, "cfbd": SOURCE_CFBD}
ERA5_MODEL = "era5"  # pinned: one reanalysis for every season
DATASET_VERSION = "weather_actuals_v1_2026-10-08"  # bump when the fetch changes
OFFSETS = tuple(range(-1, 5))  # hours from the kickoff hour: one before, four after
ERA5_LAG_DAYS = 6  # the archive trails real time by ~5 days
SLEEP_S = 0.75  # ~80 calls a minute, under the free tier's 5,000 an hour
MAX_CONSECUTIVE_FAILURES = 10
CHUNK = 500  # a single big bulk insert stalls the Neon pooler

# --check bounds: a value outside these is a units or parsing defect, not weather.
BOUNDS = {
    "temperature_f": (-40.0, 125.0),
    "humidity_pct": (0.0, 100.0),
    "wind_mph": (0.0, 90.0),
    "wind_gust_mph": (0.0, 130.0),
    "precipitation_in": (0.0, 10.0),
}


# ---------------------------------------------------------------- pure


def kickoff_hour(kickoff: datetime) -> datetime:
    """The UTC hour the game kicks off in (19:30 -> 19:00): offset 0."""
    return kickoff.replace(minute=0, second=0, microsecond=0)


def era5_window(kickoff: datetime) -> Tuple[str, str]:
    """(start_date, end_date) covering every offset, in UTC dates. A 23:00Z
    kickoff's +4 hours land on the next UTC day, so the range spans both."""
    k = kickoff_hour(kickoff)
    lo, hi = k + timedelta(hours=OFFSETS[0]), k + timedelta(hours=OFFSETS[-1])
    return lo.strftime("%Y-%m-%d"), hi.strftime("%Y-%m-%d")


def era5_rows(
    game_id: int,
    kickoff: datetime,
    series: Dict[str, dict],
    lat: float,
    lon: float,
    retrieved_at: str,
) -> List[dict]:
    """One row per offset that the series covers. An hour with no temperature is
    dropped (ERA5 not yet published there), never written as zeros."""
    k = kickoff_hour(kickoff)
    out = []
    for off in OFFSETS:
        t = k + timedelta(hours=off)
        vals = series.get(t.strftime("%Y-%m-%dT%H"))
        if not vals or vals.get("temperature_f") is None:
            continue
        out.append(
            {
                "game_id": int(game_id),
                "source": SOURCE_ERA5,
                "hour_offset": off,
                "valid_time": t.isoformat(),
                "kickoff_utc": kickoff.isoformat(),
                "temperature_f": vals.get("temperature_f"),
                "humidity_pct": vals.get("humidity_pct"),
                "dew_point_f": vals.get("dew_point_f"),
                "wind_mph": vals.get("wind_mph"),
                "wind_gust_mph": vals.get("wind_gust_mph"),
                "wind_direction_deg": vals.get("wind_direction_deg"),
                "precipitation_in": vals.get("precipitation"),
                "snowfall_in": None,
                "pressure": None,
                "weather_code": None,
                "game_indoors": None,
                "latitude": lat,
                "longitude": lon,
                "weather_model": ERA5_MODEL,
                "dataset_version": DATASET_VERSION,
                "retrieved_at": retrieved_at,
            }
        )
    return out


def _num(v) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _parse_utc(s: Optional[str]) -> Optional[datetime]:
    """CFBD's ISO time ('2016-11-05T19:30:00.000Z') -> naive UTC."""
    if not s:
        return None
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def cfbd_row(r: dict, kickoff: Optional[datetime], retrieved_at: str) -> dict:
    """One CFBD reading, as reported, at hour_offset 0."""
    valid = _parse_utc(r.get("startTime"))
    code = r.get("weatherConditionCode")
    return {
        "game_id": int(r["id"]),
        "source": SOURCE_CFBD,
        "hour_offset": 0,
        "valid_time": valid.isoformat() if valid else None,
        "kickoff_utc": kickoff.isoformat() if kickoff else None,
        "temperature_f": _num(r.get("temperature")),
        "humidity_pct": _num(r.get("humidity")),
        "dew_point_f": _num(r.get("dewPoint")),
        "wind_mph": _num(r.get("windSpeed")),
        "wind_gust_mph": None,
        "wind_direction_deg": _num(r.get("windDirection")),
        "precipitation_in": _num(r.get("precipitation")),
        "snowfall_in": _num(r.get("snowfall")),
        "pressure": _num(r.get("pressure")),
        "weather_code": int(code) if code is not None else None,
        "game_indoors": r.get("gameIndoors"),
        "latitude": None,
        "longitude": None,
        "weather_model": None,
        "dataset_version": DATASET_VERSION,
        "retrieved_at": retrieved_at,
    }


def dedupe(rows: Iterable[dict]) -> List[dict]:
    """Last write wins on the table's unique key, so a re-fetched game
    supersedes its earlier rows in the staging file."""
    latest = {(r["game_id"], r["source"], r["hour_offset"], r["dataset_version"]): r for r in rows}
    return list(latest.values())


def check(rows: List[dict]) -> Tuple[List[str], Dict[str, object]]:
    """(problems, summary). Problems block a promote: an out-of-range value, or a
    gust below the mean wind by more than rounding (docs/WEATHER.md section 2)."""
    problems: List[str] = []
    for r in rows:
        for col, (lo, hi) in BOUNDS.items():
            v = r.get(col)
            if v is not None and not (lo <= v <= hi):
                problems.append(f"game {r['game_id']} {r['source']} {col}={v}")
        w, g = r.get("wind_mph"), r.get("wind_gust_mph")
        if w is not None and g is not None and g < w - 0.5:
            problems.append(f"game {r['game_id']} offset {r['hour_offset']}: gust {g} < wind {w}")
    era5 = {r["game_id"]: r for r in rows if r["source"] == SOURCE_ERA5 and r["hour_offset"] == 0}
    cfbd = {r["game_id"]: r for r in rows if r["source"] == SOURCE_CFBD}
    both = sorted(set(era5) & set(cfbd))

    def mad(col: str) -> Optional[float]:
        d = [
            abs(era5[g][col] - cfbd[g][col])
            for g in both
            if era5[g].get(col) is not None and cfbd[g].get(col) is not None
        ]
        return round(statistics.mean(d), 2) if d else None

    summary = {
        "rows": len(rows),
        "era5_games": len({r["game_id"] for r in rows if r["source"] == SOURCE_ERA5}),
        "cfbd_games": len(cfbd),
        "games_in_both": len(both),
        "mean_abs_diff_temperature_f": mad("temperature_f"),
        "mean_abs_diff_humidity_pct": mad("humidity_pct"),
        "mean_abs_diff_wind_mph": mad("wind_mph"),
    }
    return problems, summary


# ---------------------------------------------------------------- io


def _plan(start: int, end: int):
    """Played FBS-vs-FBS games in the seasons: {game_id: (season, kickoff,
    venue_id)} plus the venue index."""
    import pandas as pd

    from beatvegas.db.models import Game, Venue
    from beatvegas.db.store import session_scope
    from beatvegas.etl.fbs import filter_fbs_games, load_fbs_teams

    now = datetime.utcnow()
    with session_scope() as s:
        games = pd.DataFrame(
            s.query(
                Game.id, Game.season, Game.start_date, Game.venue_id, Game.home_team, Game.away_team
            )
            .filter(Game.season.between(start, end), Game.start_date.isnot(None))
            .all(),
            columns=["id", "season", "start_date", "venue_id", "home_team", "away_team"],
        )
        venues = {
            v.id: {"dome": bool(v.dome), "lat": v.latitude, "lon": v.longitude, "name": v.name}
            for v in s.query(Venue).all()
        }
    games = filter_fbs_games(games, load_fbs_teams())
    games = games[games["start_date"] < now]
    plan = {
        int(g.id): (
            int(g.season),
            g.start_date.to_pydatetime(),
            None if pd.isna(g.venue_id) else int(g.venue_id),
        )
        for g in games.itertuples()
    }
    return plan, venues


def _load_done() -> set:
    if not DONE.exists():
        return set()
    return {ln.strip() for ln in DONE.read_text().splitlines() if ln.strip()}


def fetch_era5(plan, venues, done: set, limit: Optional[int]) -> int:
    from beatvegas.etl.venues import coord_problems

    cutoff = datetime.utcnow() - timedelta(days=ERA5_LAG_DAYS)
    todo = [
        (gid, k, vid)
        for gid, (_season, k, vid) in sorted(plan.items(), key=lambda kv: kv[1][1])
        if f"era5|{gid}" not in done and k <= cutoff
    ]
    used = {vid for _, _, vid in todo if vid is not None}
    bad = [
        (vid, why)
        for vid, why in coord_problems(
            [
                {
                    "id": v,
                    "name": venues[v]["name"],
                    "latitude": venues[v]["lat"],
                    "longitude": venues[v]["lon"],
                }
                for v in used
                if v in venues and not venues[v]["dome"]
            ]
        )
        if why != "missing"
    ]
    if bad:
        for vid, why in bad[:20]:
            print(f"  [BAD COORDS] venue {vid} ({venues[vid]['name']}): {why}")
        raise SystemExit(f"{len(bad)} venues have implausible coordinates; fix them first.")
    if limit:
        todo = todo[:limit]
    print(f"== era5: {len(todo)} games to fetch ({len(done)} done-keys on file) ==")
    written = skipped = fails = 0
    with STAGING.open("a") as out, DONE.open("a") as donef:
        for i, (gid, k, vid) in enumerate(todo, 1):
            v = venues.get(vid) if vid is not None else None
            if v is None or v["dome"] or v["lat"] is None or v["lon"] is None:
                skipped += 1
                donef.write(f"era5|{gid}\n")  # nothing to fetch, ever
                continue
            lo, hi = era5_window(k)
            try:
                series = fetch_hourly_series(
                    v["lat"],
                    v["lon"],
                    lo,
                    hi,
                    source=SOURCE_ERA5,
                    models=ERA5_MODEL,
                    variables=ACTUAL_VARS,
                )
            except WeatherUnavailable as e:
                fails += 1
                print(f"  [warn] game {gid}: {e}")
                if fails >= MAX_CONSECUTIVE_FAILURES:
                    print(
                        f"::warning::{MAX_CONSECUTIVE_FAILURES} calls failed in a row "
                        "(likely the daily quota) -- stopping; re-run to resume."
                    )
                    break
                continue
            fails = 0
            rows = era5_rows(gid, k, series, v["lat"], v["lon"], datetime.utcnow().isoformat())
            for r in rows:
                out.write(json.dumps(r) + "\n")
            out.flush()
            if rows:
                donef.write(f"era5|{gid}\n")
                donef.flush()
            written += len(rows)
            if i % 250 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} games, {written} rows")
            time.sleep(SLEEP_S)
    print(f"era5: staged {written} rows; {skipped} games domed or without a venue")
    return written


def fetch_cfbd(plan, start: int, end: int, done: set) -> int:
    from beatvegas.sources.cfbd import CFBDClient

    client = CFBDClient()
    written = 0
    with STAGING.open("a") as out, DONE.open("a") as donef:
        for season in range(start, end + 1):
            for st in ("regular", "postseason"):
                key = f"cfbd|{season}|{st}"
                if key in done:
                    continue
                stamp = datetime.utcnow().isoformat()
                rows = [
                    cfbd_row(r, plan[int(r["id"])][1], stamp)
                    for r in client.game_weather(season, st)
                    if r.get("id") is not None and int(r["id"]) in plan
                ]
                for r in rows:
                    out.write(json.dumps(r) + "\n")
                out.flush()
                donef.write(key + "\n")
                donef.flush()
                written += len(rows)
                print(f"  cfbd {season} {st}: {len(rows)} FBS-vs-FBS games")
    print(f"cfbd: staged {written} rows")
    return written


def _staged() -> List[dict]:
    if not STAGING.exists():
        return []
    return dedupe(json.loads(ln) for ln in STAGING.read_text().splitlines() if ln.strip())


def promote(sources: List[str]) -> None:
    from beatvegas.db.models import WeatherActual
    from beatvegas.db.store import session_scope

    rows = [r for r in _staged() if r["source"] in sources]
    problems, summary = check(rows)
    if problems:
        raise SystemExit(f"{len(problems)} problems; run --check. First: {problems[:3]}")
    for r in rows:
        for k in ("valid_time", "kickoff_utc", "retrieved_at"):
            r[k] = datetime.fromisoformat(r[k]) if r[k] else None
    print(f"promoting {len(rows)} rows: {summary}")
    with session_scope() as s:
        # Full replace per (source, version): the staging file is the complete
        # authority for what it holds, and nothing else reads this table.
        s.query(WeatherActual).filter(
            WeatherActual.source.in_(sources),
            WeatherActual.dataset_version == DATASET_VERSION,
        ).delete(synchronize_session=False)
        s.commit()
        for i in range(0, len(rows), CHUNK):
            s.bulk_insert_mappings(WeatherActual, rows[i : i + CHUNK])
            s.commit()
        total = s.query(WeatherActual).count()
    print(f"weather_actuals now holds {total} rows")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--start", type=int, default=2013)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument("--sources", default="era5,cfbd", help="comma-separated: era5, cfbd")
    ap.add_argument("--limit", type=int, help="era5: stop after N games (smoke test)")
    ap.add_argument("--check", action="store_true", help="sanity + agreement on the staging file")
    ap.add_argument("--promote", action="store_true", help="staging file -> weather_actuals")
    args = ap.parse_args(argv)
    keys = [k.strip() for k in args.sources.split(",") if k.strip()]
    unknown = [k for k in keys if k not in SOURCES]
    if unknown:
        ap.error(f"unknown source(s) {unknown}; choose from {sorted(SOURCES)}")
    sources = [SOURCES[k] for k in keys]

    if args.check:
        problems, summary = check(_staged())
        print(json.dumps(summary, indent=1))
        for p in problems[:20]:
            print(f"  [problem] {p}")
        return 1 if problems or not summary["rows"] else 0

    from beatvegas.db.store import try_init_db

    if not try_init_db():
        return 1
    if args.promote:
        promote(sources)
        return 0
    STAGING.parent.mkdir(parents=True, exist_ok=True)
    plan, venues = _plan(args.start, args.end)
    print(f"{len(plan)} played FBS-vs-FBS games in {args.start}-{args.end}")
    done = _load_done()
    if "cfbd" in keys:
        fetch_cfbd(plan, args.start, args.end, done)
    if "era5" in keys:
        fetch_era5(plan, venues, done, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
