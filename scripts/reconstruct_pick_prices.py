#!/usr/bin/env python
"""Work out where each existing pick's `price` actually came from.

    PYTHONPATH=. python scripts/reconstruct_pick_prices.py            # report only
    PYTHONPATH=. python scripts/reconstruct_pick_prices.py --write    # apply

Until 2026-09-14 the grader wrote a book's pre-kick CLOSING price into `price`
whenever a Hard Rock ticket had none. That silently turned the price at the
DECISION into the price at the CLOSE, so any price-based CLV over those rows is
identically zero by construction -- and nothing marked them, so they are
indistinguishable from genuinely priced tickets and would dilute the metric
toward zero, looking exactly like a null result.

Every ingredient for telling them apart is already on file: `poll_lines.py`
records a snapshot when only the PRICE moves (`_changed`), so the book's price
history exists even for the games whose line never budged. This classifies each
pick against it:

  logged            a snapshot for that book at or before `placed_at` carried
                    exactly this price -- the number was really available then
  backfilled_close  no such snapshot, and the price equals the book's pre-kick
                    close. Almost certainly written by the old grader.
  unknown           neither -- cannot be verified in either direction

Only `logged` rows may be used for price-based CLV. The others are reported and
excluded, rather than quietly averaged in.

Also backfills `closing_price`, which is recomputable from snapshots and was
never stored before. Writes nothing without --write.
"""

from __future__ import annotations

import argparse
from collections import Counter
from typing import Dict, List, Optional

from beatvegas.db.models import Game, ManualPick, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.hardrock import normalize_book
from beatvegas.lines import book_closing_price_before_kickoff

LOGGED = "logged"
BACKFILLED = "backfilled_close"
UNKNOWN = "unknown"


def classify(
    price: Optional[int],
    placed_at,
    book: Optional[str],
    snaps: List[OddsSnapshot],
    closing_price: Optional[int],
) -> str:
    """Where did `price` come from? See the module docstring for the three answers."""
    if price is None:
        return UNKNOWN
    if book and placed_at:
        seen = {
            s.under_price
            for s in snaps
            if normalize_book(s.book) == book
            and s.captured_at is not None
            and s.captured_at <= placed_at
            and s.under_price is not None
        }
        if price in seen:
            # The price was genuinely on the board when the pick was logged. This
            # wins even if it also happens to equal the close -- a verified number
            # is verified.
            return LOGGED
    if closing_price is not None and price == closing_price:
        return BACKFILLED
    return UNKNOWN


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--write", action="store_true", help="apply; otherwise report only")
    ap.add_argument("--season", type=int)
    args = ap.parse_args()
    if not try_init_db():
        return

    counts: Counter = Counter()
    rows: List[Dict] = []
    with session_scope() as s:
        q = s.query(ManualPick)
        if args.season:
            q = q.filter(ManualPick.season == args.season)
        picks = q.order_by(ManualPick.placed_at).all()
        games = {g.id: g for g in s.query(Game).filter(Game.id.in_([p.game_id for p in picks]))}
        for p in picks:
            game = games.get(p.game_id)
            market = "1H_total" if (p.market or "1H") == "1H" else "full_game_total"
            snaps = (
                s.query(OddsSnapshot)
                .filter(OddsSnapshot.game_id == p.game_id, OddsSnapshot.market == market)
                .all()
            )
            book = normalize_book(p.book) if p.book else None
            close = (
                book_closing_price_before_kickoff(snaps, game.start_date, book)
                if book and game is not None and game.start_date is not None
                else None
            )
            kind = classify(p.price, p.placed_at, book, snaps, close)
            counts[kind] += 1
            rows.append(
                {
                    "id": p.id,
                    "game_id": p.game_id,
                    "week": p.week,
                    "paper": bool(p.is_paper),
                    "book": book,
                    "price": p.price,
                    "close": close,
                    "kind": kind,
                }
            )
            if args.write:
                p.price_provenance = kind
                p.closing_price = close

    print(f"== pick price provenance: {len(rows)} picks ==\n")
    print(
        f"{'id':>5} {'game':>11} {'wk':>3} {'paper':>6} {'book':<14} {'price':>6} {'close':>6}  kind"
    )
    for r in rows:
        print(
            f"{r['id']:>5} {r['game_id']:>11} {str(r['week']):>3} {str(r['paper']):>6} "
            f"{str(r['book']):<14} {str(r['price']):>6} {str(r['close']):>6}  {r['kind']}"
        )
    print()
    for kind in (LOGGED, BACKFILLED, UNKNOWN):
        print(f"  {kind:<18} {counts[kind]}")
    usable = counts[LOGGED]
    print(
        f"\n{usable} of {len(rows)} picks carry a verified decision price. "
        "Only these may be used for price-based CLV; the rest are excluded, not averaged in."
    )
    print("WROTE price_provenance + closing_price" if args.write else "DRY RUN - nothing written")


if __name__ == "__main__":
    main()
