"""Hard Rock Bet helpers shared across pollers and views.

Tate is in Florida, so Hard Rock is the only bettable book. The Odds API returns
the generic `hardrockbet` key; the Florida-specific `hardrockbet_fl` seen in the
docs folds onto it at write time (`normalize_book`), so one key is the truth.
"""

from __future__ import annotations

import re
from typing import Optional, Set

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


def hr_universe_game_ids(session, season: int, week: Optional[int] = None) -> Set[int]:
    """Games Hard Rock has priced a FULL-GAME total on (odds_snapshots, captured
    by sunday.yml): the only universe bettable from Florida. Season-wide, or one
    week. Shared by the card (build_card.hr_universe) and the 1H sweep
    (poll_lines --hr-universe)."""
    from .db.models import Game, OddsSnapshot  # local: keep this module import-light

    q = (
        session.query(OddsSnapshot.game_id)
        .join(Game, Game.id == OddsSnapshot.game_id)
        .filter(
            Game.season == season,
            OddsSnapshot.market == "full_game_total",
            OddsSnapshot.book == HR_BOOK_KEY,
        )
    )
    if week is not None:
        q = q.filter(Game.week == week)
    return {r[0] for r in q.distinct().all()}


def games_with_hr_first_half(session, season: int) -> Set[int]:
    """Games that already have at least one Hard Rock 1H_total snapshot this
    season (the opener sweep skips them; the close slots still re-check)."""
    from .db.models import Game, OddsSnapshot

    q = (
        session.query(OddsSnapshot.game_id)
        .join(Game, Game.id == OddsSnapshot.game_id)
        .filter(
            Game.season == season,
            OddsSnapshot.market == "1H_total",
            OddsSnapshot.book == HR_BOOK_KEY,
        )
    )
    return {r[0] for r in q.distinct().all()}
