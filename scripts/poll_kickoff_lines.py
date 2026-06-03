#!/usr/bin/env python
"""Poll 1H totals for games kicking off SOON, so the closing line is fresh.

The daily poll (poll_lines.py) runs once at ~8am UTC, so "closing" lines can be
hours stale by kickoff — and CLV is the project's verdict metric. This light
script polls ONLY games kicking off in the next ~2h and appends a snapshot, so
the last-observed line per book is genuinely near kickoff. Run it every ~30 min
during the season (deploy/com.beatvegas.kickoff.plist).

    python scripts/poll_kickoff_lines.py
    python scripts/poll_kickoff_lines.py --within-minutes 150 --dry-run
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from typing import Dict, List

from beatvegas.config import load_config
from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import init_db, session_scope
from beatvegas.etl.match import _parse_dt, match_event
from beatvegas.season import current_season
from beatvegas.sources.odds import OddsAPIClient, normalize_first_half


def _changed(prev, line, over, under) -> bool:
    if prev is None:
        return True
    return prev.line != line or prev.over_price != over or prev.under_price != under


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--within-minutes", type=int, default=120,
                    help="only poll games kicking off within this many minutes")
    ap.add_argument("--grace-minutes", type=int, default=20,
                    help="also include games that just started (clock not yet at half)")
    ap.add_argument("--max-events", type=int, default=30,
                    help="hard cap on per-event odds calls (credit safety)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be polled; make no odds calls / writes")
    args = ap.parse_args()
    init_db()
    cfg = load_config().get("odds_api", {}) or {}

    now = datetime.utcnow()
    window_end = now + timedelta(minutes=args.within_minutes)
    window_start = now - timedelta(minutes=args.grace_minutes)

    with session_scope() as s:
        games = [{"id": r[0], "home_team": r[1], "away_team": r[2], "start_date": r[3]}
                 for r in s.query(Game.id, Game.home_team, Game.away_team,
                                  Game.start_date).filter(Game.season == args.season).all()]
        near = [g for g in games if g["start_date"] is not None
                and window_start <= g["start_date"] <= window_end]

    print(f"near-kickoff games in next {args.within_minutes}m: {len(near)}")
    if not near:
        print("nothing to poll")
        return
    if args.dry_run:
        for g in near[:args.max_events]:
            print(f"  would poll: {g['away_team']} @ {g['home_team']} "
                  f"({g['start_date']})")
        return

    client = OddsAPIClient()
    # Free listing, then keep only events matching our near-kickoff window.
    all_events = client.list_events()
    near_events = []
    for ev in all_events:
        dt = _parse_dt(ev.get("commence_time"))
        if dt is not None and window_start <= dt <= window_end:
            near_events.append(ev)
    near_events = near_events[: args.max_events]

    rows = []
    for ev in near_events:
        data = client.event_first_half_totals(ev["id"])
        if data:
            rows.extend(normalize_first_half([data], books=cfg.get("books") or None))

    written = matched = skipped = 0
    with session_scope() as s:
        games = [{"id": r[0], "home_team": r[1], "away_team": r[2], "start_date": r[3]}
                 for r in s.query(Game.id, Game.home_team, Game.away_team,
                                  Game.start_date).filter(Game.season == args.season).all()]
        for r in rows:
            gid, _ = match_event(r["home_team"], r["away_team"],
                                 r["commence_time"], games)
            if gid is None:
                continue
            matched += 1
            prev = (s.query(OddsSnapshot)
                    .filter(OddsSnapshot.game_id == gid, OddsSnapshot.book == r["book"],
                            OddsSnapshot.market == "1H_total")
                    .order_by(OddsSnapshot.captured_at.desc()).first())
            if not _changed(prev, r["line"], r["over_price"], r["under_price"]):
                skipped += 1
                continue
            s.add(OddsSnapshot(
                game_id=gid, book=r["book"], market="1H_total", line=r["line"],
                over_price=r["over_price"], under_price=r["under_price"], captured_at=now))
            written += 1

    c = client.last_credits
    print(f"near_events={len(near_events)} odds_rows={len(rows)} matched={matched} "
          f"new_snapshots={written} unchanged={skipped}")
    if c:
        print(f"credits: remaining={c.remaining} used={c.used} last_cost={c.last_cost}")


if __name__ == "__main__":
    main()
