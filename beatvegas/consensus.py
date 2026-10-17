"""The consensus fair-price engine, v1 (docs/CONSENSUS.md; docs/ROADMAP_2026.md v1.1).

The 2026 research program judges every strategy by line value: the EV of a
wager AT ITS EXACT TERMS (its line and its price) against the vig-free
consensus of the market's closing prices. This module is that judge.

For one game, one market and one wager:

1. Each counted book's closing quote: its newest CENTRED main-line row captured
   at or before kickoff, last confirmed no more than CLOSE_WINDOW_H before
   kickoff, with a line within MAX_CONVERT_PTS of the wager's line. Hard Rock
   (the book we bet into does not judge itself), Fliff and the synthetic
   "consensus" rows are never counted.
2. Each quote de-vigged (multiplicative) to the fair chance of the under GIVEN a
   decision -- a two-way price carries no push mass (docs/CENSORING_STUDY.md) --
   then made unconditional and converted to the wager's line through the
   half-point table: the historical chance the total lands on each integer, for
   games whose market expected about this total (data/halfpoint_hp1.json).
3. The median across books of that chance; at least MIN_BOOKS or the wager is
   excluded (and the exclusion is recorded, never dropped silently).
4. EV per unit staked of the wager's own price against it; a push returns the
   stake.

The same conversion against Hard Rock's OWN closing quote gives a second,
secondary reading (`ev_hr`): did the wager beat the book it was placed at.

Everything here is pure -- snapshots in, numbers out -- so `picks.grade_pick`
and the backfill call the same code and a test can work a pick by hand.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field, replace
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .devig import devig_two_way, is_centred_quote
from .grading import american_to_decimal
from .hardrock import HR_BOOK_KEY
from .lines import CLOSE_EXCLUDED_BOOKS

CONSENSUS_VERSION = "cv1"
HALFPOINT_VERSION = "hp1"
DEVIG_METHOD = "multiplicative"
# Tate's calls, 2026-10-07 (docs/CONSENSUS.md):
EXCLUDED_BOOKS = (
    CLOSE_EXCLUDED_BOOKS  # beatvegas/lines.py: one set for the judge and the displayed close
)
MIN_BOOKS = 3
MAX_CONVERT_PTS = 1.5
CLOSE_WINDOW_H = 2.0

HALFPOINT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / f"halfpoint_{HALFPOINT_VERSION}.json"
)

# The snapshot market each pick market reads.
SNAP_MARKET = {"1H": "1H_total", "full": "full_game_total"}

# Exclusion reasons, recorded on the row (VARCHAR(32)).
EX_NO_KICKOFF = "no_kickoff"
EX_NO_LINE = "no_line"
EX_FEW_BOOKS = "few_books"  # fewer than MIN_BOOKS counted books quoted it at all
EX_STALE = "stale_close"  # enough books, too few confirmed inside the close window
EX_FAR = "far_lines"  # enough fresh books, too few within MAX_CONVERT_PTS of the line
EX_OUTSIDE_TABLE = "outside_table"
EX_NO_HR_CLOSE = "no_hr_close"
EX_NO_TABLE = "no_table"
# The pick carries no price (a paper pick logged before Hard Rock priced its
# line): the consensus is read, but EV at the wager's terms cannot be. Named so
# the protocol counts it as an exclusion rather than a silent gap (2026-10-08).
EX_NO_PRICE = "no_price"


# --- the half-point table ------------------------------------------------------


class HalfPointTable:
    """P(total == k) near an expected total, per market, read from the frozen
    JSON. `mass(market, center)` returns {k: probability} for integer totals
    around `center` (a half-point grid value); a center the table lacks falls
    back to the NEAREST one it has, and `nearest_center` says which."""

    def __init__(self, data: Mapping):
        self.version = data.get("version")
        self._markets: Dict[str, Dict[float, Dict[int, float]]] = {}
        for market, spec in data["markets"].items():
            centers: Dict[float, Dict[int, float]] = {}
            for c, entry in spec["centers"].items():
                centers[float(c)] = {int(k): float(v) for k, v in entry["mass"].items()}
            self._markets[market] = centers

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "HalfPointTable":
        p = Path(path) if path is not None else HALFPOINT_PATH
        return cls(json.loads(p.read_text()))

    def nearest_center(self, market: str, center: float) -> Optional[float]:
        centers = self._markets.get(market)
        if not centers:
            return None
        return min(centers, key=lambda c: (abs(c - center), c))

    def mass(self, market: str, center: float) -> Dict[int, float]:
        c = self.nearest_center(market, center)
        return {} if c is None else self._markets[market][c]


# --- pure probability arithmetic ----------------------------------------------


def is_integer_line(line: float) -> bool:
    return abs(line - round(line)) < 1e-9


def push_mass(mass: Mapping[int, float], line: float) -> float:
    """The chance of landing exactly on `line` (zero on a half-point line)."""
    return float(mass.get(int(round(line)), 0.0)) if is_integer_line(line) else 0.0


def _covers(mass: Mapping[int, float], lo: float, hi: float) -> bool:
    """The table holds every integer in [floor(lo), ceil(hi)]."""
    if not mass:
        return False
    keys = mass.keys()
    return min(keys) <= int(lo // 1) and max(keys) >= -int(-hi // 1)


def convert_under(
    mass: Mapping[int, float], from_line: float, q_decided: float, to_line: float
) -> Optional[float]:
    """The UNCONDITIONAL chance the total lands under `to_line`, from a fair
    under-given-a-decision `q_decided` at `from_line`.

    A two-way price on an integer line excludes the push, so the unconditional
    chance under `from_line` is q * (1 - P(push at from_line)). Moving the line
    adds (or removes) the mass of every integer total in between: under 28.0 wins
    on 27 and below, under 28.5 also wins on 28. None when the table does not
    cover the move."""
    if not _covers(mass, min(from_line, to_line), max(from_line, to_line)):
        return None
    u = q_decided * (1.0 - push_mass(mass, from_line))
    if to_line > from_line:
        u += sum(p for k, p in mass.items() if from_line <= k < to_line)
    elif to_line < from_line:
        u -= sum(p for k, p in mass.items() if to_line <= k < from_line)
    return min(max(u, 0.0), 1.0 - push_mass(mass, to_line))


def win_push(u_under: float, p_push: float, side: str) -> Tuple[float, float]:
    """(P(win), P(push)) for a side, from the unconditional under chance."""
    if side == "over":
        return max(0.0, 1.0 - u_under - p_push), p_push
    return u_under, p_push


def ev_per_unit(p_win: float, p_push: float, price: Optional[int]) -> Optional[float]:
    """Expected profit per unit staked at an American `price`; a push returns
    the stake (EV 0 on that branch). None without a price."""
    if price is None:
        return None
    p_loss = max(0.0, 1.0 - p_win - p_push)
    return p_win * (american_to_decimal(price) - 1.0) - p_loss


# --- reading closing quotes off snapshots --------------------------------------


@dataclass(frozen=True)
class BookClose:
    book: str
    line: float
    over_price: int
    under_price: int
    seen_at: object  # the latest pre-kick confirmation of this quote


def _seen_at(snap, kickoff):
    stamp = snap.captured_at
    seen = getattr(snap, "last_seen_at", None)
    if seen is not None and seen <= kickoff:
        stamp = max(stamp, seen)
    return stamp


def book_closes(snaps: Sequence, kickoff, excluded=EXCLUDED_BOOKS) -> Dict[str, BookClose]:
    """Each book's newest CENTRED, fully priced row captured at or before
    kickoff, with the time it was last confirmed before kickoff. No window and
    no line filter here -- the caller applies both, so a read can say WHY a book
    did not count."""
    best: Dict[str, object] = {}
    for s in snaps:
        book = (getattr(s, "book", None) or "").lower()
        if not book or book in excluded:
            continue
        if s.captured_at is None or s.captured_at > kickoff:
            continue
        if s.line is None or s.over_price is None or s.under_price is None:
            continue
        if not is_centred_quote(s.over_price, s.under_price):
            continue
        prev = best.get(book)
        if prev is None or s.captured_at > prev.captured_at:
            best[book] = s
    return {
        b: BookClose(b, float(s.line), int(s.over_price), int(s.under_price), _seen_at(s, kickoff))
        for b, s in best.items()
    }


@dataclass
class MarketClose:
    """The consensus close of the first-half market as a research benchmark."""

    line: float
    close_at: object  # the newest counted confirmation before kickoff
    books: int


def market_close(
    snaps: Sequence, kickoff, excluded=EXCLUDED_BOOKS
) -> Optional[MarketClose]:
    """The judge's close for a GAME, not a wager (fact-check audit 2026-10-17):
    each book's newest centred quote confirmed inside CLOSE_WINDOW_H before
    kickoff, Hard Rock, Fliff and the feed's consensus row excluded, at least
    MIN_BOOKS books, and the median of their lines. It is the Market Research
    benchmark on Results and /records -- never a price anyone could bet -- so
    it carries no price. None when the window holds too few books."""
    if kickoff is None:
        return None
    start = kickoff - timedelta(hours=CLOSE_WINDOW_H)
    closes = [
        c for c in book_closes(snaps, kickoff, excluded).values() if c.seen_at >= start
    ]
    if len(closes) < MIN_BOOKS:
        return None
    return MarketClose(
        line=float(statistics.median(c.line for c in closes)),
        close_at=max(c.seen_at for c in closes),
        books=len(closes),
    )


def fair_under_decided(close: BookClose) -> float:
    _, fair_under, _ = devig_two_way(close.over_price, close.under_price, DEVIG_METHOD)
    return fair_under


@dataclass
class Reading:
    """One consensus (or Hard Rock) reading of a wager at its exact terms."""

    version: str = CONSENSUS_VERSION
    books: int = 0
    center_line: Optional[float] = None
    close_at: Optional[object] = None
    p_win: Optional[float] = None
    p_push: Optional[float] = None
    ev: Optional[float] = None
    excluded: Optional[str] = None
    book_list: List[str] = field(default_factory=list)


def read_at_terms(
    closes: Mapping[str, BookClose],
    kickoff,
    market: str,
    line: Optional[float],
    side: str,
    price: Optional[int],
    table: HalfPointTable,
    min_books: int = MIN_BOOKS,
) -> Reading:
    """The median-of-books reading of one wager from already-read closes."""
    if kickoff is None:
        return Reading(excluded=EX_NO_KICKOFF)
    if line is None:
        return Reading(excluded=EX_NO_LINE)
    floor = kickoff - timedelta(hours=CLOSE_WINDOW_H)
    fresh = [c for c in closes.values() if c.seen_at is not None and c.seen_at >= floor]
    usable = [c for c in fresh if abs(c.line - line) <= MAX_CONVERT_PTS + 1e-9]
    if len(usable) < min_books:
        # Say WHICH rule left the wager without a reading: the protocol counts
        # exclusions, and "too few books" alone could not tell a missing close
        # poll from a market that moved away from the wager's line.
        if len(closes) < min_books:
            why = EX_FEW_BOOKS
        elif len(fresh) < min_books:
            why = EX_STALE
        else:
            why = EX_FAR
        return Reading(books=len(usable), excluded=why)
    center = round(statistics.median(c.line for c in usable) * 2) / 2
    mass = table.mass(market, center)
    unders = []
    for c in usable:
        u = convert_under(mass, c.line, fair_under_decided(c), line)
        if u is None:
            return Reading(books=len(usable), center_line=center, excluded=EX_OUTSIDE_TABLE)
        unders.append(u)
    u_med = statistics.median(unders)
    p_push = push_mass(mass, line)
    p_win, p_push = win_push(u_med, p_push, side)
    return Reading(
        books=len(usable),
        center_line=center,
        close_at=max(c.seen_at for c in usable),
        p_win=p_win,
        p_push=p_push,
        ev=ev_per_unit(p_win, p_push, price),
        book_list=sorted(c.book for c in usable),
    )


def consensus_reading(
    snaps: Sequence,
    kickoff,
    market: str,
    line: Optional[float],
    side: str,
    price: Optional[int],
    table: HalfPointTable,
) -> Reading:
    """The judge: the consensus close at the wager's exact terms."""
    if kickoff is None:
        return Reading(excluded=EX_NO_KICKOFF)
    return read_at_terms(book_closes(snaps, kickoff), kickoff, market, line, side, price, table)


def hr_reading(
    snaps: Sequence,
    kickoff,
    market: str,
    line: Optional[float],
    side: str,
    price: Optional[int],
    table: HalfPointTable,
) -> Reading:
    """Secondary: the same reading against Hard Rock's own closing MAIN quote
    (its alternate rungs dropped first -- lines.hr_main_snaps)."""
    if kickoff is None:
        return Reading(excluded=EX_NO_KICKOFF)
    from .lines import hr_main_snaps  # local: lines imports picks-adjacent helpers

    hr_only = [
        s for s in hr_main_snaps(snaps) if (getattr(s, "book", "") or "").lower() == HR_BOOK_KEY
    ]
    closes = book_closes(hr_only, kickoff, excluded=frozenset())
    r = read_at_terms(closes, kickoff, market, line, side, price, table, min_books=1)
    if r.excluded == EX_FEW_BOOKS:
        r.excluded = EX_NO_HR_CLOSE
    return r


def pick_fields(cons: Reading, hr: Reading) -> dict:
    """The columns a graded pick carries (manual_picks and challenger_picks)."""
    return {
        "cons_version": CONSENSUS_VERSION,
        "cons_books": cons.books,
        "cons_line": cons.center_line,
        "cons_close_at": cons.close_at,
        "cons_p_win": cons.p_win,
        "cons_p_push": cons.p_push,
        "ev_cons": cons.ev,
        "ev_hr": hr.ev,
        "cons_excluded": cons.excluded,
    }


_TABLE: Optional[HalfPointTable] = None


def default_table() -> Optional[HalfPointTable]:
    """The frozen hp1 table, loaded once; None if the file is missing (the
    caller records `no_table` rather than failing a grading run)."""
    global _TABLE
    if _TABLE is None and HALFPOINT_PATH.exists():
        _TABLE = HalfPointTable.load()
    return _TABLE


def fields_for_pick(snaps: Sequence, kickoff, pick, table: Optional[HalfPointTable] = None) -> dict:
    """The consensus columns for one pick, from its game's snapshots of the
    pick's own market (the same list `picks.grade_pick` already read)."""
    t = table if table is not None else default_table()
    market = SNAP_MARKET.get(getattr(pick, "market", None) or "1H", "1H_total")
    side = (getattr(pick, "side", None) or "under").lower()
    if t is None:
        return pick_fields(Reading(excluded=EX_NO_TABLE), Reading(excluded=EX_NO_TABLE))
    cons = consensus_reading(snaps, kickoff, market, pick.line, side, pick.price, t)
    hr = hr_reading(snaps, kickoff, market, pick.line, side, pick.price, t)
    if pick.price is None and cons.excluded is None:
        cons = replace(cons, excluded=EX_NO_PRICE)
    return pick_fields(cons, hr)
