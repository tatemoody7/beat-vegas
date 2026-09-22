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
