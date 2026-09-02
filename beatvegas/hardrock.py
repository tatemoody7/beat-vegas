"""Hard Rock Bet helpers shared across pollers and views.

Tate is in Florida, so Hard Rock is the only bettable book. The Odds API returns
the generic `hardrockbet` key (and a Florida-specific `hardrockbet_fl` when FL
prices diverge), so prefer the FL price and fall back to the generic. See memory
beat-vegas-hardrock-oddsapi.
"""

from __future__ import annotations

import re
from typing import Optional

# Best first: Florida-specific price when present, else the generic key.
HR_BOOK_KEYS = ("hardrockbet_fl", "hardrockbet")

# Odds API aliases that mean the same book: the FL-specific key collapses onto
# the generic one so one Hard Rock line never counts twice in a median.
_BOOK_ALIASES = {"hardrockbet_fl": "hardrockbet"}
_NON_KEY_CHARS = re.compile(r"[^a-z0-9]+")


def normalize_book(key: Optional[str]) -> str:
    """Canonical `odds_snapshots.book` key for any source's spelling.

    CFBD provider strings ("DraftKings", "William Hill (US)") and Odds API keys
    ("draftkings") name the same books; storing both double-counts a book in
    consensus medians and fair prices. Lowercase, strip, collapse whitespace /
    punctuation runs to "_" ("William Hill (US)" -> "william_hill_us"), then
    apply the Hard Rock alias. Idempotent; None/"" -> ""."""
    k = _NON_KEY_CHARS.sub("_", (key or "").strip().lower()).strip("_")
    return _BOOK_ALIASES.get(k, k)


def is_hr_book(book: str) -> bool:
    return book in HR_BOOK_KEYS
