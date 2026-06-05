"""Hard Rock Bet helpers shared across pollers and views.

Tate is in Florida, so Hard Rock is the only bettable book. The Odds API returns
the generic `hardrockbet` key (and a Florida-specific `hardrockbet_fl` when FL
prices diverge), so prefer the FL price and fall back to the generic. See memory
beat-vegas-hardrock-oddsapi.
"""

from __future__ import annotations

from typing import Dict, Optional

# Best first: Florida-specific price when present, else the generic key.
HR_BOOK_KEYS = ("hardrockbet_fl", "hardrockbet")
BOARD_URL = "https://beat-vegas.vercel.app"


def is_hr_book(book: str) -> bool:
    return book in HR_BOOK_KEYS


def pick_hr_line(book_lines: Dict[str, float]) -> Optional[float]:
    """Pick the Hard Rock line from a {book_key: line} map, preferring FL."""
    for k in HR_BOOK_KEYS:
        if k in book_lines:
            return book_lines[k]
    return None
