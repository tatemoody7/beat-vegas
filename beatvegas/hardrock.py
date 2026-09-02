"""Hard Rock Bet helpers shared across pollers and views.

Tate is in Florida, so Hard Rock is the only bettable book. The Odds API returns
the generic `hardrockbet` key; the Florida-specific `hardrockbet_fl` seen in the
docs folds onto it at write time (`normalize_book`), so one key is the truth.
"""

from __future__ import annotations

import re
from typing import Optional

HR_BOOK_KEY = "hardrockbet"
HR_BOOK_KEYS = (HR_BOOK_KEY,)  # kept as a tuple for callers that iterate

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
