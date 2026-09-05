"""The weekly bet card — PURE logic, no DB.

`build_card` turns plain rows (games, 1H odds snapshots, predictions, previews)
into the card payload the Board renders (`cards.payload`). The rules mirror
web/lib/edge.ts + verdict.ts + lineCheck.ts EXACTLY so the card and the site
never disagree about a game:

  * gap basis  = Hard Rock's 1H line if posted, else the market median, else the
                 derived reference line baked in at scoring time;
  * BET        = model read AND Hard Rock posted AND Hard Rock's own gap >=
                 BET_GAP_PTS AND price fair-or-better (ev >= EV_FLOOR; an
                 unjudgeable price is not a failure, as on the site) AND NOT an
                 off-market number AND no QB listed out;
  * EDGE       = the edge score clears 60 (gap + price bonus, minus the
                 off-market / QB-out penalties) with one gate failing — the
                 blocker names it — or a no-model row where Hard Rock's price
                 alone beats the market's fair price ("price only");
  * PASS       = everything else.

Docs: docs/BETTING_POLICY.md ("The board"). Tests: tests/test_card.py.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .devig import devig_two_way, ev_under
from .hardrock import HR_BOOK_KEY, normalize_book
from .model.score import BET_GAP_PTS, EV_FLOOR, HR_OFF_MARKET_PTS, MODEL_VERSION

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

# Books that never enter the market fair price: Hard Rock (it is the book being
# judged), the sweepstakes book, CFBD's synthetic aggregate and the ~0-vig
# exchanges (their prices are not a comparable two-way hold).
FAIR_PRICE_EXCLUDED = frozenset(
    {HR_BOOK_KEY, "fliff", "consensus", "kalshi", "polymarket", "novig", "prophetx", "betopenly"}
)
# CFBD's synthetic aggregate is not a book anyone can bet and double-counts the
# real ones: it never enters the market line either (web/lib/books.ts).
SYNTHETIC_BOOKS = frozenset({"consensus"})

TIER_ORDER = {"BET": 0, "EDGE": 1, "PASS": 2}
REFERENCE_MODEL_VERSION = "derived_lines"


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


def market_read(snaps: Sequence[Dict]) -> Dict[str, Any]:
    """Hard Rock's line/price/open, the market median line, and the market's
    no-vig fair under at Hard Rock's SAME number (median over comparable books,
    FAIR_PRICE_EXCLUDED dropped). Also each side's hold for the slate note."""
    by_book = _latest_by_book(snaps)
    hr = by_book.get(HR_BOOK_KEY)
    hr_line = hr["line"] if hr else None
    lines = [o["line"] for b, o in by_book.items() if b not in SYNTHETIC_BOOKS]
    comparable = [
        _fair_under_of(o)
        for b, o in by_book.items()
        if b not in FAIR_PRICE_EXCLUDED
        and hr_line is not None
        and abs(o["line"] - hr_line) <= 0.5  # same window as web/lib/lineCheck.ts
        and _fair_under_of(o) is not None
    ]
    fair_under = _median(comparable)
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
) -> Dict[str, Any]:
    """One card item for one game (the edge.ts rules, minus the context-only
    score, which never decides a tier)."""
    m = market_read(snaps)
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

    is_bet = (
        has_model
        and hr_gap is not None
        and hr_gap >= BET_GAP_PTS
        and not off_market
        and not price_neg
        and not qb_out
    )
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
        "ev": None if ev is None else round(ev, 4),
        "bv_line": None if bv_line is None else round2(bv_line),
        "gap": gap,
        "kill_line": k_line,
        "kill_price": k_price,
        "action": action,
        "why": why,
        "paper_logged": False,
        # not part of the web contract; stripped by build_card, kept for the note.
        "_hr_hold": m["hr_hold"],
        "_market_hold": m["market_hold"],
        "_has_model": has_model,
    }


# --- the card ---------------------------------------------------------------------


def _sort_key(item: Dict) -> tuple:
    ev = item["ev"] if item["ev"] is not None else -math.inf
    gap = item["gap"] if item["gap"] is not None else -math.inf
    return (TIER_ORDER[item["tier"]], -ev, -gap, item["kick"] or "", item["away"])


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
) -> Dict[str, Any]:
    """The card payload for one week.

    games:       {game_id, away, home, kick: datetime (UTC)}
    snapshots:   every 1H_total odds row for those games:
                 {game_id, book, line, over_price, under_price, captured_at}
    predictions: {game_id, model_version, bv_line, line_used} — the gbm_v1 row
                 (with bv_line) is the model read; a derived_lines row (or the
                 gbm_v1 line_used) is the reference line when no book has posted.
    previews:    {game_id, qb_out, qb_out_detail}
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
            )
        )
    items.sort(key=_sort_key)

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
    counts = {
        "bet": sum(1 for it in public if it["tier"] == "BET"),
        "edge": sum(1 for it in public if it["tier"] == "EDGE"),
        "pass": sum(1 for it in public if it["tier"] == "PASS"),
    }
    return json_clean(
        {
            "season": int(season),
            "week": int(week),
            "built_at": _iso(now),
            "model_read": model_read,
            "counts": counts,
            "items": public,
            "notes": notes,
        }
    )
