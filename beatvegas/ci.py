"""GitHub Actions surface: non-fatal warnings and the card job's slot resolver.

`warn` prints a `::warning::` annotation (shows on the run page) and, when the
job exposes `$GITHUB_STEP_SUMMARY`, appends one line to the run summary. On a
local shell it is just a print. Failures are not handled here: a red run is
reported by GitHub's failed-workflow email and re-checked by the Claude routines.

`resolve_slot` maps a card.yml cron string (or a workflow_dispatch input) to ONE
card slot and its arguments, so the schedule has a single, unit-tested source
of truth (tests/test_ci_slots.py) and an unmapped cron fails the run loudly.
The Saturday final is gated on the EASTERN clock — Tate bets in one sitting
Saturday ~9am ET, so the card must be final by ~8:45am ET in EDT and EST alike
without editing cron strings at the DST change.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, time, timezone
from typing import Dict, Optional
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
    # --- dispatch-only legacy slots (no crons since 2026-09-08) ---
    # Tue/Wed/Thu ~4:05pm ET: tonight's games (kicking off within 10 hours)
    "weeknight": "--hr-universe --kickoff-within-min 600 --hours-back 0",
    # Fri ~6:05pm ET preview: the whole weekend slate
    "friday": "--hr-universe --hours-back 0 --days-ahead 3",
    # Sat ~8:15am ET FINAL: the Saturday slate (+ Sunday/Monday stragglers)
    "saturday": "--hr-universe --hours-back 0 --days-ahead 2",
    # workflow_dispatch with no slot: a full refresh of the week
    "manual": "--hr-universe --hours-back 0 --days-ahead 6",
}
# The card status a CLEAN build of each slot publishes (beatvegas/card.py
# build_card -> payload["status"]; web/lib/card.ts CardStatus). "final" = bet
# off it; "preview" = an earlier build the Saturday final replaces. A failed
# input overrides both with "degraded" — tests/test_card_degraded.py asserts
# every slot in SWEEP_ARGS has an entry here.
CARD_STATUS_BY_SLOT: Dict[str, str] = {
    "morning": "final",  # today's decision build for every game before the next build
    "weeknight": "final",  # the decision build for tonight's games
    "friday": "preview",  # the Saturday final replaces it
    "saturday": "final",  # the card Tate bets off in one sitting
    "manual": "preview",  # an ad-hoc refresh is never the final
}
# Paper-log only games kicking off within N hours of the build (the DECISION
# build for those games — docs/BETTING_POLICY.md). None = every upcoming game.
PAPER_WINDOW_HOURS: Dict[str, Optional[float]] = {
    # 24 h, not more: Friday's 8am build must stop short of Saturday's noon
    # kickoffs so each game is paper-logged exactly once, by ITS morning build.
    "morning": 24.0,
    "weeknight": 10.0,
    "friday": 6.0,
    "saturday": 20.0,
    "manual": None,
}
# cron string -> (slot, retry_since_utc_hhmm | None). A retry slot only runs
# when no SCHEDULED run of the workflow succeeded since that UTC time today.
CRON_SLOTS: Dict[str, tuple] = {
    # Morning build, Tue-Sat: four UTC slots so one of them lands 8:05-8:45am ET
    # in both EDT (12:05Z/12:35Z) and EST (13:05Z/13:35Z); the ET gate below
    # picks the right ones and the retry check skips a second success.
    "5 12 * * 2-6": ("morning", None),
    "35 12 * * 2-6": ("morning", None),
    "5 13 * * 2-6": ("morning", None),
    "35 13 * * 2-6": ("morning", None),
}
MORNING_GATE_ET = (time(7, 45), time(9, 15))  # run only inside this ET window
MORNING_RETRY_SINCE_ET = time(7, 30)  # skip if a scheduled run succeeded since


def warn(message: str) -> None:
    print(f"::warning::{message}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"WARNING: {message}\n")


def resolve_slot(schedule: str, now_utc: datetime, input_slot: str = "") -> Dict[str, object]:
    """The card slot for this run.

    schedule:   github.event.schedule ('' for workflow_dispatch)
    now_utc:    the run's wall clock (aware UTC)
    input_slot: workflow_dispatch input ('' = manual full refresh)

    Returns {slot, retry_since (UTC ISO or ''), force_sweep, force_preview,
    paper_window ('' or hours), sweep_args, reason}. slot == 'skip' when the
    morning slot fired outside its ET window. Raises ValueError on an unmapped
    cron or unknown input so the workflow fails loudly instead of building the
    wrong card."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    if schedule == "":
        slot = input_slot or "manual"
        if slot not in SWEEP_ARGS:
            raise ValueError(f"unknown slot input '{input_slot}'")
        retry_since = ""
        reason = "workflow_dispatch"
    else:
        if schedule not in CRON_SLOTS:
            raise ValueError(f"unmapped cron '{schedule}' - add it to beatvegas.ci.CRON_SLOTS")
        slot, retry_hhmm = CRON_SLOTS[schedule]
        retry_since = ""
        reason = f"cron '{schedule}'"
        if retry_hhmm:
            h, m = (int(x) for x in retry_hhmm.split(":"))
            retry_since = now_utc.replace(hour=h, minute=m, second=0, microsecond=0).isoformat()
        if slot == "morning":
            et = now_utc.astimezone(ET)
            lo, hi = MORNING_GATE_ET
            if not (lo <= et.time() <= hi):
                return {
                    "slot": "skip",
                    "retry_since": "",
                    "force_sweep": False,
                    "force_preview": False,
                    "paper_window": "",
                    "sweep_args": "",
                    "reason": f"morning slot at {et:%H:%M} ET is outside {lo:%H:%M}-{hi:%H:%M} ET",
                }
            since_et = datetime.combine(et.date(), MORNING_RETRY_SINCE_ET, tzinfo=ET)
            retry_since = since_et.astimezone(timezone.utc).isoformat()
    window = PAPER_WINDOW_HOURS[slot]
    return {
        "slot": slot,
        "retry_since": retry_since,
        # Every decision build re-sweeps: an evening close poll would
        # otherwise satisfy "a 1H snapshot exists today" and the morning card
        # would build on yesterday's numbers.
        "force_sweep": slot in ("morning", "friday", "saturday", "manual"),
        # Fresh QB news on every morning card (0 Odds credits).
        "force_preview": slot in ("morning", "saturday"),
        "paper_window": "" if window is None else f"{window:g}",
        "sweep_args": SWEEP_ARGS[slot],
        "reason": reason,
    }


def resolve_slot_cli() -> None:
    """Entry point for card.yml: reads SCHEDULE / INPUT_SLOT, appends the slot
    fields to $GITHUB_OUTPUT (or prints JSON locally)."""
    out = resolve_slot(
        os.environ.get("SCHEDULE", ""),
        datetime.now(timezone.utc),
        os.environ.get("INPUT_SLOT", ""),
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
