#!/usr/bin/env python
"""Poll The Odds API for current first-half totals and store snapshots.

Each run captures the current totals_h1 line per (game, book). New snapshots are
written only when the line/prices changed vs the last observation, so the table
becomes a compact movement history; the earliest row per game = posting time. A
poll that finds the number unchanged stamps `last_seen_at` on the existing row,
so a pre-kick confirmation is provable without a duplicate row.

Paid Odds API tier (2026-09): capture EVERY Hard Rock first-half line. Three
modes, driven by lines_watch.yml / card.yml:

    # opener sweep: Hard Rock-priced games in the next 6 days that have no HR
    # 1H line yet (a game stops being paid for once it is captured)
    python scripts/poll_lines.py --hr-universe --missing-hr-only --hours-back 0 --days-ahead 6
    # per-game close: only games kicking off within the next 75 minutes
    python scripts/poll_lines.py --hr-universe --kickoff-within-min 75 --hours-back 0
    # full refresh of the weekend slate (Friday preview / Saturday final card)
    python scripts/poll_lines.py --hr-universe --hours-back 0 --days-ahead 3

Per-event 1H calls cost markets x regions credits (2). --max-credits-per-run is
the runaway guard; --credit-floor protects the month's reserve for sunday.yml.
Every run prints credits_spent= and calls_404= so the budget is auditable.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Dict, List, Optional

import requests

from beatvegas.ci import warn
from beatvegas.config import load_config
from beatvegas.db.models import Game, OddsSnapshot, TeamTempo, Weather
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import match_event
from beatvegas.hardrock import games_with_hr_first_half, hr_universe_game_ids, normalize_book
from beatvegas.season import current_season
from beatvegas.sources.odds import OddsAPIClient, normalize_first_half, redact_key
from beatvegas.sweep import (
    CLOSE_SPREAD,
    build_context,
    filter_hr_universe,
    filter_missing_hr,
    latest_pace_by_team,
    rank_events,
    select_window,
)


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
        help="only pull odds for events kicking off within N days (1H totals only post game-week)",
    )
    ap.add_argument(
        "--kickoff-within-min",
        type=int,
        default=None,
        dest="kickoff_within_min",
        help="CLOSE mode: only events kicking off within the next N minutes "
        "(overrides --days-ahead; pair with --hours-back 0)",
    )
    ap.add_argument(
        "--hours-back",
        type=float,
        default=24.0,
        help="window lower bound: include events that kicked off up to N hours "
        "ago (0 = upcoming games only, so closing-line runs don't spend on "
        "in-play games)",
    )
    ap.add_argument(
        "--hr-universe",
        action="store_true",
        dest="hr_universe",
        help="only events matched to a game Hard Rock has priced a full-game "
        "total on (sunday.yml); falls back to every event, with a warning, "
        "when no such game exists yet",
    )
    ap.add_argument(
        "--missing-hr-only",
        action="store_true",
        dest="missing_hr_only",
        help="OPENER mode: skip games that already have a Hard Rock 1H snapshot",
    )
    ap.add_argument(
        "--max-events",
        type=int,
        default=0,
        help="cap on per-event odds calls after ranking (0 = no cap; the paid "
        "tier sweeps every game in the window)",
    )
    ap.add_argument(
        "--max-credits-per-run",
        type=int,
        default=400,
        dest="max_credits_per_run",
        help="stop the paid loop once this run has spent N credits (runaway guard; 0 disables)",
    )
    ap.add_argument(
        "--credit-floor",
        type=int,
        default=300,
        help="stop per-event odds calls once remaining monthly credits hit this "
        "floor (reserves budget for the Sunday opener capture); 0 disables",
    )
    args = ap.parse_args()

    if not try_init_db():
        return
    cfg = load_config().get("odds_api", {}) or {}
    client = OddsAPIClient()

    # 1) Free: list events, then keep only those in the window (a days-ahead
    # sweep, or the games kicking off within --kickoff-within-min for a close).
    now = datetime.utcnow()
    all_events = client.list_events()
    in_window = select_window(
        all_events,
        now,
        days_ahead=args.days_ahead,
        hours_back=args.hours_back,
        kickoff_within_min=args.kickoff_within_min,
    )
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
        universe = hr_universe_game_ids(s, args.season) if args.hr_universe else set()
        have_hr_1h = games_with_hr_first_half(s, args.season) if args.missing_hr_only else set()
    ctx = build_context(in_window, slate, dome_by_game, pace_by_team)
    n_window = len(in_window)
    if args.hr_universe:
        in_window, fallback = filter_hr_universe(in_window, ctx, universe)
        if fallback:
            warn(
                "No Hard Rock full-game lines on file for this season (sunday.yml "
                "capture missing?) — sweeping every event in the window instead."
            )
    if args.missing_hr_only:
        in_window = filter_missing_hr(in_window, ctx, have_hr_1h)
    # Rank the window by bettability BEFORE spending credits, so a capped or
    # credit-limited run pays for the right games first.
    in_window = rank_events(in_window, ctx, args.max_events)
    n_close = sum(
        1
        for e in in_window
        if (c := ctx.get(e["id"])) and c["spread"] is not None and abs(c["spread"]) <= CLOSE_SPREAD
    )
    mode = (
        f"close<={args.kickoff_within_min}m"
        if args.kickoff_within_min is not None
        else f"sweep<={args.days_ahead}d"
    )
    print(
        f"[sweep:{mode}] {n_window} events in window -> polling {len(in_window)} "
        f"({n_close} with |spread|<={CLOSE_SPREAD:g}, {len(ctx)} matched to games"
        f"{', HR universe ' + str(len(universe)) if args.hr_universe else ''})"
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
    calls_404 = 0
    used_at_start = client.last_credits.used if client.last_credits else None

    def _spent() -> Optional[int]:
        c = client.last_credits
        if used_at_start is None or c is None or c.used is None:
            return None
        return c.used - used_at_start

    for i, ev in enumerate(in_window):
        try:
            data = client.event_first_half_totals(ev["id"])
        except requests.RequestException as e:
            fetch_error = redact_key(f"{type(e).__name__}: {e}")
            print(
                f"[fetch] FAILED at event {i + 1}/{len(in_window)} ({fetch_error}) — "
                "processing what was already fetched."
            )
            break
        if not data:
            calls_404 += 1  # no odds posted yet for this event
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
        spent = _spent()
        if (
            args.max_credits_per_run > 0
            and spent is not None
            and spent >= args.max_credits_per_run
            and i + 1 < len(in_window)
        ):
            warn(
                f"1H sweep stopped at the per-run cap of {args.max_credits_per_run} credits "
                f"(spent {spent}) after {i + 1}/{len(in_window)} events — "
                "processing what was fetched."
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
                # Same number: no new row, but record that we re-confirmed it now
                # (a pre-kick confirmation is the close time for CLV).
                prev.last_seen_at = r.get("fetched_at") or now
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
    spent = _spent()
    print(
        f"events_total={len(all_events)} in_window={len(in_window)} "
        f"odds_rows={len(rows)} matched={matched} unmatched={unmatched} "
        f"new_snapshots={written} unchanged={skipped} calls_404={calls_404} "
        f"credits_spent={spent if spent is not None else 'unknown'}"
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
