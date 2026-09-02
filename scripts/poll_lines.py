#!/usr/bin/env python
"""Poll The Odds API for current first-half totals and store snapshots.

Each run captures the current totals_h1 line per (game, book). New snapshots are
written only when the line/prices changed vs the last observation, so the table
becomes a compact movement history; the earliest row per game = posting time.

The window is ranked by bettability (beatvegas/sweep.py) before any paid call,
and the sweep stops at --credit-floor so the Sunday opener capture (sunday.yml)
keeps its budget. Runs from GitHub Actions (lines_watch.yml) Friday + Saturday.

    python scripts/poll_lines.py
    python scripts/poll_lines.py --season 2025
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from beatvegas.ci import warn
from beatvegas.config import load_config
from beatvegas.db.models import Game, OddsSnapshot, TeamTempo, Weather
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import _parse_dt, match_event
from beatvegas.hardrock import normalize_book
from beatvegas.season import current_season
from beatvegas.sources.odds import OddsAPIClient, normalize_first_half
from beatvegas.sweep import CLOSE_SPREAD, build_context, latest_pace_by_team, rank_events


def _candidate_games(session, season: int) -> List[Dict]:
    rows = (
        session.query(Game.id, Game.home_team, Game.away_team, Game.start_date, Game.spread)
        .filter(Game.season == season)
        .all()
    )
    return [
        {"id": r[0], "home_team": r[1], "away_team": r[2], "start_date": r[3], "spread": r[4]}
        for r in rows
    ]


def _latest_snapshot(session, game_id: int, book: str):
    return (
        session.query(OddsSnapshot)
        .filter(
            OddsSnapshot.game_id == game_id,
            OddsSnapshot.book == book,
            OddsSnapshot.market == "1H_total",
        )
        .order_by(OddsSnapshot.captured_at.desc())
        .first()
    )


def _changed(prev, line, over, under) -> bool:
    if prev is None:
        return True
    return prev.line != line or prev.over_price != over or prev.under_price != under


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument(
        "--days-ahead",
        type=int,
        default=8,
        help="only pull odds for events kicking off within N days "
        "(conserves credits; 1H totals only post game-week)",
    )
    ap.add_argument(
        "--max-events",
        type=int,
        default=80,
        help="hard cap on per-event odds calls (credit safety)",
    )
    ap.add_argument(
        "--hours-back",
        type=float,
        default=24.0,
        help="window lower bound: include events that kicked off up to N hours "
        "ago (0 = upcoming games only, so closing-line runs don't spend the "
        "event cap on in-play games)",
    )
    ap.add_argument(
        "--credit-floor",
        type=int,
        default=60,
        help="stop per-event odds calls once remaining monthly credits hit this "
        "floor (reserves budget for the Sunday opener capture); 0 disables",
    )
    args = ap.parse_args()

    if not try_init_db():
        return
    cfg = load_config().get("odds_api", {}) or {}
    client = OddsAPIClient()

    # 1) Free: list events, then keep only those in the upcoming window.
    now = datetime.utcnow()
    horizon = now + timedelta(days=args.days_ahead)
    all_events = client.list_events()
    in_window = []
    for ev in all_events:
        dt = _parse_dt(ev.get("commence_time"))
        if dt is None or now - timedelta(hours=args.hours_back) <= dt <= horizon:
            in_window.append(ev)
    # Rank the window by bettability BEFORE spending credits. A plain [:max]
    # took the earliest kickoffs (Friday night + the Saturday noon wave), so the
    # evening games the card wants were never swept on the free-tier cap.
    with session_scope() as s:
        slate = _candidate_games(s, args.season)
        dome_by_game = dict(
            s.query(Weather.game_id, Weather.dome)
            .join(Game, Game.id == Weather.game_id)
            .filter(Game.season == args.season)
            .all()
        )
        pace_by_team = latest_pace_by_team(
            s.query(
                TeamTempo.season, TeamTempo.week, TeamTempo.team, TeamTempo.seconds_per_play
            ).all()
        )
    ctx = build_context(in_window, slate, dome_by_game, pace_by_team)
    n_window = len(in_window)
    in_window = rank_events(in_window, ctx, args.max_events)
    n_close = sum(
        1
        for e in in_window
        if (c := ctx.get(e["id"])) and c["spread"] is not None and abs(c["spread"]) <= CLOSE_SPREAD
    )
    print(
        f"[sweep] {n_window} events in window -> sweeping {len(in_window)} "
        f"({n_close} with |spread|<={CLOSE_SPREAD:g}, {len(ctx)} matched to games)"
    )

    def _credits_low() -> bool:
        return client.credits_low(args.credit_floor)

    # list_events is free but still returns the credit headers — bail before
    # the paid loop if the month's budget is already at the reserve floor.
    if _credits_low():
        warn(
            f"Odds API credits at reserve floor ({client.last_credits.remaining} "
            f"<= {args.credit_floor}) — skipping the 1H sweep to protect the "
            "Sunday opener budget."
        )
        return

    # 2) Paid (markets x regions credits/event): fetch totals_h1 per event.
    # A mid-loop HTTP error (expired key, 429, transient 5xx) must not discard
    # what was already paid for: stop fetching, process the partial batch, and
    # fail the run at the end so the workflow still shows red.
    rows = []
    fetch_error: Optional[str] = None
    for i, ev in enumerate(in_window):
        try:
            data = client.event_first_half_totals(ev["id"])
        except requests.RequestException as e:
            fetch_error = f"{type(e).__name__}: {e}"
            print(
                f"[fetch] FAILED at event {i + 1}/{len(in_window)} ({fetch_error}) — "
                "processing what was already fetched."
            )
            break
        if data:
            # Stamp rows with the actual fetch moment: a long sweep can span
            # minutes, and bucketing every snapshot to run-start misorders
            # intra-run line movement.
            fetched_at = datetime.utcnow()
            for row in normalize_first_half([data], books=cfg.get("books") or None):
                row["fetched_at"] = fetched_at
                row["book"] = normalize_book(row["book"])  # one spelling per book
                rows.append(row)
        if _credits_low():
            warn(
                f"1H sweep stopped at the {args.credit_floor}-credit reserve floor "
                f"({client.last_credits.remaining} left this month) after "
                f"{i + 1}/{len(in_window)} events — processing what was fetched."
            )
            break
    written = matched = unmatched = skipped = 0
    unmatched_names = []

    with session_scope() as s:
        games = _candidate_games(s, args.season)
        for r in rows:
            gid, _score = match_event(r["home_team"], r["away_team"], r["commence_time"], games)
            if gid is None:
                unmatched += 1
                unmatched_names.append(f"{r['away_team']} @ {r['home_team']}")
                continue
            matched += 1
            prev = _latest_snapshot(s, gid, r["book"])
            if not _changed(prev, r["line"], r["over_price"], r["under_price"]):
                skipped += 1
                continue
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book=r["book"],
                    market="1H_total",
                    line=r["line"],
                    over_price=r["over_price"],
                    under_price=r["under_price"],
                    captured_at=r.get("fetched_at") or now,
                )
            )
            written += 1

    c = client.last_credits
    print(
        f"events_total={len(all_events)} in_window={len(in_window)} "
        f"odds_rows={len(rows)} matched={matched} unmatched={unmatched} "
        f"new_snapshots={written} unchanged={skipped}"
    )
    if c:
        print(f"credits: remaining={c.remaining} used={c.used} last_cost={c.last_cost}")
    if unmatched_names:
        uniq = sorted(set(unmatched_names))
        print(f"unmatched events ({len(uniq)}): {uniq[:10]}" + (" ..." if len(uniq) > 10 else ""))
        if not games:
            print(
                "  (no games loaded for this season yet — run backfill --season "
                f"{args.season} first)"
            )
    if fetch_error:
        # Partial batch was processed and written above; still fail the run so
        # the workflow shows red (the sweep did NOT cover the slate).
        print(f"[fetch] sweep incomplete ({fetch_error}) — failing the run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
