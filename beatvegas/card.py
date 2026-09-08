"""The weekly bet card — PURE logic, no DB.

`build_card` turns plain rows (games, 1H odds snapshots, predictions, previews)
into the card payload the Board renders (`cards.payload`). The rules mirror
web/lib/edge.ts + verdict.ts + lineCheck.ts EXACTLY so the card and the site
never disagree about a game:

  * gap basis  = Hard Rock's 1H line if posted, else the market median, else the
                 derived reference line baked in at scoring time;
  * BET        = model read AND Hard Rock posted AND Hard Rock's own gap >=
                 BET_GAP_PTS AND a JUDGEABLE price that is fair-or-better
                 (ev >= EV_FLOOR against the exchange-first fair price; no
                 comparable price = blocker no_fair_price, paper only) AND NOT
                 an off-market number AND no QB listed out;
  * EDGE       = the edge score clears 60 (gap + price bonus, minus the
                 off-market / QB-out penalties) with one gate failing — the
                 blocker names it — or a no-model row where Hard Rock's price
                 alone beats the market's fair price ("price only");
  * PASS       = everything else.

Docs: docs/BETTING_POLICY.md ("The board"). Tests: tests/test_card.py.
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from .ci import CARD_STATUS_BY_SLOT
from .devig import devig_two_way, ev_under
from .hardrock import HR_BOOK_KEY, normalize_book
from .model.score import BET_GAP_PTS, EV_FLOOR, HR_OFF_MARKET_PTS, MODEL_VERSION, WEEKLY_BET_CAP

# lineCheck.ts evVerdictFor: "pos" above this, "neg" below EV_FLOOR, else fair.
PRICE_EDGE_EV = 0.005
# edge.ts score constants (the tier boundary + the price/penalty terms).
EDGE_SCORE_MIN = 60
PRICE_BONUS_CAP = 8
OFF_MARKET_PENALTY = 10
QB_OUT_PENALTY = 5
# Hard Rock's average hold on the slate must be at least this much worse than
# the other books' before the card says so (3 cents per dollar).
HOLD_NOTE_CENTS = 0.03

# CFTC-regulated exchanges / prediction markets (Odds API region us_ex; mirrors
# web/lib/books.ts EXCHANGE_KEYS — tests/test_gate_parity.py). ~Zero hold, so a
# quote at Hard Rock's EXACT number is the sharpest fair price we can get and
# wins outright over the books' de-vigged median (exchange-first, PR-6).
EXCHANGE_BOOKS = frozenset({"kalshi", "polymarket", "novig", "prophetx", "betopenly"})
# An exchange only earns that privilege by actually being ~zero hold and live.
# One wide illiquid two-way (+200/-500, hold 0.167) de-vigs to a fair under near
# 0.71 — on its own enough to flip a BET and set the kill price — and
# _latest_by_book keeps a book's newest row forever, so a delisted Friday quote
# is still "latest" on Saturday. Books need neither guard: they enter as a
# MEDIAN over several quotes, which absorbs one bad one.
EXCHANGE_MAX_HOLD = 0.02
EXCHANGE_MAX_AGE_H = 24.0
# Books that never enter the BOOK median fair price: Hard Rock (it is the book
# being judged), the sweepstakes book, CFBD's synthetic aggregate and the
# exchanges (their prices are not a comparable two-way hold; they enter through
# the exchange-first path above instead).
FAIR_PRICE_EXCLUDED = frozenset({HR_BOOK_KEY, "fliff", "consensus"} | EXCHANGE_BOOKS)
# A book is "comparable" to Hard Rock's number when its line sits within this
# many points of it (same window as web/lib/lineCheck.ts). Python-only name for
# the literal both sides share; not a verdict gate.
FAIR_PRICE_LINE_WINDOW = 0.5
# ...except BELOW Hard Rock's line when Hard Rock is posting ABOVE the market
# (hr_vs_market > 0). That is the single best case for an under — and the case
# where, by construction, no book sits within half a point, so a real BET would
# silently become paper for want of a price to judge. A book priced at a LOWER
# total is a CONSERVATIVE reference for an under (the under is likelier at the
# lower number, so its fair under-probability is higher, so the price bar it
# sets is harder): clearing the price gate against it is a strictly safe test
# and cannot manufacture a bet a like-for-like price would have blocked.
FAIR_PRICE_WIDE_WINDOW = 1.5
# CFBD's synthetic aggregate is not a book anyone can bet and double-counts the
# real ones: it never enters the market line either (web/lib/books.ts).
SYNTHETIC_BOOKS = frozenset({"consensus"})

TIER_ORDER = {"BET": 0, "EDGE": 1, "PASS": 2}
REFERENCE_MODEL_VERSION = "derived_lines"

# Display chips (NOT gates — decided 2026-09-07: the post-mortem judges them at
# season end). Same bands/keys as beatvegas/postmortem.py so the live ledger
# and the historical tables read alike.
KEY_NUMBERS_1H = (24.0, 28.0, 31.0)
TOTAL_BANDS = ((45.0, "<45"), (52.0, "45–52"), (60.0, "52–60"), (math.inf, "60+"))
# Paper-ledger blockers, in the order the gates are checked. off_market and
# price are market reads on Hard Rock's number; no_fair_price is the price
# gate's "cannot judge" branch (no book or exchange priced at that number, or
# Hard Rock itself unpriced) so it follows price; qb_out is transient news
# resolved by kickoff.
PAPER_BLOCKERS = ("off_market", "price", "no_fair_price", "qb_out")

# Inputs that can fail on a build while every job still reports success. Each
# one either narrows the slate the card was built from or makes a gate read
# "clear" for the wrong reason, so a card built on one is PAPER ONLY:
#   sweep    the 1H sweep stopped early (credit floor/cap, fetch error) — the
#            games it never reached carry a stale or absent Hard Rock number;
#   preview  the research preview failed — the QB-out gate is reading a stale
#            (or empty) injury file, which passes EVERY game;
#   pace     a model game with no pace read (the strongest genuine 1H signal);
#   weather  an outdoor game with no weather;
#   tempo    the tempo table stored zero teams (TeamRankings mapper collapse).
# Order = the order degraded_inputs reports them. Mirrored by the card status
# banner in web/lib/card.ts (cardHealth).
DEGRADED_INPUTS = ("sweep", "preview", "pace", "weather", "tempo")
DEGRADED_BLOCKER = "degraded"


def total_band(total: Optional[float]) -> Optional[str]:
    """Full-game total band chip (<45 / 45–52 / 52–60 / 60+)."""
    t = _num(total)
    if t is None:
        return None
    for hi, label in TOTAL_BANDS:
        if t < hi:
            return label
    return None


def hook_side(line: Optional[float]) -> Optional[str]:
    """'key+0.5' when the line sits half a point above 24/28/31 (an under at
    24.5 wins on a landing AT the key number), 'key−0.5' half a point below,
    'on_key' when the line IS a key number (a landing there pushes), else
    'other'."""
    v = _num(line)
    if v is None:
        return None
    for k in KEY_NUMBERS_1H:
        if abs(v - k) < 1e-9:
            return "on_key"
        if abs((v - k) - 0.5) < 1e-9:
            return "key+0.5"
        if abs((k - v) - 0.5) < 1e-9:
            return "key−0.5"
    return "other"


def key_dist(line: Optional[float]) -> Optional[float]:
    """Distance from the line to the nearest 1H key number."""
    v = _num(line)
    return None if v is None else min(abs(v - k) for k in KEY_NUMBERS_1H)


# --- small helpers (mirroring web/lib/format.ts + edge.ts) --------------------


def _num(v: Any) -> Optional[float]:
    """Float or None; NaN/inf/None/'' all read as None."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _int(v: Any) -> Optional[int]:
    f = _num(v)
    return None if f is None else int(round(f))


def round2(x: float) -> float:
    return round(x * 100) / 100


def fmt(n: Optional[float], dp: int = 1) -> str:
    """Fixed-decimal number, '—' for None (format.ts fmt)."""
    return "—" if n is None else f"{n:.{dp}f}"


def american(p: int) -> str:
    return f"+{p}" if p > 0 else f"{p}"


def round_half_up(x: float) -> float:
    """Round UP to the next half point (23.55 -> 24, 23.1 -> 23.5, 23.5 -> 23.5)."""
    return math.ceil(x * 2 - 1e-9) / 2


def _american_steps() -> Iterable[int]:
    """American prices in 5-cent steps from worst payout to best (-100 is +100)."""
    for p in range(-1000, 1001, 5):
        if p == -100 or -100 < p < 100:
            continue
        yield p


def break_even_price(fair_under: float, floor: float = EV_FLOOR) -> Optional[int]:
    """The worst American price (5-cent steps) at which the under still clears
    `floor` against `fair_under`; None if nothing in +/-1000 does."""
    for p in _american_steps():
        if ev_under(fair_under, p) >= floor:
            return p
    return None


def kill_line(bv_line: float) -> float:
    """Our number plus the bet gap, rounded up to the next half point."""
    return round_half_up(bv_line + BET_GAP_PTS)


def ev_verdict(ev: Optional[float]) -> str:
    if ev is None:
        return "na"
    if ev > PRICE_EDGE_EV:
        return "pos"
    if ev < EV_FLOOR:
        return "neg"
    return "fair"


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _median(xs: Sequence[float]) -> Optional[float]:
    return statistics.median(xs) if xs else None


def fair_price_window(hr_vs_market: Optional[float]) -> tuple:
    """(points BELOW Hard Rock's line, points ABOVE it) a book may sit and still
    price Hard Rock's number. Half a point both ways, widened below to
    FAIR_PRICE_WIDE_WINDOW when Hard Rock is above the market — see the constant.
    Mirrored by web/lib/lineCheck.ts fairPriceWindow."""
    below = (
        FAIR_PRICE_WIDE_WINDOW
        if hr_vs_market is not None and hr_vs_market > 0
        else FAIR_PRICE_LINE_WINDOW
    )
    return (below, FAIR_PRICE_LINE_WINDOW)


def json_clean(obj: Any) -> Any:
    """Recursively replace NaN/inf floats with None so the payload is strict JSON."""
    if isinstance(obj, dict):
        return {k: json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_clean(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


# --- market read per game ------------------------------------------------------


def _latest_by_book(snaps: Sequence[Dict]) -> Dict[str, Dict]:
    """Latest 1H observation per normalized book key (captured_at desc)."""
    out: Dict[str, Dict] = {}
    for sn in snaps:
        book = normalize_book(sn.get("book"))
        if not book or _num(sn.get("line")) is None:
            continue
        prev = out.get(book)
        cap = _naive_utc(sn.get("captured_at"))
        if prev is None or (cap or datetime.min) >= (prev["_cap"] or datetime.min):
            out[book] = {
                "line": _num(sn["line"]),
                "over_price": _int(sn.get("over_price")),
                "under_price": _int(sn.get("under_price")),
                "_cap": cap,
            }
    return out


def _hr_open(snaps: Sequence[Dict]) -> Optional[float]:
    """Hard Rock's FIRST captured 1H line (the number it opened at)."""
    first: Optional[Dict] = None
    for sn in snaps:
        if normalize_book(sn.get("book")) != HR_BOOK_KEY or _num(sn.get("line")) is None:
            continue
        cap = _naive_utc(sn.get("captured_at")) or datetime.min
        if first is None or cap < first["_cap"]:
            first = {"line": _num(sn["line"]), "_cap": cap}
    return None if first is None else first["line"]


def _fair_under_of(obs: Dict) -> Optional[float]:
    if obs.get("over_price") is None or obs.get("under_price") is None:
        return None
    return devig_two_way(obs["over_price"], obs["under_price"])[1]


def _hold_of(obs: Dict) -> Optional[float]:
    if obs.get("over_price") is None or obs.get("under_price") is None:
        return None
    return devig_two_way(obs["over_price"], obs["under_price"])[2]


def _reference_now(snaps: Sequence[Dict], now: Optional[datetime]) -> Optional[datetime]:
    """The instant the market read is "as of" (naive UTC). The card passes its
    build time; without one, the newest snapshot in the set stands in, so a
    replayed historical week judges staleness against its own clock."""
    n = _naive_utc(now)
    if n is not None:
        return n
    caps = [c for c in (_naive_utc(sn.get("captured_at")) for sn in snaps) if c is not None]
    return max(caps) if caps else None


def _exchange_fair_under(obs: Dict, ref_now: Optional[datetime]) -> Optional[float]:
    """The de-vigged fair under from ONE exchange quote, or None when the quote
    is one-sided, wider than EXCHANGE_MAX_HOLD, or older than EXCHANGE_MAX_AGE_H.
    An unknown capture time is not evidence of staleness — keep the quote."""
    if obs.get("over_price") is None or obs.get("under_price") is None:
        return None
    hold = _hold_of(obs)
    if hold is None or hold > EXCHANGE_MAX_HOLD:
        return None
    cap = obs.get("_cap")
    if (
        cap is not None
        and ref_now is not None
        and (ref_now - cap).total_seconds() > EXCHANGE_MAX_AGE_H * 3600.0
    ):
        return None
    # Two-way multiplicative de-vig: on a ~0-hold quote this is (almost exactly)
    # the raw midpoint of the two implied probabilities.
    return devig_two_way(obs["over_price"], obs["under_price"], "multiplicative")[1]


def market_read(snaps: Sequence[Dict], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Hard Rock's line/price/open, the market median line, and the market's
    no-vig fair under at Hard Rock's number — EXCHANGE-FIRST: the median of the
    tight, fresh exchanges quoting Hard Rock's exact line, else the median over
    comparable books (`fair_price_window`, FAIR_PRICE_EXCLUDED dropped), else
    None (the price cannot be judged). Also Hard Rock's distance from the other
    books' median (`hr_vs_market`) and each side's hold for the slate note.

    `now`: the instant the read is "as of" (the card's build time), used only to
    age out exchange quotes; defaults to the newest snapshot in `snaps`."""
    by_book = _latest_by_book(snaps)
    ref_now = _reference_now(snaps, now)
    hr = by_book.get(HR_BOOK_KEY)
    hr_line = hr["line"] if hr else None
    lines = [o["line"] for b, o in by_book.items() if b not in SYNTHETIC_BOOKS]
    # Hard Rock vs the OTHER books' median (a display chip + why sentence, and
    # the reason the comparable window widens below). `market_line` keeps Hard
    # Rock in its median so off_market and the web's liveLine are untouched.
    others = _median(
        [o["line"] for b, o in by_book.items() if b not in SYNTHETIC_BOOKS and b != HR_BOOK_KEY]
    )
    hr_vs_market = round2(hr_line - others) if hr_line is not None and others is not None else None
    # Exchanges at the SAME line (exact equality — a half point off is another
    # market), each one tight and recent enough to be a live price.
    exchange = [
        f
        for b, o in by_book.items()
        if b in EXCHANGE_BOOKS and hr_line is not None and abs(o["line"] - hr_line) < 1e-9
        for f in [_exchange_fair_under(o, ref_now)]
        if f is not None
    ]
    lo, hi = fair_price_window(hr_vs_market)
    comparable = [
        _fair_under_of(o)
        for b, o in by_book.items()
        if b not in FAIR_PRICE_EXCLUDED
        and hr_line is not None
        and -lo <= (o["line"] - hr_line) <= hi
        and _fair_under_of(o) is not None
    ]
    fair_source: Optional[str]
    if exchange:
        # MEDIAN, so one odd quote among three or more cannot drag the fair
        # price (for one or two quotes the median IS the mean).
        fair_under, fair_source = statistics.median(exchange), "exchange"
    elif comparable:
        fair_under, fair_source = _median(comparable), "books"
    else:
        fair_under, fair_source = None, None
    hr_price = hr["under_price"] if hr else None
    ev = ev_under(fair_under, hr_price) if fair_under is not None and hr_price is not None else None
    market_holds = [
        h
        for b, o in by_book.items()
        if b not in FAIR_PRICE_EXCLUDED
        for h in [_hold_of(o)]
        if h is not None
    ]
    return {
        "hr_line": hr_line,
        "hr_price": hr_price,
        "hr_open": _hr_open(snaps),
        "hr_hold": _hold_of(hr) if hr else None,
        "market_line": _median(lines),
        "fair_under": fair_under,
        "fair_source": fair_source,
        "n_exchange": len(exchange),
        "hr_vs_market": hr_vs_market,
        "ev": ev,
        "market_hold": _median(market_holds),
        "n_books": len(lines),
    }


# --- one game -------------------------------------------------------------------


def _price_sentence(hr_line, hr_price, ev, ev_v) -> str:
    """verdict.ts priceSentence, word for word."""
    if hr_line is None:
        return "Hard Rock hasn’t posted a first-half line for this game yet."
    at = (
        f"under {fmt(hr_line)}"
        if hr_price is None
        else f"under {fmt(hr_line)} at {american(hr_price)}"
    )
    if ev is None:
        # Two different causes, and the action line above already branches on
        # them: blaming the other books when Hard Rock itself posted no price
        # contradicts it (and is simply wrong — the books may all be priced).
        if hr_price is None:
            return f"Hard Rock has {at}, but hasn’t posted a price for it yet — nothing to judge."
        return f"Hard Rock has {at}; not enough other books at that number to judge the price."
    pct = fmt(abs(ev) * 100)
    if ev_v == "pos":
        return (
            f"Hard Rock’s {at} pays about {pct}% better than the market’s fair price "
            "(books plus no-vig exchanges) — a good price."
        )
    if ev_v == "neg":
        return (
            f"Hard Rock’s {at} pays about {pct}% worse than the market’s fair price "
            "(books plus no-vig exchanges) — you’d be paying extra vig."
        )
    return f"Hard Rock’s {at} is priced about the same as the rest of the market — a fair price, no extra edge."


def _gap_sentence(has_model, bv_line, hr_line, market_line, reference, gap) -> str:
    if not has_model:
        line = (
            hr_line
            if hr_line is not None
            else market_line
            if market_line is not None
            else reference
        )
        ref = (
            f"The {fmt(line)} shown is a reference first-half number, not a prediction."
            if line is not None
            else "No first-half line has been posted yet."
        )
        return f"No model read yet — the model needs both teams to have played 2 games this season. {ref}"
    if hr_line is not None:
        hr_gap = round2(hr_line - bv_line)
        direction = (
            "above our number, which leans under"
            if hr_gap > 0
            else "below our number, which leans over"
            if hr_gap < 0
            else "right on our number"
        )
        market = (
            f" (the market consensus is {fmt(market_line)})."
            if market_line is not None and abs(market_line - hr_line) >= 0.05
            else "."
        )
        return (
            f"Hard Rock has the first half at {fmt(hr_line)}; our number is {fmt(bv_line)}{market} "
            f"Hard Rock’s line is {fmt(abs(hr_gap))} points {direction}."
        )
    basis = market_line if market_line is not None else reference
    if basis is None or gap is None:
        return (
            f"Our number for the first half is {fmt(bv_line)}, but no Vegas line has been "
            "captured to compare it to."
        )
    src = (
        "The market has (Hard Rock has not posted)"
        if market_line is not None
        else "The estimated line is"
    )
    direction = (
        "above our number, which leans under"
        if gap > 0
        else "below our number, which leans over"
        if gap < 0
        else "right on our number"
    )
    return (
        f"{src} the first half at {fmt(basis)}; our number is {fmt(bv_line)}. "
        f"The line is {fmt(abs(gap))} points {direction}."
    )


def build_item(
    game: Dict,
    snaps: Sequence[Dict],
    prediction: Optional[Dict],
    reference_line: Optional[float],
    preview: Optional[Dict],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """One card item for one game (the edge.ts rules, minus the context-only
    score, which never decides a tier). `now` is the build time — it only ages
    out stale exchange quotes (market_read)."""
    m = market_read(snaps, now)
    hr_line, hr_price, ev = m["hr_line"], m["hr_price"], m["ev"]
    market_line, fair_under = m["market_line"], m["fair_under"]
    ev_v = ev_verdict(ev)
    price_pos, price_neg = ev_v == "pos", ev_v == "neg"

    bv_line = _num((prediction or {}).get("bv_line"))
    has_model = bv_line is not None
    qb_out = bool((preview or {}).get("qb_out"))
    qb_detail = (preview or {}).get("qb_out_detail")

    off_market = (
        hr_line is not None
        and market_line is not None
        and market_line - hr_line > HR_OFF_MARKET_PTS
    )
    basis = (
        hr_line
        if hr_line is not None
        else market_line
        if market_line is not None
        else reference_line
    )
    gap = round2(basis - bv_line) if has_model and basis is not None else None
    hr_gap = round2(hr_line - bv_line) if has_model and hr_line is not None else None

    k_line = kill_line(bv_line) if has_model else None
    k_price = break_even_price(fair_under) if fair_under is not None else None

    # --- tier + blocker (edge.ts) -------------------------------------------
    price_bonus = (
        max(-PRICE_BONUS_CAP, min(PRICE_BONUS_CAP, round(ev * 100)))
        if hr_price is not None and ev is not None
        else 0
    )
    score = 0
    if has_model:
        score = max(0, min(100, round(50 + 10 * (gap or 0))))
        score += price_bonus
        if off_market:
            score -= OFF_MARKET_PENALTY
        if qb_out:
            score -= QB_OUT_PENALTY
        score = max(0, min(100, score))

    # A BET needs a JUDGEABLE price: ev None (no book or exchange priced at
    # Hard Rock's number, or Hard Rock unpriced) is paper only (verdict.ts).
    is_bet = (
        has_model
        and hr_gap is not None
        and hr_gap >= BET_GAP_PTS
        and not off_market
        and not price_neg
        and ev is not None
        and not qb_out
    )
    # Paper ledger (decided 2026-09-07): EVERY game whose Hard Rock 1H line sits
    # >= BET_GAP_PTS above our number is logged, tagged with the gate that
    # blocked a real bet (None = it was a BET). The weekly cap adds "cap" later.
    qualifies = has_model and hr_gap is not None and hr_gap >= BET_GAP_PTS
    paper_blocker: Optional[str] = None
    # Gate order (PAPER_BLOCKERS): off_market and price are market reads on
    # Hard Rock's number; no_fair_price is the price gate's "cannot judge"
    # branch, so it follows price; qb_out is transient news resolved by
    # kickoff; gap is the residual (EDGE only).
    if qualifies:
        if off_market:
            paper_blocker = "off_market"
        elif price_neg:
            paper_blocker = "price"
        elif ev is None:
            paper_blocker = "no_fair_price"
        elif qb_out:
            paper_blocker = "qb_out"
    blocker: Optional[str] = None
    if is_bet:
        tier = "BET"
    elif has_model and score >= EDGE_SCORE_MIN:
        tier = "EDGE"
        if hr_line is None:
            blocker = "no_hr_line"
        elif off_market:
            blocker = "off_market"
        elif price_neg:
            blocker = "price"
        elif ev is None:
            blocker = "no_fair_price"
        elif qb_out:
            blocker = "qb_out"
        else:
            blocker = "gap"
    elif not has_model and price_pos:
        tier, blocker = "EDGE", "no_model"
    else:
        tier = "PASS"

    # --- action (edge.ts wording) --------------------------------------------
    if tier == "BET":
        at = f" at {american(hr_price)}" if hr_price is not None else ""
        action = f"Bet now: 1H under {fmt(hr_line)}{at} on Hard Rock."
    elif not has_model:
        action = (
            f"Price only: Hard Rock pays {fmt((ev or 0) * 100)}% better than the market on this "
            "under. No model behind it."
            if price_pos
            else "Pass: no model read this week and no price edge at Hard Rock."
        )
    elif blocker == "no_hr_line" or basis is None:
        lead = "No line captured yet." if basis is None else "No Hard Rock line yet."
        action = f"{lead} A bet at under {fmt(k_line)} or higher, -110 or better."
    elif blocker == "off_market":
        diff = round2(market_line - hr_line)
        action = (
            f"Wait: Hard Rock’s {fmt(hr_line)} is {fmt(diff)} below the market’s {fmt(market_line)} "
            f"— giving up points and a void risk. Bet if it moves to {fmt(market_line - 0.5)} or higher."
        )
    elif blocker == "price":
        needs = (
            f"{american(k_price)} or better"
            if k_price is not None
            else "a fair price (-110 or better)"
        )
        hr = american(hr_price) if hr_price is not None else "unpriced"
        action = f"Wait: Hard Rock is {hr}; needs {needs}."
    elif blocker == "no_fair_price":
        if hr_price is None:
            action = (
                f"Wait: Hard Rock hasn’t priced its {fmt(hr_line)} under yet — nothing to judge. "
                "Paper only until Hard Rock posts a price."
            )
        else:
            hr = american(hr_price)
            action = (
                f"Wait: Hard Rock’s {hr} can’t be judged — no other book or exchange is priced at "
                f"{fmt(hr_line)}. Paper only until a comparable price appears."
            )
    elif blocker == "qb_out":
        action = "Wait: a starting QB is listed out — re-check the number after the news settles."
    else:
        g = gap or 0
        action = (
            f"Pass: the line is only {fmt(g)} above our number; needs {fmt(k_line)} or higher."
            if g > 0
            else f"Pass: the line is {fmt(abs(g))} below our number (leans over); needs {fmt(k_line)} or higher."
        )

    # --- why (2-4 plain sentences) ---------------------------------------------
    why: List[str] = [
        _gap_sentence(has_model, bv_line, hr_line, market_line, reference_line, gap),
        _price_sentence(hr_line, hr_price, ev, ev_v),
    ]
    if hr_line is not None and m["hr_open"] is not None and abs(m["hr_open"] - hr_line) >= 0.05:
        moved = "up" if hr_line > m["hr_open"] else "down"
        why.append(
            f"Hard Rock opened at {fmt(m['hr_open'])} and has moved {moved} to {fmt(hr_line)}."
        )
    d = m["hr_vs_market"]
    if d is not None and abs(d) >= 0.05:
        why.append(
            f"Hard Rock’s {fmt(hr_line)} is {fmt(abs(d))} points {'above' if d > 0 else 'below'} "
            f"the other books’ median ({fmt(hr_line - d)}) — a {'better' if d > 0 else 'worse'} "
            "number for an under."
        )
    if qb_out:
        why.append(
            "QB OUT (live Rotowire, unofficial): "
            f"{qb_detail or 'a starting quarterback is listed out'}. "
            "The model’s number does not know this — re-check before betting."
        )

    return {
        "game_id": int(game["game_id"]),
        "away": game["away"],
        "home": game["home"],
        "kick": _iso(game.get("kick")),
        "tier": tier,
        "blocker": blocker,
        "hr_line": hr_line,
        "hr_price": hr_price,
        "hr_open": m["hr_open"],
        "market_line": market_line,
        "fair_under": None if fair_under is None else round(fair_under, 4),
        "fair_source": m["fair_source"],
        "hr_vs_market": m["hr_vs_market"],
        "ev": None if ev is None else round(ev, 4),
        "bv_line": None if bv_line is None else round2(bv_line),
        "gap": gap,
        "kill_line": k_line,
        "kill_price": k_price,
        "action": action,
        "why": why,
        "paper_logged": False,
        # paper ledger + weekly cap (apply_weekly_cap fills cap_rank / over_cap)
        "qualifies": qualifies,
        "paper_blocker": paper_blocker,
        "cap_rank": None,
        "over_cap": False,
        # inputs that failed for this game on this build (apply_degraded)
        "degraded_inputs": [],
        # display chips (not gates)
        "full_game_total": _num(game.get("total")),
        "spread": _num(game.get("spread")),
        "total_band": total_band(game.get("total")),
        "hook_side": hook_side(hr_line),
        "key_dist": key_dist(hr_line),
        # not part of the web contract; stripped by build_card, kept for the note.
        "_hr_hold": m["hr_hold"],
        "_market_hold": m["market_hold"],
        "_has_model": has_model,
    }


# --- the card ---------------------------------------------------------------------


def _sort_key(item: Dict) -> tuple:
    """BET, EDGE, PASS; within a tier by gap desc (the cap-5 rule the real-close
    backtest measured ranks by gap), then price, then kickoff."""
    ev = item["ev"] if item["ev"] is not None else -math.inf
    gap = item["gap"] if item["gap"] is not None else -math.inf
    return (TIER_ORDER[item["tier"]], -gap, -ev, item["kick"] or "", item["away"])


def apply_weekly_cap(
    items: List[Dict],
    held_game_ids: Optional[Set[int]] = None,
    prior_bet_game_ids: Optional[Set[int]] = None,
    cap: int = WEEKLY_BET_CAP,
) -> List[Dict]:
    """Rank the BET items for the week's real-money cap (docs/BETTING_POLICY.md:
    at most `cap` bets, ranked by gap). Items keep tier BET (every gate passed);
    the 6th+ get blocker "cap", over_cap True and a paper-only action.

    held_game_ids: BETs already logged this week (paper or real) keep their slot
    ahead of new arrivals — a decision made Thursday is not undone Saturday.
    prior_bet_game_ids: real bets this week on games NOT on this card (e.g. a
    Thursday game already played) — they consume slots too; ids that are on the
    card are ignored here (they rank through `held`). Mutates + returns.

    Rank key: (held-first, gap desc, ev desc, kickoff asc, away). Mirrored by
    postmortem.weekly_cap minus ev (historical rows carry none).

    Only BETs whose blocker is CLEAR are ranked: apply_degraded runs first and
    tags a bet built on a failed input with blocker "degraded", so a degraded
    bet consumes no weekly slot and the real bets below it rank 1..cap."""
    held = set(held_game_ids or ())
    bets = [it for it in items if it["tier"] == "BET" and it["blocker"] is None]
    on_card = {it["game_id"] for it in bets}
    used = len({g for g in (prior_bet_game_ids or ()) if g not in on_card})

    def key(it: Dict) -> tuple:
        ev = it["ev"] if it["ev"] is not None else -math.inf
        gap = it["gap"] if it["gap"] is not None else -math.inf
        return (0 if it["game_id"] in held else 1, -gap, -ev, it["kick"] or "", it["away"])

    for i, it in enumerate(sorted(bets, key=key)):
        rank = used + i + 1
        it["cap_rank"] = rank
        if rank > cap:
            it["over_cap"] = True
            it["blocker"] = "cap"
            it["action"] = (
                f"Over the weekly cap (#{rank} by gap): paper only — the card carries "
                f"{cap} real bets."
            )
    return items


# --- degraded inputs -------------------------------------------------------------


def _pred_factors(pred: Dict) -> Optional[Dict]:
    """The stored factors payload of a prediction row, or None when the row
    carries none. None means "cannot tell", NOT "missing": a caller that never
    loaded factors must not make every game read as degraded."""
    f = pred.get("factors")
    if f is None:
        f = pred.get("factors_json")
    if isinstance(f, str):
        try:
            f = json.loads(f)
        except (TypeError, ValueError):
            return None
    return f if isinstance(f, dict) else None


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _day_start(now: Optional[datetime]) -> Optional[datetime]:
    n = _naive_utc(now)
    return None if n is None else n.replace(hour=0, minute=0, second=0, microsecond=0)


def card_games(games: Sequence[Dict], now: Optional[datetime]) -> List[Dict]:
    """The games build_card will put on the card: kickoff strictly after `now`.
    Exposed so a caller can work out the degraded inputs for exactly that set
    without rebuilding the card."""
    now_n = _naive_utc(now)
    out = []
    for g in games:
        kick = _naive_utc(g.get("kick"))
        if kick is None or (now_n is not None and kick <= now_n):
            continue
        out.append(g)
    return out


def degraded_inputs(
    items: Sequence[Dict],
    *,
    sweep_status: Optional[Dict] = None,
    preview_status: Optional[Dict] = None,
    previews: Sequence[Dict] = (),
    predictions: Sequence[Dict] = (),
    tempo_rows: Optional[int] = None,
    now: Optional[datetime] = None,
) -> List[Dict]:
    """Which of DEGRADED_INPUTS failed for this card, and on which games.

    `items` only needs a game_id per entry — card items or the `card_games`
    rows they are built from. Every returned game id is on this card.

    sweep_status / preview_status: the JSON scripts/poll_lines.py and
    scripts/research_preview.py write with --status-file. None (the file was
    never written because the step did not run) is NOT a failure — only a
    status that says so is.
    previews:    {game_id, updated_at} rows on file (a preview last written
                 before today is a stale QB read).
    predictions: the model rows, with their stored `factors` (or factors_json).
    tempo_rows:  how many tempo rows the pace lookup can see; 0 = the table
                 stored nothing. None = not checked.
    """
    card_ids = {int(it["game_id"]) for it in items}
    out: List[Dict] = []
    if not card_ids:
        return out

    def add(name: str, detail: str, ids: Sequence[int]) -> None:
        out.append({"input": name, "detail": detail, "game_ids": sorted(set(ids))})

    # sweep: the games the run never reached carry a stale/absent HR number.
    if sweep_status is not None and not sweep_status.get("complete", True):
        unpolled = [
            int(g) for g in (sweep_status.get("unpolled_game_ids") or []) if int(g) in card_ids
        ]
        # Unknown coverage (an old status file, or a stop before the ids were
        # known) means we cannot say which games are stale — assume all of them.
        ids = unpolled or sorted(card_ids)
        reason = sweep_status.get("reason") or "incomplete"
        polled = sweep_status.get("events_polled")
        total = sweep_status.get("events_in_window")
        where = f" after {polled} of {total} events" if polled is not None else ""
        add("sweep", f"stopped early ({reason}){where}", ids)

    # preview: the QB-out gate reads whatever preview is on file, and a blank
    # file passes EVERY game. Affected = no preview, or one written before today.
    if preview_status is not None and not preview_status.get("ok", True):
        cutoff = _day_start(now)
        fresh = set()
        for p in previews:
            gid = int(p["game_id"])
            up = _naive_utc(p.get("updated_at"))
            if up is not None and (cutoff is None or up >= cutoff):
                fresh.add(gid)
        ids = sorted(card_ids - fresh)
        reason = preview_status.get("reason") or "failed"
        add("preview", f"{reason}: {len(ids)} games with no QB read from today", ids)

    # pace / weather: per-game model inputs, read off the stored factors.
    model_ids: Set[int] = set()
    no_pace: List[int] = []
    no_weather: List[int] = []
    for p in predictions:
        gid = int(p["game_id"])
        if gid not in card_ids or p.get("model_version") != MODEL_VERSION:
            continue
        if _num(p.get("bv_line")) is None:
            continue
        model_ids.add(gid)
        f = _pred_factors(p)
        if f is None:
            continue
        if _blank(f.get("pace")):
            no_pace.append(gid)
        # _weather_str returns "Dome" for a dome, so a blank weather on a game
        # that is not KNOWN to be a dome is a genuinely missing forecast.
        if _blank(f.get("weather")) and f.get("dome") is not True:
            no_weather.append(gid)
    if no_pace:
        add("pace", f"{len(no_pace)} model games have no pace read", no_pace)
    if no_weather:
        add("weather", f"{len(no_weather)} outdoor model games have no weather", no_weather)

    # tempo: the whole pace lookup is empty, so no game has a real pace.
    if tempo_rows is not None and tempo_rows == 0 and model_ids:
        add("tempo", "the tempo table stored 0 rows", sorted(model_ids))

    order = {name: i for i, name in enumerate(DEGRADED_INPUTS)}
    out.sort(key=lambda d: order.get(d["input"], len(order)))
    return out


def apply_degraded(items: Sequence[Dict], degraded: Sequence[Dict]) -> List[Dict]:
    """Tag every item a failed input touched: blocker "degraded", the inputs
    that failed, and a paper-only action. The TIER is unchanged — the read is
    still the read; what changed is that we cannot trust the inputs behind it.

    Runs BEFORE apply_weekly_cap so a degraded bet consumes no weekly slot.
    Mutates + returns `items`."""
    by_game: Dict[int, List[str]] = {}
    for d in degraded:
        name = d.get("input")
        if not name:
            continue
        for gid in d.get("game_ids") or ():
            by_game.setdefault(int(gid), []).append(name)
    order = {name: i for i, name in enumerate(DEGRADED_INPUTS)}
    for it in items:
        names = by_game.get(int(it["game_id"]))
        if not names:
            continue
        uniq = sorted(set(names), key=lambda n: (order.get(n, len(order)), n))
        it["degraded_inputs"] = uniq
        it["blocker"] = DEGRADED_BLOCKER
        if it.get("qualifies"):
            it["paper_blocker"] = DEGRADED_BLOCKER
        it["action"] = (
            f"Degraded inputs ({', '.join(uniq)}): paper only — re-check Hard Rock’s "
            "number and the QB report yourself before betting."
        )
    return list(items)


def hold_note(items: Sequence[Dict]) -> Optional[str]:
    """One sentence when Hard Rock's average hold across the slate is worse than
    the other books' by HOLD_NOTE_CENTS or more; None otherwise."""
    pairs = [
        (it["_hr_hold"], it["_market_hold"])
        for it in items
        if it.get("_hr_hold") is not None and it.get("_market_hold") is not None
    ]
    if not pairs:
        return None
    hr = statistics.mean(p[0] for p in pairs)
    mk = statistics.mean(p[1] for p in pairs)
    if hr - mk < HOLD_NOTE_CENTS:
        return None
    return (
        f"Hard Rock’s average hold on this slate is {hr * 100:.1f}% vs {mk * 100:.1f}% at the "
        f"other books — about {(hr - mk) * 100:.0f} cents more per dollar of vig, so a fair "
        "price there is rarer than the gap alone suggests."
    )


def build_card(
    games: Sequence[Dict],
    snapshots: Sequence[Dict],
    predictions: Sequence[Dict],
    previews: Sequence[Dict],
    *,
    season: int,
    week: int,
    now: datetime,
    held_game_ids: Optional[Set[int]] = None,
    prior_bet_game_ids: Optional[Set[int]] = None,
    slot: Optional[str] = None,
    degraded: Sequence[Dict] = (),
) -> Dict[str, Any]:
    """The card payload for one week.

    games:       {game_id, away, home, kick: datetime (UTC), total?, spread?}
    snapshots:   every 1H_total odds row for those games:
                 {game_id, book, line, over_price, under_price, captured_at}
    predictions: {game_id, model_version, bv_line, line_used} — the gbm_v1 row
                 (with bv_line) is the model read; a derived_lines row (or the
                 gbm_v1 line_used) is the reference line when no book has posted.
    previews:    {game_id, qb_out, qb_out_detail}
    slot:        which build wrote this card (beatvegas.ci.CARD_STATUS_BY_SLOT);
                 None on an ad-hoc build.
    degraded:    the failed inputs from `degraded_inputs`. Any entry makes the
                 card status "degraded" and every game it touched paper only.
    Only games kicking off after `now` are on the card.
    """
    now_n = _naive_utc(now)
    snaps_by_game: Dict[int, List[Dict]] = {}
    for sn in snapshots:
        snaps_by_game.setdefault(int(sn["game_id"]), []).append(sn)
    model_by_game: Dict[int, Dict] = {}
    reference_by_game: Dict[int, float] = {}
    for p in predictions:
        gid = int(p["game_id"])
        mv = p.get("model_version")
        if mv == MODEL_VERSION and _num(p.get("bv_line")) is not None:
            model_by_game[gid] = p
        if mv == REFERENCE_MODEL_VERSION and _num(p.get("line_used")) is not None:
            reference_by_game[gid] = _num(p["line_used"])
        elif mv == MODEL_VERSION and gid not in reference_by_game and _num(p.get("line_used")):
            reference_by_game[gid] = _num(p["line_used"])
    preview_by_game = {int(p["game_id"]): p for p in previews}

    items: List[Dict] = []
    for g in games:
        kick = _naive_utc(g.get("kick"))
        if kick is None or kick <= now_n:
            continue
        gid = int(g["game_id"])
        items.append(
            build_item(
                g,
                snaps_by_game.get(gid, []),
                model_by_game.get(gid),
                reference_by_game.get(gid),
                preview_by_game.get(gid),
                now_n,
            )
        )
    items.sort(key=_sort_key)
    # Degrade FIRST: a bet built on a failed input is paper only, so it must
    # not consume one of the week's real-money cap slots.
    deg = [
        {
            "input": d.get("input"),
            "detail": d.get("detail") or "",
            "game_ids": sorted({int(g) for g in (d.get("game_ids") or ())}),
        }
        for d in degraded
        if d.get("input")
    ]
    apply_degraded(items, deg)
    apply_weekly_cap(items, held_game_ids, prior_bet_game_ids)

    model_read = any(it["_has_model"] for it in items)
    notes: List[str] = []
    if items and not model_read:
        notes.append(
            "No model read this week (weeks 1-2): every call below is a price read, not a model bet."
        )
    if items and all(it["hr_line"] is None for it in items):
        notes.append("Hard Rock has not posted a first-half line on any game yet.")
    note = hold_note(items)
    if note:
        notes.append(note)

    public = [{k: v for k, v in it.items() if not k.startswith("_")} for it in items]
    # counts.bet = bettable BETs (inside the weekly cap): what the site and the
    # Saturday text read. Over-cap BETs keep tier BET but are tallied apart.
    counts = {
        "bet": sum(1 for it in public if it["tier"] == "BET" and not it["over_cap"]),
        "edge": sum(1 for it in public if it["tier"] == "EDGE"),
        "pass": sum(1 for it in public if it["tier"] == "PASS"),
        "over_cap": sum(1 for it in public if it["over_cap"]),
        "degraded": sum(1 for it in public if it["blocker"] == DEGRADED_BLOCKER),
    }
    paper = {
        "qualifying": sum(1 for it in public if it["qualifies"]),
        "over_cap": sum(1 for it in public if it["over_cap"]),
        "cap": WEEKLY_BET_CAP,
    }
    return json_clean(
        {
            "season": int(season),
            "week": int(week),
            "built_at": _iso(now),
            "model_read": model_read,
            "slot": slot,
            # A failed input beats the slot's own status: the site's banner and
            # the Saturday text both key off this one word.
            "status": ("degraded" if deg else CARD_STATUS_BY_SLOT.get(slot or "", "final")),
            "degraded": deg,
            "counts": counts,
            "paper": paper,
            "items": public,
            "notes": notes,
        }
    )
