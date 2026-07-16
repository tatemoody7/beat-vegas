#!/usr/bin/env python
"""Surgically repair false-zero first_half_total rows (the ~44-game corruption).

Placeholder CFBD line scores (all-zero quarters on a game that really scored)
were summed to a false 1H total of 0 before etl/first_half.py grew its
trustworthiness guard. This script finds every stored `first_half_total = 0`
whose final score is > 0, re-derives the first half through the FIXED ETL
(line scores, then optional play-by-play fallback), and updates only the four
first-half columns. Untrusted rows become NULL — never a false 0 — so grading
skips them instead of fabricating an under win.

Idempotent and surgical (like backfill_spread.py): touches only the bad rows.

    python scripts/repair_first_half.py                # line scores only
    python scripts/repair_first_half.py --use-pbp      # + PBP fallback
    python scripts/repair_first_half.py --dry-run
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, Tuple

from beatvegas.db.models import Game
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.first_half import attach_first_half, first_half_from_plays
from beatvegas.sources.cfbd import CFBDClient

_FH_COLS = (
    "home_first_half_points",
    "away_first_half_points",
    "first_half_total",
    "first_half_source",
)


def _bad_games(session):
    """Games needing repair: the false-zero corruption (1H total 0 on a game
    that really scored) plus finished games whose 1H is NULL (recoverable via
    trusted line scores or the play-by-play fallback)."""
    from sqlalchemy import and_, or_

    return (
        session.query(Game)
        .filter(
            or_(
                and_(
                    Game.first_half_total == 0,
                    (Game.home_points + Game.away_points) > 0,
                ),
                and_(
                    Game.first_half_total.is_(None),
                    Game.home_points.isnot(None),
                    Game.away_points.isnot(None),
                ),
            )
        )
        .order_by(Game.season, Game.week)
        .all()
    )


def repair(use_pbp: bool, dry_run: bool) -> None:
    client = CFBDClient()
    with session_scope() as s:
        bad = _bad_games(s)
        if not bad:
            print("no false-zero first_half_total rows found — nothing to repair")
            return
        print(f"found {len(bad)} false-zero games")

        # One CFBD /games call per affected (season, season_type); PBP per
        # affected (season, week) only when requested.
        season_types = {(g.season, g.season_type or "regular") for g in bad}
        cfbd_by_id: Dict[int, Dict[str, Any]] = {}
        for season, stype in sorted(season_types):
            for cg in client.games(year=season, season_type=stype):
                gid = cg.get("id")
                if gid is not None:
                    cfbd_by_id[gid] = cg

        pbp_lookup: Dict[int, Tuple[int, int]] = {}
        if use_pbp:
            weeks = {(g.season, g.season_type or "regular", g.week) for g in bad if g.week}
            for season, stype, wk in sorted(weeks):
                try:
                    pbp_lookup.update(
                        first_half_from_plays(
                            client.plays(year=season, week=wk, season_type=stype)
                        )
                    )
                except Exception as e:  # noqa: BLE001 - log and continue
                    print(f"  [warn] plays {season} wk{wk}: {e}")

        fixed = nulled = missing = 0
        for g in bad:
            old = g.first_half_total
            cg = cfbd_by_id.get(g.id)
            if cg is None:
                print(f"  {g.season} wk{g.week} {g.away_team} @ {g.home_team}: not in CFBD — left as is")
                missing += 1
                continue
            fh = attach_first_half(cg, pbp_lookup if use_pbp else None)
            new_total = fh["first_half_total"]
            if new_total is None and old is None:
                continue  # still unrecoverable; nothing to change or report
            label = "→ NULL (untrusted)" if new_total is None else f"→ {new_total} ({fh['first_half_source']})"
            print(f"  {g.season} wk{g.week} {g.away_team} @ {g.home_team}: {old} {label}")
            if not dry_run:
                for col in _FH_COLS:
                    setattr(g, col, fh[col])
            if new_total is None:
                nulled += 1
            else:
                fixed += 1

        verb = "would repair" if dry_run else "repaired"
        print(f"{verb} {fixed + nulled}/{len(bad)}: {fixed} real totals, {nulled} nulled, {missing} missing")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--use-pbp", action="store_true", help="fill gaps via play-by-play (slower)")
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    args = ap.parse_args()
    if not try_init_db():
        return
    repair(args.use_pbp, args.dry_run)


if __name__ == "__main__":
    main()
