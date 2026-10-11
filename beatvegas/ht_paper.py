"""The high-total arm H-ARM-HT1H (docs/HYPOTHESES.md; roadmap v1.8, Tate's calls
of 2026-10-10): a paper first-half UNDER on every game whose consensus
full-game total at the build is 60.0 or more, at Hard Rock's centred main line
and under price, into challenger_picks only.

The consensus total is the median of each counted book's newest centred
`full_game_total` quote captured at or before the build, from at least
`consensus.MIN_BOOKS` books. The counted books are the judge's: every book but
`consensus.EXCLUDED_BOOKS` (Hard Rock, Fliff and the synthetic consensus;
exchanges count, roadmap v1.1). Centred is `devig.is_centred_quote` on the
quote's two prices, so a book whose only quotes are off-centre rungs does not
count, and a book whose newest quote is a rung counts its last centred one.

It reads no model and makes no network call -- the snapshots on file at the
build are its whole input -- so it adds nothing to the card's clock. A game
logs once, at its first eligible build inside the paper window; uncapped; a
manual build logs nothing (the card runs no arm under --no-paper).
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from .card import parse_kick
from .challenger_picks import add_challenger_pick
from .consensus import EXCLUDED_BOOKS, MIN_BOOKS
from .db.models import OddsSnapshot
from .devig import is_centred_quote
from .hardrock import HR_BOOK_KEY
from .markets import FULL_GAME
from .protocol import ARM_HT_1H
from .wx_paper import _in_window, _logged, _priced_first_half

HT_TOTAL_MIN = 60.0  # frozen 2026-10-10: the consensus full-game total at the build


def consensus_totals(session, game_ids: Iterable[int], now: datetime) -> Dict[int, Dict[str, Any]]:
    """{game_id: {"total", "books", "quotes"}} for each game that has at least
    MIN_BOOKS counted books: the median of each counted book's newest centred
    full-game total captured at or before `now`. A game short of MIN_BOOKS is
    absent, never a total from fewer books."""
    ids = sorted({int(g) for g in game_ids})
    if not ids:
        return {}
    rows = (
        session.query(OddsSnapshot)
        .filter(
            OddsSnapshot.game_id.in_(ids),
            OddsSnapshot.market == FULL_GAME.snapshot_market,
            OddsSnapshot.captured_at <= now,
            OddsSnapshot.line.isnot(None),
        )
        .all()
    )
    newest: Dict[int, Dict[str, OddsSnapshot]] = {}
    # Oldest first, so the last write per book is its newest quote (id breaks a
    # tie on the capture time).
    for r in sorted(rows, key=lambda r: (r.captured_at, r.id or 0)):
        if r.book is None or r.book in EXCLUDED_BOOKS:
            continue
        if not is_centred_quote(r.over_price, r.under_price):
            continue
        newest.setdefault(int(r.game_id), {})[r.book] = r
    out: Dict[int, Dict[str, Any]] = {}
    for gid, by_book in newest.items():
        if len(by_book) < MIN_BOOKS:
            continue
        quotes = [by_book[b] for b in sorted(by_book)]
        out[gid] = {
            "total": float(statistics.median([float(q.line) for q in quotes])),
            "books": len(quotes),
            "quotes": [
                {"book": q.book, "line": float(q.line), "captured_at": q.captured_at.isoformat()}
                for q in quotes
            ],
        }
    return out


def qualifies(entry: Optional[Dict[str, Any]], total_min: float = HT_TOTAL_MIN) -> bool:
    return entry is not None and float(entry["total"]) >= total_min


def frozen(entry: Dict[str, Any]) -> str:
    """The consensus a pick was decided on, frozen beside the row."""
    return json.dumps(
        {
            "consensus_fg_total": entry["total"],
            "books": entry["books"],
            "quotes": entry["quotes"],
            "total_min": HT_TOTAL_MIN,
            "min_books": MIN_BOOKS,
        },
        sort_keys=True,
    )


def log_first_half(
    session, card: Dict, now: datetime, window_hours: Optional[float] = None
) -> Dict[str, int]:
    """H-ARM-HT1H: a paper first-half UNDER at Hard Rock's centred main line and
    under price on every game in the build's window whose consensus full-game
    total is HT_TOTAL_MIN or more."""
    items = [it for it in card.get("items", []) if _priced_first_half(it)]
    totals = consensus_totals(session, [it["game_id"] for it in items], now)
    logged = _logged(session, ARM_HT_1H)
    added = high = 0
    for it in items:
        gid = int(it["game_id"])
        entry = totals.get(gid)
        if not qualifies(entry):
            continue
        high += 1
        if gid in logged or not _in_window(parse_kick(it.get("kick")), now, window_hours):
            continue
        add_challenger_pick(
            session,
            arm=ARM_HT_1H,
            game_id=gid,
            season=int(card["season"]),
            week=int(card["week"]),
            home_team=it["home"],
            away_team=it["away"],
            side="under",
            market="1H",
            line=float(it["hr_line"]),
            price=int(it["hr_price"]),
            book=HR_BOOK_KEY,
            slot=card.get("slot"),
            placed_at=now,
            factors_json_at_pick=frozen(entry),
        )
        logged.add(gid)
        added += 1
    return {"priced": len(items), "with_consensus": len(totals), "high": high, "added": added}


def summary_lines(stats: Optional[Dict[str, Any]]) -> List[str]:
    """The card summary's line about the high-total arm."""
    tag = (
        f"  ARM {ARM_HT_1H} (paper first-half unders, consensus full-game total {HT_TOTAL_MIN:g}+)"
    )
    if not stats:
        return [f"{tag}: not run"]
    return [
        f"{tag}: {stats.get('high', 0)} of {stats.get('priced', 0)} Hard Rock-priced games "
        f"({stats.get('with_consensus', 0)} with a {MIN_BOOKS}+ book consensus), "
        f"+{stats.get('added', 0)} logged"
    ]
