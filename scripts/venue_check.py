#!/usr/bin/env python
"""H-VENUE-1 (docs/HYPOTHESES.md; exploratory, accruing): Hard Rock against
Kalshi, read on data already captured -- the two-venue question of the October
review (docs/program/REVIEW_2026-10.md, roadmap v2.0; Tate's call 2026-10-11:
measure first, no account, no capture, no credits).

For every graded game of the season with a Hard Rock full-game total AND a
Kalshi full-game total (The Odds API's `us_ex` region, captured since
2026-09-02), each confirmed inside the judge's 2-hour close window, and at
least three OTHER books (not Hard Rock, Kalshi, Fliff or the feed's consensus
row) in the same window:

1. how far each venue's close sits from the other books' median line, and how
   often it is a point or more off;
2. the judge's EV (beatvegas/consensus.py, the same engine every arm is judged
   by) of the UNDER and the OVER at each venue's own close and price, judged
   against a consensus that counts neither venue;
3. the EV a bettor who may take EITHER venue would book: per side, the better
   of the two venues' readings;
4. the realized units of each side at each venue, on the trusted result.

Kalshi's "line" is a rung of a ladder of binary contracts (the feed reports
one rung with its two prices); a rung more than 1.5 points from the other books'
lines has no reading (`far_lines`) and is counted, not dropped silently.
Intervals resample games (one season, few weeks). Exploratory: it reports;
nothing is adopted from it. READ-ONLY; writes reports/venue_check_<UTC>.{md,json}.
Runs through study.yml.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beatvegas.backtest.early_close import settle, units  # noqa: E402
from beatvegas.consensus import (  # noqa: E402
    CLOSE_WINDOW_H,
    EXCLUDED_BOOKS,
    MIN_BOOKS,
    HalfPointTable,
    book_closes,
    read_at_terms,
)
from beatvegas.db.models import Game, OddsSnapshot  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402
from beatvegas.hardrock import HR_BOOK_KEY  # noqa: E402

MARKET = "full_game_total"
KALSHI = "kalshi"
VENUES = (HR_BOOK_KEY, KALSHI)
SIDES = ("under", "over")
OFF_PTS = 1.0
REPS = 2000
IN_BLOCK = 500


def _price(close, side: str) -> int:
    return close.under_price if side == "under" else close.over_price


def game_record(
    gid: int, week: int, kickoff, total: Optional[float], snaps: Sequence, table
) -> Optional[dict]:
    """One record per game, or None when a venue or the reference books are missing."""
    every = book_closes(snaps, kickoff, excluded=frozenset())
    floor = kickoff - timedelta(hours=CLOSE_WINDOW_H)
    venue_close = {}
    for v in VENUES:
        c = every.get(v)
        if c is None or c.seen_at is None or c.seen_at < floor:
            return None
        venue_close[v] = c
    judge = {b: c for b, c in every.items() if b not in EXCLUDED_BOOKS and b != KALSHI}
    fresh = [c for c in judge.values() if c.seen_at is not None and c.seen_at >= floor]
    if len(fresh) < MIN_BOOKS:
        return None
    median = statistics.median(c.line for c in fresh)
    rec = {"game_id": gid, "week": week, "total": total, "median": median, "books": len(fresh)}
    for v, c in venue_close.items():
        entry = {"line": c.line, "off": c.line - median}
        for side in SIDES:
            price = _price(c, side)
            r = read_at_terms(judge, kickoff, MARKET, c.line, side, price, table)
            entry[side] = {
                "price": price,
                "ev": r.ev,
                "excluded": r.excluded,
                "units": units(settle(total, c.line, side), price) if total is not None else None,
            }
        rec[v] = entry
    return rec


def records(session, season: int, table) -> List[dict]:
    games = (
        session.query(Game)
        .filter(
            Game.season == season,
            Game.start_date.isnot(None),
            Game.home_points.isnot(None),
            Game.away_points.isnot(None),
        )
        .all()
    )
    meta = {g.id: g for g in games}
    ids = sorted(meta)
    snaps = defaultdict(list)
    for i in range(0, len(ids), IN_BLOCK):
        block = ids[i : i + IN_BLOCK]
        for sn in (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.game_id.in_(block), OddsSnapshot.market == MARKET)
            .all()
        ):
            snaps[sn.game_id].append(sn)
    out = []
    for gid in ids:
        sn = snaps.get(gid)
        if not sn:
            continue
        g = meta[gid]
        total = float(g.home_points + g.away_points)
        rec = game_record(gid, g.week, g.start_date, total, sn, table)
        if rec is not None:
            out.append(rec)
    return out


def _mean(xs: Sequence[float]) -> Optional[float]:
    return statistics.fmean(xs) if xs else None


def _boot_ci(xs: Sequence[float], reps: int = REPS, seed: int = 7):
    if len(xs) < 2:
        return None
    rng = random.Random(seed)
    n = len(xs)
    means = sorted(statistics.fmean(rng.choice(xs) for _ in range(n)) for _ in range(reps))
    return (means[int(0.025 * reps)], means[int(0.975 * reps) - 1])


def summarize(recs: Sequence[dict]) -> dict:
    """The numbers the report prints; pure, so a unit test can pin it."""
    out: dict = {"games": len(recs), "weeks": sorted({r["week"] for r in recs}), "venues": {}}
    for v in VENUES:
        offs = [r[v]["off"] for r in recs]
        ventry = {
            "off_mean_abs": _mean([abs(o) for o in offs]),
            "off_1pt_share": (sum(1 for o in offs if abs(o) >= OFF_PTS) / len(offs))
            if offs
            else None,
            "off_1pt_n": sum(1 for o in offs if abs(o) >= OFF_PTS),
            "sides": {},
        }
        for side in SIDES:
            evs = [r[v][side]["ev"] for r in recs if r[v][side]["ev"] is not None]
            us = [r[v][side]["units"] for r in recs if r[v][side]["units"] is not None]
            why: Dict[str, int] = defaultdict(int)
            for r in recs:
                if r[v][side]["excluded"]:
                    why[r[v][side]["excluded"]] += 1
            ventry["sides"][side] = {
                "n": len(evs),
                "ev_mean": _mean(evs),
                "ev_ci95": _boot_ci(evs),
                "units_n": len(us),
                "units_mean": _mean(us),
                "units_total": sum(us) if us else None,
                "excluded_by_reason": dict(why),
            }
        out["venues"][v] = ventry
    # the better of the two venues, per side, where both read
    best = {}
    for side in SIDES:
        pairs = [
            (r[HR_BOOK_KEY][side]["ev"], r[KALSHI][side]["ev"])
            for r in recs
            if r[HR_BOOK_KEY][side]["ev"] is not None and r[KALSHI][side]["ev"] is not None
        ]
        bests = [max(a, b) for a, b in pairs]
        best[side] = {
            "n": len(pairs),
            "ev_mean": _mean(bests),
            "ev_ci95": _boot_ci(bests),
            "kalshi_better_share": (sum(1 for a, b in pairs if b > a) / len(pairs))
            if pairs
            else None,
            "hr_mean_same_games": _mean([a for a, _ in pairs]),
            "kalshi_mean_same_games": _mean([b for _, b in pairs]),
        }
    out["best_of_two"] = best
    return out


def _pct(x) -> str:
    return "—" if x is None else f"{100 * x:+.2f}%"


def _ci(c) -> str:
    return "—" if c is None else f"{_pct(c[0])} to {_pct(c[1])}"


def render(s: dict, season: int, stamp: str) -> str:
    L = [
        f"# H-VENUE-1, Hard Rock against Kalshi on captured data ({stamp})",
        "",
        f"Season {season}, full-game totals, graded games where both venues and at least "
        f"{MIN_BOOKS} other books closed inside the judge's {CLOSE_WINDOW_H:g}-hour window; "
        "the judge counts neither venue. Kalshi's line is one rung of its ladder as the feed "
        "reports it. Intervals resample games. Exploratory: nothing is adopted from it.",
        "",
        f"Games: **{s['games']}** (weeks {', '.join(map(str, s['weeks'])) or '—'}).",
        "",
        "| venue | mean |line − median| | ≥1 pt off (share) | side | n read | mean EV (95%) | realized units (n) | no reading |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for v, ve in s["venues"].items():
        for side in SIDES:
            sd = ve["sides"][side]
            why = (
                ", ".join(f"{k} {n}" for k, n in sorted(sd["excluded_by_reason"].items())) or "none"
            )
            ut = "—" if sd["units_total"] is None else f"{sd['units_total']:+.2f} ({sd['units_n']})"
            off = "—" if ve["off_mean_abs"] is None else f"{ve['off_mean_abs']:.2f}"
            share = (
                "—"
                if ve["off_1pt_share"] is None
                else f"{ve['off_1pt_n']} ({100 * ve['off_1pt_share']:.0f}%)"
            )
            L.append(
                f"| {v} | {off} | {share} | {side} | {sd['n']} | {_pct(sd['ev_mean'])} ({_ci(sd['ev_ci95'])}) | {ut} | {why} |"
            )
    L += [
        "",
        "**The better of the two venues, per side, on games where both read**",
        "",
        "| side | games | Hard Rock mean EV | Kalshi mean EV | best-of-two mean EV (95%) | Kalshi better (share) |",
        "|---|---|---|---|---|---|",
    ]
    for side, b in s["best_of_two"].items():
        kb = "—" if b["kalshi_better_share"] is None else f"{100 * b['kalshi_better_share']:.0f}%"
        L.append(
            f"| {side} | {b['n']} | {_pct(b['hr_mean_same_games'])} | {_pct(b['kalshi_mean_same_games'])} | "
            f"{_pct(b['ev_mean'])} ({_ci(b['ev_ci95'])}) | {kb} |"
        )
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", default="reports")
    args = ap.parse_args(argv)
    if not try_init_db():
        return 1
    table = HalfPointTable.load()
    with session_scope() as s:
        recs = records(s, args.season, table)
    summary = summarize(recs)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md = render(summary, args.season, stamp)
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"venue_check_{stamp}.md").write_text(md)
    (outdir / f"venue_check_{stamp}.json").write_text(
        json.dumps({"summary": summary, "records": recs}, indent=1, default=str)
    )
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
