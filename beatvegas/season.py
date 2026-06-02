"""Current season / active week helpers (shared by scripts + the daily runner)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple


def current_season(now: Optional[datetime] = None) -> int:
    now = now or datetime.utcnow()
    # CFB season N runs Aug N -> early Jan N+1; treat Jun+ as the upcoming season.
    return now.year if now.month >= 6 else now.year - 1


def detect_week(season: int, now: Optional[datetime] = None) -> Optional[int]:
    """Most common game week kicking off in [now-2d, now+9d], else None."""
    from .db.models import Game
    from .db.store import session_scope

    now = now or datetime.utcnow()
    lo, hi = now - timedelta(days=2), now + timedelta(days=9)
    with session_scope() as s:
        rows = (s.query(Game.week, Game.start_date)
                .filter(Game.season == season, Game.start_date.isnot(None)).all())
    counts: Dict[int, int] = {}
    for wk, dt in rows:
        if wk is not None and dt is not None and lo <= dt <= hi:
            counts[wk] = counts.get(wk, 0) + 1
    return max(counts, key=counts.get) if counts else None


def active(now: Optional[datetime] = None) -> Tuple[int, Optional[int]]:
    s = current_season(now)
    return s, detect_week(s, now)
