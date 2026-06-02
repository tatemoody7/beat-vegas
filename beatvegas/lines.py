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
