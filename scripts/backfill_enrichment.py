#!/usr/bin/env python
"""Backfill historical pace (TeamRankings) for all games, so it can become a real
model feature (not just current-week display).

  python scripts/backfill_enrichment.py --start 2017 --end 2025

One TeamRankings pull per season/week (as-of that week's median date). Idempotent
(upserts). Slow; safe to re-run / resume.

WEATHER USED TO LIVE HERE AND NO LONGER DOES. It keyed a local-time Open-Meteo
series with a UTC kickoff, so every value it wrote was displaced by the venue's
UTC offset, and it wrote a 72F/0mph/0in dome placeholder that the rest of the
codebase exists to scrub. Use `scripts/backfill_weather.py`, which writes
`weather_obs` with the lead and the provenance attached.
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

from beatvegas.db.models import Game, Team, TeamTempo
from beatvegas.db.store import init_db, session_scope, upsert
from beatvegas.season import current_season
from beatvegas.sources.cfbd import CFBDClient  # noqa: F401  (ensures key check)
from beatvegas.sources.teamrankings import fetch_tempo, map_to_cfbd


def backfill_tempo(start: int, end: int) -> None:
    from datetime import datetime

    with session_scope() as s:
        teams = [t[0] for t in s.query(Team.school).distinct().all()]
        games = pd.DataFrame(
            s.query(Game.season, Game.week, Game.start_date)
            .filter(Game.season.between(start, end), Game.start_date.isnot(None))
            .all(),
            columns=["season", "week", "start_date"],
        )
    games["start_date"] = pd.to_datetime(games["start_date"])
    wk_dates = games.groupby(["season", "week"])["start_date"].median().dt.strftime("%Y-%m-%d")
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
            rows.append(
                {
                    "season": int(season),
                    "week": int(week),
                    "team": school,
                    "seconds_per_play": _num(r["seconds_per_play"]),
                    "plays_per_game": _num(r["plays_per_game"]),
                    "as_of_date": date,
                    "captured_at": datetime.utcnow(),
                }
            )
        with session_scope() as s:
            upsert(s, TeamTempo, rows, ["season", "week", "team"])
        print(f"  tempo {season} wk{week}: {len(rows)} teams")
        time.sleep(0.4)  # be polite to TeamRankings


def _num(v):
    return None if v != v else float(v)  # NaN -> None


def main() -> None:
    ap = argparse.ArgumentParser()
    # accepted for compatibility (enrich_tempo.yml passes it); tempo is all this does now
    ap.add_argument("--tempo", action="store_true")
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=current_season())
    args = ap.parse_args()
    init_db()
    print(f"== tempo backfill {args.start}-{args.end} ==")
    backfill_tempo(args.start, args.end)
    print("done")


if __name__ == "__main__":
    main()
