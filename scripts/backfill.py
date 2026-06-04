#!/usr/bin/env python
"""One-time historical load: games, first-half points, full-game totals, venues.

Idempotent (upserts by id) so it's safe to re-run. Requires a CFBD key
(config.yaml cfbd.api_key or CFBD_API_KEY env).

Usage:
    python scripts/backfill.py                 # uses config backfill range
    python scripts/backfill.py --season 2023   # single season
    python scripts/backfill.py --use-pbp       # fill 1H gaps via play-by-play
"""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any, Dict, Optional

from beatvegas.config import load_config
from beatvegas.db.models import Game, Team, Venue
from beatvegas.db.store import init_db, session_scope, upsert
from beatvegas.etl.first_half import attach_first_half, first_half_from_plays
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.cfbd_lines import pick_total_spread as _pick_total


def _get(d: Dict[str, Any], *names: str) -> Any:
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def backfill_season(
    client: CFBDClient, season: int, season_type: str, use_pbp: bool
) -> Dict[str, int]:
    games = client.games(year=season, season_type=season_type)
    lines_resp = client.lines(year=season, season_type=season_type)
    total_by_game = {}
    for g in lines_resp:
        gid = _get(g, "id")
        ou, sp, prov = _pick_total(_get(g, "lines") or [])
        if gid is not None and ou is not None:
            total_by_game[gid] = (ou, sp, prov)

    # Optional play-by-play fallback, fetched per week only if needed.
    pbp_lookup: Dict[int, Any] = {}
    if use_pbp:
        weeks = sorted({_get(g, "week") for g in games if _get(g, "week") is not None})
        for wk in weeks:
            try:
                pbp_lookup.update(
                    first_half_from_plays(
                        client.plays(year=season, week=wk, season_type=season_type)
                    )
                )
            except Exception as e:  # noqa: BLE001 - log and continue
                print(f"  [warn] plays {season} wk{wk}: {e}")

    game_rows, team_rows = [], {}
    n_with_1h = 0
    for g in games:
        gid = _get(g, "id")
        fh = attach_first_half(g, pbp_lookup if use_pbp else None)
        if fh["first_half_total"] is not None:
            n_with_1h += 1
        ou, sp, prov = total_by_game.get(gid, (None, None, None))
        row = {
            "id": gid,
            "season": _get(g, "season") or season,
            "week": _get(g, "week"),
            "season_type": _get(g, "seasonType", "season_type"),
            "start_date": _parse_dt(_get(g, "startDate", "start_date")),
            "neutral_site": _get(g, "neutralSite", "neutral_site"),
            "venue_id": _get(g, "venueId", "venue_id"),
            "home_team": _get(g, "homeTeam", "home_team"),
            "away_team": _get(g, "awayTeam", "away_team"),
            "home_team_id": _get(g, "homeId", "home_id"),
            "away_team_id": _get(g, "awayId", "away_id"),
            "home_points": _get(g, "homePoints", "home_points"),
            "away_points": _get(g, "awayPoints", "away_points"),
            "full_game_total": ou,
            "full_game_total_book": prov,
            "spread": sp,
        }
        row.update(fh)
        game_rows.append(row)

        for tid, name, conf in [
            (row["home_team_id"], row["home_team"], _get(g, "homeConference", "home_conference")),
            (row["away_team_id"], row["away_team"], _get(g, "awayConference", "away_conference")),
        ]:
            if tid is not None and tid not in team_rows:
                team_rows[tid] = {"id": tid, "school": name, "conference": conf}

    with session_scope() as s:
        upsert(s, Game, game_rows, "id")
        upsert(s, Team, list(team_rows.values()), "id")

    return {
        "games": len(game_rows),
        "with_1h": n_with_1h,
        "with_total": sum(1 for r in game_rows if r["full_game_total"] is not None),
    }


def backfill_venues(client: CFBDClient) -> int:
    rows = []
    for v in client.venues():
        loc = _get(v, "location") or {}
        rows.append(
            {
                "id": _get(v, "id"),
                "name": _get(v, "name"),
                "city": _get(v, "city"),
                "state": _get(v, "state"),
                "latitude": _get(v, "latitude") or _get(loc, "x"),
                "longitude": _get(v, "longitude") or _get(loc, "y"),
                "dome": _get(v, "dome"),
            }
        )
    rows = [r for r in rows if r["id"] is not None]
    with session_scope() as s:
        upsert(s, Venue, rows, "id")
    return len(rows)


def main() -> None:
    cfg = load_config().get("backfill", {}) or {}
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, help="single season override")
    ap.add_argument("--start", type=int, default=cfg.get("start_season", 2015))
    ap.add_argument("--end", type=int, default=cfg.get("end_season", 2024))
    ap.add_argument("--season-type", default=cfg.get("season_type", "regular"))
    ap.add_argument(
        "--use-pbp", action="store_true", help="fill first-half gaps via play-by-play (slower)"
    )
    args = ap.parse_args()

    init_db()
    client = CFBDClient()

    print(f"venues: {backfill_venues(client)} loaded")
    seasons = [args.season] if args.season else range(args.start, args.end + 1)
    for season in seasons:
        stats = backfill_season(client, season, args.season_type, args.use_pbp)
        print(
            f"{season}: {stats['games']} games, {stats['with_1h']} with 1H, "
            f"{stats['with_total']} with full-game total"
        )


if __name__ == "__main__":
    main()
