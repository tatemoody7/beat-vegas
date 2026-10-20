"""The one writer of `research_snapshots` (final-2026 plan, section C11).

Everything the Odds API programme captures that the registered readers must
never see -- a sharp region, Hard Rock's alternate ladder, team totals, Monday
openers, midweek paths, archive waves -- lands here, tagged with its `purpose`,
the `region` of the call that paid for it and the `odds_spend` row that did.
`odds_snapshots` stays what cv1 (the judge), pv1 (the pricing study), the
HT1H trigger and the card's fair-price window read; nothing in this module
touches it, and no frozen reader imports this module.

Two write modes:

- `dedupe=True` (live purposes): the same write-on-change rule as
  `odds_snapshots` -- an unchanged quote bumps `last_seen_at` on the newest row
  for (event, book, market, team, purpose) and keeps the provider stamps apart
  (snapshots_provenance); a changed one is a new row with `captured_at` = the
  poll's own clock.
- `dedupe=False` (archive waves): every row is written as given, `captured_at`
  = the historical envelope's timestamp, `source` = 'historical'. Two waves of
  the same unchanged quote are two rows on purpose: a wave is an observation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Mapping, Optional

from .db.models import ResearchSnapshot
from .hardrock import normalize_book
from .snapshots_provenance import feed_stamp_for, note_reseen
from .sources.odds_regions import UNKNOWN, region_of

PURPOSES = (
    "sharp_eu",
    "fg_midweek",
    "sharp_1h_close",
    "opener_mon",
    "midweek_1h",
    "hr_ladder_close",
    "team_totals",
    "archive_pinnacle_2026",
    "archive_hr_ladder",
    "archive_fg_paths",
    "archive_hr_release",
    "archive_hr_tt1h",
    "archive_pinnacle_2025",
    "archive_hr_ladder_2025",
    "archive_fg_paths_us2",
    "archive_pinnacle_2024",
    "probe",
)
SOURCES = ("live", "historical")

_PRICE_KEYS = ("line", "spread", "over_price", "under_price", "home_price", "away_price")


def _latest(session, *, event_id, game_id, book, market, team, purpose):
    q = session.query(ResearchSnapshot).filter(
        ResearchSnapshot.book == book,
        ResearchSnapshot.market == market,
        ResearchSnapshot.team == team,
        ResearchSnapshot.purpose == purpose,
    )
    if event_id:
        q = q.filter(ResearchSnapshot.event_id == event_id)
    else:
        q = q.filter(ResearchSnapshot.game_id == game_id)
    return q.order_by(ResearchSnapshot.captured_at.desc()).first()


def _unchanged(prev, row: Mapping[str, Any]) -> bool:
    return all(getattr(prev, k) == row.get(k) for k in _PRICE_KEYS)


def write_rows(
    session,
    rows: Iterable[Mapping[str, Any]],
    *,
    purpose: str,
    region: Optional[str] = None,
    request_id: Optional[int] = None,
    source: str = "live",
    dedupe: bool = True,
    now: Optional[datetime] = None,
) -> Dict[str, int]:
    """Write normalized feed rows to `research_snapshots`. Returns counts:
    `written` (new rows) and `reseen` (unchanged quotes whose `last_seen_at`
    moved). `region` is the call's region when it named one; otherwise each
    row's book decides (odds_regions). A row needs `book` and `market`; `team`
    defaults to ''; `captured_at` is taken from the row when present (archive
    waves), else `fetched_at`, else `now`."""
    if purpose not in PURPOSES:
        raise ValueError(f"unknown research purpose {purpose!r}")
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    now = now or datetime.utcnow()
    written = reseen = 0
    for r in rows:
        book = normalize_book(r["book"])
        market = r["market"]
        team = r.get("team") or ""
        event_id = r.get("event_id")
        game_id = r.get("game_id")
        seen_at = r.get("captured_at") or r.get("fetched_at") or now
        stamp = feed_stamp_for(r, seen_at)
        if dedupe:
            prev = _latest(
                session,
                event_id=event_id,
                game_id=game_id,
                book=book,
                market=market,
                team=team,
                purpose=purpose,
            )
            if prev is not None and _unchanged(prev, r):
                prev.last_seen_at = seen_at
                note_reseen(prev, stamp)
                reseen += 1
                continue
        session.add(
            ResearchSnapshot(
                game_id=game_id,
                event_id=event_id,
                book=book,
                market=market,
                team=team,
                line=r.get("line"),
                spread=r.get("spread"),
                over_price=r.get("over_price"),
                under_price=r.get("under_price"),
                home_price=r.get("home_price"),
                away_price=r.get("away_price"),
                captured_at=seen_at,
                last_seen_at=seen_at if dedupe else None,
                feed_updated_at=stamp,
                purpose=purpose,
                region=region or region_of(book) or UNKNOWN,
                request_id=request_id,
                source=source,
            )
        )
        written += 1
    return {"written": written, "reseen": reseen}


def latest_research(session, *, game_id: int, book: str, market: str, purpose: str, team: str = ""):
    """The newest research row for one (game, book, market, purpose)."""
    return _latest(
        session,
        event_id=None,
        game_id=game_id,
        book=normalize_book(book),
        market=market,
        team=team,
        purpose=purpose,
    )
