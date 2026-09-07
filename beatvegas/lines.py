"""Shared consensus-line helpers over captured odds snapshots."""

from __future__ import annotations

import statistics
from typing import List, Optional, Sequence, Tuple

from .devig import devig_two_way


def consensus_open_close(snaps: Sequence) -> Tuple[Optional[float], Optional[float]]:
    """Median across books of each book's first / last observed 1H line.

    `snaps`: objects with .book, .line, .captured_at (e.g. OddsSnapshot)."""
    by_book = {}
    for sn in snaps:
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
    for sn in snaps:
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
    pre = _pre_kickoff(snaps, kickoff)
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


def _pre_kickoff(snaps: Sequence, kickoff) -> list:
    """Snapshots captured at or before kickoff (all of them if unknown)."""
    pre = [s for s in snaps if kickoff is None or s.captured_at is None or s.captured_at <= kickoff]
    return pre or list(snaps)


def fair_under_before_kickoff(
    snaps: Sequence, kickoff, method: str = "multiplicative"
) -> Tuple[Optional[float], Optional[float]]:
    """(open_fair_under, close_fair_under) using only PRE-kickoff snapshots."""
    return consensus_fair_under_open_close(_pre_kickoff(snaps, kickoff), method)


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
