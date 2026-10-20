"""The archive items (final-2026 plan C11-C12, PR-C10; Tate's decisions C-D5,
C-D9, C-D13, C-D17, C-D20, C-D21).

Each item turns expiring Odds API credits into a permanent historical dataset in
`research_snapshots` (purpose `archive_*`, source `historical`), never in
`odds_snapshots`: no registered reader (cv1, pv1, HT1H, the card) can see them.
`scripts/archive_buy.py auto` runs the items in Tate's order inside the last days
of a billing cycle; each item spends at most what it is handed and stops cleanly
when that runs out (`BudgetExhausted`). Resumable: what was already bought is read
back from the credit ledger (`odds_spend.params_json` keeps each call's `date` and
event) and from the rows already written, so a rerun never pays twice.

Four kinds of item:

- **Close waves** (Pinnacle 2026 / 2025 / 2024): one historical BULK totals call
  on the `eu` region (10 credits) at kickoff - 30 min, grouping kickoffs within
  30 min of the wave's first game, FBS-vs-FBS games only. Rows kept: the wave's
  own games (kicking off 30-60 min later). Every row written (a wave is an
  observation).
- **Full-game paths** (2026 weeks 1-7, `us` then `us2`): one bulk totals call
  every 4 h (00Z, 04Z, ...) from the Sunday 16:00Z before a week's first kickoff
  to its last kickoff, rows for that week's games still to kick off, written on
  change (an unchanged quote moves `last_seen_at`, as the live capture does).
- **Hard Rock 1H release time** (2026 weeks 1-4): per Hard-Rock-priced game, a
  search for the first 5-minute archive snapshot that carries Hard Rock's
  `totals_h1`, asking Hard Rock alone (an empty answer is free, a present one 10
  credits). The window ends at our first live capture of that line and starts 72 h
  earlier; a line already present at the window's start is written at the start
  (read: "at or before"). Earlier finds of the same week are tried first (Hard Rock
  posts in batches). One row per game: the line and prices at first sighting.
- **Hard Rock 1H team totals** (2026 weeks 1-7, C-D21): per Hard-Rock-priced game,
  `team_totals_h1` from Hard Rock alone at kickoff - 30 min (10 credits when
  present), one row per team (market `team_total_1h`, `team` = the feed's name).

Event ids for the per-game items: the live capture's `event_id` when it has one,
else the archive's events list for that week (1 credit a week).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import research_capture
from .db.models import Game, OddsSnapshot, OddsSpend, ResearchSnapshot
from .etl.fbs import load_fbs_teams
from .etl.match import match_event
from .hardrock import HR_BOOK_KEY, normalize_book
from .sources.odds import _implied, _rows_for_market

LEAD_MIN = 30  # a close wave asks the archive at kickoff - 30 min
GROUP_MIN = 30  # ... and covers every kickoff up to 30 min after the wave's first
PATH_STEP_H = 4  # full-game paths: one snapshot every 4 h
PATH_START_HOUR_UTC = 16  # from the Sunday 16:00Z (noon ET) before the week's first kickoff
RELEASE_STEP_MIN = 5  # the archive's snapshot interval
RELEASE_LOOKBACK_H = 72  # the release search starts 72 h before our first live capture
RELEASE_HINTS = 3  # earlier finds of the same week tried first
HIST_BULK_COST = 10  # per market per region
HIST_EVENT_COST = 10  # per market returned
HIST_EVENTS_COST = 1


class BudgetExhausted(Exception):
    """The item's credits are spent: stop cleanly, keep what was bought."""


class Budget:
    """What one item may spend in this run, counted from the provider's own
    `x-requests-last` header after every call."""

    def __init__(self, cap: int):
        self.cap = int(cap)
        self.spent = 0
        self.calls = 0

    def check(self, estimate: int, what: str) -> None:
        if self.spent + estimate > self.cap:
            raise BudgetExhausted(f"{what}: {self.spent} spent + {estimate} > {self.cap}")

    def note(self, client) -> int:
        c = getattr(client, "last_credits", None)
        cost = int(c.last_cost) if c is not None and c.last_cost is not None else 0
        self.spent += cost
        self.calls += 1
        return cost


def iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# The games each item covers, and its waves (pure)
# --------------------------------------------------------------------------- #
def target_games(
    session, season: int, weeks: Optional[Sequence[int]] = None, fbs_both: bool = True
) -> List[Dict[str, Any]]:
    """Regular-season games with a kickoff, FBS-vs-FBS by default (etl/fbs.py)."""
    q = session.query(Game).filter(
        Game.season == season, Game.start_date.isnot(None), Game.season_type == "regular"
    )
    if weeks:
        q = q.filter(Game.week.in_(list(weeks)))
    fbs = load_fbs_teams() if fbs_both else {}
    teams = fbs.get(season) or (fbs[max(fbs)] if fbs else set())
    out = []
    for g in q.order_by(Game.start_date.asc(), Game.id.asc()).all():
        if fbs_both and not (g.home_team in teams and g.away_team in teams):
            continue
        out.append(
            {
                "id": int(g.id),
                "week": int(g.week),
                "home_team": g.home_team,
                "away_team": g.away_team,
                "start_date": g.start_date,
            }
        )
    return out


def close_waves(
    games: Sequence[Dict[str, Any]], lead_min: int = LEAD_MIN, group_min: int = GROUP_MIN
) -> List[Tuple[datetime, List[Dict[str, Any]]]]:
    """[(wave time, its games)]: the earliest uncovered kickoff K opens a wave at
    K - lead; every kickoff in [K, K + group] joins it (30-60 min before its own)."""
    rest = sorted(games, key=lambda g: (g["start_date"], g["id"]))
    waves: List[Tuple[datetime, List[Dict[str, Any]]]] = []
    i = 0
    while i < len(rest):
        k0 = rest[i]["start_date"]
        members = []
        while i < len(rest) and rest[i]["start_date"] <= k0 + timedelta(minutes=group_min):
            members.append(rest[i])
            i += 1
        waves.append((k0 - timedelta(minutes=lead_min), members))
    return waves


def path_waves(
    games: Sequence[Dict[str, Any]], step_h: int = PATH_STEP_H
) -> List[Tuple[datetime, List[Dict[str, Any]]]]:
    """[(wave time, the week's games still to kick off)] every `step_h` hours on
    the UTC grid, from the Sunday 16:00Z before each week's first kickoff to its
    last kickoff."""
    by_week: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for g in games:
        by_week[g["week"]].append(g)
    out: List[Tuple[datetime, List[Dict[str, Any]]]] = []
    for wk in sorted(by_week):
        gs = by_week[wk]
        first = min(g["start_date"] for g in gs)
        last = max(g["start_date"] for g in gs)
        day = first.date() - timedelta(days=(first.weekday() + 1) % 7)  # the Sunday on/before
        start = datetime(day.year, day.month, day.day, PATH_START_HOUR_UTC)
        if start >= first:
            start -= timedelta(days=7)
        t = start
        while t < last:
            ahead = [g for g in gs if g["start_date"] > t]
            if ahead:
                out.append((t, ahead))
            t += timedelta(hours=step_h)
    return out


def floor_step(t: datetime, step_min: int = RELEASE_STEP_MIN) -> datetime:
    t = t.replace(second=0, microsecond=0)
    return t - timedelta(minutes=t.minute % step_min)


def find_first_present(
    probe: Callable[[datetime], Optional[Dict[str, Any]]],
    lo: datetime,
    hi: datetime,
    step: timedelta = timedelta(minutes=RELEASE_STEP_MIN),
    hints: Iterable[datetime] = (),
) -> Optional[Tuple[datetime, Dict[str, Any], bool]]:
    """The first grid time in [lo, hi] at which `probe` finds the market, given
    that presence never ends once it starts. (time, envelope, at_window_start) or
    None when even `hi` lacks it. Hints (earlier finds) are tried first."""
    e_hi = probe(hi)
    if not e_hi:
        return None
    e_lo = probe(lo)
    if e_lo:
        return lo, e_lo, True
    best = (hi, e_hi)
    for h in hints:
        if not (lo < h < hi):
            continue
        e = probe(h)
        if not e:
            lo = h
            continue
        hi, best = h, (h, e)
        before = h - step
        if before <= lo:
            return h, e, False
        e_before = probe(before)
        if not e_before:
            return h, e, False
        hi, best = before, (before, e_before)
    while hi - lo > step:
        n = int((hi - lo) / step)
        mid = lo + step * (n // 2)
        e = probe(mid)
        if e:
            hi, best = mid, (mid, e)
        else:
            lo = mid
    return best[0], best[1], False


# --------------------------------------------------------------------------- #
# Parsing (pure)
# --------------------------------------------------------------------------- #
def team_total_rows(payload: Dict[str, Any], market_key: str = "team_totals_h1") -> List[Dict]:
    """One row per (book, team) from an event's team-total market: the point
    pair whose two prices are closest to even (a book may post several)."""
    rows: List[Dict[str, Any]] = []
    for bm in payload.get("bookmakers") or []:
        for mk in bm.get("markets") or []:
            if mk.get("key") != market_key:
                continue
            pairs: Dict[Tuple[str, float], Dict[str, Any]] = {}
            for o in mk.get("outcomes") or []:
                team, pt, side = o.get("description"), o.get("point"), o.get("name")
                if team is None or pt is None or side not in ("Over", "Under"):
                    continue
                pairs.setdefault((team, float(pt)), {})[side] = o.get("price")
            best: Dict[str, Tuple[float, float, Any, Any]] = {}
            for (team, pt), pr in pairs.items():
                if "Over" not in pr or "Under" not in pr:
                    continue
                po, pu = _implied(pr["Over"]), _implied(pr["Under"])
                skew = abs((po or 0.5) - (pu or 0.5))
                if team not in best or skew < best[team][0]:
                    best[team] = (skew, pt, pr["Over"], pr["Under"])
            for team, (_s, pt, over, under) in best.items():
                rows.append(
                    {
                        "event_id": payload.get("id"),
                        "book": normalize_book(bm.get("key")),
                        "market": "team_total_1h",
                        "team": team,
                        "line": pt,
                        "over_price": over,
                        "under_price": under,
                        "last_update": mk.get("last_update") or bm.get("last_update"),
                    }
                )
    return rows


def has_market(payload: Optional[Dict[str, Any]], market_key: str, book: str) -> bool:
    for bm in (payload or {}).get("bookmakers") or []:
        if normalize_book(bm.get("key")) != book:
            continue
        for mk in bm.get("markets") or []:
            if mk.get("key") == market_key and mk.get("outcomes"):
                return True
    return False


# --------------------------------------------------------------------------- #
# What was already bought (the ledger and the rows)
# --------------------------------------------------------------------------- #
def bought_calls(session, purpose: str) -> Set[Tuple[Optional[str], Optional[str]]]:
    """(event_id or None, date) of every answered call this purpose made."""
    out: Set[Tuple[Optional[str], Optional[str]]] = set()
    for (pj,) in (
        session.query(OddsSpend.params_json)
        .filter(OddsSpend.purpose == purpose, OddsSpend.http_status == 200)
        .all()
    ):
        try:
            p = json.loads(pj or "{}")
        except ValueError:
            continue
        out.add((p.get("event_id"), p.get("date")))
    return out


def games_written(session, purpose: str) -> Set[int]:
    return {
        int(g)
        for (g,) in session.query(ResearchSnapshot.game_id)
        .filter(ResearchSnapshot.purpose == purpose, ResearchSnapshot.game_id.isnot(None))
        .distinct()
        .all()
    }


def hr_first_captures(
    session, game_ids: Sequence[int]
) -> Dict[int, Tuple[datetime, Optional[str]]]:
    """{game: (our first live capture of Hard Rock's 1H line, its event id if any)}."""
    out: Dict[int, Tuple[datetime, Optional[str]]] = {}
    if not game_ids:
        return out
    rows = (
        session.query(OddsSnapshot.game_id, OddsSnapshot.captured_at, OddsSnapshot.event_id)
        .filter(
            OddsSnapshot.book == HR_BOOK_KEY,
            OddsSnapshot.market == "1H_total",
            OddsSnapshot.game_id.in_(list(game_ids)),
        )
        .order_by(OddsSnapshot.captured_at.asc())
        .all()
    )
    for gid, at, ev in rows:
        if gid not in out:
            out[int(gid)] = (at, ev)
        elif ev and not out[int(gid)][1]:
            out[int(gid)] = (out[int(gid)][0], ev)
    return out


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def write_rows(
    session_scope,
    rows: List[Dict[str, Any]],
    *,
    purpose: str,
    region: Optional[str],
    request_id: Optional[int],
    captured_at: datetime,
    dedupe: bool,
) -> int:
    for r in rows:
        r["captured_at"] = captured_at
        r.setdefault("market", "full_game_total")
    with session_scope() as s:
        n = research_capture.write_rows(
            s,
            rows,
            purpose=purpose,
            region=region,
            request_id=request_id,
            source="historical",
            dedupe=dedupe,
            now=captured_at,
        )
    return n["written"]


def _match(rows: List[Dict[str, Any]], games: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the rows whose event matches one of `games`; set their game_id."""
    ids = {g["id"] for g in games}
    cache: Dict[Any, Optional[int]] = {}
    kept = []
    for r in rows:
        key = r.get("event_id")
        if key not in cache:
            gid, _ = match_event(r["home_team"], r["away_team"], r["commence_time"], list(games))
            cache[key] = gid if gid in ids else None
        if cache[key] is not None:
            r["game_id"] = cache[key]
            kept.append(r)
    return kept


# --------------------------------------------------------------------------- #
# The four item kinds. Each returns the credits it spent; BudgetExhausted ends
# the item early (the caller catches it).
# --------------------------------------------------------------------------- #
def _bulk(client, budget: Budget, when: datetime, regions: str, purpose: str):
    budget.check(HIST_BULK_COST * len(regions.split(",")), f"{purpose} bulk {iso_z(when)}")
    env = client.historical_bulk_totals(iso_z(when), regions=regions, envelope=True)
    budget.note(client)
    return env or {}, getattr(client, "last_spend_id", None)


def run_close_waves(
    client, session_scope, *, season: int, weeks, purpose: str, regions: str, budget: Budget, log
) -> int:
    with session_scope() as s:
        games = target_games(s, season, weeks)
        done = {d for _e, d in bought_calls(s, purpose)}
    written = 0
    for when, members in close_waves(games):
        if iso_z(when) in done:
            continue
        env, req = _bulk(client, budget, when, regions, purpose)
        at = parse_ts(env.get("timestamp")) or when
        rows = _match(_rows_for_market(env.get("data") or [], "totals"), members)
        written += write_rows(
            session_scope,
            rows,
            purpose=purpose,
            region=regions,
            request_id=req,
            captured_at=at,
            dedupe=False,
        )
    log(f"{purpose}: {written} rows, {budget.spent} credits")
    return budget.spent


def run_paths(
    client, session_scope, *, season: int, weeks, purpose: str, regions: str, budget: Budget, log
) -> int:
    with session_scope() as s:
        games = target_games(s, season, weeks)
        done = {d for _e, d in bought_calls(s, purpose)}
    written = 0
    for when, ahead in path_waves(games):
        if iso_z(when) in done:
            continue
        env, req = _bulk(client, budget, when, regions, purpose)
        at = parse_ts(env.get("timestamp")) or when
        rows = _match(_rows_for_market(env.get("data") or [], "totals"), ahead)
        written += write_rows(
            session_scope,
            rows,
            purpose=purpose,
            region=regions,
            request_id=req,
            captured_at=at,
            dedupe=True,
        )
    log(f"{purpose}: {written} rows, {budget.spent} credits")
    return budget.spent


def _event_ids(client, budget: Budget, games: List[Dict[str, Any]], known: Dict[int, str]):
    """{game: event id}: the live capture's id where known, else the archive's
    events list as of the Sunday 16:00Z before each week (1 credit a week)."""
    out = dict(known)
    by_week: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for g in games:
        if g["id"] not in out:
            by_week[g["week"]].append(g)
    for _wk, gs in sorted(by_week.items()):
        first = min(g["start_date"] for g in gs)
        day = first.date() - timedelta(days=(first.weekday() + 1) % 7)
        at = datetime(day.year, day.month, day.day, PATH_START_HOUR_UTC)
        if at >= first:
            at -= timedelta(days=7)
        budget.check(HIST_EVENTS_COST, f"events list {iso_z(at)}")
        events = client.list_historical_events(iso_z(at))
        budget.note(client)
        for ev in events or []:
            gid, _ = match_event(
                ev.get("home_team"), ev.get("away_team"), ev.get("commence_time"), gs
            )
            if gid is not None and gid not in out:
                out[gid] = ev.get("id")
    return out


def run_hr_release(
    client, session_scope, *, season: int, weeks, purpose: str, budget: Budget, log
) -> int:
    with session_scope() as s:
        games = target_games(s, season, weeks)
        firsts = hr_first_captures(s, [g["id"] for g in games])
        done = games_written(s, purpose)
    games = [g for g in games if g["id"] in firsts and g["id"] not in done]
    ids = _event_ids(client, budget, games, {g: ev for g, (_t, ev) in firsts.items() if ev})
    found: Dict[int, Counter] = defaultdict(Counter)
    n_found = n_missing = 0
    for g in games:
        ev = ids.get(g["id"])
        if not ev:
            n_missing += 1
            continue
        hi = floor_step(firsts[g["id"]][0])
        lo = hi - timedelta(hours=RELEASE_LOOKBACK_H)
        meta: Dict[datetime, Optional[int]] = {}

        def probe(t: datetime, ev=ev, meta=meta) -> Optional[Dict[str, Any]]:
            budget.check(HIST_EVENT_COST, f"{purpose} {ev} {iso_z(t)}")
            env = client.historical_event_odds(
                ev, iso_z(t), "totals_h1", [HR_BOOK_KEY], envelope=True
            )
            budget.note(client)
            meta[t] = getattr(client, "last_spend_id", None)
            return env if has_market((env or {}).get("data"), "totals_h1", HR_BOOK_KEY) else None

        hints = [t for t, _n in found[g["week"]].most_common(RELEASE_HINTS)]
        res = find_first_present(probe, lo, hi, hints=hints)
        if res is None:
            n_missing += 1
            continue
        t1, env, _at_start = res
        found[g["week"]][t1] += 1
        rows = _rows_for_market([env["data"]], "totals_h1", [HR_BOOK_KEY])
        for r in rows:
            r["game_id"], r["market"] = g["id"], "1H_total"
        write_rows(
            session_scope,
            rows,
            purpose=purpose,
            region=None,
            request_id=meta.get(t1),
            captured_at=parse_ts(env.get("timestamp")) or t1,
            dedupe=False,
        )
        n_found += 1
    log(f"{purpose}: {n_found} games found, {n_missing} not in the archive, {budget.spent} credits")
    return budget.spent


def run_hr_tt1h(
    client, session_scope, *, season: int, weeks, purpose: str, budget: Budget, log
) -> int:
    with session_scope() as s:
        games = target_games(s, season, weeks)
        firsts = hr_first_captures(s, [g["id"] for g in games])
        done_games = games_written(s, purpose)
        asked = bought_calls(s, purpose)
    games = [g for g in games if g["id"] in firsts and g["id"] not in done_games]
    ids = _event_ids(client, budget, games, {g: ev for g, (_t, ev) in firsts.items() if ev})
    written = empty = 0
    for g in games:
        ev = ids.get(g["id"])
        if not ev:
            continue
        when = g["start_date"] - timedelta(minutes=LEAD_MIN)
        if (ev, iso_z(when)) in asked:
            continue  # asked before and answered empty (a present answer wrote rows)
        budget.check(HIST_EVENT_COST, f"{purpose} {ev}")
        env = client.historical_event_odds(
            ev, iso_z(when), "team_totals_h1", [HR_BOOK_KEY], envelope=True
        )
        budget.note(client)
        rows = team_total_rows((env or {}).get("data") or {})
        for r in rows:
            r["game_id"] = g["id"]
        if not rows:
            empty += 1
            continue
        written += write_rows(
            session_scope,
            rows,
            purpose=purpose,
            region=None,
            request_id=getattr(client, "last_spend_id", None),
            captured_at=parse_ts((env or {}).get("timestamp")) or when,
            dedupe=False,
        )
    log(f"{purpose}: {written} rows, {empty} games without the market, {budget.spent} credits")
    return budget.spent


# --------------------------------------------------------------------------- #
# Estimates for `archive_buy.py status` (free; what is left to buy)
# --------------------------------------------------------------------------- #
RELEASE_EST_PER_GAME = 60  # about 10 asks, half of them present, without a batch hint


def estimate(session, kind: str, *, season: int, weeks, purpose: str) -> Dict[str, int]:
    """{units left, credits left (upper estimate)} for one item."""
    games = target_games(session, season, weeks)
    if kind in ("close", "paths"):
        waves = close_waves(games) if kind == "close" else path_waves(games)
        done = {d for _e, d in bought_calls(session, purpose)}
        left = sum(1 for w, _m in waves if iso_z(w) not in done)
        return {"units": left, "credits": HIST_BULK_COST * left}
    firsts = hr_first_captures(session, [g["id"] for g in games])
    done = games_written(session, purpose)
    left = [g for g in games if g["id"] in firsts and g["id"] not in done]
    weeks_left = len({g["week"] for g in left})
    per = RELEASE_EST_PER_GAME if kind == "release" else HIST_EVENT_COST
    return {"units": len(left), "credits": per * len(left) + HIST_EVENTS_COST * weeks_left}
