#!/usr/bin/env python
"""Backfill historical pace (TeamRankings) + weather (Open-Meteo) for all games,
so they can become real model features (not just current-week display).

  python scripts/backfill_enrichment.py --tempo --weather --start 2017 --end 2025

- Tempo: one TeamRankings pull per season/week (as-of that week's median date).
- Weather: ONE ranged Open-Meteo call per venue (its whole game span), sliced to
  each game's kickoff hour — ~hundreds of calls instead of ~9,500.
Idempotent (upserts). Slow; safe to re-run / resume.
"""
from __future__ import annotations

import argparse
import time
from typing import Dict

import pandas as pd

from beatvegas.db.models import Game, Team, TeamTempo, Venue, Weather
from beatvegas.db.store import init_db, session_scope, upsert
from beatvegas.sources.cfbd import CFBDClient  # noqa: F401  (ensures key check)
from beatvegas.sources.teamrankings import fetch_tempo, map_to_cfbd
from beatvegas.sources.weather import fetch_weather_series


def backfill_tempo(start: int, end: int) -> None:
    from datetime import datetime
    with session_scope() as s:
        teams = [t[0] for t in s.query(Team.school).distinct().all()]
        games = pd.DataFrame(
            s.query(Game.season, Game.week, Game.start_date)
            .filter(Game.season.between(start, end),
                    Game.start_date.isnot(None)).all(),
            columns=["season", "week", "start_date"])
    games["start_date"] = pd.to_datetime(games["start_date"])
    wk_dates = (games.groupby(["season", "week"])["start_date"]
                .median().dt.strftime("%Y-%m-%d"))
    for (season, week), date in wk_dates.items():
        try:
            df = fetch_tempo(date=date)
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] tempo {season} wk{week} {date}: {e}")
            continue
        tmap = map_to_cfbd(df["tr_team"].tolist(), teams)
        seen, rows = set(), []
        for _, r in df.iterrows():
            school = tmap.get(r["tr_team"])
            if not school or school in seen:
                continue
            seen.add(school)
            rows.append({
                "season": int(season), "week": int(week), "team": school,
                "seconds_per_play": _num(r["seconds_per_play"]),
                "plays_per_game": _num(r["plays_per_game"]),
                "as_of_date": date, "captured_at": datetime.utcnow()})
        with session_scope() as s:
            upsert(s, TeamTempo, rows, ["season", "week", "team"])
        print(f"  tempo {season} wk{week}: {len(rows)} teams")
        time.sleep(0.4)            # be polite to TeamRankings


def backfill_weather(start: int, end: int) -> None:
    with session_scope() as s:
        rows = (s.query(Game.id, Game.venue_id, Game.start_date)
                .filter(Game.season.between(start, end),
                        Game.start_date.isnot(None)).all())
        venues = {v.id: {"dome": v.dome, "lat": v.latitude, "lon": v.longitude,
                         "name": v.name} for v in s.query(Venue).all()}
    games = pd.DataFrame(rows, columns=["id", "venue_id", "start_date"])
    games["start_date"] = pd.to_datetime(games["start_date"])

    for vid, grp in games.groupby("venue_id"):
        v = venues.get(vid)
        if v is None:
            continue
        if v["dome"]:
            wrows = [{"game_id": int(g.id), "temperature_f": 72.0, "wind_mph": 0.0,
                      "precipitation": 0.0, "dome": True} for g in grp.itertuples()]
            with session_scope() as s:
                upsert(s, Weather, wrows, ["game_id"])
            continue
        if v["lat"] is None or v["lon"] is None:
            continue
        lo = grp["start_date"].min().strftime("%Y-%m-%d")
        hi = grp["start_date"].max().strftime("%Y-%m-%d")
        series = fetch_weather_series(v["lat"], v["lon"], lo, hi)
        if not series:
            print(f"  [warn] weather venue {vid} ({v['name']}) empty")
            continue
        wrows = []
        for g in grp.itertuples():
            key = pd.Timestamp(g.start_date).strftime("%Y-%m-%dT%H")
            w = series.get(key) or series.get(
                pd.Timestamp(g.start_date).strftime("%Y-%m-%dT%H").replace(
                    f"T{g.start_date.hour:02d}", "T19"))
            if not w or w.get("temperature_f") is None:
                continue
            wrows.append({"game_id": int(g.id), "temperature_f": w["temperature_f"],
                          "wind_mph": w["wind_mph"], "precipitation": w["precipitation"],
                          "dome": False})
        with session_scope() as s:
            upsert(s, Weather, wrows, ["game_id"])
        print(f"  weather venue {vid} ({v['name']}): {len(wrows)}/{len(grp)} games")
        time.sleep(0.3)


def _num(v):
    return None if v != v else float(v)     # NaN -> None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tempo", action="store_true")
    ap.add_argument("--weather", action="store_true")
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2025)
    args = ap.parse_args()
    if not (args.tempo or args.weather):
        args.tempo = args.weather = True
    init_db()
    if args.tempo:
        print(f"== tempo backfill {args.start}-{args.end} ==")
        backfill_tempo(args.start, args.end)
    if args.weather:
        print(f"== weather backfill {args.start}-{args.end} ==")
        backfill_weather(args.start, args.end)
    print("done")


if __name__ == "__main__":
    main()
