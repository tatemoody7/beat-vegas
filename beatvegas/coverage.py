"""Close-window coverage: how many of last Saturday's games the close polls reached.

`last_close_capture_at` stays fresh on three sweeps a Saturday, which is exactly
what happened in 2026 week 4: GitHub's cron fired 3 of 18 close slots, the gauge
looked healthy, and only 18 of 57 Hard-Rock-priced games had ANY first-half
snapshot inside the registered close window (`lines.REAL_1H_CLOSE_WINDOW_H`)
before kickoff -- the window H-STOP-2's line-value clock takes its closes from.
This module measures that share so it can be a gauge (`ops.CLOSE_COVERAGE_PCT`,
written by scripts/close_coverage.py) and a health fact
(`lines_watch.close_window_coverage`). Read-only; the caller writes.

A game counts as Hard-Rock-priced when a `hardrockbet` 1H_total row was captured
before kickoff, and as covered when any 1H_total row was captured OR re-seen
(`last_seen_at`: an unchanged number writes no row) inside the window. Games are
grouped by their Eastern kickoff date; the most recent Saturday with at least one
kicked-off Hard-Rock-priced game inside the look-back is the one reported, so a
Saturday-afternoon call judges the games that have kicked off so far.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import or_

from .db.models import Game, OddsSnapshot
from .hardrock import HR_BOOK_KEY
from .lines import REAL_1H_CLOSE_WINDOW_H

ET = ZoneInfo("America/New_York")
FIRST_HALF_MARKET = "1H_total"
LOOKBACK_DAYS = 8
SATURDAY = 5  # datetime.weekday()


def _et_date(naive_utc: datetime) -> date:
    return naive_utc.replace(tzinfo=timezone.utc).astimezone(ET).date()


def last_saturday_games(
    session, now: datetime
) -> Tuple[Optional[date], List[Tuple[int, datetime]]]:
    """(ET date, [(game_id, kickoff naive UTC), ...]) for the most recent Saturday
    (ET) inside the look-back with a kicked-off game; (None, []) when none."""
    lo = now - timedelta(days=LOOKBACK_DAYS)
    rows = (
        session.query(Game.id, Game.start_date)
        .filter(Game.start_date.isnot(None), Game.start_date >= lo, Game.start_date < now)
        .all()
    )
    by_date: Dict[date, List[Tuple[int, datetime]]] = {}
    for gid, kick in rows:
        d = _et_date(kick)
        if d.weekday() == SATURDAY:
            by_date.setdefault(d, []).append((int(gid), kick))
    if not by_date:
        return None, []
    d = max(by_date)
    return d, by_date[d]


def close_window_coverage(session, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """{"date", "games", "covered", "share"} for the most recent Saturday, or None
    when no Hard-Rock-priced game kicked off on a Saturday inside the look-back."""
    now = now or datetime.utcnow()
    d, games = last_saturday_games(session, now)
    if d is None:
        return None
    ids = [gid for gid, _ in games]
    priced = {
        int(gid)
        for (gid,) in (
            session.query(OddsSnapshot.game_id)
            .join(Game, Game.id == OddsSnapshot.game_id)
            .filter(
                OddsSnapshot.game_id.in_(ids),
                OddsSnapshot.book == HR_BOOK_KEY,
                OddsSnapshot.market == FIRST_HALF_MARKET,
                OddsSnapshot.captured_at < Game.start_date,
            )
            .distinct()
            .all()
        )
    }
    if not priced:
        return None
    window = timedelta(hours=REAL_1H_CLOSE_WINDOW_H)
    covered = 0
    for gid, kick in games:
        if gid not in priced:
            continue
        lo = kick - window
        n = (
            session.query(OddsSnapshot.id)
            .filter(
                OddsSnapshot.game_id == gid,
                OddsSnapshot.market == FIRST_HALF_MARKET,
                or_(
                    (OddsSnapshot.captured_at >= lo) & (OddsSnapshot.captured_at < kick),
                    (OddsSnapshot.last_seen_at >= lo) & (OddsSnapshot.last_seen_at < kick),
                ),
            )
            .count()
        )
        if n > 0:
            covered += 1
    return {
        "date": d.isoformat(),
        "games": len(priced),
        "covered": covered,
        "share": covered / len(priced),
    }
