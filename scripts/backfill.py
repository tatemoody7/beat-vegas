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
from beatvegas.etl.first_half import (
    attach_first_half,
    first_half_from_line_scores,
    first_half_from_plays,
    line_scores_trustworthy,
)
from beatvegas.line_sources import strip_protected_line_fields
from beatvegas.season import current_season
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


def _needs_pbp(g: Dict[str, Any]) -> bool:
    """A finished game whose line scores can't produce a trusted 1H total."""
    finished = (
        _get(g, "homePoints", "home_points") is not None
        or _get(g, "awayPoints", "away_points") is not None
    )
    if not finished:
        return False
    fh = first_half_from_line_scores(g)
    return fh is None or not line_scores_trustworthy(g, fh)


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

    # Play-by-play fallback. --use-pbp fetches every week; otherwise fetch ONLY
    # the weeks holding finished games whose line scores are missing or fail the
    # trust guard (e.g. a genuine 0-0 first half, which line_scores_trustworthy
    # must reject as a *linescore* but PBP can confirm as real). This keeps the
    # default run cheap while never leaving a resolvable game NULL.
    pbp_lookup: Dict[int, Any] = {}
    if use_pbp:
        weeks = sorted({_get(g, "week") for g in games if _get(g, "week") is not None})
    else:
        weeks = sorted({_get(g, "week") for g in games if _needs_pbp(g)} - {None})
    for wk in weeks:
        try:
            pbp_lookup.update(
                first_half_from_plays(client.plays(year=season, week=wk, season_type=season_type))
            )
        except Exception as e:  # noqa: BLE001 - log and continue
            print(f"  [warn] plays {season} wk{wk}: {e}")

    game_rows, team_rows = [], {}
    n_with_1h = 0
    for g in games:
        gid = _get(g, "id")
        fh = attach_first_half(g, pbp_lookup or None)
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

    cfbd_with_total = sum(1 for r in game_rows if r["full_game_total"] is not None)
    with session_scope() as s:
        # The Sunday/card-day capture (Odds API / DK) owns the total + spread it
        # wrote; CFBD's consensus number must not overwrite it every Monday.
        sources = {
            gid: (fg_src, sp_src)
            for gid, fg_src, sp_src in s.query(
                Game.id, Game.full_game_total_source, Game.spread_source
            ).filter(Game.season == season)
        }
        game_rows = [
            strip_protected_line_fields(r, *sources.get(r["id"], (None, None))) for r in game_rows
        ]
        upsert(s, Game, game_rows, "id")
        upsert(s, Team, list(team_rows.values()), "id")

    return {
        "games": len(game_rows),
        "with_1h": n_with_1h,
        "cfbd_with_total": cfbd_with_total,
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
    ap.add_argument("--end", type=int, default=cfg.get("end_season") or current_season())
    ap.add_argument("--season-type", default=cfg.get("season_type", "both"))
    ap.add_argument(
        "--use-pbp", action="store_true", help="fill first-half gaps via play-by-play (slower)"
    )
    args = ap.parse_args()

    init_db()
    client = CFBDClient()

    print(f"venues: {backfill_venues(client)} loaded")
    seasons = [args.season] if args.season else range(args.start, args.end + 1)
    # "both" iterates the two types separately: postseason week numbers restart
    # at 1, so the per-week /plays fetches must never mix types in one pass.
    season_types = ["regular", "postseason"] if args.season_type == "both" else [args.season_type]
    for season in seasons:
        for st in season_types:
            stats = backfill_season(client, season, st, args.use_pbp)
            print(
                f"{season} {st}: {stats['games']} games, {stats['with_1h']} with 1H, "
                f"{stats['cfbd_with_total']} with a CFBD-supplied full-game total"
            )


if __name__ == "__main__":
    main()
