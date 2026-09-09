"""GitHub Actions surface: non-fatal warnings and the card job's slot resolver.

`warn` prints a `::warning::` annotation (shows on the run page) and, when the
job exposes `$GITHUB_STEP_SUMMARY`, appends one line to the run summary. On a
local shell it is just a print. Failures are not handled here: a red run is
reported by GitHub's failed-workflow email and re-checked by the Claude routines.

`resolve_slot` maps a card.yml cron string (or a workflow_dispatch input) to ONE
card slot and its arguments, so the schedule has a single, unit-tested source
of truth (tests/test_ci_slots.py) and an unmapped cron fails the run loudly.
FOUR decision builds a week, each a whole-week sweep and each `final`:
`tue_pm`, `thu_pm`, `fri_pm` (4:05pm ET) and `sat_am` (8:05am ET). The times
track when Hard Rock actually posts first-half lines — it posted 23 of this
week's games on Tuesday afternoon and the bulk of the Saturday slate on Friday
afternoon — rather than sweeping every morning for numbers that have not moved.
Each slot is gated on the EASTERN clock so no cron needs editing at the DST
change, and carries four crons firing year-round with the gate picking the two
that land inside the window in the current regime.

A build already on record for the slot today (`slots_built_today`, a `cards`
row for today's ET date) makes the others skip. That probe replaced a
`gh run list --status success` check that counted a gate-skip run as a success:
from November (EST) the 12:35Z skip blocked the 13:05Z build and no morning card
ever built from cron. Since the primary trigger is now a Vercel cron dispatching
an explicit slot (GitHub cron is the backup), the probe ALSO applies to a
dispatch that names a scheduled slot — otherwise both triggers would build and
each build spends a full sweep. `force=true` overrides it for a deliberate
rebuild, and `manual` never self-skips.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, time, timezone
from typing import Callable, Dict, Optional, Set, Tuple
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Sweep arguments per slot (scripts/poll_lines.py).
WEEK_SWEEP = "--hr-universe --hours-back 0 --days-ahead 6"
# Every slot sweeps the SAME thing: the whole rolling week's upcoming Hard Rock
# games. The board is one rolling week (each game locks at its own kickoff), so
# each build is the decision build for every game kicking off before the next
# one. ~82 events x 1 credit (bookmakers pricing, see sources/odds.py).
# `--days-ahead 6` from sat_am reaches next week's Thu/Fri games, so the
# Saturday build doubles as the opener capture the retired 1h_open crons did.
# NO slot adds the exchange region us_ex: probed against the live Odds API on
# 2026-09-07, us_ex returned ZERO first-half-total bookmakers across three
# upcoming NCAAF games — the exchanges do not post this market, so the region
# costs more per event and buys nothing. The card's exchange-first fair price
# (beatvegas/card.py) stays in place, dormant, for the day one does.
SWEEP_ARGS: Dict[str, str] = {
    "tue_pm": WEEK_SWEEP,
    "thu_pm": WEEK_SWEEP,
    "fri_pm": WEEK_SWEEP,
    "sat_am": WEEK_SWEEP,
    # workflow_dispatch with no slot: a full refresh of the week
    "manual": WEEK_SWEEP,
}

# The card status a CLEAN build of each slot publishes (beatvegas/card.py
# build_card -> payload["status"]; web/lib/card.ts CardStatus). "final" = bet
# off it; "preview" = a build that is never the one to bet off. A failed
# input overrides both with "degraded" — tests/test_card_degraded.py asserts
# every slot in SWEEP_ARGS has an entry here.
CARD_STATUS_BY_SLOT: Dict[str, str] = {
    "tue_pm": "final",
    "thu_pm": "final",
    "fri_pm": "final",
    "sat_am": "final",
    "manual": "preview",  # an ad-hoc refresh is never the final
}

# Paper-log only games kicking off within N hours of the build (the DECISION
# build for those games — docs/BETTING_POLICY.md). None = every upcoming game.
# Paper-log only games kicking off within N hours of the build — the games this
# build is the DECISION build for (docs/BETTING_POLICY.md). None = every
# upcoming game.
#
# Each window is EXACTLY the gap to the next build, and that is load-bearing.
# picks.py::existing_pick guards on game_id, so a game is logged at most once no
# matter what; the window does not control duplication, it controls WHICH
# build's line gets frozen onto the pick. A window wider than the gap would let
# an earlier build claim a game that a later, fresher build should have priced
# (Thursday freezing Saturday's games at Thursday's line); a narrower one leaves
# games logged by nobody — which is a live bug on the old flat 24 h morning
# window, under which no Sunday or Monday game was ever paper-logged.
# SLOT_BUILD_ET below encodes the build times these gaps come from, and
# tests/test_ci_slots.py recomputes each gap from it, so moving a slot without
# moving its window fails CI.
PAPER_WINDOW_HOURS: Dict[str, Optional[float]] = {
    "tue_pm": 48.0,  # Tue 4:05pm -> Thu 4:05pm
    "thu_pm": 24.0,  # Thu 4:05pm -> Fri 4:05pm
    "fri_pm": 16.0,  # Fri 4:05pm -> Sat 8:05am
    "sat_am": 80.0,  # Sat 8:05am -> Tue 4:05pm; the only build that covers
    # Sunday and Monday games. They are frozen early (up to ~60 h before
    # kickoff) — the honest cost of a four-build week, and still better than
    # the old schedule, which logged them never. The true close is still
    # captured for CLV by lines_watch.yml.
    # `manual` never logs: see no_paper in resolve_slot.
    "manual": None,
}

# Nominal build weekday (ISO: Mon=1) and ET wall-clock time per scheduled slot.
# Documentation in code: the paper windows above are the gaps between these, and
# a test asserts exactly that.
SLOT_BUILD_ET: Dict[str, Tuple[int, time]] = {
    "tue_pm": (2, time(16, 5)),
    "thu_pm": (4, time(16, 5)),
    "fri_pm": (5, time(16, 5)),
    "sat_am": (6, time(8, 5)),
}

# ET weekday short name per scheduled slot — lets tests/test_gate_parity.py
# compare SLOT_GATE_ET against web/lib/card.ts BUILD_GATE_CLOSE_ET_MIN, which is
# keyed by weekday because the board's stale-card banner only knows what day it
# is.
SLOT_WEEKDAY_ET: Dict[str, str] = {
    "tue_pm": "Tue",
    "thu_pm": "Thu",
    "fri_pm": "Fri",
    "sat_am": "Sat",
}

# cron string -> slot. Both crons of a slot fire year-round; the ET gate below
# picks the one that lands inside the slot's window (EDT vs EST), and the
# `built_today` probe makes the second one skip once a build is on record.
CRON_SLOTS: Dict[str, str] = {
    # Four UTC crons per slot so two land inside the ET gate in BOTH regimes.
    # Afternoon (16:05 ET target, gate 15:45-17:15):
    #   EDT 20:05Z=16:05 ok, 20:35Z=16:35 ok, 21:05Z=17:05 ok, 21:35Z=17:35 no
    #   EST 20:05Z=15:05 no, 20:35Z=15:35 no, 21:05Z=16:05 ok, 21:35Z=16:35 ok
    # Saturday morning (08:05 ET target, gate 07:45-09:15):
    #   EDT 12:05Z=08:05 ok, 12:35Z=08:35 ok, 13:05Z=09:05 ok, 13:35Z=09:35 no
    #   EST 12:05Z=07:05 no, 12:35Z=07:35 no, 13:05Z=08:05 ok, 13:35Z=08:35 ok
    # Minutes are :05/:35, never the top of the hour, where GitHub's scheduler
    # is most congested and drops the most runs.
    "5 20 * * 2": "tue_pm",
    "35 20 * * 2": "tue_pm",
    "5 21 * * 2": "tue_pm",
    "35 21 * * 2": "tue_pm",
    "5 20 * * 4": "thu_pm",
    "35 20 * * 4": "thu_pm",
    "5 21 * * 4": "thu_pm",
    "35 21 * * 4": "thu_pm",
    "5 20 * * 5": "fri_pm",
    "35 20 * * 5": "fri_pm",
    "5 21 * * 5": "fri_pm",
    "35 21 * * 5": "fri_pm",
    "5 12 * * 6": "sat_am",
    "35 12 * * 6": "sat_am",
    "5 13 * * 6": "sat_am",
    "35 13 * * 6": "sat_am",
}
# Slots that a cron can fire. A workflow_dispatch naming one of these respects
# the built-today probe (see resolve_slot); `manual` does not.
SCHEDULED_SLOTS = frozenset(CRON_SLOTS.values())
# A scheduled run of the slot only builds inside this ET window.
# web/lib/card.ts BUILD_GATE_CLOSE_ET_MIN mirrors these closes, keyed by the
# weekday in SLOT_WEEKDAY_ET (tests/test_gate_parity.py).
SLOT_GATE_ET: Dict[str, Tuple[time, time]] = {
    "tue_pm": (time(15, 45), time(17, 15)),
    "thu_pm": (time(15, 45), time(17, 15)),
    "fri_pm": (time(15, 45), time(17, 15)),
    "sat_am": (time(7, 45), time(9, 15)),
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
        "no_paper": False,
        "sweep_args": "",
        "reason": reason,
    }


def resolve_slot(
    schedule: str,
    now_utc: datetime,
    input_slot: str = "",
    built_today: Optional[Set[str]] = None,
    force: bool = False,
) -> Dict[str, object]:
    """The card slot for this run. Pure: the DB probe result is passed in.

    schedule:    github.event.schedule ('' for workflow_dispatch)
    now_utc:     the run's wall clock (aware UTC)
    input_slot:  workflow_dispatch input ('' = manual full refresh)
    built_today: slots with a card row for today's ET date (slots_built_today)
    force:       workflow_dispatch input; rebuild even if already built today

    Returns {slot, force_sweep, force_preview, paper_window ('' or hours),
    no_paper, sweep_args, reason}. slot == 'skip' when a slot fired outside its ET window
    or already built today.

    A DISPATCH naming a scheduled slot also respects the built-today probe:
    the primary trigger is a Vercel cron dispatching that slot and GitHub cron
    is the backup, so without this both would build and each build spends a
    whole sweep. `force=True` overrides it, and `manual` never self-skips.
    Raises ValueError on an unmapped cron or unknown input so the workflow
    fails loudly instead of building the wrong card."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    built_today = built_today or set()
    if schedule == "":
        slot = input_slot or "manual"
        if slot not in SWEEP_ARGS:
            raise ValueError(f"unknown slot input '{input_slot}'")
        reason = "workflow_dispatch"
        if slot in SCHEDULED_SLOTS and not force and slot in built_today:
            return _skip(
                f"{slot} card already built today (ET); re-dispatch with force=true to rebuild"
            )
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
        "force_sweep": True,
        # Fresh QB news on every scheduled card (0 Odds credits).
        "force_preview": slot in SCHEDULED_SLOTS,
        "paper_window": "" if window is None else f"{window:g}",
        # A `manual` build is a PREVIEW — explicitly never the one to bet off —
        # so it must not create the permanent paper record either. Without this
        # an ad-hoc refresh logs every qualifying game in the week at that
        # moment's line, and no later build can replace it (picks.py
        # existing_pick guards on game_id), so Saturday's picks would sit frozen
        # at whenever someone happened to hit refresh.
        "no_paper": slot not in SCHEDULED_SLOTS,
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
    to know. The season/week filter is deliberate, not just a narrowing: a
    dispatched rehearsal build for ANOTHER week (`gh workflow run card.yml -f
    week=...`) also writes a card row today, and it must not suppress today's
    real build for the active week. Empty when there is no active week, or when
    the DB is unreachable outside GitHub Actions (inside GHA `try_init_db`
    re-raises, so a bad secret fails the run instead of building twice). Only
    called for an in-gate scheduled tick (resolve_for_cli)."""
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


def resolve_for_cli(
    schedule: str,
    now_utc: datetime,
    input_slot: str = "",
    probe: Optional[Callable[[datetime], Set[str]]] = None,
    force: bool = False,
) -> Dict[str, object]:
    """resolve_slot with the DB probe wired in, GATE FIRST: a scheduled tick is
    resolved against an empty probe, and only a tick that lands inside its ET
    window pays for `slots_built_today`. The gate-skip ticks (two of each
    slot's four crons, depending on the DST regime) therefore never open Neon —
    `try_init_db` runs DDL, and inside GHA re-raises on a bad connection, so a
    tick that was going to skip anyway must not be able to fail the run.

    A DISPATCH now probes too, because a named slot can already have been built
    today by the Vercel cron or by GitHub's backup cron. The exceptions are a
    `manual` dispatch and a forced one, which build unconditionally and so have
    nothing to learn from the probe."""
    out = resolve_slot(schedule, now_utc, input_slot, force=force)
    if out["slot"] == "skip":
        return out
    if schedule == "" and (force or out["slot"] not in SCHEDULED_SLOTS):
        return out
    probe_fn = probe if probe is not None else slots_built_today
    return resolve_slot(schedule, now_utc, input_slot, probe_fn(now_utc), force=force)


def resolve_slot_cli() -> None:
    """Entry point for card.yml: reads SCHEDULE / INPUT_SLOT / INPUT_FORCE,
    probes the cards table only when the answer can change (resolve_for_cli),
    appends the slot fields to $GITHUB_OUTPUT (or prints JSON locally)."""
    schedule = os.environ.get("SCHEDULE", "")
    now = datetime.now(timezone.utc)
    out = resolve_for_cli(
        schedule,
        now,
        os.environ.get("INPUT_SLOT", ""),
        force=os.environ.get("INPUT_FORCE", "") == "true",
    )
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
