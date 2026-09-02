"""Current season / active week helpers (shared by scripts + the daily runner)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple


def current_season(now: Optional[datetime] = None) -> int:
    now = now or datetime.utcnow()
    # CFB season N runs Aug N -> early Jan N+1; treat Jun+ as the upcoming season.
    return now.year if now.month >= 6 else now.year - 1


def detect_week(season: int, now: Optional[datetime] = None) -> Optional[int]:
    """The week to work on, from games kicking off in [now-2d, now+9d].

    Prefers the UPCOMING week: among weeks with a kickoff still ahead, the one
    whose earliest future kickoff comes first — restricted to weeks where at
    least half the in-window games are still ahead, so a Labor Day Monday
    straggler can't hold week 1 through the first Sunday run. A Saturday-
    morning run (most of the week still ahead) keeps the week in play. With no
    future kickoff in the window (postseason lull), falls back to the most
    common week, ties toward the nearest kickoff. None when the window is empty."""
    from .db.models import Game
    from .db.store import session_scope

    now = now or datetime.utcnow()
    lo, hi = now - timedelta(days=2), now + timedelta(days=9)
    with session_scope() as s:
        rows = (
            s.query(Game.week, Game.start_date)
            .filter(Game.season == season, Game.start_date.isnot(None))
            .all()
        )
    counts: Dict[int, int] = {}
    nearest: Dict[int, float] = {}
    future: Dict[int, int] = {}
    next_kick: Dict[int, datetime] = {}
    for wk, dt in rows:
        if wk is None or dt is None or not (lo <= dt <= hi):
            continue
        counts[wk] = counts.get(wk, 0) + 1
        delta = abs((dt - now).total_seconds())
        nearest[wk] = min(delta, nearest.get(wk, delta))
        if dt >= now:
            future[wk] = future.get(wk, 0) + 1
            next_kick[wk] = min(dt, next_kick.get(wk, dt))
    if not counts:
        return None
    upcoming = [wk for wk in next_kick if 2 * future[wk] >= counts[wk]] or list(next_kick)
    if upcoming:
        return min(upcoming, key=lambda wk: next_kick[wk])
    return max(counts, key=lambda wk: (counts[wk], -nearest[wk]))


def active(now: Optional[datetime] = None) -> Tuple[int, Optional[int]]:
    s = current_season(now)
    return s, detect_week(s, now)
