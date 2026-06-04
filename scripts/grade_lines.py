#!/usr/bin/env python
"""Run the posted full-game lines through our derived-1H pricing — READ ONLY.

For each posted game it prints the full-game total, the spread, and OUR
spread-adjusted derived 1H total (via proxy_line.proxy_total + the adopted
multiplier). This is a deterministic derivation of the posted line — NOT a model
pick, NOT a graded result, and it writes nothing to the DB.

    python scripts/grade_lines.py --season 2026 --week 1
    python scripts/grade_lines.py --source cfbd        # all posted upcoming games
"""

from __future__ import annotations

import argparse
from typing import Dict, List

from beatvegas.db.models import Game
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import match_event
from beatvegas.etl.proxy_line import fh_share, proxy_total
from beatvegas.season import current_season
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.cfbd_lines import full_game_rows as cfbd_full_game_rows
from beatvegas.sources.draftkings import DraftKingsClient, normalize_full_game


def _fetch(source: str, season: int):
    """(rows, source_used). Mirrors poll_full_game._fetch (DK → CFBD fallback)."""
    if source in ("dk", "auto"):
        rows = normalize_full_game(DraftKingsClient().fetch_ncaaf())
        if rows or source == "dk":
            return rows, "dk"
    return cfbd_full_game_rows(CFBDClient(), season), "cfbd"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int, help="filter to one week (e.g. 1)")
    ap.add_argument("--source", choices=("dk", "cfbd", "auto"), default="auto")
    args = ap.parse_args()

    if not try_init_db():
        return

    rows, source = _fetch(args.source, args.season)

    with session_scope() as s:
        gmeta: Dict[int, Dict] = {
            g.id: {"week": g.week, "home": g.home_team, "away": g.away_team}
            for g in s.query(Game).filter(Game.season == args.season).all()
        }
        games = [
            {"id": gid, "home_team": m["home"], "away_team": m["away"], "start_date": None}
            for gid, m in gmeta.items()
        ]

        out: List[Dict] = []
        for r in rows:
            gid = r.get("game_id")
            if gid is None:
                gid, _ = match_event(r["home_team"], r["away_team"], r["commence_time"], games)
            meta = gmeta.get(gid)
            week = meta["week"] if meta else None
            if args.week is not None and week != args.week:
                continue
            total, spread = r["line"], r.get("spread")
            out.append(
                {
                    "week": week,
                    "away": (meta["away"] if meta else r.get("away_team")),
                    "home": (meta["home"] if meta else r.get("home_team")),
                    "total": total,
                    "spread": spread,
                    "derived_1h": proxy_total(total, spread=spread),
                    "share": fh_share(spread),
                }
            )

    out.sort(key=lambda x: (x["week"] is None, x["week"] or 0, f"{x['away']} @ {x['home']}"))

    scope = f"wk{args.week}" if args.week is not None else "all upcoming"
    print(
        f"source={source} season={args.season} {scope} — {len(out)} games "
        f"(derived 1H from posted line; not a pick, not graded)\n"
    )
    print(f"{'wk':>3}  {'matchup':42}  {'FG tot':>6}  {'spread':>6}  {'1H':>5}  {'share':>5}")
    print("-" * 80)
    for r in out:
        wk = "" if r["week"] is None else str(r["week"])
        sp = "" if r["spread"] is None else f"{r['spread']:+.1f}"
        matchup = f"{r['away']} @ {r['home']}"
        print(
            f"{wk:>3}  {matchup:42.42}  {r['total']:>6.1f}  {sp:>6}  "
            f"{r['derived_1h']:>5.1f}  {r['share']:>5.3f}"
        )


if __name__ == "__main__":
    main()
