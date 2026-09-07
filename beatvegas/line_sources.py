"""Who owns a game's stored line, and what the CFBD upsert may overwrite.

Game.full_game_total / Game.spread have two writers: the live opener capture
(scripts/poll_full_game.py: The Odds API, or DraftKings locally) and Monday's
CFBD /lines backfill (scripts/backfill.py, backfill_spread.py). store.upsert
overwrites any non-None value, so without a guard the CFBD consensus number
would silently replace the captured opener every Monday. Each game records who
wrote each field (Game.full_game_total_source / Game.spread_source); the CFBD
path strips the protected keys from its row before upsert.

Import-light on purpose (no SQLAlchemy): pure functions the scripts can call.
"""

from __future__ import annotations

from typing import Dict, Optional

# Sources whose numbers CFBD must not overwrite.
LIVE_LINE_SOURCES = frozenset({"oddsapi", "dk"})
CFBD_SOURCE = "cfbd"


def strip_protected_line_fields(
    row: Dict, fg_source: Optional[str], spread_source: Optional[str]
) -> Dict:
    """A copy of a CFBD game row safe to upsert over the stored game.

    `fg_source` / `spread_source` are the stored game's current tags (None for
    a new or legacy row). A live-sourced total drops `full_game_total` +
    `full_game_total_book`; a live-sourced spread drops `spread`. Otherwise the
    CFBD value stands and is tagged 'cfbd' — only when the row actually carries
    a value (upsert skips None, so a NULL total must not get a source)."""
    out = dict(row)
    if fg_source in LIVE_LINE_SOURCES:
        out.pop("full_game_total", None)
        out.pop("full_game_total_book", None)
        out.pop("full_game_total_source", None)
    elif out.get("full_game_total") is not None:
        out["full_game_total_source"] = CFBD_SOURCE
    if spread_source in LIVE_LINE_SOURCES:
        out.pop("spread", None)
        out.pop("spread_source", None)
    elif out.get("spread") is not None:
        out["spread_source"] = CFBD_SOURCE
    return out
