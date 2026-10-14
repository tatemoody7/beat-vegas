"""H-ARM-EVP, the EXPLORATORY value-at-price collector (docs/HYPOTHESES.md;
docs/program/EVP_SPEC_2026-10.md; Tate's call of 2026-10-14, option A).

Not a registered arm: no ledger slot, no alpha, no SPRT, not in
`protocol.ARMS`. It logs a paper first-half UNDER into challenger_picks (arm
'H-ARM-EVP') when the estimated value at Hard Rock's price is +2% or more, so
the judge (`consensus.py`, cv1) reads it exactly as it reads every other paper
pick. The January 2027 review decides whether a confirmatory 2027 arm is
registered; nothing is adopted from these rows.

The rule, exactly as the spec states it (and as the development replay of
weeks 4-7 computed it -- that replay is development evidence and wrote no row):

1. Eligible: Hard Rock's newest 1H quote is its main line (`hr_centred`), its
   under is priced (`hr_price`), the card has a vig-free fair under at Hard
   Rock's line (`fair_under`), the market's centre (`market_line`) and the
   model's number (`bv_line`).
2. Fair centre: the market centre M moved toward the model's number B by the
   frozen blend weight, shift s = (1 - w) * (M - B), w = 0.80 (docs/BLEND.md,
   H3A, fitted on 2023-25; a constant here, so no refit can move it).
   s > 0 (the model below the market) moves the distribution DOWN: more unders.
3. Fair chance of the under at Hard Rock's line L: the market's unconditional
   under chance at L (`consensus.convert_under` on the frozen hp1 table at
   centre M), plus the mass the shift moves across L, each integer's mass
   spread evenly over [k - 0.5, k + 0.5]. Bounded to [0, 1 - P(push)].
4. Value at Hard Rock's under price: `consensus.ev_per_unit` (a push returns the
   stake on a whole-number line).
5. Log when ev >= +2%. Uncapped; one pick per game, at its first qualifying
   build inside the paper window; scheduled builds only (a manual build runs no
   arm). M, B, w, s, the fair chance, the push chance and ev are frozen in
   `factors_json_at_pick`.

Missing or uncertain inputs never qualify: any missing field, or an hp1 table
that does not cover the line and the shift, leaves the game unread (counted in
the build line by reason) rather than logged.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from . import consensus as C
from .card import parse_kick
from .challenger_picks import add_challenger_pick
from .hardrock import HR_BOOK_KEY
from .wx_paper import _in_window, _logged

ARM_EVP = "H-ARM-EVP"
# Frozen 2026-10-14: the H3A fit (docs/BLEND.md), pinned by tests/test_evp_paper.py.
EVP_BLEND_W = 0.80
EVP_MIN_EV = 0.02  # Tate's threshold, fixed before the first build
EVP_MARKET = "1H_total"  # the hp1 table's first-half market

# Why a game on the card was not read (the build line counts them).
SKIP_NOT_MAIN = "not_main_line"
SKIP_NO_PRICE = "no_price"
SKIP_NO_FAIR = "no_fair_under"
SKIP_NO_MARKET = "no_market_line"
SKIP_NO_MODEL = "no_model"
SKIP_TABLE = "outside_table"


def shift_points(market_line: float, bv_line: float, w: float = EVP_BLEND_W) -> float:
    """s = (1 - w) * (M - B): how far the fair centre sits BELOW the market's."""
    return (1.0 - w) * (float(market_line) - float(bv_line))


def shifted_under(
    mass: Mapping[int, float], line: float, q_decided: float, s: float
) -> Optional[float]:
    """The unconditional chance of the under at `line` once the market's
    distribution moves down by `s` points (s < 0 moves it up). None when the
    table does not cover the line and every integer the shift crosses."""
    lo, hi = (line, line + s) if s >= 0 else (line + s, line)
    if not C._covers(mass, lo - 0.5, hi + 0.5):
        return None
    u = C.convert_under(mass, line, q_decided, line)
    if u is None:
        return None
    moved = 0.0
    for k, p in mass.items():
        overlap = max(0.0, min(hi, k + 0.5) - max(lo, k - 0.5))
        moved += p * overlap
    u = u + moved if s >= 0 else u - moved
    return min(max(u, 0.0), 1.0 - C.push_mass(mass, line))


def evaluate(it: Mapping[str, Any], table) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(the frozen read, None) for a readable card item, else (None, reason)."""
    if not it.get("hr_centred") or it.get("hr_line") is None:
        return None, SKIP_NOT_MAIN
    if it.get("hr_price") is None:
        return None, SKIP_NO_PRICE
    if it.get("fair_under") is None:
        return None, SKIP_NO_FAIR
    if it.get("market_line") is None:
        return None, SKIP_NO_MARKET
    if it.get("bv_line") is None:
        return None, SKIP_NO_MODEL
    line, price = float(it["hr_line"]), int(it["hr_price"])
    m, b = float(it["market_line"]), float(it["bv_line"])
    mass = table.mass(EVP_MARKET, m) if table is not None else {}
    s = shift_points(m, b)
    p_under = shifted_under(mass, line, float(it["fair_under"]), s)
    if p_under is None:
        return None, SKIP_TABLE
    p_push = C.push_mass(mass, line)
    ev = C.ev_per_unit(p_under, p_push, price)
    return {
        "market_line": m,
        "bv_line": b,
        "w": EVP_BLEND_W,
        "shift": round(s, 4),
        "hr_line": line,
        "hr_price": price,
        "fair_under_decided": float(it["fair_under"]),
        "fair_source": it.get("fair_source"),
        "p_under": round(p_under, 6),
        "p_push": round(p_push, 6),
        "ev": None if ev is None else round(ev, 6),
        "min_ev": EVP_MIN_EV,
        "table": C.HALFPOINT_VERSION,
        "table_center": table.nearest_center(EVP_MARKET, m) if table is not None else None,
    }, None


def qualifies(read: Optional[Mapping[str, Any]]) -> bool:
    return read is not None and read.get("ev") is not None and float(read["ev"]) >= EVP_MIN_EV


def log_first_half(
    session,
    card: Dict,
    now: datetime,
    window_hours: Optional[float] = None,
    predictions: Sequence[Dict] = (),
    table=None,
) -> Dict[str, Any]:
    """H-ARM-EVP: a paper first-half UNDER at Hard Rock's main line and under
    price on every game in the build's window whose value at that price is
    EVP_MIN_EV or more. Returns the build line's counts."""
    from .model.score import MODEL_VERSION  # local: the card already loaded the model

    t = table if table is not None else C.default_table()
    refit_by_game = {
        int(p["game_id"]): p.get("refit_id")
        for p in predictions
        if p.get("model_version") == MODEL_VERSION
    }
    logged = _logged(session, ARM_EVP)
    items = card.get("items", [])
    read = qualifying = added = 0
    skipped: Dict[str, int] = {}
    for it in items:
        r, why = evaluate(it, t)
        if r is None:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        read += 1
        if not qualifies(r):
            continue
        qualifying += 1
        gid = int(it["game_id"])
        if gid in logged or not _in_window(parse_kick(it.get("kick")), now, window_hours):
            continue
        add_challenger_pick(
            session,
            arm=ARM_EVP,
            game_id=gid,
            season=int(card["season"]),
            week=int(card["week"]),
            home_team=it["home"],
            away_team=it["away"],
            side="under",
            market="1H",
            line=r["hr_line"],
            price=r["hr_price"],
            book=HR_BOOK_KEY,
            slot=card.get("slot"),
            placed_at=now,
            arm_line_at_pick=r["bv_line"],
            champion_line_at_pick=r["bv_line"],
            gap_at_pick=None if it.get("gap") is None else float(it["gap"]),
            factors_json_at_pick=json.dumps(r, sort_keys=True),
            refit_id=refit_by_game.get(gid),
        )
        logged.add(gid)
        added += 1
    return {
        "items": len(items),
        "read": read,
        "qualifying": qualifying,
        "added": added,
        "skipped": skipped,
    }


def summary_lines(stats: Optional[Dict[str, Any]]) -> List[str]:
    """The card summary's line about the exploratory collector."""
    tag = (
        f"  EXPLORATORY {ARM_EVP} (paper first-half unders at EV >= +{EVP_MIN_EV:.0%} "
        "at Hard Rock's price; no alpha, never a reading for an arm)"
    )
    if not stats:
        return [f"{tag}: not run"]
    skipped = stats.get("skipped") or {}
    why = ", ".join(f"{k} {v}" for k, v in sorted(skipped.items())) or "none"
    return [
        f"{tag}: {stats.get('qualifying', 0)} of {stats.get('read', 0)} games read qualify, "
        f"+{stats.get('added', 0)} logged; not read: {why}"
    ]
