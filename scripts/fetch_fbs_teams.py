#!/usr/bin/env python
"""Snapshot FBS membership per season from CFBD `/teams/fbs?year=` into the
git-tracked `data/fbs_teams.json` (read by beatvegas/etl/fbs.py).

Why a snapshot: the feature frame, backtest and weekly scoring filter to
FBS-vs-FBS games, and the cloud jobs must not spend CFBD credits (or depend on
the API being up) to know who was FBS in 2017. One call per season.

    python scripts/fetch_fbs_teams.py                    # config backfill.start_season..end_season
    python scripts/fetch_fbs_teams.py --seasons 2015 2026
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List

from beatvegas.config import load_config
from beatvegas.etl.fbs import FBS_TEAMS_PATH
from beatvegas.sources.cfbd import CFBDClient

# FBS has had 120-136 members every season since 2015; anything far below that
# means a bad/partial API response, and silently writing it would drop most of
# a season's games from the engine.
MIN_PLAUSIBLE_FBS_TEAMS = 100


def build_fbs_map(
    client, seasons: Iterable[int], min_teams: int = MIN_PLAUSIBLE_FBS_TEAMS
) -> Dict[int, List[str]]:
    out: Dict[int, List[str]] = {}
    for yr in seasons:
        schools = sorted({r["school"] for r in client.fbs_teams(yr) if r.get("school")})
        if len(schools) < min_teams:
            raise ValueError(
                f"CFBD returned only {len(schools)} FBS teams for {yr}; refusing to snapshot"
            )
        out[int(yr)] = schools
    return out


def write_snapshot(fbs_map: Dict[int, List[str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(k): list(v) for k, v in sorted(fbs_map.items())}
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"))
    ap.add_argument("--out", type=Path, default=FBS_TEAMS_PATH)
    args = ap.parse_args()
    if args.seasons:
        first, last = args.seasons
    else:
        bf = load_config().get("backfill", {}) or {}
        first, last = int(bf.get("start_season", 2015)), int(bf.get("end_season", 2026))
    fbs_map = build_fbs_map(CFBDClient(), range(first, last + 1))
    write_snapshot(fbs_map, args.out)
    for yr, schools in fbs_map.items():
        print(f"{yr}: {len(schools)} FBS teams")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
