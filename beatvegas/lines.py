"""Shared consensus-line helpers over captured odds snapshots."""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from .db.models import OddsSnapshot
from .devig import devig_two_way, is_centred_quote

# A "real" close is a snapshot captured this close to kickoff. The 48-hour
# Sunday opener alone must never grade as a close: the 1H market posts on game
# week and the close polls run inside 2 h; full-game polls are sparser (3 h).
REAL_1H_CLOSE_WINDOW_H = 2.0
REAL_FG_CLOSE_WINDOW_H = 3.0


def centred_snaps(snaps: Sequence) -> list:
    """Snapshots whose prices look like a book's MAIN number.

    A feed sometimes serves an off-centre rung of the alternate ladder as if it
    were the main total, and the price skew is the tell (devig.is_centred_quote).
    This matters most exactly where it hurts most: Hard Rock is centred on 100%
    of quotes more than 24 h from kickoff and off-centre on 26 of 28 inside 3 h
    -- the window the close polls run in. Grading CLV against that was measuring
    us against a number nobody could bet.

    Dropping the rungs rather than the book means a book still contributes its
    last CENTRED quote. Falls back to all of them when nothing qualifies, so a
    caller always gets a consensus rather than nothing.
    """
    # getattr, not attribute access: several callers pass snapshot-like objects
    # that carry only book/line/captured_at, and a quote with no prices cannot
    # be judged -- which this treats as centred, per is_centred_quote.
    ok = [
        s
        for s in snaps
        if is_centred_quote(getattr(s, "over_price", None), getattr(s, "under_price", None))
    ]
    return ok or list(snaps)


def consensus_open_close(snaps: Sequence) -> Tuple[Optional[float], Optional[float]]:
    """Median across books of each book's first / last observed 1H line.

    `snaps`: objects with .book, .line, .captured_at (e.g. OddsSnapshot).

    Off-centre rungs are dropped first -- see centred_snaps."""
    by_book = {}
    for sn in centred_snaps(snaps):
        by_book.setdefault(sn.book, []).append(sn)
    opens: List[float] = []
    closes: List[float] = []
    for book_snaps in by_book.values():
        book_snaps = sorted(book_snaps, key=lambda s: s.captured_at)
        opens.append(book_snaps[0].line)
        closes.append(book_snaps[-1].line)
    if not opens:
        return None, None
    return statistics.median(opens), statistics.median(closes)


def consensus_fair_under_open_close(
    snaps: Sequence, method: str = "multiplicative"
) -> Tuple[Optional[float], Optional[float]]:
    """Median across books of each book's first / last NO-VIG fair-under prob.

    Only snapshots carrying both prices contribute (devig needs both sides).
    Isolates the juice dimension — fair-under is ~0.5 at any fair line, so this
    measures the price asymmetry, NOT line movement (see consensus_open_close
    for the line)."""
    by_book = {}
    for sn in centred_snaps(snaps):
        if sn.over_price is None or sn.under_price is None:
            continue
        by_book.setdefault(sn.book, []).append(sn)
    opens: List[float] = []
    closes: List[float] = []
    for book_snaps in by_book.values():
        book_snaps = sorted(book_snaps, key=lambda s: s.captured_at)
        first, last = book_snaps[0], book_snaps[-1]
        opens.append(devig_two_way(first.over_price, first.under_price, method)[1])
        closes.append(devig_two_way(last.over_price, last.under_price, method)[1])
    if not opens:
        return None, None
    return statistics.median(opens), statistics.median(closes)


def closing_before_kickoff(
    snaps: Sequence, kickoff
) -> Tuple[Optional[float], Optional[float], Optional[object]]:
    """(opening, closing, closing_captured_at) using only PRE-kickoff snapshots.

    CLV is the project's verdict, so the closing line must reflect the market
    near kickoff — not a stray poll that ran after the game started. We keep
    snapshots with captured_at <= kickoff (all of them if kickoff/captured_at is
    unknown), and report the freshest used timestamp as the trust signal.
    """
    pre = pre_kickoff(snaps, kickoff)
    opening, closing = consensus_open_close(pre)
    stamps = []
    for s in pre:
        stamp = s.captured_at
        # A poll that found the number unchanged wrote no row but stamped
        # last_seen_at; that later PRE-kick confirmation is the real close time.
        seen = getattr(s, "last_seen_at", None)
        if seen is not None and (kickoff is None or seen <= kickoff):
            stamp = seen if stamp is None else max(stamp, seen)
        if stamp is not None:
            stamps.append(stamp)
    closing_at = max(stamps) if stamps and closing is not None else None
    return opening, closing, closing_at


def pre_kickoff(snaps: Sequence, kickoff) -> list:
    """Snapshots captured at or before kickoff.

    Falls back to ALL of them when none qualifies, so a caller with no usable
    kickoff still gets a consensus rather than nothing. That fallback means a
    non-empty result is NOT proof the snapshots are pre-kick: a caller that must
    never see a live number (the residual engine's ranking line) has to check
    for itself — see scripts/weekly_update.ranking_line_lookup.
    """
    pre = [s for s in snaps if kickoff is None or s.captured_at is None or s.captured_at <= kickoff]
    return pre or list(snaps)


def fair_under_before_kickoff(
    snaps: Sequence, kickoff, method: str = "multiplicative"
) -> Tuple[Optional[float], Optional[float]]:
    """(open_fair_under, close_fair_under) using only PRE-kickoff snapshots."""
    return consensus_fair_under_open_close(pre_kickoff(snaps, kickoff), method)


def book_closing_before_kickoff(
    snaps: Sequence, kickoff, book: str
) -> Tuple[Optional[float], Optional[float], Optional[object]]:
    """(opening, closing, closing_at) for ONE book's pre-kickoff snapshots — the
    number you actually bet at Hard Rock, not the consensus. Same rules as
    closing_before_kickoff; (None, None, None) when the book has no snapshot."""
    mine = [s for s in snaps if getattr(s, "book", None) == book]
    if not mine:
        return None, None, None
    return closing_before_kickoff(mine, kickoff)


def real_closes(
    session,
    game_ids: Sequence[int],
    kickoffs: Dict[int, datetime],
    market: str = "1H_total",
    within_hours: Optional[float] = None,
) -> Dict[int, float]:
    """game_id -> pre-kickoff consensus close for `market` from captured
    snapshots; games without one are simply absent. `within_hours` keeps only
    snapshots at most that many hours before kickoff (REAL_1H_CLOSE_WINDOW_H /
    REAL_FG_CLOSE_WINDOW_H) so an opener-only game never grades as a real close;
    None keeps every pre-kickoff snapshot."""
    if not game_ids:
        return {}
    by_game: Dict[int, List] = {}
    ids = list(game_ids)
    for i in range(0, len(ids), 1000):
        for snap in (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.market == market, OddsSnapshot.game_id.in_(ids[i : i + 1000]))
            .all()
        ):
            k = kickoffs.get(snap.game_id)
            if (
                within_hours is not None
                and k is not None
                and snap.captured_at is not None
                and not (0 <= (k - snap.captured_at).total_seconds() <= within_hours * 3600)
            ):
                continue
            by_game.setdefault(snap.game_id, []).append(snap)
    out: Dict[int, float] = {}
    for gid, snaps in by_game.items():
        _open, close, _at = closing_before_kickoff(snaps, kickoffs.get(gid))
        if close is not None:
            out[gid] = float(close)
    return out


def book_closing_price_before_kickoff(snaps: Sequence, kickoff, book: str) -> Optional[int]:
    """ONE book's closing UNDER price: the `under_price` of its latest pre-kickoff
    snapshot that carries one (an unpriced row is skipped, not read as -110).
    None when the book has no priced pre-kick snapshot. Fills a pick logged
    with a NULL price (an unpriced Hard Rock line) at grade time."""
    mine = [s for s in snaps if getattr(s, "book", None) == book]
    if not mine:
        return None
    priced = [s for s in pre_kickoff(mine, kickoff) if getattr(s, "under_price", None) is not None]
    if not priced:
        return None
    last = sorted(priced, key=lambda s: s.captured_at or datetime.min)[-1]
    return int(last.under_price)
