"""The Board's top-10 analysis (H-1H-SHORTLIST; website plan PR D, Tate 2026-10-15; reshaped
2026-10-16).

Each scheduled card saves one frozen analysis for EVERY game it rates; the site shows it on the game
page of the Board's #1-#10 (the green badges), so clicking a top-10 card opens the deeper read Tate
decides from. There is no second ranking: the Board's rank is the only one. Ported from the approved
prototype (`research/1h-factors-2026-10/proto.py`) with every pricing safeguard kept exactly:

- only Hard Rock's MAIN 1H line with a price (`hr_centred`) is ever priced; an alternate rung or a
  missing price is saved as "insufficient pricing data" with its reason, never filled in.
- price: estimated EV at Hard Rock's exact line and price against the consensus fair share, from
  reference books confirmed in the SAME sweep as Hard Rock's last confirmation
  (`pricing.reference_quotes`, grace 0), within 1.5 pts, converted through hp1; Hard Rock, Fliff and
  the feed's consensus row excluded; at least `consensus.MIN_BOOKS` (3) books.
- a Hard Rock price last confirmed more than `STALE_H` (6) hours ago, too few books, a line outside
  the conversion table or no matching Hard Rock snapshot is "insufficient pricing data".
- the rough range is a bootstrap over the books joined with hp1's conservative low; it is an
  ESTIMATE, not proof of profit, and narrower than the true uncertainty (books copy each other).
- no factor carries weight (H-1H-FACTORS: 64 screened, none passed). The analysis is descriptive
  and worded by scoring, never by the bet (Q5).

The core is pure (plain dicts in, a publication dict out); `load_inputs` is the only database
reader and `write_publication` the only writer (insert-only: a card publishes once).
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import random
import statistics as st
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import consensus as C
from . import pricing as PR
from .devig import devig_two_way

ROW_ID = "H-1H-SHORTLIST"
STALE_H = 6.0  # a Hard Rock price last confirmed longer ago than this is not priced
BOOT_DRAWS = 500
POTENTIAL_MIN_EV = 0.01  # the point estimate a "Potential positive market value" label needs
GAME_LEN = timedelta(hours=4)  # a game counts as finished 4 h after kickoff (build_frame.py)
HR_BOOK = "hardrockbet"
METHOD = (
    "every game the card rates; EV is an estimate; no factor weight (H-1H-FACTORS: 0 of 64 passed)"
)

LABEL_POTENTIAL = "Potential positive market value"
LABEL_FAIR = "Fair price"
LABEL_EXPENSIVE = "Expensive"
LABEL_INSUFFICIENT = "Insufficient pricing data"

REFERENCE_PATH = Path(__file__).resolve().parents[1] / "data" / "shortlist_reference.json"

# The eight descriptive stats beside each entry: (factor, words, the direction that points to LESS
# scoring: "low" = a low value, "high" = a high value). Percentiles are against the 2023-26 screen
# frame (data/shortlist_reference.json); a stat in the bottom or top third points to less or more
# scoring. Descriptive only: the screen found none of them beats the closing line.
CONTEXT: Tuple[Tuple[str, str, str], ...] = (
    ("std_fh_pf", "combined first-half points scored per game this season", "low"),
    ("std_fh_pa", "combined first-half points allowed per game this season", "low"),
    ("fh_off_epa", "combined first-half offensive EPA per play this season", "low"),
    ("fh_off_explosive", "combined first-half explosive-play rate this season", "low"),
    ("sec_per_play", "average seconds per play (pace)", "high"),
    ("plays_per_game", "combined plays per game", "low"),
    ("prior_sp_off", "combined SP+ offense rating (last season)", "low"),
    ("prior_sp_def", "combined SP+ defense rating (last season; lower = better defenses)", "low"),
)
SITUATIONAL = (
    "min_rest_days",
    "either_off_bye",
    "either_short_week",
    "away_travel_km",
    "kick_local_hour",
)
WIND_LESS_SCORING_MPH = 10.0


def parse_ts(s: Any) -> Optional[datetime]:
    """A naive-UTC datetime from a stored value (datetime, ISO text with or without Z)."""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s.replace(tzinfo=None)
    return datetime.fromisoformat(str(s).replace("Z", "")).replace(tzinfo=None)


def implied(price: int) -> float:
    """American price -> implied probability (vig included)."""
    return 100 / (price + 100) if price > 0 else -price / (-price + 100)


def confirmed_at(s: PR.Snap) -> datetime:
    """The last time the feed confirmed this exact quote: an unchanged price is re-stamped in
    last_seen_at, not re-written, so freshness is never the first capture."""
    return max(s.captured_at, s.last_seen_at or s.captured_at)


# --------------------------------------------------------------------------------------------- #
# Price
# --------------------------------------------------------------------------------------------- #
def _hr_snapshot(item: Mapping[str, Any], snaps: Sequence[PR.Snap]) -> Optional[PR.Snap]:
    """The Hard Rock snapshot the card read: captured at `hr_as_of`, same line and price."""
    hr_t = parse_ts(item.get("hr_as_of"))
    if hr_t is None:
        return None
    return next(
        (
            s
            for s in snaps
            if s.book == HR_BOOK
            and abs((s.captured_at - hr_t).total_seconds()) < 1
            and s.line == item["hr_line"]
            and s.under_price == item["hr_price"]
        ),
        None,
    )


def price_read(
    item: Mapping[str, Any],
    snaps: Sequence[PR.Snap],
    mass_table: PR.MassTable,
    now: datetime,
) -> Dict[str, Any]:
    """Hard Rock's under at the card's exact line and price, against the same sweep's books."""
    if not priceable(item):
        reason = (
            "Hard Rock was showing an alternate line at the build"
            if item.get("hr_line") is not None and not item.get("hr_centred")
            else "no Hard Rock main line and price at the build"
        )
        return {
            "hr_line": item.get("hr_line"),
            "hr_under": item.get("hr_price"),
            "hr_over": item.get("hr_over_price"),
            "hr_quote_at": item.get("hr_as_of"),
            "breakeven": None,
            "hr_hold": None,
            "status": f"insufficient pricing data ({reason})",
        }
    hr_price = int(item["hr_price"])
    over = item.get("hr_over_price")
    out: Dict[str, Any] = {
        "hr_line": item["hr_line"],
        "hr_under": hr_price,
        "hr_over": over,
        "hr_quote_at": item.get("hr_as_of"),
        "breakeven": implied(hr_price),
        "hr_hold": None if over is None else implied(hr_price) + implied(int(over)) - 1,
    }
    hr = _hr_snapshot(item, snaps)
    if hr is None:
        out["status"] = "no matching Hard Rock snapshot"
        return out
    confirmed = confirmed_at(hr)
    age_h = (now - confirmed).total_seconds() / 3600
    out["hr_age_h"] = age_h
    out["hr_confirmed_at"] = confirmed.isoformat()
    refs = PR.reference_quotes(snaps, "1H_total", confirmed, grace_min=0)
    usable = [
        r for r in refs if r.line is not None and abs(r.line - hr.line) <= C.MAX_CONVERT_PTS + 1e-9
    ]
    out["ref_books"] = sorted(r.book for r in usable)
    same_line = [r for r in usable if r.line == hr.line]
    out["best_other_under"] = max(
        (r.under_price for r in same_line), key=lambda p: -implied(p), default=None
    )
    if len(usable) < C.MIN_BOOKS:
        out["status"] = (
            f"insufficient pricing data ({len(usable)} reference books in the same sweep)"
        )
        return out
    point = PR.ev_totals(hr, usable, mass_table, conservative=False)
    cons = PR.ev_totals(hr, usable, mass_table, conservative=True)
    if (
        point is None
        or cons is None
        or point.get("ev_under") is None
        or cons.get("ev_under") is None
    ):
        out["status"] = "insufficient pricing data (line outside the conversion table)"
        return out
    center = round(st.median(r.line for r in usable) * 2) / 2
    mass = mass_table.mass("1H_total", center, False)
    unders = [
        C.convert_under(
            mass,
            float(r.line),
            devig_two_way(int(r.over_price), int(r.under_price), PR.DEVIG)[1],
            float(hr.line),
        )
        for r in usable
    ]
    push = C.push_mass(mass, float(hr.line))
    out["fair_under"] = st.median(unders) / (1 - push) if push < 1 else None
    rng = random.Random(int(item["game_id"]))
    boots: List[float] = []
    for _ in range(BOOT_DRAWS):
        smp = [rng.choice(usable) for _ in usable]
        e = PR.ev_totals(hr, smp, mass_table, conservative=False)
        if e and e.get("ev_under") is not None:
            boots.append(e["ev_under"])
    if not boots:
        out["status"] = "insufficient pricing data (no usable resample)"
        return out
    boots.sort()
    lo_b, hi_b = boots[int(0.05 * len(boots))], boots[int(0.95 * len(boots)) - 1]
    out.update(
        {
            "ev_point": point["ev_under"],
            "ev_table_low": cons["ev_under"],
            "range_low": min(lo_b, cons["ev_under"]),
            "range_high": hi_b,
            "ref_line": point["ref_line"],
        }
    )
    out["status"] = (
        f"insufficient pricing data (Hard Rock price {age_h:.0f} h old)"
        if age_h > STALE_H
        else "priced"
    )
    return out


def label(pr: Mapping[str, Any]) -> str:
    if pr.get("status") != "priced":
        return LABEL_INSUFFICIENT
    if pr["range_low"] > 0 and pr["ev_point"] >= POTENTIAL_MIN_EV:
        return LABEL_POTENTIAL
    if pr["range_high"] < 0:
        return LABEL_EXPENSIVE
    return LABEL_FAIR


def hr_history(snaps: Sequence[PR.Snap]) -> Tuple[Optional[dict], Optional[dict]]:
    """Hard Rock's first quote on file and its newest, each with the time it was last confirmed."""
    sn = sorted((s for s in snaps if s.book == HR_BOOK), key=lambda s: s.captured_at)
    if not sn:
        return None, None

    def q(s: PR.Snap) -> dict:
        return {"line": s.line, "under": s.under_price, "at": confirmed_at(s).isoformat()}

    return q(sn[0]), q(sn[-1])


def rank_key(e: Mapping[str, Any]) -> tuple:
    p = e["price"]
    if p.get("status") == "priced":
        return (0, -p["range_low"], -p["ev_point"], -len(p.get("ref_books", [])))
    ev = p.get("ev_point")
    return (1, -(ev if ev is not None else -9.0), 0, -len(p.get("ref_books", [])))


# --------------------------------------------------------------------------------------------- #
# Descriptive analysis (a focused port of research/1h-factors-2026-10/build_frame.py::factors)
# --------------------------------------------------------------------------------------------- #
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    return (
        2
        * r
        * math.asin(
            math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
        )
    )


class _SeasonToDate:
    """Season-to-date means for (season, team) over rows whose kickoff + 4 h is before a cutoff."""

    def __init__(self, rows: Iterable[Mapping[str, Any]], team_key: str):
        self.idx: Dict[Tuple[int, str], List[Mapping[str, Any]]] = defaultdict(list)
        for r in rows:
            if r.get("kick") is None:
                continue
            self.idx[(int(r["season"]), r[team_key])].append(r)
        for v in self.idx.values():
            v.sort(key=lambda r: r["kick"])
        self.kicks = {k: [r["kick"] for r in v] for k, v in self.idx.items()}

    def mean(self, season: int, team: str, cutoff: datetime, metric: str) -> Optional[float]:
        rows = self.idx.get((season, team))
        if not rows:
            return None
        n = bisect.bisect_left(self.kicks[(season, team)], cutoff - GAME_LEN)
        vals = [r[metric] for r in rows[:n] if r.get(metric) is not None]
        return sum(vals) / len(vals) if vals else None


def _trusted_fh(g: Mapping[str, Any]) -> Optional[float]:
    from .grading import trusted_first_half_total

    return trusted_first_half_total(
        g.get("first_half_total"),
        g.get("home_points"),
        g.get("away_points"),
        g.get("first_half_source"),
    )


@dataclass
class FactorContext:
    """Everything the descriptive analysis reads, as plain rows (dicts)."""

    games: Dict[int, Dict[str, Any]]
    fh_rows: List[Dict[str, Any]]
    tempo: List[Dict[str, Any]]
    venues: Dict[int, Dict[str, Any]]
    sp: Dict[Tuple[int, str], Dict[str, Any]]
    adv: Dict[Tuple[int, str], Dict[str, Any]]
    _team: _SeasonToDate = field(init=False, repr=False)
    _off: _SeasonToDate = field(init=False, repr=False)
    _kicks: Dict[str, List[datetime]] = field(init=False, repr=False)
    _home_venue: Dict[str, int] = field(init=False, repr=False)
    _tempo_by: Dict[str, List[Tuple[str, Dict[str, Any]]]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for g in self.games.values():
            g["kick_dt"] = parse_ts(g.get("kick"))
        team_rows = []
        for g in self.games.values():
            if g.get("home_points") is None or g.get("away_points") is None or g["kick_dt"] is None:
                continue
            fh = _trusted_fh(g)
            for side, opp in (("home", "away"), ("away", "home")):
                r = {"season": g["season"], "team": g[f"{side}_team"], "kick": g["kick_dt"]}
                if fh is not None and g.get(f"{side}_first_half_points") is not None:
                    r["fh_pf"] = g[f"{side}_first_half_points"]
                    r["fh_pa"] = g[f"{opp}_first_half_points"]
                team_rows.append(r)
        self._team = _SeasonToDate(team_rows, "team")
        for r in self.fh_rows:
            g = self.games.get(int(r["game_id"]))
            r["kick"] = g["kick_dt"] if g else None
        self._off = _SeasonToDate(self.fh_rows, "off_team")
        kicks: Dict[str, List[datetime]] = defaultdict(list)
        hv: Dict[str, Counter] = defaultdict(Counter)
        for g in self.games.values():
            if g["kick_dt"]:
                for t in (g["home_team"], g["away_team"]):
                    kicks[t].append(g["kick_dt"])
            if g.get("venue_id") and not g.get("neutral_site"):
                hv[g["home_team"]][int(g["venue_id"])] += 1
        for v in kicks.values():
            v.sort()
        self._kicks = kicks
        self._home_venue = {t: c.most_common(1)[0][0] for t, c in hv.items()}
        tb: Dict[str, List[Tuple[str, Dict[str, Any]]]] = defaultdict(list)
        for r in self.tempo:
            if r.get("as_of_date"):
                tb[r["team"]].append((str(r["as_of_date"])[:10], r))
        for v in tb.values():
            v.sort(key=lambda x: x[0])
        self._tempo_by = tb

    def factors(self, game_id: int, t: datetime) -> Dict[str, Any]:
        """The stats and situation of one game as known at decision time `t`."""
        g = self.games.get(int(game_id))
        if g is None:
            return {}
        s, h, a = int(g["season"]), g["home_team"], g["away_team"]
        f: Dict[str, Any] = {}

        def comb(fn):
            x, y = fn(h), fn(a)
            return None if x is None or y is None else x + y

        for m in ("fh_pf", "fh_pa"):
            f[f"std_{m}"] = comb(lambda tm, m=m: self._team.mean(s, tm, t, m))
        for m in ("epa", "explosive", "n_plays"):
            f[f"fh_off_{m}"] = comb(lambda tm, m=m: self._off.mean(s, tm, t, m))

        def sp_side(tm: str, side: str) -> Optional[float]:
            return ((self.sp.get((s - 1, tm)) or {}).get(side) or {}).get("rating")

        f["prior_sp_off"] = comb(lambda tm: sp_side(tm, "offense"))
        f["prior_sp_def"] = comb(lambda tm: sp_side(tm, "defense"))

        def tempo_at(tm: str) -> Optional[Dict[str, Any]]:
            rows = self._tempo_by.get(tm, [])
            d = t.strftime("%Y-%m-%d")
            i = bisect.bisect_left([x[0] for x in rows], d)
            if not i:
                return None
            r = rows[i - 1][1]
            return r if int(r["season"]) == s else None

        th, ta = tempo_at(h), tempo_at(a)
        f["sec_per_play"] = (
            None
            if not (th and ta) or None in (th["seconds_per_play"], ta["seconds_per_play"])
            else (th["seconds_per_play"] + ta["seconds_per_play"]) / 2
        )
        f["plays_per_game"] = (
            None
            if not (th and ta) or None in (th["plays_per_game"], ta["plays_per_game"])
            else th["plays_per_game"] + ta["plays_per_game"]
        )

        def rest(tm: str) -> Optional[float]:
            ks = self._kicks.get(tm, [])
            i = bisect.bisect_left(ks, g["kick_dt"])
            return (g["kick_dt"] - ks[i - 1]).total_seconds() / 86400 if i else None

        rs = [x for x in (rest(h), rest(a)) if x is not None and x < 60]
        f["min_rest_days"] = min(rs) if len(rs) == 2 else None
        f["either_short_week"] = None if len(rs) < 2 else float(min(rs) < 6)
        f["either_off_bye"] = None if len(rs) < 2 else float(max(rs) >= 13)
        v = self.venues.get(int(g["venue_id"])) if g.get("venue_id") else None
        hv = self._home_venue.get(a)
        av = self.venues.get(hv) if hv else None
        if (
            v
            and av
            and None not in (v["latitude"], v["longitude"], av["latitude"], av["longitude"])
        ):
            f["away_travel_km"] = _haversine_km(
                v["latitude"], v["longitude"], av["latitude"], av["longitude"]
            )
        else:
            f["away_travel_km"] = None
        f["kick_local_hour"] = (
            None
            if not v or v.get("longitude") is None
            else (g["kick_dt"].hour + g["kick_dt"].minute / 60 + v["longitude"] / 15.0) % 24
        )
        # Estimated first-half possessions (descriptive): combined first-half offensive plays per
        # game this season over last season's plays per drive of the two offenses.
        ppd = []
        for tm in (h, a):
            adv = self.adv.get((s - 1, tm))
            if adv and (adv.get("offense") or {}).get("drives"):
                ppd.append(adv["offense"]["plays"] / adv["offense"]["drives"])
        f["est_1h_possessions"] = (
            f["fh_off_n_plays"] / st.mean(ppd)
            if (f.get("fh_off_n_plays") and len(ppd) == 2)
            else None
        )
        return f


def load_reference(path: Path = REFERENCE_PATH) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def percentile(
    reference: Mapping[str, Any], factor: str, value: Optional[float]
) -> Optional[float]:
    """Share of the 2023-26 screen frame at or below `value` (the prototype's `pct`)."""
    vals = (reference.get("values") or {}).get(factor) or []
    if value is None or not vals:
        return None
    return bisect.bisect_right(vals, value) / len(vals)


def analysis(
    f: Mapping[str, Any],
    reference: Mapping[str, Any],
    forecast: Optional[Mapping[str, Any]],
    preview: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """The descriptive block beside an entry. Every stat carries its percentile and its screen
    verdict; `scoring` says "less" or "more" for a value in the bottom or top third, else None."""
    verdicts = reference.get("verdicts") or {}
    stats = []
    for key, words, d in CONTEXT:
        value = f.get(key)
        p = percentile(reference, key, value)
        scoring = None
        if p is not None:
            if (d == "low" and p <= 0.33) or (d == "high" and p >= 0.67):
                scoring = "less"
            elif (d == "low" and p >= 0.67) or (d == "high" and p <= 0.33):
                scoring = "more"
        stats.append(
            {
                "key": key,
                "words": words,
                "value": value,
                "pct": p,
                "scoring": scoring,
                "verdict": verdicts.get(key, "not screened"),
            }
        )
    weather = None
    if forecast and forecast.get("dome"):
        weather = {"dome": True}
    elif forecast and forecast.get("wind_mph") is not None:
        weather = {
            "dome": False,
            "wind_mph": forecast.get("wind_mph"),
            "gust_mph": forecast.get("wind_gust_mph"),
            "temperature_f": forecast.get("temperature_f"),
            "precipitation_mm": forecast.get("precipitation"),
            "fetched_at": forecast.get("fetched_at"),
            "scoring": "less" if forecast["wind_mph"] >= WIND_LESS_SCORING_MPH else None,
            "verdict": verdicts.get("wx_wind", "not screened"),
        }
    pv = preview or {}
    qb = (
        {"out": True, "detail": pv.get("qb_out_detail") or ""}
        if pv.get("qb_out")
        else {"out": False, "detail": "no QB flagged out (Rotowire; thin coverage)"}
    )
    return {
        "stats": stats,
        "situational": {k: f.get(k) for k in SITUATIONAL},
        "est_1h_possessions": f.get("est_1h_possessions"),
        "weather": weather,
        "qb": qb,
    }


# --------------------------------------------------------------------------------------------- #
# The publication
# --------------------------------------------------------------------------------------------- #
def pool(items: Sequence[Mapping[str, Any]], t: datetime) -> List[Mapping[str, Any]]:
    """Every card item kicking off after `t`: the analysis is saved for each game the card rates
    (Tate 2026-10-16), and the site shows it for the Board's #1-#10."""
    out = []
    for it in items:
        kick = parse_ts(it.get("kick"))
        if kick is not None and kick > t:
            out.append(it)
    return out


def priceable(it: Mapping[str, Any]) -> bool:
    """Only Hard Rock's MAIN line with a price is ever priced; an alternate rung never is."""
    return (
        bool(it.get("hr_centred"))
        and it.get("hr_price") is not None
        and it.get("hr_line") is not None
    )


def build_publication(
    card: Mapping[str, Any],
    snaps: Mapping[int, Sequence[PR.Snap]],
    ctx: FactorContext,
    reference: Mapping[str, Any],
    forecasts: Mapping[int, Mapping[str, Any]],
    previews: Mapping[int, Mapping[str, Any]],
    mass_table: PR.MassTable,
    now: datetime,
) -> Dict[str, Any]:
    """The frozen analysis of every game one card rates. `card`: id, season, week, slot, built_at,
    items."""
    built = parse_ts(card["built_at"])
    entries = []
    for it in pool(card["items"], now):
        gid = int(it["game_id"])
        sn = list(snaps.get(gid, []))
        pr = price_read(it, sn, mass_table, now)
        first, last = hr_history(sn)
        f = ctx.factors(gid, built) if built else {}
        entries.append(
            {
                "game_id": gid,
                "matchup": f"{it['away']} @ {it['home']}",
                "kick": it["kick"],
                "price": pr,
                "label": label(pr),
                "model": {
                    "bv_line": it.get("bv_line"),
                    "market_line": it.get("market_line"),
                    "gap": it.get("gap"),
                },
                "first_hr": first,
                "latest_hr": last,
                "analysis": analysis(f, reference, forecasts.get(gid), previews.get(gid)),
            }
        )
    # Stored in price order for a stable record; the site shows each entry on its own game page
    # for the Board's #1-#10 and never shows this order as a ranking.
    entries.sort(key=rank_key)
    for i, e in enumerate(entries, 1):
        e["rank"] = i
    return {
        "published_at": now.isoformat() + "Z",
        "card_id": int(card["id"]),
        "season": int(card["season"]),
        "week": int(card["week"]),
        "slot": card["slot"],
        "card_built": built.isoformat() if built else None,
        "pool": len(entries),
        "method": METHOD,
        "entries": entries,
    }


def canonical(pub: Mapping[str, Any]) -> str:
    return json.dumps(pub, sort_keys=True, default=str)


def publication_sha(pub: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(pub).encode()).hexdigest()


# --------------------------------------------------------------------------------------------- #
# Database edge
# --------------------------------------------------------------------------------------------- #
def card_dict(row) -> Dict[str, Any]:
    p = json.loads(row.payload)
    return {
        "id": row.id,
        "season": row.season,
        "week": row.week,
        "slot": p.get("slot"),
        "built_at": row.built_at,
        "items": p.get("items") or [],
    }


def load_inputs(session, card: Mapping[str, Any], now: datetime):
    """Everything build_publication reads, for one card, from the database and the CFBD cache."""
    from .db.models import (
        BuildForecast,
        FhTeamGame,
        Game,
        GamePreview,
        OddsSnapshot,
        TeamTempo,
        Venue,
    )
    from .sources.season_stats import CACHE

    season = int(card["season"])
    ids = [int(it["game_id"]) for it in pool(card["items"], now)]
    snaps: Dict[int, List[PR.Snap]] = defaultdict(list)
    if ids:
        for r in session.query(OddsSnapshot).filter(
            OddsSnapshot.market == "1H_total", OddsSnapshot.game_id.in_(ids)
        ):
            snaps[int(r.game_id)].append(
                PR.Snap(
                    game_id=int(r.game_id),
                    book=r.book,
                    market="1H_total",
                    line=r.line,
                    over_price=r.over_price,
                    under_price=r.under_price,
                    home_price=None,
                    away_price=None,
                    captured_at=r.captured_at,
                    last_seen_at=r.last_seen_at,
                )
            )
    previews = {
        int(r.game_id): {"qb_out": r.qb_out, "qb_out_detail": r.qb_out_detail}
        for r in session.query(GamePreview).filter(GamePreview.game_id.in_(ids or [0]))
    }
    forecasts: Dict[int, Dict[str, Any]] = {}
    for r in (
        session.query(BuildForecast)
        .filter(BuildForecast.game_id.in_(ids or [0]))
        .order_by(BuildForecast.fetched_at)
    ):
        forecasts[int(r.game_id)] = {
            "wind_mph": r.wind_mph,
            "wind_gust_mph": r.wind_gust_mph,
            "temperature_f": r.temperature_f,
            "precipitation": r.precipitation,
            "dome": r.dome,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
        }
    # Rest days and home venues read the games of the four seasons before this one too.
    games = {
        int(g.id): {
            "id": int(g.id),
            "season": g.season,
            "kick": g.start_date,
            "neutral_site": g.neutral_site,
            "venue_id": g.venue_id,
            "home_team": g.home_team,
            "away_team": g.away_team,
            "home_points": g.home_points,
            "away_points": g.away_points,
            "home_first_half_points": g.home_first_half_points,
            "away_first_half_points": g.away_first_half_points,
            "first_half_total": g.first_half_total,
            "first_half_source": g.first_half_source,
        }
        for g in session.query(Game).filter(Game.season >= season - 4, Game.season <= season)
    }
    fh_rows = [
        {
            "game_id": r.game_id,
            "season": r.season,
            "off_team": r.off_team,
            "epa": r.epa,
            "explosive": r.explosive,
            "n_plays": r.n_plays,
        }
        for r in session.query(FhTeamGame).filter(FhTeamGame.season == season)
    ]
    tempo = [
        {
            "season": r.season,
            "team": r.team,
            "seconds_per_play": r.seconds_per_play,
            "plays_per_game": r.plays_per_game,
            "as_of_date": r.as_of_date,
        }
        for r in session.query(TeamTempo).filter(TeamTempo.season == season)
    ]
    venues = {
        int(v.id): {"latitude": v.latitude, "longitude": v.longitude, "dome": v.dome}
        for v in session.query(Venue)
    }

    def cache_rows(kind: str) -> Dict[Tuple[int, str], Dict[str, Any]]:
        fp = CACHE / f"{kind}_{season - 1}.json"
        if not fp.exists():
            return {}
        return {(season - 1, r["team"]): r for r in json.loads(fp.read_text()) if r.get("team")}

    ctx = FactorContext(
        games=games,
        fh_rows=fh_rows,
        tempo=tempo,
        venues=venues,
        sp=cache_rows("sp"),
        adv=cache_rows("adv"),
    )
    return snaps, ctx, forecasts, previews


def already_published(session, card_id: int) -> bool:
    from .db.models import ShortlistEntry

    return (
        session.query(ShortlistEntry.id).filter(ShortlistEntry.card_id == card_id).first()
        is not None
    )


def write_publication(session, pub: Mapping[str, Any]) -> int:
    """Insert the publication's entries; never touch an existing one. Returns rows written
    (0 when the card already has a publication: frozen means written once)."""
    from .db.models import ShortlistEntry

    if already_published(session, int(pub["card_id"])):
        return 0
    sha = publication_sha(pub)
    published = parse_ts(pub["published_at"])
    for e in pub["entries"]:
        session.add(
            ShortlistEntry(
                card_id=int(pub["card_id"]),
                season=int(pub["season"]),
                week=int(pub["week"]),
                slot=pub["slot"],
                published_at=published,
                card_built=pub["card_built"],
                pool_size=int(pub["pool"]),
                method=pub["method"],
                publication_sha256=sha,
                game_id=int(e["game_id"]),
                rank=int(e["rank"]),
                label=e["label"],
                payload_json=json.dumps(e, sort_keys=True, default=str),
            )
        )
    session.flush()
    return len(pub["entries"])


def publication_from_rows(rows: Sequence[Any]) -> Dict[str, Any]:
    """Rebuild a stored publication exactly, so its sha256 can be re-checked."""
    rows = sorted(rows, key=lambda r: r.rank)
    r0 = rows[0]
    return {
        "published_at": r0.published_at.isoformat() + "Z",
        "card_id": r0.card_id,
        "season": r0.season,
        "week": r0.week,
        "slot": r0.slot,
        "card_built": r0.card_built,
        "pool": r0.pool_size,
        "method": r0.method,
        "entries": [json.loads(r.payload_json) for r in rows],
    }
