#!/usr/bin/env python
"""Backfill REAL first-half closing lines from The Odds API HISTORICAL endpoint.

Replaces the 0.52*full-game proxy with the true 1H number that books posted —
the dataset the backtest needs to stop being proxy-graded (research doc Stage 1).

This is the EXPENSIVE phase: the historical per-event totals_h1 endpoint costs
(markets x regions) credits per call, at a higher historical multiplier. So it is
gated hard — you pick the season + week(s) + a game cap, and it is idempotent
(games that already carry a 1H_total snapshot are skipped). Always dry-run first.

    python scripts/backfill_1h_history.py --season 2024 --week 8 --dry-run
    python scripts/backfill_1h_history.py --season 2024 --week 8 --limit 20

For each in-scope game it pulls ONE near-kickoff snapshot (kickoff - lead minutes)
and stores it as the closing 1H line per book. closing_before_kickoff then treats
it as the close for grading/CLV.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from beatvegas.config import load_config
from beatvegas.db.models import Game, OddsSnapshot, Prediction
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.fbs import FbsMap, load_fbs_teams
from beatvegas.etl.match import match_event
from beatvegas.hardrock import normalize_book
from beatvegas.season import current_season
from beatvegas.sources.odds import OddsAPIClient, normalize_first_half


def target_snapshot_ts(start_date: datetime, lead_min: int) -> datetime:
    """The near-kickoff timestamp we probe as the 1H 'close' (kickoff - lead)."""
    return start_date - timedelta(minutes=lead_min)


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def events_snapshot_ts(target_ts: datetime) -> datetime:
    """The events-list snapshot to use for a game: the start of its UTC day. A
    snapshot lists every event commencing after it, so one call per day covers
    that day's games instead of one per distinct kickoff (10 credits each)."""
    return target_ts.replace(hour=0, minute=0, second=0, microsecond=0)


def games_needing_backfill(
    session,
    season: int,
    week: Optional[int],
    limit: int,
    fbs: Optional[FbsMap] = None,
    rated_only: Optional[str] = None,
) -> List[Dict]:
    """In-scope games with NO 1H_total snapshot yet (idempotent), with a kickoff.
    `fbs` keeps only games where both teams were FBS that season; `rated_only`
    keeps only games that carry a prediction of that model_version (the games a
    real-line regrade can actually use)."""
    rated = None
    if rated_only:
        rated = {
            gid
            for (gid,) in session.query(Prediction.game_id)
            .filter(Prediction.model_version == rated_only)
            .distinct()
        }
    have = {
        gid
        for (gid,) in session.query(OddsSnapshot.game_id)
        .filter(OddsSnapshot.market == "1H_total")
        .distinct()
    }
    q = session.query(Game.id, Game.home_team, Game.away_team, Game.start_date, Game.week).filter(
        Game.season == season, Game.start_date.isnot(None)
    )
    if week is not None:
        q = q.filter(Game.week == week)
    teams = fbs.get(int(season)) if fbs is not None else None
    games = [
        {"id": r[0], "home_team": r[1], "away_team": r[2], "start_date": r[3], "week": r[4]}
        for r in q.all()
        if r[0] not in have
        and (teams is None or (r[1] in teams and r[2] in teams))
        and (rated is None or r[0] in rated)
    ]
    games.sort(key=lambda g: (g["start_date"], g["id"]))
    return games[:limit] if limit else games


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int, default=None, help="restrict to one week (recommended)")
    ap.add_argument("--limit", type=int, default=20, help="max games per run (credit cap); 0 = all")
    ap.add_argument(
        "--lead-min",
        type=int,
        default=30,
        help="minutes before kickoff to snapshot as the 1H close",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="list the games + target timestamps WITHOUT spending any credits",
    )
    ap.add_argument(
        "--fbs-only",
        action="store_true",
        help="only games where both teams were FBS that season (data/fbs_teams.json)",
    )
    ap.add_argument(
        "--rated-only",
        default=None,
        metavar="MODEL_VERSION",
        help="only games carrying a prediction of this model_version (e.g. gbm_v1)",
    )
    ap.add_argument(
        "--regions",
        default="us",
        help="Odds API regions for the historical pull (cost is 10 credits per region "
        "per market per event; Hard Rock did not exist historically, so 'us' is enough)",
    )
    ap.add_argument(
        "--max-credits",
        type=int,
        default=0,
        help="stop once this many credits have been spent in this run (0 = no cap)",
    )
    ap.add_argument(
        "--credit-floor",
        type=int,
        default=200,
        help="stop once the account's remaining credits hit this floor",
    )
    args = ap.parse_args()

    if not try_init_db():
        return
    cfg = load_config().get("odds_api", {}) or {}
    books = cfg.get("books") or None
    fbs = load_fbs_teams() if args.fbs_only else None

    with session_scope() as s:
        scope = games_needing_backfill(
            s, args.season, args.week, args.limit, fbs=fbs, rated_only=args.rated_only
        )

    print(
        f"[backfill] season={args.season} week={args.week} "
        f"games_needing={len(scope)} lead_min={args.lead_min}"
    )
    if args.dry_run:
        for g in scope[:30]:
            ts = target_snapshot_ts(g["start_date"], args.lead_min)
            print(f"  would pull {g['away_team']} @ {g['home_team']}  @ {_iso_z(ts)}")
        if len(scope) > 30:
            print(f"  ... and {len(scope) - 30} more")
        days = {
            events_snapshot_ts(target_snapshot_ts(g["start_date"], args.lead_min)) for g in scope
        }
        n_regions = len([r for r in args.regions.split(",") if r.strip()])
        est = 10 * n_regions * len(scope) + 10 * len(days)
        print(
            f"[backfill] estimate: {len(scope)} event calls x {10 * n_regions} + "
            f"{len(days)} events-list calls x 10 ≈ {est} credits"
        )
        print("[backfill] DRY RUN — no credits spent.")
        return
    if not scope:
        print("[backfill] nothing to do.")
        return

    client = OddsAPIClient()
    client.regions = args.regions
    events_cache: Dict[str, List[Dict]] = {}
    written = matched = missing = 0
    spent = 0
    stopped = None

    def _spend(c) -> None:
        nonlocal spent
        if c is not None and c.last_cost is not None:
            spent += c.last_cost

    for i, g in enumerate(scope, 1):
        if args.max_credits and spent >= args.max_credits:
            stopped = f"run budget of {args.max_credits} credits reached"
            break
        if client.credits_low(args.credit_floor):
            stopped = f"account floor of {args.credit_floor} credits reached"
            break
        ts = target_snapshot_ts(g["start_date"], args.lead_min)
        ts_iso = _iso_z(ts)
        # One events-list call per UTC day (cached); it lists every later kickoff.
        day_iso = _iso_z(events_snapshot_ts(ts))
        if day_iso not in events_cache:
            events_cache[day_iso] = client.list_historical_events(day_iso)
            _spend(client.last_credits)
        event_id, _score = _match_game_to_event(g, events_cache[day_iso])
        if event_id is None:
            missing += 1
            continue
        data = client.historical_event_first_half_totals(event_id, ts_iso)
        _spend(client.last_credits)
        if i % 50 == 0:
            c = client.last_credits
            print(
                f"[backfill] {i}/{len(scope)} matched={matched} missing={missing} "
                f"spent={spent} remaining={c.remaining if c else '?'}",
                flush=True,
            )
        rows = normalize_first_half([data], books=books) if data else []
        if not rows:
            missing += 1
            continue
        matched += 1
        with session_scope() as s:
            for r in rows:
                s.add(
                    OddsSnapshot(
                        game_id=g["id"],
                        book=normalize_book(r["book"]),
                        market="1H_total",
                        line=r["line"],
                        over_price=r["over_price"],
                        under_price=r["under_price"],
                        captured_at=ts,
                    )
                )
                written += 1

    c = client.last_credits
    if stopped:
        print(f"[backfill] stopped early: {stopped}")
    print(
        f"[backfill] games={len(scope)} matched={matched} missing={missing} "
        f"snapshots_written={written} credits_spent={spent}"
    )
    if c:
        print(f"[backfill] credits: remaining={c.remaining} used={c.used} last_cost={c.last_cost}")


def _match_game_to_event(game: Dict, events: List[Dict]):
    """Find the historical event that matches one CFBD game (id, teams, kickoff)."""
    for ev in events:
        gid, score = match_event(
            ev.get("home_team"), ev.get("away_team"), ev.get("commence_time"), [game]
        )
        if gid == game["id"]:
            return ev.get("id"), score
    return None, 0.0


if __name__ == "__main__":
    main()
