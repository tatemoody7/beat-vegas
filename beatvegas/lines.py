"""Shared consensus-line helpers over captured odds snapshots."""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .db.models import OddsSnapshot
from .devig import devig_two_way, is_centred_quote, is_hr_rung
from .hardrock import HR_BOOK_KEY, normalize_book

# A "real" close is a snapshot captured this close to kickoff. The 48-hour
# Sunday opener alone must never grade as a close: the 1H market posts on game
# week and the close polls run inside 2 h; full-game polls are sparser (3 h).
REAL_1H_CLOSE_WINDOW_H = 2.0
REAL_FG_CLOSE_WINDOW_H = 3.0


def centred_snaps(snaps: Sequence, strict: bool = False) -> list:
    """Snapshots whose prices look like a book's MAIN number.

    A feed sometimes serves an off-centre rung of the alternate ladder as if it
    were the main total, and the price skew is the tell (devig.is_centred_quote).
    This matters most exactly where it hurts most: Hard Rock is centred on 100%
    of quotes more than 24 h from kickoff and off-centre on 26 of 28 inside 3 h
    -- the window the close polls run in. Grading CLV against that was measuring
    us against a number nobody could bet.

    Dropping the rungs rather than the book means a book still contributes its
    last CENTRED quote.

    `strict` decides what happens when NOTHING qualifies, and the right answer
    depends on how many books the caller is aggregating:

    * MULTI-BOOK consensus (strict=False, the default): fall back to all of
      them. A median over rungs is a poor number, but every book being
      off-centre at once is itself unusual, and some consensus beats none.
    * SINGLE-BOOK reads (strict=True): return []. There is no consensus to fall
      back to -- the fallback just hands back the one rung the filter was there
      to reject. Hard Rock inside 3 h is off-centre on 26 of 28 quotes, so the
      lenient fallback fired EVERY TIME the filter mattered, and the caller
      believed it had a real close. See book_closing_before_kickoff.
    """
    # getattr, not attribute access: several callers pass snapshot-like objects
    # that carry only book/line/captured_at, and a quote with no prices cannot
    # be judged -- which this treats as centred, per is_centred_quote.
    ok = [
        s
        for s in snaps
        if is_centred_quote(getattr(s, "over_price", None), getattr(s, "under_price", None))
    ]
    if strict:
        return ok
    return ok or list(snaps)


# Books that are no main-line opinion to judge Hard Rock against: the synthetic
# consensus and the exchanges (they quote any line at a price). Must equal
# card.SYNTHETIC_BOOKS | card.EXCHANGE_BOOKS -- tests/test_price_skew_filter.py
# asserts it; card.py is not imported here to keep this module light.
RUNG_REFERENCE_EXCLUDED = frozenset(
    {"consensus", "kalshi", "polymarket", "novig", "prophetx", "betopenly"}
)


def _field(s, key):
    return s.get(key) if isinstance(s, dict) else getattr(s, key, None)


def hr_rung_flags(snaps: Sequence, book: str = HR_BOOK_KEY, cap=None) -> List[Tuple[Any, bool]]:
    """[(snapshot, is_rung)] for each of `book`'s snapshots in `snaps`.

    Each one is judged by devig.is_hr_rung against the OTHER books as of its own
    capture: every reference book's latest centred quote at or before it (a
    sweep stamps every book with the same captured_at, so that is the same
    sweep). `snaps` must therefore carry the other books too; with none, only
    the price check can fire. `cap` reads a snapshot's capture time (default
    its `captured_at`); a snapshot with no time is judged on price alone.
    Works on ORM rows and on dicts alike."""
    cap = cap or (lambda s: _field(s, "captured_at"))
    mine: list = []
    refs: Dict[str, list] = {}
    for s in snaps:
        b = normalize_book(_field(s, "book"))
        if b == book:
            mine.append(s)
            continue
        if not b or b in RUNG_REFERENCE_EXCLUDED or _field(s, "line") is None or cap(s) is None:
            continue
        if not is_centred_quote(_field(s, "over_price"), _field(s, "under_price")):
            continue
        refs.setdefault(b, []).append(s)
    out: List[Tuple[Any, bool]] = []
    for s in mine:
        t = cap(s)
        others: List[float] = []
        if t is not None:
            for quotes in refs.values():
                seen = [q for q in quotes if cap(q) <= t]
                if seen:
                    others.append(float(_field(max(seen, key=cap), "line")))
        line = _field(s, "line")
        rung = is_hr_rung(
            _field(s, "over_price"),
            _field(s, "under_price"),
            None if line is None else float(line),
            others,
        )
        out.append((s, rung))
    return out


def _first_half(snaps: Sequence) -> bool:
    """True unless a snapshot says it is another market (a snapshot-like object
    with no `market` is taken as 1H, which every caller of the rule reads)."""
    return all(_field(s, "market") in (None, "1H_total") for s in snaps)


def hr_main_snaps(snaps: Sequence, book: str = HR_BOOK_KEY, cap=None) -> list:
    """`book`'s snapshots that are its MAIN line (hr_rung_flags), in input order."""
    return [s for s, rung in hr_rung_flags(snaps, book, cap) if not rung]


def consensus_open_close(snaps: Sequence) -> Tuple[Optional[float], Optional[float]]:
    """Median across books of each book's first / last observed 1H line.

    `snaps`: objects with .book, .line, .captured_at (e.g. OddsSnapshot).

    Off-centre rungs are dropped first -- see centred_snaps."""
    by_book = {}
    for sn in centred_snaps(snaps):
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


def consensus_fair_under_open_close(
    snaps: Sequence, method: str = "multiplicative"
) -> Tuple[Optional[float], Optional[float]]:
    """Median across books of each book's first / last NO-VIG fair-under prob.

    Only snapshots carrying both prices contribute (devig needs both sides).
    Isolates the juice dimension — fair-under is ~0.5 at any fair line, so this
    measures the price asymmetry, NOT line movement (see consensus_open_close
    for the line)."""
    by_book = {}
    for sn in centred_snaps(snaps):
        if sn.over_price is None or sn.under_price is None:
            continue
        by_book.setdefault(sn.book, []).append(sn)
    opens: List[float] = []
    closes: List[float] = []
    for book_snaps in by_book.values():
        book_snaps = sorted(book_snaps, key=lambda s: s.captured_at)
        first, last = book_snaps[0], book_snaps[-1]
        opens.append(devig_two_way(first.over_price, first.under_price, method)[1])
        closes.append(devig_two_way(last.over_price, last.under_price, method)[1])
    if not opens:
        return None, None
    return statistics.median(opens), statistics.median(closes)


def closing_before_kickoff(
    snaps: Sequence, kickoff
) -> Tuple[Optional[float], Optional[float], Optional[object]]:
    """(opening, closing, closing_captured_at) using only PRE-kickoff snapshots.

    CLV is the project's verdict, so the closing line must reflect the market
    near kickoff — not a stray poll that ran after the game started. We keep
    snapshots with captured_at <= kickoff (all of them if kickoff/captured_at is
    unknown), and report the freshest used timestamp as the trust signal.
    """
    pre = pre_kickoff(snaps, kickoff)
    opening, closing = consensus_open_close(pre)
    stamps = []
    for s in pre:
        stamp = s.captured_at
        # A poll that found the number unchanged wrote no row but stamped
        # last_seen_at; that later PRE-kick confirmation is the real close time.
        seen = getattr(s, "last_seen_at", None)
        if seen is not None and (kickoff is None or seen <= kickoff):
            stamp = seen if stamp is None else max(stamp, seen)
        if stamp is not None:
            stamps.append(stamp)
    closing_at = max(stamps) if stamps and closing is not None else None
    return opening, closing, closing_at


def pre_kickoff(snaps: Sequence, kickoff) -> list:
    """Snapshots captured at or before kickoff.

    Falls back to ALL of them when none qualifies, so a caller with no usable
    kickoff still gets a consensus rather than nothing. That fallback means a
    non-empty result is NOT proof the snapshots are pre-kick: a caller that must
    never see a live number (the residual engine's ranking line) has to check
    for itself — see scripts/weekly_update.ranking_line_lookup.
    """
    pre = [s for s in snaps if kickoff is None or s.captured_at is None or s.captured_at <= kickoff]
    return pre or list(snaps)


# --- as-of reads: what the market showed at a decision time -------------------
#
# Everything above answers "what was the closing number?". A model that claims to
# price a game on Tuesday has to answer a different question -- "what could I
# have seen by Tuesday?" -- and the difference is not cosmetic. `Game.spread` and
# `Game.full_game_total` are single MUTABLE columns holding the last capture that
# touched them, so reading either in a backtest puts Saturday's number into a
# Tuesday feature. Measured on 2026: a game's spread moves a median 1.5 points
# over its snapshot history (p90 3.0), and spread is the primary driver of the
# first-half share. A backtest that reads those columns will look excellent.
#
# So an as-of read goes through the snapshot table, and these helpers are the
# only sanctioned way to do it.

# Hours before kickoff at which a decision is simulated. Reported SEPARATELY,
# never blended: averaging them describes an information environment that never
# existed, and it hides the question the research says matters most -- when is
# the best time to bet? These bracket the production build slots (ci.resolve_slot:
# tue_pm / thu_pm / fri_pm / sat_am) for a Saturday kickoff.
DECISION_OFFSETS_H = {"t_minus_72": 72.0, "t_minus_24": 24.0, "t_minus_3": 3.0}


def as_of(snaps: Sequence, t) -> list:
    """Snapshots captured at or before `t`. STRICT -- there is no fallback.

    Deliberately unlike pre_kickoff, which returns every snapshot when none
    qualifies so a consensus caller still gets a number. That fallback is
    harmless for a close and FATAL here: it would hand back quotes from after
    the decision time, which is the exact leak this function exists to prevent.
    An empty result means "the market had not spoken yet", and the caller must
    be able to say so.

    A snapshot with no `captured_at` is EXCLUDED. It cannot be proven to precede
    `t`, and an unprovable timestamp is not evidence.
    """
    if t is None:
        raise ValueError("as_of needs a decision time; None would silently admit everything")
    out = []
    for sn in snaps:
        stamp = getattr(sn, "captured_at", None)
        if stamp is not None and stamp <= t:
            out.append(sn)
    return out


def decision_times(kickoff, offsets: Optional[Dict[str, float]] = None) -> Dict[str, datetime]:
    """{label: timestamp} for each simulated decision point before `kickoff`."""
    offs = DECISION_OFFSETS_H if offsets is None else offsets
    return {k: kickoff - timedelta(hours=h) for k, h in offs.items()}


def consensus_as_of(snaps: Sequence, t) -> Tuple[Optional[float], Optional[float]]:
    """(median line, median spread) across books as of `t`.

    Each book contributes its LAST quote at or before `t` -- the number it was
    actually showing then -- and off-centre ladder rungs are dropped first
    (centred_snaps). The spread median is taken over whichever books carry one,
    which before 2026 is none of them: `odds_snapshots.spread` is NULL for every
    earlier row, so the spread here is None for historical seasons and
    Game.spread_open is the only honest alternative.
    """
    usable = centred_snaps(as_of(snaps, t))
    by_book: Dict[str, Any] = {}
    for sn in usable:
        book = getattr(sn, "book", None)
        prev = by_book.get(book)
        if prev is None or sn.captured_at > prev.captured_at:
            by_book[book] = sn
    lines = [s.line for s in by_book.values() if getattr(s, "line", None) is not None]
    spreads = [s.spread for s in by_book.values() if getattr(s, "spread", None) is not None]
    return (
        statistics.median(lines) if lines else None,
        statistics.median(spreads) if spreads else None,
    )


def opening_as_of(snaps: Sequence) -> Tuple[Optional[float], Optional[float], Optional[object]]:
    """(line, spread, captured_at) of the EARLIEST centred quote on file.

    The "opening" decision point. It is the earliest thing we can prove was
    visible, which is not the same as the true market open -- capture began
    mid-September in 2023-25, so for those seasons this is the earliest number
    WE saw, not the earliest number that existed. Report it as such."""
    usable = [s for s in centred_snaps(snaps) if getattr(s, "captured_at", None) is not None]
    if not usable:
        return None, None, None
    first = min(usable, key=lambda s: s.captured_at)
    t = first.captured_at
    line, spread = consensus_as_of(usable, t)
    return line, spread, t


def fair_under_before_kickoff(
    snaps: Sequence, kickoff, method: str = "multiplicative"
) -> Tuple[Optional[float], Optional[float]]:
    """(open_fair_under, close_fair_under) using only PRE-kickoff snapshots."""
    return consensus_fair_under_open_close(pre_kickoff(snaps, kickoff), method)


def book_closing_before_kickoff(
    snaps: Sequence, kickoff, book: str
) -> Tuple[Optional[float], Optional[float], Optional[object]]:
    """(opening, closing, closing_at) for ONE book's pre-kickoff snapshots — the
    number you actually bet at Hard Rock, not the consensus. Same rules as
    closing_before_kickoff; (None, None, None) when the book has no snapshot.

    Centring is STRICT here (centred_snaps strict=True): one book is not a
    consensus, so "nothing centred" must mean no close rather than the rung the
    filter just rejected. A caller that gets None has to say so -- it must not
    substitute a number nobody was offered."""
    mine = [s for s in snaps if getattr(s, "book", None) == book]
    if not mine:
        return None, None, None
    mine = centred_snaps(mine, strict=True)
    if book == HR_BOOK_KEY and _first_half(mine):
        # Hard Rock's own 1H alternate lines pass the general price bar (they run
        # -145..-160), so its reads also go through the Hard Rock rule, judged
        # against the other books in `snaps` (devig.is_hr_rung). Measured on 1H
        # quotes only, so a full-game read keeps the general rule.
        keep = {id(s) for s in hr_main_snaps(snaps, book)}
        mine = [s for s in mine if id(s) in keep]
    if not mine:
        return None, None, None
    return closing_before_kickoff(mine, kickoff)


def real_closes(
    session,
    game_ids: Sequence[int],
    kickoffs: Dict[int, datetime],
    market: str = "1H_total",
    within_hours: Optional[float] = None,
) -> Dict[int, float]:
    """game_id -> pre-kickoff consensus close for `market` from captured
    snapshots; games without one are simply absent. `within_hours` keeps only
    snapshots at most that many hours before kickoff (REAL_1H_CLOSE_WINDOW_H /
    REAL_FG_CLOSE_WINDOW_H) so an opener-only game never grades as a real close;
    None keeps every pre-kickoff snapshot."""
    if not game_ids:
        return {}
    by_game: Dict[int, List] = {}
    ids = list(game_ids)
    for i in range(0, len(ids), 1000):
        for snap in (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.market == market, OddsSnapshot.game_id.in_(ids[i : i + 1000]))
            .all()
        ):
            k = kickoffs.get(snap.game_id)
            if (
                within_hours is not None
                and k is not None
                and snap.captured_at is not None
                and not (0 <= (k - snap.captured_at).total_seconds() <= within_hours * 3600)
            ):
                continue
            by_game.setdefault(snap.game_id, []).append(snap)
    out: Dict[int, float] = {}
    for gid, snaps in by_game.items():
        _open, close, _at = closing_before_kickoff(snaps, kickoffs.get(gid))
        if close is not None:
            out[gid] = float(close)
    return out


def book_closing_price_before_kickoff(snaps: Sequence, kickoff, book: str) -> Optional[int]:
    """ONE book's closing UNDER price: the `under_price` of its latest pre-kickoff
    snapshot that carries one (an unpriced row is skipped, not read as -110).
    None when the book has no priced pre-kick snapshot. Fills a pick logged
    with a NULL price (an unpriced Hard Rock line) at grade time.

    Off-centre rungs are rejected (strict, single-book — see centred_snaps): the
    whole point of this helper is to record what the bettor was charged, and a
    ladder rung's lopsided price is the one number that was never on offer at
    the main total."""
    mine = [s for s in snaps if getattr(s, "book", None) == book]
    if not mine:
        return None
    mine = centred_snaps(mine, strict=True)
    if book == HR_BOOK_KEY and _first_half(mine):
        keep = {id(s) for s in hr_main_snaps(snaps, book)}  # see book_closing_before_kickoff
        mine = [s for s in mine if id(s) in keep]
    if not mine:
        return None
    priced = [s for s in pre_kickoff(mine, kickoff) if getattr(s, "under_price", None) is not None]
    if not priced:
        return None
    last = sorted(priced, key=lambda s: s.captured_at or datetime.min)[-1]
    return int(last.under_price)
