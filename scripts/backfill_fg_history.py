#!/usr/bin/env python
"""Backfill REAL full-game closing totals from The Odds API HISTORICAL bulk endpoint.

Why: the 2023-25 post-mortem grades the first-half picks against real 1H closes,
but the same picks' FULL-GAME outcome was only ever graded against the Sunday
opener. This pulls the pre-kick full-game consensus so the two markets can be
compared apples to apples (decided 2026-09-07, ~5,500 credits for the true close).

How: games are grouped into KICKOFF WAVES — the hour bucket of (kickoff - 30 min)
— and ONE bulk historical /odds call is made per wave (10 credits x regions,
whatever the slate size). The response lists every event commencing after that
timestamp, so a wave's snapshot is matched to every in-scope game kicking off
from that hour on that day and written as a `full_game_total` snapshot per book
at captured_at = the wave time. A game is done once it has a full-game snapshot
within 3 hours before kickoff (idempotent; re-runs skip it).

    python scripts/backfill_fg_history.py --season 2024 --fbs-only --rated-only gbm_v1 --dry-run
    python scripts/backfill_fg_history.py --season 2024 --fbs-only --rated-only gbm_v1 --max-credits 2000
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy import and_

from beatvegas.config import load_config
from beatvegas.db.models import Game, OddsSnapshot, Prediction
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.fbs import FbsMap, load_fbs_teams
from beatvegas.etl.match import match_event
from beatvegas.hardrock import normalize_book
from beatvegas.season import current_season
from beatvegas.sources.odds import OddsAPIClient, normalize_full_game

LEAD_MIN = 30
DONE_WITHIN_HOURS = 3.0  # a full-game snapshot this close to kickoff counts as the close


def wave_ts(start_date: datetime, lead_min: int = LEAD_MIN) -> datetime:
    """The bulk-snapshot timestamp for a game: the hour bucket of kickoff - lead."""
    t = start_date - timedelta(minutes=lead_min)
    return t.replace(minute=0, second=0, microsecond=0)


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def games_needing_fg_close(
    session,
    season: int,
    week: Optional[int] = None,
    limit: int = 0,
    fbs: Optional[FbsMap] = None,
    rated_only: Optional[str] = None,
    done_within_hours: float = DONE_WITHIN_HOURS,
) -> List[Dict]:
    """In-scope games with a kickoff and NO full-game snapshot captured within
    `done_within_hours` before it. Optional FBS-vs-FBS and rated-only filters
    mirror backfill_1h_history."""
    q = session.query(Game.id, Game.home_team, Game.away_team, Game.start_date, Game.week).filter(
        Game.season == season, Game.start_date.isnot(None)
    )
    if week is not None:
        q = q.filter(Game.week == week)
    if rated_only:
        rated_ids = {
            r[0]
            for r in session.query(Prediction.game_id)
            .filter(Prediction.model_version == rated_only)
            .distinct()
            .all()
        }
        q = q.filter(Game.id.in_(rated_ids)) if rated_ids else q.filter(False)
    rows = q.all()
    have: Set[int] = set()
    ids = [r[0] for r in rows]
    kick = {r[0]: r[3] for r in rows}
    for i in range(0, len(ids), 1000):
        for gid, cap in (
            session.query(OddsSnapshot.game_id, OddsSnapshot.captured_at)
            .filter(
                and_(
                    OddsSnapshot.market == "full_game_total",
                    OddsSnapshot.game_id.in_(ids[i : i + 1000]),
                )
            )
            .all()
        ):
            k = kick.get(gid)
            if (
                cap is not None
                and k is not None
                and 0 <= (k - cap).total_seconds() <= done_within_hours * 3600
            ):
                have.add(gid)
    games = [
        {"id": r[0], "home_team": r[1], "away_team": r[2], "start_date": r[3], "week": r[4]}
        for r in rows
        if r[0] not in have
    ]
    if fbs is not None:
        teams = fbs.get(int(season)) or set()
        games = [g for g in games if g["home_team"] in teams and g["away_team"] in teams]
    games.sort(key=lambda g: (g["start_date"], g["id"]))
    return games[:limit] if limit else games


def group_by_wave(games: List[Dict], lead_min: int = LEAD_MIN) -> Dict[datetime, List[Dict]]:
    """wave timestamp -> games in that wave (sorted by wave)."""
    waves: Dict[datetime, List[Dict]] = defaultdict(list)
    for g in games:
        waves[wave_ts(g["start_date"], lead_min)].append(g)
    return dict(sorted(waves.items()))


def match_events_to_games(events: List[Dict], games: List[Dict]) -> Dict[str, int]:
    """event id -> game id for the events that match one of `games`."""
    out: Dict[str, int] = {}
    for ev in events:
        gid, _score = match_event(
            ev.get("home_team"), ev.get("away_team"), ev.get("commence_time"), games
        )
        if gid is not None:
            out[ev["id"]] = gid
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0, help="max games (0 = all in scope)")
    ap.add_argument("--dry-run", action="store_true", help="list waves + estimate; spend nothing")
    ap.add_argument("--fbs-only", action="store_true")
    ap.add_argument("--rated-only", default=None, metavar="MODEL_VERSION")
    ap.add_argument("--regions", default="us", help="10 credits per region per wave")
    ap.add_argument("--max-credits", type=int, default=0, help="stop after spending N (0 = no cap)")
    ap.add_argument("--credit-floor", type=int, default=2000, help="stop at this account balance")
    args = ap.parse_args()

    if not try_init_db():
        return
    cfg = load_config().get("odds_api", {}) or {}
    books = cfg.get("books") or None
    fbs = load_fbs_teams() if args.fbs_only else None
    with session_scope() as s:
        scope = games_needing_fg_close(
            s, args.season, args.week, args.limit, fbs=fbs, rated_only=args.rated_only
        )
    waves = group_by_wave(scope)
    n_regions = len([r for r in args.regions.split(",") if r.strip()])
    est = 10 * n_regions * len(waves)
    print(
        f"[fg-backfill] season={args.season} week={args.week} games_needing={len(scope)} "
        f"waves={len(waves)} estimate≈{est} credits"
    )
    if args.dry_run:
        for ts, gs in list(waves.items())[:20]:
            print(f"  {_iso_z(ts)}: {len(gs)} games")
        if len(waves) > 20:
            print(f"  ... and {len(waves) - 20} more waves")
        print("[fg-backfill] DRY RUN — no credits spent.")
        return
    if not waves:
        print("[fg-backfill] nothing to do.")
        return

    client = OddsAPIClient()
    written = matched = missing = spent = 0
    stopped = None
    for i, (ts, gs) in enumerate(waves.items(), 1):
        if args.max_credits and spent >= args.max_credits:
            stopped = f"run budget of {args.max_credits} credits reached"
            break
        if client.credits_low(args.credit_floor):
            stopped = f"account floor of {args.credit_floor} credits reached"
            break
        events = client.historical_bulk_totals(_iso_z(ts), regions=args.regions)
        c = client.last_credits
        if c is not None and c.last_cost is not None:
            spent += c.last_cost
        ev_to_game = match_events_to_games(events, gs)
        hit = set(ev_to_game.values())
        missing += len(gs) - len(hit)
        matched += len(hit)
        rows = normalize_full_game([ev for ev in events if ev.get("id") in ev_to_game], books=books)
        with session_scope() as s:
            for r in rows:
                gid = ev_to_game.get(r["event_id"])
                if gid is None:
                    continue
                s.add(
                    OddsSnapshot(
                        game_id=gid,
                        book=normalize_book(r["book"]),
                        market="full_game_total",
                        line=r["line"],
                        over_price=r["over_price"],
                        under_price=r["under_price"],
                        captured_at=ts,
                    )
                )
                written += 1
        if i % 25 == 0:
            print(
                f"[fg-backfill] {i}/{len(waves)} waves matched={matched} missing={missing} "
                f"spent={spent} remaining={c.remaining if c else '?'}",
                flush=True,
            )
    c = client.last_credits
    if stopped:
        print(f"[fg-backfill] stopped early: {stopped}")
    print(
        f"[fg-backfill] waves={len(waves)} games={len(scope)} matched={matched} missing={missing} "
        f"snapshots_written={written} credits_spent={spent}"
    )
    if c:
        print(
            f"[fg-backfill] credits: remaining={c.remaining} used={c.used} last_cost={c.last_cost}"
        )


if __name__ == "__main__":
    main()
