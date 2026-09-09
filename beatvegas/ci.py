"""GitHub Actions surface: non-fatal warnings and the card job's slot resolver.

`warn` prints a `::warning::` annotation (shows on the run page) and, when the
job exposes `$GITHUB_STEP_SUMMARY`, appends one line to the run summary. On a
local shell it is just a print. Failures are not handled here: a red run is
reported by GitHub's failed-workflow email and re-checked by the Claude routines.

`resolve_slot` maps a card.yml cron string (or a workflow_dispatch input) to ONE
card slot and its arguments, so the schedule has a single, unit-tested source
of truth (tests/test_ci_slots.py) and an unmapped cron fails the run loudly.
Two slots are scheduled, both gated on the EASTERN clock so neither needs a
cron edit at the DST change: `morning` (Tue-Sat, the decision build for every
game before the next build, 7:45-9:15am ET) and `afternoon` (Thu+Fri, tonight's
kickoffs, 3:45-5:15pm ET — Hard Rock posts first-half lines for weeknight games
during the day, after the morning build). Each slot has two crons an hour
apart; the ET gate picks the right one, and a build already on record for the
slot today (`slots_built_today`, a `cards` row for today's ET date) makes the
other one skip. The DB probe replaced a `gh run list --status success` check
that counted a gate-skip run as a success: from November (EST) the 12:35Z skip
blocked the 13:05Z build and no morning card ever built from cron.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, time, timezone
from typing import Dict, Optional, Set, Tuple
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Sweep arguments per slot (scripts/poll_lines.py). Every slot sweeps only the
# Hard Rock universe and only upcoming games, on the config regions (us,us2).
# NO slot adds the exchange region us_ex: probed against the live Odds API on
# 2026-09-07, us_ex returned ZERO first-half-total bookmakers across three
# upcoming NCAAF games — the exchanges do not post this market, so the region
# costs ~50% more per event and buys nothing. The card's exchange-first fair
# price (beatvegas/card.py) stays in place, dormant, for the day one does.
SWEEP_ARGS: Dict[str, str] = {
    # Tue-Sat ~8:05am ET: the whole week's upcoming games, every morning. The
    # board is one rolling week (each game locks at its own kickoff), so every
    # morning build is the decision build for the games kicking off before the
    # next one. ~60 events x 2 credits.
    "morning": "--hr-universe --hours-back 0 --days-ahead 6",
    # Thu/Fri ~4:05pm ET: tonight's games (kicking off within 10 hours). Hard
    # Rock posts weeknight first-half lines during the day, after the morning
    # build, so this is the build that actually sees them. A handful of events.
    "afternoon": "--hr-universe --kickoff-within-min 600 --hours-back 0",
    # workflow_dispatch with no slot: a full refresh of the week
    "manual": "--hr-universe --hours-back 0 --days-ahead 6",
}
# The card status a CLEAN build of each slot publishes (beatvegas/card.py
# build_card -> payload["status"]; web/lib/card.ts CardStatus). "final" = bet
# off it; "preview" = a build that is never the one to bet off. A failed
# input overrides both with "degraded" — tests/test_card_degraded.py asserts
# every slot in SWEEP_ARGS has an entry here.
CARD_STATUS_BY_SLOT: Dict[str, str] = {
    "morning": "final",  # today's decision build for every game before the next build
    "afternoon": "final",  # the decision build for tonight's games (newest card wins)
    "manual": "preview",  # an ad-hoc refresh is never the final
}
# Paper-log only games kicking off within N hours of the build (the DECISION
# build for those games — docs/BETTING_POLICY.md). None = every upcoming game.
PAPER_WINDOW_HOURS: Dict[str, Optional[float]] = {
    # 24 h, not more: Friday's 8am build must stop short of Saturday's noon
    # kickoffs so each game is paper-logged exactly once, by ITS morning build.
    "morning": 24.0,
    # 10 h: that evening's kickoffs only, so a Friday 4pm build never reaches
    # Saturday's games (they stay with Saturday's morning build).
    "afternoon": 10.0,
    "manual": None,
}
# cron string -> slot. Both crons of a slot fire year-round; the ET gate below
# picks the one that lands inside the slot's window (EDT vs EST), and the
# `built_today` probe makes the second one skip once a build is on record.
CRON_SLOTS: Dict[str, str] = {
    # Morning build, Tue-Sat: four UTC slots so one of them lands 8:05-8:45am ET
    # in both EDT (12:05Z/12:35Z) and EST (13:05Z/13:35Z).
    "5 12 * * 2-6": "morning",
    "35 12 * * 2-6": "morning",
    "5 13 * * 2-6": "morning",
    "35 13 * * 2-6": "morning",
    # Afternoon build, Thu+Fri: 20:00Z = 4pm EDT, 21:00Z = 4pm EST.
    "0 20 * * 4,5": "afternoon",
    "0 21 * * 4,5": "afternoon",
}
# A scheduled run of the slot only builds inside this ET window.
# web/lib/card.ts MORNING_GATE_CLOSE_ET_MIN mirrors the morning close (9:15).
SLOT_GATE_ET: Dict[str, Tuple[time, time]] = {
    "morning": (time(7, 45), time(9, 15)),
    "afternoon": (time(15, 45), time(17, 15)),
}


def warn(message: str) -> None:
    print(f"::warning::{message}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"WARNING: {message}\n")


def _skip(reason: str) -> Dict[str, object]:
    return {
        "slot": "skip",
        "force_sweep": False,
        "force_preview": False,
        "paper_window": "",
        "sweep_args": "",
        "reason": reason,
    }


def resolve_slot(
    schedule: str,
    now_utc: datetime,
    input_slot: str = "",
    built_today: Optional[Set[str]] = None,
) -> Dict[str, object]:
    """The card slot for this run. Pure: the DB probe result is passed in.

    schedule:    github.event.schedule ('' for workflow_dispatch)
    now_utc:     the run's wall clock (aware UTC)
    input_slot:  workflow_dispatch input ('' = manual full refresh)
    built_today: slots with a card row for today's ET date (slots_built_today)

    Returns {slot, force_sweep, force_preview, paper_window ('' or hours),
    sweep_args, reason}. slot == 'skip' when a scheduled slot fired outside its
    ET window or already built today; a dispatch never self-skips. Raises
    ValueError on an unmapped cron or unknown input so the workflow fails
    loudly instead of building the wrong card."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    built_today = built_today or set()
    if schedule == "":
        slot = input_slot or "manual"
        if slot not in SWEEP_ARGS:
            raise ValueError(f"unknown slot input '{input_slot}'")
        reason = "workflow_dispatch"
    else:
        if schedule not in CRON_SLOTS:
            raise ValueError(f"unmapped cron '{schedule}' - add it to beatvegas.ci.CRON_SLOTS")
        slot = CRON_SLOTS[schedule]
        reason = f"cron '{schedule}'"
        gate = SLOT_GATE_ET.get(slot)
        if gate is not None:
            et = now_utc.astimezone(ET)
            lo, hi = gate
            if not (lo <= et.time() <= hi):
                return _skip(f"{slot} slot at {et:%H:%M} ET is outside {lo:%H:%M}-{hi:%H:%M} ET")
        if slot in built_today:
            return _skip(f"{slot} card already built today (ET)")
    window = PAPER_WINDOW_HOURS[slot]
    return {
        "slot": slot,
        # Every decision build re-sweeps: an evening close poll would
        # otherwise satisfy "a 1H snapshot exists today" and the morning card
        # would build on yesterday's numbers.
        "force_sweep": slot in ("morning", "afternoon", "manual"),
        # Fresh QB news on every scheduled card (0 Odds credits).
        "force_preview": slot in ("morning", "afternoon"),
        "paper_window": "" if window is None else f"{window:g}",
        "sweep_args": SWEEP_ARGS[slot],
        "reason": reason,
    }


def et_midnight_as_naive_utc(now_utc: datetime) -> datetime:
    """Today's ET midnight expressed as a NAIVE UTC datetime — the clock
    `cards.built_at` is written on (scripts/build_card.py, datetime.utcnow())."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    et_day = now_utc.astimezone(ET).date()
    midnight_et = datetime.combine(et_day, time(0, 0), tzinfo=ET)
    return midnight_et.astimezone(timezone.utc).replace(tzinfo=None)


def slots_built_today(now_utc: datetime) -> Set[str]:
    """Slots with a `cards` row for the active season/week built since today's
    ET midnight. A card row is a positive fact that the build happened (a
    gate-skip run writes none), which is what the second cron of a slot needs
    to know. Empty when there is no active week, or when the DB is unreachable
    outside GitHub Actions (inside GHA `try_init_db` re-raises, so a bad secret
    fails the run instead of building twice)."""
    from .db.models import Card
    from .db.store import session_scope, try_init_db
    from .season import active

    if not try_init_db():
        return set()
    season, week = active()
    if week is None:
        return set()
    since = et_midnight_as_naive_utc(now_utc)
    with session_scope() as s:
        payloads = [
            p
            for (p,) in s.query(Card.payload).filter(
                Card.season == season, Card.week == week, Card.built_at >= since
            )
        ]
    slots: Set[str] = set()
    for raw in payloads:
        try:
            slot = json.loads(raw).get("slot")
        except (TypeError, ValueError, AttributeError):
            continue
        if slot is not None:
            slots.add(str(slot))
    return slots


def resolve_slot_cli() -> None:
    """Entry point for card.yml: reads SCHEDULE / INPUT_SLOT, probes the cards
    table on a scheduled run, appends the slot fields to $GITHUB_OUTPUT (or
    prints JSON locally)."""
    schedule = os.environ.get("SCHEDULE", "")
    now = datetime.now(timezone.utc)
    built_today: Set[str] = slots_built_today(now) if schedule != "" else set()
    out = resolve_slot(schedule, now, os.environ.get("INPUT_SLOT", ""), built_today)
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            for k, v in out.items():
                fh.write(f"{k}={str(v).lower() if isinstance(v, bool) else v}\n")
    print(json.dumps(out))


if __name__ == "__main__":
    try:
        resolve_slot_cli()
    except ValueError as e:
        print(f"::error::{e}")
        sys.exit(1)
