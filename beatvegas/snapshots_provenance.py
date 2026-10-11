"""Capture provenance for odds_snapshots (2026-10-11,
docs/program/CAPTURE_DESIGN_2026-10.md): the one place the three stamps get
their meanings, shared by scripts/poll_lines.py and scripts/poll_full_game.py.

- `captured_at`   our first poll that saw this price state (the writer sets it)
- `last_seen_at`  our last poll that still saw it unchanged (the writer sets it)
- `feed_updated_at` the provider's `last_update` for the quote at FIRST capture;
                  never overwritten (feed_stamp_for)
- `feed_reseen_at`  the newest provider stamp seen while the price stayed
                  unchanged, when it differs from the first (note_reseen)

Two polls seeing the same price prove it was quoted at both instants, not that
it stood continuously between them; the reader of these columns owns that
distinction. A missing or unparseable provider stamp is NULL, never invented.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from .ci import warn
from .sources.odds import parse_feed_stamp

# A provider stamp this far AHEAD of our own clock is reported (clock skew or a
# feed fault); the row still keeps it, because it is what the feed said.
FEED_AHEAD_WARN = timedelta(minutes=10)


def feed_stamp_for(row: Mapping[str, Any], captured_at: datetime) -> Optional[datetime]:
    """The feed row's `last_update` as naive UTC, or None. Warns (never raises)
    when the stamp sits more than FEED_AHEAD_WARN after our capture time."""
    stamp = parse_feed_stamp(row.get("last_update"))
    if stamp is not None and stamp - captured_at > FEED_AHEAD_WARN:
        warn(
            f"feed last_update {stamp.isoformat()} is ahead of our capture "
            f"{captured_at.isoformat()} for {row.get('book')} event {row.get('event_id')}"
        )
    return stamp


def note_reseen(prev: Any, stamp: Optional[datetime]) -> None:
    """On a re-sighting of an UNCHANGED price: keep `feed_updated_at` as first
    captured; record a newer provider stamp in `feed_reseen_at` (the newest
    wins). A re-sighting without a stamp changes neither."""
    if stamp is None:
        return
    first = getattr(prev, "feed_updated_at", None)
    if first is not None and stamp <= first:
        return
    # A row written before the column existed has no first-capture stamp and
    # never gets one: feed_updated_at means "at first capture" or nothing. The
    # stamps seen later go to feed_reseen_at, where a reader can see they are
    # re-sightings (Tate 2026-10-11: preserve the original, track the rest apart).
    cur = getattr(prev, "feed_reseen_at", None)
    if cur is None or stamp > cur:
        prev.feed_reseen_at = stamp
