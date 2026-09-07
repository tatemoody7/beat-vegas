#!/usr/bin/env python
"""Populate ONLY Game.spread from CFBD /lines, for the spread-adjusted multiplier.

Surgical by design: it UPDATEs existing games' `spread` and nothing else, so it
never touches the PBP-derived first-half ground truth (re-running the full
backfill.py without --use-pbp would null those — see etl/first_half). Idempotent.

Games whose spread came from a live capture (Game.spread_source in
line_sources.LIVE_LINE_SOURCES: oddsapi / dk) are skipped unless --force, so
this never overwrites the Sunday opener's number with CFBD's consensus.

    python scripts/backfill_spread.py                 # config range
    python scripts/backfill_spread.py --start 2015 --end 2025
    python scripts/backfill_spread.py --season 2026
    python scripts/backfill_spread.py --season 2026 --force   # CFBD wins everywhere
"""

from __future__ import annotations

import argparse

from beatvegas.config import load_config
from beatvegas.db.models import Game
from beatvegas.db.store import init_db, session_scope
from beatvegas.line_sources import CFBD_SOURCE, LIVE_LINE_SOURCES
from beatvegas.season import current_season
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.cfbd_lines import DEFAULT_SEASON_TYPE, _season_types

# Same provider priority backfill.py uses to pick one number per game.
PROVIDER_PRIORITY = ["consensus", "DraftKings", "Bovada", "ESPN Bet", "William Hill (US)"]


def _get(d, *names):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return None


def _pick_spread(lines):
    """Home-relative spread by provider priority, else first non-null."""
    by_provider = {}
    for ln in lines or []:
        sp = _get(ln, "spread")
        prov = _get(ln, "provider")
        if sp is not None and prov is not None and prov not in by_provider:
            by_provider[prov] = float(sp)
    for prov in PROVIDER_PRIORITY:
        if prov in by_provider:
            return by_provider[prov]
    return next(iter(by_provider.values())) if by_provider else None


def backfill_season(client: CFBDClient, season: int, season_type: str, force: bool = False) -> int:
    """UPDATE Game.spread from CFBD for `season`; returns games updated. Games
    tagged with a live spread source are left alone unless `force`."""
    spread_by_game = {}
    for st in _season_types(season_type):
        for g in client.lines(year=season, season_type=st):
            gid = _get(g, "id")
            sp = _pick_spread(_get(g, "lines") or [])
            if gid is not None and sp is not None:
                spread_by_game[gid] = sp
    updated = 0
    with session_scope() as s:
        for gid, sp in spread_by_game.items():
            g = s.query(Game).filter(Game.id == gid).one_or_none()
            if g is None:
                continue
            if not force and g.spread_source in LIVE_LINE_SOURCES:
                continue
            g.spread = sp
            g.spread_source = CFBD_SOURCE
            updated += 1
    return updated


def main() -> None:
    cfg = load_config().get("backfill", {}) or {}
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, help="single season override")
    ap.add_argument("--start", type=int, default=cfg.get("start_season", 2015))
    ap.add_argument("--end", type=int, default=cfg.get("end_season") or current_season())
    ap.add_argument("--season-type", default=cfg.get("season_type", DEFAULT_SEASON_TYPE))
    ap.add_argument(
        "--force",
        action="store_true",
        help="also overwrite spreads a live capture (Odds API / DK) wrote",
    )
    args = ap.parse_args()

    init_db()
    client = CFBDClient()
    seasons = [args.season] if args.season else range(args.start, args.end + 1)
    for season in seasons:
        n = backfill_season(client, season, args.season_type, force=args.force)
        print(f"{season}: {n} games updated with spread")


if __name__ == "__main__":
    main()
