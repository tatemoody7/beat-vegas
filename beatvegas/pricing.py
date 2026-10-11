"""H-PRICE-HR (docs/HYPOTHESES.md, exploratory; docs/PRICING_RESEARCH.md): is Hard
Rock's price ever better than the vig-free market reference at the same moment?

Pure functions over odds_snapshots rows, reusing the consensus engine
(beatvegas/consensus.py: the half-point table, line conversion, EV at terms)
and the de-vig (beatvegas/devig.py). Nothing here writes, and nothing an arm,
the judge or the card reads imports this module. The I/O is
scripts/pricing_check.py (study.yml).

THE FROZEN RULE `pv1` (Tate 2026-10-11; a change is `pv2`, read beside it, never
in place):
  - Hard Rock's MAIN quote only (devig.is_hr_rung: no price at -140 or worse, not
    2+ points off the field's median with 3+ books).
  - The reference is every other centred book (Fliff and the feed's consensus
    row excluded) whose quote is CONFIRMED PRESENT at the capture minute: its
    latest row captured at or before that minute, re-seen at or after it
    (last_seen_at) or captured in the same minute. MIN_BOOKS = 3.
  - Totals: each reference quote de-vigged (multiplicative) and converted to
    Hard Rock's exact line through the frozen table (within MAX_CONVERT_PTS);
    the median of the converted under-probabilities is the fair under. A flag
    needs EV >= EV_FLAG at the LOWER bound of the table's integer masses
    (CONSERVATIVE_Z): a one-point line difference is worth one integer's mass,
    and that mass carries sampling error.
  - Moneylines: each reference book's de-vigged home probability, the median is
    fair; no line conversion. Only games where BOTH of Hard Rock's prices sit
    within ML_MAX_ABS_PRICE (+/-200): on lopsided lines the multiplicative de-vig
    overstates the longshot's fair chance (the favourite-longshot bias), and the
    first local read (2026-10-11) flagged 18 longshots at +275 to +1100 and
    nothing else, so that range is reported as a drop, not compared.
    Spreads are NOT compared: the frozen table has no
    spread market, so two spreads one point apart cannot be priced against each
    other honestly.
  - One opportunity per game-side: the FIRST qualifying price state.

EVIDENCE TIERS (every flag carries one; tiers 0-1 are feed observations and are
never called available in Florida):
  0  one feed observation
  1  the provider's stamp within FRESH_MIN of our capture AND the price re-seen
     at a later poll (quoted and persisting; NOT "available between polls")
  2  a Florida-app screenshot within 10 minutes with the same line and prices
  3  a ticket at that price
Tiers 2 and 3 come from Tate's records, never from this code.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from . import consensus as C
from .devig import devig_two_way, is_centred_quote, is_hr_rung
from .hardrock import HR_BOOK_KEY

RULE_VERSION = "pv1"
ROW_ID = "H-PRICE-HR"
MIN_BOOKS = C.MIN_BOOKS  # 3
MAX_CONVERT_PTS = C.MAX_CONVERT_PTS  # 1.5
DEVIG = "multiplicative"
EV_FLAG = 0.02
CONSERVATIVE_Z = 1.96
GRACE_MIN = 0  # a reference quote must be confirmed at the capture minute
FRESH_MIN = 5  # tier 1 needs the provider's stamp this close to our capture
ML_MAX_ABS_PRICE = 200  # moneylines compared only when both HR prices are within +/-200
EXCLUDED_BOOKS = frozenset({HR_BOOK_KEY, "fliff", "consensus"})
TOTALS_MARKETS = ("1H_total", "full_game_total")
SIDE_MARKETS = ("full_game_ml",)
MARKETS = TOTALS_MARKETS + SIDE_MARKETS
REFUSED_MARKETS = {
    "full_game_spread": "no frozen half-point table for spreads: lines cannot be converted"
}
_ET = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")


@dataclass
class Snap:
    """The columns of odds_snapshots this study reads."""

    game_id: int
    book: str
    market: str
    line: Optional[float]
    over_price: Optional[int]
    under_price: Optional[int]
    home_price: Optional[int]
    away_price: Optional[int]
    captured_at: datetime
    last_seen_at: Optional[datetime] = None
    feed_updated_at: Optional[datetime] = None
    feed_reseen_at: Optional[datetime] = None


@dataclass
class GameRow:
    id: int
    week: Optional[int]
    home: str
    away: str
    kickoff: datetime
    home_points: Optional[int] = None
    away_points: Optional[int] = None
    first_half_total: Optional[int] = None


# --- the table's sampling error ---------------------------------------------------


class MassTable:
    """The frozen half-point table plus each centre's game count, so a lower-bound
    mass can be formed: m - z*sqrt(m(1-m)/n), floored at zero."""

    def __init__(self, data: Mapping[str, Any]):
        self.table = C.HalfPointTable(data)
        self._n: Dict[str, Dict[float, int]] = {}
        for market, spec in data["markets"].items():
            self._n[market] = {float(c): int(e.get("n") or 0) for c, e in spec["centers"].items()}

    @classmethod
    def load(cls, path=None) -> "MassTable":
        p = path or C.HALFPOINT_PATH
        return cls(json.loads(p.read_text()))

    def mass(self, market: str, center: float, conservative: bool) -> Dict[int, float]:
        c = self.table.nearest_center(market, center)
        if c is None:
            return {}
        mass = self.table.mass(market, center)
        if not conservative:
            return mass
        n = self._n.get(market, {}).get(c, 0)
        if n <= 0:
            return mass
        return {
            k: max(0.0, m - CONSERVATIVE_Z * math.sqrt(m * (1.0 - m) / n)) for k, m in mass.items()
        }


# --- references and EV -----------------------------------------------------------


def _minute(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)


def reference_quotes(
    game_snaps: Sequence[Snap], market: str, t: datetime, grace_min: int = GRACE_MIN
) -> List[Snap]:
    """Each other book's quote as of `t`: its latest row captured at or before t,
    confirmed present at t (captured in t's minute, or last_seen_at >= t), with a
    `grace_min` allowance for staleness (0 under pv1). Centred quotes only."""
    best: Dict[str, Snap] = {}
    for s in game_snaps:
        if s.market != market or s.book in EXCLUDED_BOOKS or s.captured_at > t:
            continue
        if market in TOTALS_MARKETS:
            if s.line is None or not is_centred_quote(s.over_price, s.under_price):
                continue
        elif s.home_price is None or s.away_price is None:
            continue
        prev = best.get(s.book)
        if prev is None or s.captured_at > prev.captured_at:
            best[s.book] = s
    out = []
    for s in best.values():
        seen = s.captured_at
        if s.last_seen_at and s.last_seen_at > seen:
            seen = s.last_seen_at
        if _minute(s.captured_at) == _minute(t) or seen + timedelta(minutes=grace_min) >= t:
            out.append(s)
    return out


def ev_totals(
    hr: Snap, refs: Sequence[Snap], table: MassTable, conservative: bool
) -> Optional[Dict[str, Any]]:
    """EV of the over and the under at Hard Rock's exact line and prices against the
    median of the references converted to that line. None without MIN_BOOKS usable
    references or when the table does not cover the move."""
    usable = [
        r for r in refs if r.line is not None and abs(r.line - hr.line) <= MAX_CONVERT_PTS + 1e-9
    ]
    if len(usable) < MIN_BOOKS:
        return None
    center = round(statistics.median(r.line for r in usable) * 2) / 2
    mass = table.mass(hr.market, center, conservative)
    unders = []
    for r in usable:
        _, fu, _ = devig_two_way(int(r.over_price), int(r.under_price), DEVIG)
        u = C.convert_under(mass, float(r.line), fu, float(hr.line))
        if u is None:
            return None
        unders.append(u)
    u_med = statistics.median(unders)
    p_push = C.push_mass(mass, float(hr.line))
    pw_u, pp = C.win_push(u_med, p_push, "under")
    pw_o, _ = C.win_push(u_med, p_push, "over")
    return {
        "books": len(usable),
        "ref_line": statistics.median(r.line for r in usable),
        "ev_under": C.ev_per_unit(pw_u, pp, hr.under_price),
        "ev_over": C.ev_per_unit(pw_o, pp, hr.over_price),
    }


def ev_moneyline(hr: Snap, refs: Sequence[Snap]) -> Optional[Dict[str, Any]]:
    """EV of each side at Hard Rock's moneyline prices against the median de-vigged
    home probability of the references. No line, so no conversion."""
    usable = [r for r in refs if r.home_price is not None and r.away_price is not None]
    if len(usable) < MIN_BOOKS or hr.home_price is None or hr.away_price is None:
        return None
    homes = [devig_two_way(int(r.home_price), int(r.away_price), DEVIG)[0] for r in usable]
    p_home = statistics.median(homes)
    return {
        "books": len(usable),
        "ref_line": None,
        "ev_home": C.ev_per_unit(p_home, 0.0, hr.home_price),
        "ev_away": C.ev_per_unit(1.0 - p_home, 0.0, hr.away_price),
    }


# --- price states ----------------------------------------------------------------


def evidence_tier(hr: Snap) -> int:
    """0 or 1 from the feed alone (see the module docstring); 2 and 3 never here."""
    fresh = (
        hr.feed_updated_at is not None
        and abs((hr.captured_at - hr.feed_updated_at).total_seconds()) <= FRESH_MIN * 60
    )
    reseen = hr.last_seen_at is not None and hr.last_seen_at > hr.captured_at
    return 1 if fresh and reseen else 0


TIER_LABEL = {
    0: "unverified: one feed observation",
    1: "unverified: quoted and re-seen (feed), not confirmed in the Florida app",
    2: "available in Florida (screenshot)",
    3: "bet in Florida (ticket)",
}


def _result_totals(g: GameRow, market: str, line: float, side: str) -> Optional[str]:
    total = (
        g.first_half_total
        if market == "1H_total"
        else (
            None
            if g.home_points is None or g.away_points is None
            else g.home_points + g.away_points
        )
    )
    if total is None:
        return None
    if total == line:
        return "push"
    return "win" if ((total < line) == (side == "under")) else "loss"


def _result_ml(g: GameRow, side: str) -> Optional[str]:
    if g.home_points is None or g.away_points is None:
        return None
    if g.home_points == g.away_points:
        return "push"
    return "win" if ((g.home_points > g.away_points) == (side == "home")) else "loss"


def _close_ev_totals(
    game_snaps: Sequence[Snap], g: GameRow, state: Dict[str, Any], table: MassTable
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    rows = [s for s in game_snaps if s.market == state["market"]]
    closes = C.book_closes(rows, g.kickoff)
    rd = C.read_at_terms(
        closes,
        g.kickoff,
        state["market"],
        state["hr_line"],
        state["side"],
        state["price"],
        table.table,
    )
    usable = [
        c for c in closes.values() if c.seen_at >= g.kickoff - timedelta(hours=C.CLOSE_WINDOW_H)
    ]
    line_clv = None
    if len(usable) >= MIN_BOOKS:
        med = statistics.median(c.line for c in usable)
        line_clv = (
            (state["hr_line"] - med) if state["side"] == "under" else (med - state["hr_line"])
        )
    return rd.ev, line_clv, rd.excluded


def _close_ev_ml(
    game_snaps: Sequence[Snap], g: GameRow, state: Dict[str, Any]
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    floor = g.kickoff - timedelta(hours=C.CLOSE_WINDOW_H)
    best: Dict[str, Snap] = {}
    for s in game_snaps:
        if s.market != "full_game_ml" or s.book in EXCLUDED_BOOKS or s.captured_at > g.kickoff:
            continue
        if s.home_price is None or s.away_price is None:
            continue
        prev = best.get(s.book)
        if prev is None or s.captured_at > prev.captured_at:
            best[s.book] = s
    fresh = []
    for s in best.values():
        seen = (
            max(s.captured_at, s.last_seen_at)
            if s.last_seen_at and s.last_seen_at <= g.kickoff
            else s.captured_at
        )
        if seen >= floor:
            fresh.append(s)
    if len(fresh) < MIN_BOOKS:
        return None, None, C.EX_STALE if best else C.EX_FEW_BOOKS
    p_home = statistics.median(
        devig_two_way(int(s.home_price), int(s.away_price), DEVIG)[0] for s in fresh
    )
    p = p_home if state["side"] == "home" else 1.0 - p_home
    return C.ev_per_unit(p, 0.0, state["price"]), None, None


def price_states(
    games: Mapping[int, GameRow],
    snaps_by_game: Mapping[int, Sequence[Snap]],
    market: str,
    table: MassTable,
    grace_min: int = GRACE_MIN,
) -> Tuple[List[Dict[str, Any]], Counter]:
    """Every pre-kickoff Hard Rock MAIN price state in `market` with a usable
    reference at its capture minute, with both EV readings (point and lower bound),
    the chosen side, the close reading, the realized result and the evidence tier.
    Drops are counted: rung, no_reference, outside_table."""
    if market in REFUSED_MARKETS:
        raise ValueError(
            f"{market} is not compared under {RULE_VERSION}: {REFUSED_MARKETS[market]}"
        )
    out: List[Dict[str, Any]] = []
    drops: Counter = Counter()
    for gid, gs in snaps_by_game.items():
        g = games.get(gid)
        if g is None:
            continue
        for s in gs:
            if s.book != HR_BOOK_KEY or s.market != market or s.captured_at >= g.kickoff:
                continue
            drops["hr_states"] += 1
            refs = reference_quotes(gs, market, s.captured_at, grace_min)
            if market in TOTALS_MARKETS:
                if s.line is None or s.over_price is None or s.under_price is None:
                    drops["unpriced"] += 1
                    continue
                if is_hr_rung(s.over_price, s.under_price, s.line, [r.line for r in refs]):
                    drops["rung"] += 1
                    continue
                point = ev_totals(s, refs, table, conservative=False)
                lower = ev_totals(s, refs, table, conservative=True)
                if point is None or lower is None:
                    drops["no_reference" if len(refs) < MIN_BOOKS else "outside_table"] += 1
                    continue
                side = "under" if point["ev_under"] >= point["ev_over"] else "over"
                ev_point = point[f"ev_{side}"]
                ev_lower = lower[f"ev_{side}"]
                price = s.under_price if side == "under" else s.over_price
                result = _result_totals(g, market, float(s.line), side)
            else:
                if s.home_price is None or s.away_price is None:
                    drops["unpriced"] += 1
                    continue
                if max(abs(s.home_price), abs(s.away_price)) > ML_MAX_ABS_PRICE:
                    drops["lopsided"] += 1
                    continue
                point = ev_moneyline(s, refs)
                if point is None:
                    drops["no_reference"] += 1
                    continue
                side = "home" if point["ev_home"] >= point["ev_away"] else "away"
                ev_point = ev_lower = point[f"ev_{side}"]
                price = s.home_price if side == "home" else s.away_price
                result = _result_ml(g, side)
            seen = max(s.captured_at, s.last_seen_at) if s.last_seen_at else s.captured_at
            tier = evidence_tier(s)
            state = {
                "rule": RULE_VERSION,
                "market": market,
                "game_id": gid,
                "week": g.week,
                "game": f"{g.away} @ {g.home}",
                "kickoff": g.kickoff,
                "captured_at": s.captured_at,
                "seen_polls_span_min": round((seen - s.captured_at).total_seconds() / 60, 1),
                "feed_lag_s": None
                if s.feed_updated_at is None
                else round((s.captured_at - s.feed_updated_at).total_seconds(), 1),
                "hr_line": s.line,
                "hr_over": s.over_price,
                "hr_under": s.under_price,
                "hr_home": s.home_price,
                "hr_away": s.away_price,
                "ref_line": point["ref_line"],
                "books": point["books"],
                "side": side,
                "price": price,
                "ev_ref": ev_point,
                "ev_ref_lower": ev_lower,
                "flag": ev_lower is not None and ev_lower >= EV_FLAG,
                "hrs_to_kick": round((g.kickoff - s.captured_at).total_seconds() / 3600, 2),
                "weekday_et": s.captured_at.replace(tzinfo=_UTC).astimezone(_ET).strftime("%a"),
                "tier": tier,
                "evidence": TIER_LABEL[tier],
                "result": result,
            }
            if market in TOTALS_MARKETS:
                ev_close, line_clv, excl = _close_ev_totals(gs, g, state, table)
            else:
                ev_close, line_clv, excl = _close_ev_ml(gs, g, state)
            state["ev_close"] = ev_close
            state["line_clv"] = line_clv
            state["close_excluded"] = excl
            # Did the market move toward Hard Rock by the close? Judged on EV, which
            # covers both line and price: toward = the wager's close EV fell below
            # its reference EV by more than a rounding sliver.
            if ev_close is None:
                state["market_moved"] = "unknown"
            elif ev_close < ev_point - 0.0025:
                state["market_moved"] = "toward_hr"
            elif ev_close > ev_point + 0.0025:
                state["market_moved"] = "away_from_hr"
            else:
                state["market_moved"] = "unchanged"
            out.append(state)
    return out, drops


def first_per_game_side(
    states: Iterable[Dict[str, Any]], flagged_only: bool = True
) -> List[Dict[str, Any]]:
    """One opportunity per (game, side): the FIRST qualifying price state in time."""
    seen = set()
    out = []
    for s in sorted(states, key=lambda r: r["captured_at"]):
        if flagged_only and not s["flag"]:
            continue
        key = (s["game_id"], s["side"])
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


# --- summaries ---------------------------------------------------------------------


def _mean_ci(xs: Sequence[Optional[float]]) -> Dict[str, Any]:
    v = [float(x) for x in xs if x is not None]
    if not v:
        return {"n": 0, "mean": None, "ci": None}
    m = sum(v) / len(v)
    if len(v) < 2:
        return {"n": len(v), "mean": m, "ci": None}
    h = 1.96 * statistics.stdev(v) / math.sqrt(len(v))
    return {"n": len(v), "mean": m, "ci": (m - h, m + h)}


def summarize_market(states: List[Dict[str, Any]], drops: Counter) -> Dict[str, Any]:
    """The per-market numbers the weekly report prints (counts, means, intervals)."""
    pos = [s for s in states if s["ev_ref"] > 0]
    ge1 = [s for s in states if s["ev_ref"] >= 0.01]
    ge2 = [s for s in states if s["ev_ref"] >= 0.02]
    flagged = [s for s in states if s["flag"]]
    opps = first_per_game_side(states)
    moved = Counter(s["market_moved"] for s in opps)
    rec = Counter(s["result"] for s in opps)
    by_hours = defaultdict(list)
    for s in states:
        h = s["hrs_to_kick"]
        by_hours[
            "<2h"
            if h < 2
            else "2-6h"
            if h < 6
            else "6-24h"
            if h < 24
            else "1-3d"
            if h < 72
            else ">3d"
        ].append(s)
    return {
        "states_compared": len(states),
        "games": len({s["game_id"] for s in states}),
        "drops": dict(drops),
        "mean_ev_ref": _mean_ci([s["ev_ref"] for s in states])["mean"],
        "ev_pos": len(pos),
        "ev_ge1_point": len(ge1),
        "ev_ge2_point": len(ge2),
        "flagged_lower_bound": len(flagged),
        "opportunities": len(opps),
        "opps_tiers": dict(Counter(s["tier"] for s in opps)),
        "opps_ev_ref": _mean_ci([s["ev_ref"] for s in opps]),
        "opps_ev_ref_lower": _mean_ci([s["ev_ref_lower"] for s in opps]),
        "opps_ev_close": _mean_ci([s["ev_close"] for s in opps]),
        "opps_line_clv": _mean_ci([s["line_clv"] for s in opps]),
        "opps_market_moved": dict(moved),
        "opps_record": dict(rec),
        "opps_units": round(
            sum(
                (C.american_to_decimal(s["price"]) - 1.0)
                if s["result"] == "win"
                else (-1.0 if s["result"] == "loss" else 0.0)
                for s in opps
                if s["result"]
            ),
            2,
        ),
        "by_hours_to_kick": {
            k: {
                "n": len(v),
                "flag_share": sum(1 for s in v if s["flag"]) / len(v),
                "mean_ev_ref": _mean_ci([s["ev_ref"] for s in v])["mean"],
            }
            for k, v in sorted(by_hours.items())
        },
        "by_weekday": {
            k: {"n": n, "flags": f}
            for k, (n, f) in sorted(
                {
                    d: (len(v), sum(1 for s in v if s["flag"]))
                    for d, v in _group(states, "weekday_et").items()
                }.items()
            )
        },
    }


def _group(states: Iterable[Dict[str, Any]], key: str) -> Dict[Any, List[Dict[str, Any]]]:
    g: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for s in states:
        g[s[key]].append(s)
    return g
