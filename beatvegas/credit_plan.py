"""The Odds API credit budget controller (final-2026 plan C11, PR-C3).

The plan is 20,000 credits a month, a hard cap with no rollover, and the
Nov 5 -> Dec 5 cycle is the last. Tate's guardrail, in one sentence: every
optional pull and archive buy must leave the balance at or above the floor
(1,500) plus the measured recurring need for the cycle's remaining weeks (to
min(reset, the season's last kickoff)); archive buys run only in the last four
days before the reset, once that Saturday's closes are captured.

Pure functions plus two DB readers (`load_settings`, `measured_recurring`).
Nothing here spends a credit or writes a row; `scripts/credit_plan.py` is the
command line (`report`, `allow`, the `set-*` writers). No workflow calls it yet:
the optional pulls (PR-C4a/C4b/C10) ask `allow` before paying and the digest
(PR-C11) reads `report`. Never read by a gate.

Settings live in `app_settings` (naive UTC, like every timestamp here), so a
value changes without a deploy and `app_settings_log` keeps the history.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Union

from . import protocol

# app_settings keys (all fit String(32)).
RESET_AT_KEY = "odds_cycle_reset_at"  # ISO naive UTC; unset -> None
FLOOR_KEY = "odds_credit_floor"
ARCHIVE_WINDOW_KEY = "odds_archive_window_days"
RECURRING_FALLBACK_KEY = "odds_recurring_fallback_per_week"

DEFAULT_FLOOR = 1500
DEFAULT_ARCHIVE_WINDOW_DAYS = 4
# Measured Tue 10-13 -> Sun 10-18 before the PR-C2 efficiency fixes; a setting so
# it can drop to ~450 when C2 lands without a deploy.
DEFAULT_RECURRING_FALLBACK = 840

# Jobs whose spend is the recurring need (card builds, close polls, Sunday
# capture). `research`, `archive`, `probe` and `hand` rows are optional pulls.
RECURRING_JOBS = ("card", "lines_watch", "sunday")

# Per-week credit estimates per purpose (plan C11), for the digest's spend-vs-plan
# check. "recurring" is the post-C2 figure.
PLAN: Dict[str, int] = {
    "recurring": 450,
    "sharp_eu": 35,
    "fg_midweek": 40,
    "sharp_1h_close": 65,
    "opener_mon": 150,
    "hr_ladder_close": 100,
    "midweek_1h": 165,
    "team_totals": 550,
}

_DateLike = Union[datetime, str]


def _dt(x: _DateLike) -> datetime:
    return x if isinstance(x, datetime) else datetime.fromisoformat(x)


def parse_utc(text: Optional[str]) -> Optional[datetime]:
    """An ISO timestamp as naive UTC, or None when empty or unparsable. A
    timezone-aware value is converted to UTC and stripped."""
    if text is None or not str(text).strip():
        return None
    try:
        d = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is not None:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d


def cycle_end(reset_at: Optional[_DateLike], season_end: _DateLike) -> datetime:
    """min(reset, season end); the season end alone when the reset is unset."""
    end = _dt(season_end)
    return end if reset_at is None else min(_dt(reset_at), end)


def remaining_weeks(
    now: _DateLike,
    reset_at: Optional[_DateLike],
    season_end: _DateLike = protocol.SEASON_LAST_KICKOFF,
) -> float:
    """Fractional weeks from now to min(reset_at, season_end); never negative."""
    seconds = (cycle_end(reset_at, season_end) - _dt(now)).total_seconds()
    return max(0.0, seconds / (7 * 86400))


def recurring_need(
    now: _DateLike,
    reset_at: Optional[_DateLike],
    recurring_per_week: float,
    season_end: _DateLike = protocol.SEASON_LAST_KICKOFF,
) -> int:
    return int(round(recurring_per_week * remaining_weeks(now, reset_at, season_end)))


def allowance(
    balance: int,
    now: _DateLike,
    reset_at: Optional[_DateLike],
    floor: int,
    recurring_per_week: float,
    season_end: _DateLike = protocol.SEASON_LAST_KICKOFF,
) -> int:
    """Credits an optional pull may spend now: balance - floor - recurring need
    for the weeks left. May be negative."""
    need = recurring_per_week * remaining_weeks(now, reset_at, season_end)
    return int(round(balance - floor - need))


def archive_window_open(
    now: _DateLike,
    reset_at: Optional[_DateLike],
    window_days: float = DEFAULT_ARCHIVE_WINDOW_DAYS,
    last_saturday_closed: bool = True,
) -> bool:
    """True only inside [reset_at - window_days, reset_at) and only when the most
    recent Saturday's closes are captured. False when the reset is unset."""
    if reset_at is None or not last_saturday_closed:
        return False
    n, r = _dt(now), _dt(reset_at)
    return r - timedelta(days=window_days) <= n < r


def saturday_closes_in(coverage_note: Optional[str], now: _DateLike) -> bool:
    """Whether the close-coverage gauge (`note` = `sat=<date> games=<n> covered=<k>`)
    names the most recent Saturday that is over in Eastern time and found at least
    one Hard-Rock-priced game with a close. Pure; the caller reads the gauge."""
    if not coverage_note:
        return False
    fields = dict(p.split("=", 1) for p in coverage_note.split() if "=" in p)
    try:
        from datetime import timezone
        from zoneinfo import ZoneInfo

        today = (
            _dt(now).replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/New_York")).date()
        )
        back = (today.weekday() - 5) % 7 or 7  # the latest Saturday strictly before today
        latest = today - timedelta(days=back)
        return fields.get("sat") == latest.isoformat() and int(fields.get("covered", "0")) > 0
    except (ValueError, KeyError):
        return False


@dataclass
class Settings:
    reset_at: Optional[datetime]
    floor: int
    archive_window_days: int
    recurring_fallback: int


def _int_setting(session, key: str, default: int) -> int:
    from .db.models import AppSetting

    row = session.get(AppSetting, key)
    try:
        return int(float(row.value)) if row is not None else default
    except (TypeError, ValueError):
        return default


def load_settings(session) -> Settings:
    from .db.models import AppSetting

    row = session.get(AppSetting, RESET_AT_KEY)
    return Settings(
        reset_at=parse_utc(row.value) if row is not None else None,
        floor=_int_setting(session, FLOOR_KEY, DEFAULT_FLOOR),
        archive_window_days=_int_setting(session, ARCHIVE_WINDOW_KEY, DEFAULT_ARCHIVE_WINDOW_DAYS),
        recurring_fallback=_int_setting(
            session, RECURRING_FALLBACK_KEY, DEFAULT_RECURRING_FALLBACK
        ),
    )


def measured_recurring(session, now: _DateLike, days: int = 7) -> Optional[int]:
    """Credits a week the recurring jobs (card, lines_watch, sunday) spend: the
    `odds_spend.credits` sum over the trailing `days`, scaled to seven. None when
    the ledger's oldest row is younger than `days` (not a full window yet), so the
    caller uses the fallback setting."""
    from sqlalchemy import func

    from .db.models import OddsSpend

    n = _dt(now)
    first = session.query(func.min(OddsSpend.spent_at)).scalar()
    since = n - timedelta(days=days)
    if first is None or first > since:
        return None
    total = (
        session.query(func.coalesce(func.sum(OddsSpend.credits), 0))
        .filter(OddsSpend.job.in_(RECURRING_JOBS))
        .filter(OddsSpend.spent_at > since, OddsSpend.spent_at <= n)
        .scalar()
    )
    return int(round(int(total) * 7 / days))
