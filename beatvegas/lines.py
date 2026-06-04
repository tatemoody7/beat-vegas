"""Shared consensus-line helpers over captured odds snapshots."""

from __future__ import annotations

import statistics
from typing import List, Optional, Sequence, Tuple


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


def closing_before_kickoff(
    snaps: Sequence, kickoff
) -> Tuple[Optional[float], Optional[float], Optional[object]]:
    """(opening, closing, closing_captured_at) using only PRE-kickoff snapshots.

    CLV is the project's verdict, so the closing line must reflect the market
    near kickoff — not a stray poll that ran after the game started. We keep
    snapshots with captured_at <= kickoff (all of them if kickoff/captured_at is
    unknown), and report the freshest used timestamp as the trust signal.
    """
    pre = [s for s in snaps if kickoff is None or s.captured_at is None or s.captured_at <= kickoff]
    pre = pre or list(snaps)
    opening, closing = consensus_open_close(pre)
    caps = [s.captured_at for s in pre if s.captured_at is not None]
    closing_at = max(caps) if caps and closing is not None else None
    return opening, closing, closing_at
