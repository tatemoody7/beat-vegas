"""Operational gauges: the few numbers that say whether the system can keep
running, written where they are learned and read by the board.

Eleven of the fourteen failures of 2026-08/09 were silent -- a run that exited 0
and produced nothing, a budget that hit zero, a close poll that never fired. The
only alarm was GitHub's failed-run email, which fires on none of those. Each
gauge is one row in `app_settings` (the table the real-money pause already uses):
`key` -> text `value`, `updated_at` naive UTC. web/lib/boardHealth.ts turns them
into a banner and /api/health exposes them. 2026-09-22.

Writers never raise: a gauge is a courtesy to the reader, and a failed write must
not take down the run that was about to record a real result. Nothing is written
without DATABASE_URL, so unit tests and laptops with the default SQLite are left
alone unless they opt in.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

CFBD_CALLS_REMAINING = "cfbd_calls_remaining"
ODDS_CREDITS_REMAINING = "odds_credits_remaining"
LAST_CLOSE_CAPTURE_AT = "last_close_capture_at"
LAST_CLOSE_CAPTURE_EVENTS = "last_close_capture_events"
LAST_GRADE_COMPLETED_AT = "last_grade_completed_at"

GAUGE_KEYS = (
    CFBD_CALLS_REMAINING,
    ODDS_CREDITS_REMAINING,
    LAST_CLOSE_CAPTURE_AT,
    LAST_CLOSE_CAPTURE_EVENTS,
    LAST_GRADE_COMPLETED_AT,
)

# One more per Vercel cron job, written by web/app/api/cron/[job]/route.ts (not
# by Python): the last time a tick ACTED inside its window -- dispatched a build
# or found one already there. GitHub's crons are the backup and a hand dispatch
# is indistinguishable in the runs API, so this is the only row that says the
# primary trigger is alive. Same naive-UTC-to-the-second value shape as the
# gauges above; read by web/lib/boardHealth.ts::opsWarnings.
LAST_DISPATCH_PREFIX = "last_dispatch_"


def last_dispatch_key(job_id: str) -> str:
    """`app_settings.key` for one cron job's trigger gauge (fits String(32))."""
    return f"{LAST_DISPATCH_PREFIX}{job_id}"


# One more per scheduled Neon-writing job, written by scripts/health_check.py as
# the job's LAST step (beatvegas/health.py): value = the verdict (ok / degraded /
# failed), note = run id, trigger, slot and every missed check. The gauges above
# say whether the system can keep running; this one says whether the run that
# just finished left behind what it was for. Kept out of GAUGE_KEYS like the
# dispatch keys: the board derives the four keys from HEALTH_JOBS itself
# (web/lib/boardHealth.ts HEALTH_JOB_IDS, parity-tested).
HEALTH_PREFIX = "last_health_"
HEALTH_JOBS = ("card", "grade", "sunday", "lines_watch")


def health_key(job: str) -> str:
    """`app_settings.key` for one job's health verdict (fits String(32))."""
    return f"{HEALTH_PREFIX}{job}"


def gauges_enabled() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def record_gauge(key: str, value, note: Optional[str] = None, *, session=None) -> bool:
    """Upsert one gauge. Returns True when written. Never raises."""
    if session is None and not gauges_enabled():
        return False
    try:
        from .db.models import AppSetting
        from .db.store import session_scope

        def _write(s) -> None:
            row = s.get(AppSetting, key)
            if row is None:
                row = AppSetting(key=key, value=str(value), note=note)
                s.add(row)
            else:
                row.value = str(value)
                if note is not None:
                    row.note = note
            row.updated_at = datetime.utcnow()

        if session is not None:
            _write(session)
            session.flush()
        else:
            with session_scope() as s:
                _write(s)
        return True
    except Exception as e:  # noqa: BLE001 - a gauge must never fail the run
        print(f"[ops] gauge {key} not recorded: {e}")
        return False


def read_gauge(session, key: str):
    """(value, updated_at) or (None, None)."""
    from .db.models import AppSetting

    row = session.get(AppSetting, key)
    return (None, None) if row is None else (row.value, row.updated_at)
