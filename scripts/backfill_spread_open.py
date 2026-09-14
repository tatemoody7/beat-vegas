#!/usr/bin/env python
"""Populate ONLY Game.spread_open from CFBD /lines — the one as-of spread that
is recoverable after the fact.

WHY THIS EXISTS. `Game.spread` is mutable: every capture carrying a spread
overwrites it, so what is stored is whatever the last run before the row went
quiet happened to see — a closing number with no timestamp saying so. And
`odds_snapshots.spread` is NULL for every row before 2026 (the bulk pull only
started requesting `totals,spreads` together that season). So a model trained on
2023-25 has NO honest spread to read, while the spread is the primary driver of
the first-half share: implied share runs 0.498 -> 0.552 across spread buckets,
and the underdog's first-half shutout rate runs 8.8% -> 37.6%.

Measured on 2026, the only season with per-snapshot spreads: a game's spread
moves a median 1.5 points over its snapshot history, 3.0 at the 90th percentile,
and only 4 of 142 games never moved. Reading the stored spread while pretending
to price a game earlier in the week is not a rounding error.

An OPENING line, by contrast, is a historical fact. It never moves, so it is a
legitimate as-of feature at the earliest decision point — and CFBD has been
serving it as `spreadOpen` all along.

Surgical by design: UPDATEs `spread_open` / `spread_open_source` and nothing
else — never the PBP-derived first-half truth, never the mutable `spread`.

IDEMPOTENT AND WRITE-ONCE. A non-NULL opener is left alone without --force,
because re-running must never churn a value the whole point of which is that it
does not change. That is the opposite of backfill_spread.py's rule, which
protects LIVE sources from CFBD; here CFBD is the only source there is.

    python scripts/backfill_spread_open.py --start 2023 --end 2025
    python scripts/backfill_spread_open.py --season 2024 --dry-run
    python scripts/backfill_spread_open.py --season 2024 --force

COST. One CFBD call per (season, season_type). CFBD has been out of monthly
quota since 2026-09-12 and resets ~Oct 1; cfbd.py raises CFBDQuotaExceeded on
the spot rather than spending the retry ladder, so running this early fails fast
and cheap.
"""

from __future__ import annotations

import argparse
from typing import Dict, Optional, Sequence, Tuple

from beatvegas.config import load_config
from beatvegas.db.models import Game
from beatvegas.db.store import init_db, session_scope
from beatvegas.line_sources import CFBD_SOURCE
from beatvegas.season import current_season
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.cfbd_lines import (
    DEFAULT_SEASON_TYPE,
    _get,
    _season_types,
    pick_spread_open,
)


def openers_for_season(
    client: CFBDClient, season: int, season_type: str
) -> Dict[int, Tuple[float, str]]:
    """{game_id: (opening_spread, provider)} for a season from CFBD /lines."""
    out: Dict[int, Tuple[float, str]] = {}
    for st in _season_types(season_type):
        for g in client.lines(year=season, season_type=st):
            gid = _get(g, "id")
            sp, prov = pick_spread_open(_get(g, "lines") or [])
            if gid is not None and sp is not None:
                out[int(gid)] = (sp, prov or CFBD_SOURCE)
    return out


def backfill_season(
    client: CFBDClient,
    season: int,
    season_type: str,
    force: bool = False,
    dry_run: bool = False,
) -> Tuple[int, int, int]:
    """(written, already_had_one, no_opener_offered) for `season`."""
    openers = openers_for_season(client, season, season_type)
    written = kept = 0
    with session_scope() as s:
        rows = s.query(Game).filter(Game.season == season).all()
        n_games = len(rows)
        for g in rows:
            hit = openers.get(g.id)
            if hit is None:
                continue
            if g.spread_open is not None and not force:
                kept += 1
                continue
            if not dry_run:
                g.spread_open = hit[0]
                g.spread_open_source = CFBD_SOURCE
            written += 1
        if dry_run:
            s.rollback()
    return written, kept, n_games - written - kept


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    cfg = load_config().get("backfill", {}) or {}
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, help="single season override")
    ap.add_argument("--start", type=int, default=cfg.get("start_season", 2015))
    ap.add_argument("--end", type=int, default=cfg.get("end_season") or current_season())
    ap.add_argument("--season-type", default=cfg.get("season_type", DEFAULT_SEASON_TYPE))
    ap.add_argument(
        "--force",
        action="store_true",
        help="overwrite an opener already on file (an opening line does not move; "
        "use only to repair a bad write)",
    )
    ap.add_argument("--dry-run", action="store_true", help="report counts, write nothing")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    init_db()
    client = CFBDClient()
    seasons = [args.season] if args.season else range(args.start, args.end + 1)
    for season in seasons:
        w, kept, none = backfill_season(
            client, season, args.season_type, force=args.force, dry_run=args.dry_run
        )
        verb = "would write" if args.dry_run else "wrote"
        print(
            f"{season}: {verb} {w} openers, kept {kept} already on file, {none} with none offered"
        )
    if client.calls_remaining is not None:
        print(f"CFBD calls remaining: {client.calls_remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
