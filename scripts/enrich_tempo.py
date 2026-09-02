#!/usr/bin/env python
"""Scrape TeamRankings pace and store it as team_tempo rows (CFBD-mapped names).

    python scripts/enrich_tempo.py --season 2025 --week 8 --date 2025-10-13
    python scripts/enrich_tempo.py --season 2026 --week 5          # current, no date

`--date` (optional) pulls season-to-date values AS OF that date (leak-free for
backtests); omit it to pull the latest.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from beatvegas.db.models import Team, TeamTempo
from beatvegas.db.store import session_scope, try_init_db, upsert
from beatvegas.sources.teamrankings import fetch_tempo, map_to_cfbd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--date", help="as-of date YYYY-MM-DD (leak-free)")
    args = ap.parse_args()
    if not try_init_db():
        return

    df = fetch_tempo(date=args.date)
    now = datetime.utcnow()
    with session_scope() as s:
        teams = [t[0] for t in s.query(Team.school).distinct().all()]
        mapping = map_to_cfbd(df["tr_team"].tolist(), teams)
        rows, unmatched = [], []
        for _, r in df.iterrows():
            school = mapping.get(r["tr_team"])
            if not school:
                unmatched.append(r["tr_team"])
                continue
            rows.append(
                {
                    "season": args.season,
                    "week": args.week,
                    "team": school,
                    "seconds_per_play": None
                    if r["seconds_per_play"] != r["seconds_per_play"]
                    else float(r["seconds_per_play"]),
                    "plays_per_game": None
                    if r["plays_per_game"] != r["plays_per_game"]
                    else float(r["plays_per_game"]),
                    "as_of_date": args.date,
                    "captured_at": now,
                }
            )
        n = upsert(s, TeamTempo, rows, ["season", "week", "team"])
    print(
        f"stored tempo for {n} teams ({args.season} wk{args.week}"
        + (f", as-of {args.date}" if args.date else "")
        + ")"
    )
    if unmatched:
        print(f"unmatched TeamRankings names ({len(unmatched)}): {unmatched}")


if __name__ == "__main__":
    main()
