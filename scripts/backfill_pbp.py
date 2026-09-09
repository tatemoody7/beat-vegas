#!/usr/bin/env python
"""Backfill first-half play-by-play aggregates into fh_team_game.

For each season: load normalized plays (free cfbfastR parquet for <=2021, CFBD
/plays for 2022+), compute per-(game, offense) 1H aggregates, attach our own
canonical team names from the games table, and upsert. Raw plays are processed
transiently — only the compact aggregates are stored.

    python scripts/backfill_pbp.py                 # 2015-2025
    python scripts/backfill_pbp.py --season 2024
    python scripts/backfill_pbp.py --seasons 2015-2021
    python scripts/backfill_pbp.py --season 2026 --only-missing   # the daily grading run

Resumable (upsert by game_id+off_team) and fail-silent per season. `--only-missing`
fetches just the weeks holding a FINISHED FBS-vs-FBS game with no fh_team_game
rows yet (one CFBD /plays call per such week, usually one), instead of the whole
season's 20 weeks twice a day.
"""

from __future__ import annotations

import argparse
from typing import List, Optional

import pandas as pd

from beatvegas.db.models import FhTeamGame, Game
from beatvegas.db.store import get_engine, init_db, resync_table_sequence, session_scope, upsert
from beatvegas.etl.fbs import load_fbs_teams
from beatvegas.etl.fh_factors import aggregate_fh
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.cfbpbp import PARQUET_MAX_YEAR, load_plays


def _games_meta(season: int) -> pd.DataFrame:
    with session_scope() as s:
        return pd.DataFrame(
            s.query(Game.id, Game.season, Game.week, Game.home_team, Game.away_team)
            .filter(Game.season == season)
            .all(),
            columns=["game_id", "season", "week", "home_team", "away_team"],
        )


def _resync_sequence() -> None:
    """Neon/Postgres: bring the pkey sequence up to MAX(id) (never down) before insert."""
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        resync_table_sequence(conn, "fh_team_game")


def _weeks_missing_pbp(session, season: int) -> List[int]:
    """Weeks holding a FINISHED FBS-vs-FBS game (both point columns written —
    backfill.py only writes them once CFBD says the game is complete) that has
    no fh_team_game rows yet. Per GAME, not per week: a week whose Thursday game
    was aggregated on Friday still comes back on Sunday for its Saturday games.
    The FBS filter uses the git-tracked membership snapshot and is skipped for
    a season the snapshot does not carry (FCS games never get PBP rows, so
    without the filter they would re-queue their week every day)."""
    try:
        fbs = load_fbs_teams().get(season)
    except FileNotFoundError:
        fbs = None
    finished = (
        session.query(Game.id, Game.week, Game.home_team, Game.away_team)
        .filter(
            Game.season == season,
            Game.week.isnot(None),
            Game.home_points.isnot(None),
            Game.away_points.isnot(None),
        )
        .all()
    )
    have = {
        gid
        for (gid,) in session.query(FhTeamGame.game_id)
        .join(Game, Game.id == FhTeamGame.game_id)
        .filter(Game.season == season)
        .distinct()
    }
    weeks = set()
    for gid, wk, home, away in finished:
        if gid in have:
            continue
        if fbs is not None and (home not in fbs or away not in fbs):
            continue
        weeks.add(int(wk))
    return sorted(weeks)


def backfill_season(season: int, client: CFBDClient, only_missing: bool = False) -> int:
    week_list: Optional[List[int]] = None
    if only_missing:
        with session_scope() as s:
            week_list = _weeks_missing_pbp(s, season)
        if not week_list:
            return 0
        print(f"{season}: weeks missing PBP rows: {week_list}")
    plays = load_plays(season, client=client, week_list=week_list)
    if plays.empty:
        return 0
    agg = aggregate_fh(plays)
    meta = _games_meta(season)
    if agg.empty or meta.empty:
        return 0
    df = agg.merge(meta, on="game_id", how="inner")
    if df.empty:
        return 0
    src = "cfbfastr" if season <= PARQUET_MAX_YEAR else "cfbd"
    rows = []
    for r in df.itertuples(index=False):
        is_home = bool(r.is_home_off)
        off_team = r.home_team if is_home else r.away_team
        def_team = r.away_team if is_home else r.home_team
        rows.append(
            {
                "game_id": int(r.game_id),
                "season": int(r.season),
                "week": int(r.week),
                "off_team": off_team,
                "def_team": def_team,
                "is_home": is_home,
                "source": src,
                "n_plays": int(r.n_plays),
                "epa": _f(r.epa),
                "success": _f(r.success),
                "explosive": _f(r.explosive),
                "pass_rate": _f(r.pass_rate),
                "early_success": _f(r.early_success),
                "third_conv": _f(r.third_conv),
                "havoc_suffered": _f(r.havoc_suffered),
                "turnovers": _f(r.turnovers),
                "opening_score": _i(r.opening_score),
                "opening_3out": _i(r.opening_3out),
                "redzone_td": _f(r.redzone_td),
                "fourth_go": _f(r.fourth_go),
            }
        )
    _resync_sequence()
    with session_scope() as s:
        upsert(s, FhTeamGame, rows, ["game_id", "off_team"])
    return len(rows)


def _f(v):
    return None if pd.isna(v) else float(v)


def _i(v):
    return None if pd.isna(v) else int(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--seasons", default="2015-2025")
    ap.add_argument(
        "--only-missing",
        action="store_true",
        help="fetch only the weeks with finished FBS games lacking fh_team_game rows",
    )
    args = ap.parse_args()
    init_db()
    client = CFBDClient()

    if args.season:
        seasons = [args.season]
    else:
        a, b = (int(x) for x in args.seasons.split("-"))
        seasons = list(range(a, b + 1))

    total = 0
    for yr in seasons:
        try:
            n = backfill_season(yr, client, only_missing=args.only_missing)
            total += n
            print(f"{yr}: {n} team-game rows")
        except Exception as e:
            print(f"{yr}: ERROR {type(e).__name__}: {str(e)[:160]}")
    print(f"done: {total} rows")


if __name__ == "__main__":
    main()
