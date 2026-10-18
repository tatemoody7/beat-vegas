"""Which Odds API region a bookmaker key is served from (best effort).

The feed's responses do not say which region a bookmaker came from, so a row's
`region` is set from the CALL that paid for it when the call named one region,
and from this table otherwise. The table follows The Odds API's bookmaker list
as read on 2026-10-18; a key missing here reads `unknown` and nothing downstream
depends on the value being right -- it is a convenience for the research reads
(final-2026 plan, section C11), never a filter for a frozen reader.
"""

from __future__ import annotations

from typing import Dict

UNKNOWN = "unknown"

BOOK_REGION: Dict[str, str] = {
    # us
    "draftkings": "us",
    "fanduel": "us",
    "betmgm": "us",
    "williamhill_us": "us",
    "betrivers": "us",
    "bovada": "us",
    "betonlineag": "us",
    "betus": "us",
    "mybookieag": "us",
    "lowvig": "us",
    "betanysports": "us",
    "fanatics": "us",
    "rebet": "us",
    # us2
    "hardrockbet": "us2",
    "fliff": "us2",
    "ballybet": "us2",
    "betparx": "us2",
    "espnbet": "us2",
    "windcreek": "us2",
    "courtside": "us2",
    # us_ex (exchanges)
    "kalshi": "us_ex",
    "novig": "us_ex",
    "prophetx": "us_ex",
    "polymarket": "us_ex",
    "betopenly": "us_ex",
    # eu
    "pinnacle": "eu",
    "betfair_ex_eu": "eu",
    "williamhill": "eu",
    "unibet_eu": "eu",
    "betsson": "eu",
    "onexbet": "eu",
    "matchbook": "eu",
    "sport888": "eu",
    "betclic": "eu",
    "nordicbet": "eu",
}


def region_of(book: str) -> str:
    """The region a (normalized) bookmaker key is served from, or `unknown`."""
    return BOOK_REGION.get((book or "").lower(), UNKNOWN)
