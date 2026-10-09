"""Per-game early line, consensus close and result: the shared frame behind the
weather history look (H-WX-HIST) and the judge check (H-JUDGE), both
exploratory rows of the October 2026 strategic review.

For one market, every FBS-vs-FBS game in the seasons asked for gets:
- `early`: the median of each counted book's EARLIEST centred line captured at
  least EARLY_MIN_HOURS before kickoff, on the half-point grid (the 2023-25
  history holds a snapshot about 48 hours out and one about 30 minutes out);
- `under` / `over`: the consensus engine's reading (beatvegas/consensus.py, the
  2026 judge) of a standard bet at the early line priced -110, against the
  consensus close;
- `close`: the consensus closing line itself, the median of the counted books
  last seen within the judge's 2-hour window, when at least MIN_BOOKS are;
- `total`: the realized total (the trusted first-half total, or the final
  score's sum) -- None when it cannot be trusted.

READ-ONLY. Pure helpers plus one loader; nothing here writes.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import timedelta
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd

from ..consensus import (
    CLOSE_WINDOW_H,
    EXCLUDED_BOOKS,
    MIN_BOOKS,
    HalfPointTable,
    book_closes,
    read_at_terms,
)
from ..db.models import Game, OddsSnapshot
from ..devig import is_centred_quote
from ..etl.fbs import filter_fbs_games, load_fbs_teams
from ..grading import american_to_decimal, trusted_first_half_total

EARLY_MIN_HOURS = 24.0
STANDARD_PRICE = -110
IN_BLOCK = 1000


def early_line(snaps: Sequence, kickoff, min_hours: float = EARLY_MIN_HOURS) -> Optional[float]:
    """Median of each counted book's earliest centred line at least `min_hours`
    before kickoff, on the half-point grid; None without one."""
    cutoff = kickoff - timedelta(hours=min_hours)
    first: Dict[str, object] = {}
    for s in snaps:
        b = (s.book or "").lower()
        if not b or b in EXCLUDED_BOOKS or s.captured_at is None or s.captured_at > cutoff:
            continue
        if s.line is None or s.over_price is None or s.under_price is None:
            continue
        if not is_centred_quote(s.over_price, s.under_price):
            continue
        if b not in first or s.captured_at < first[b].captured_at:
            first[b] = s
    if not first:
        return None
    return round(statistics.median(s.line for s in first.values()) * 2) / 2


def consensus_close_line(closes: Dict, kickoff) -> Optional[float]:
    """The consensus closing line: the median line of the counted books last seen
    within the judge's window, if at least MIN_BOOKS are; else None."""
    floor = kickoff - timedelta(hours=CLOSE_WINDOW_H)
    fresh = [c.line for c in closes.values() if c.seen_at is not None and c.seen_at >= floor]
    if len(fresh) < MIN_BOOKS:
        return None
    return round(statistics.median(fresh) * 2) / 2


def settle(total: Optional[float], line: Optional[float], side: str) -> Optional[str]:
    """'win' / 'loss' / 'push' for one side at one line, or None."""
    if total is None or line is None:
        return None
    if total == line:
        return "push"
    under_wins = total < line
    return "win" if under_wins == (side == "under") else "loss"


def units(result: Optional[str], price: int = STANDARD_PRICE) -> Optional[float]:
    """Profit per unit staked at `price`."""
    if result is None:
        return None
    return {"win": american_to_decimal(price) - 1.0, "loss": -1.0, "push": 0.0}[result]


def realized_total(g, market: str) -> Optional[float]:
    if market == "1H_total":
        return trusted_first_half_total(
            g.first_half_total, g.home_points, g.away_points, g.first_half_source
        )
    if g.home_points is None or g.away_points is None:
        return None
    return float(g.home_points + g.away_points)


def records(
    session, seasons: Iterable[int], market: str, table: Optional[HalfPointTable] = None
) -> List[dict]:
    """One dict per FBS-vs-FBS game in `seasons` with snapshots in `market`."""
    table = table or HalfPointTable.load()
    seasons = sorted({int(x) for x in seasons})
    games = session.query(Game).filter(Game.season.in_(seasons), Game.start_date.isnot(None)).all()
    df = pd.DataFrame(
        [
            {"id": g.id, "season": g.season, "home_team": g.home_team, "away_team": g.away_team}
            for g in games
        ]
    )
    if df.empty:
        return []
    keep = set(filter_fbs_games(df, load_fbs_teams())["id"])
    meta = {g.id: g for g in games if g.id in keep}
    ids = sorted(meta)
    snaps = defaultdict(list)
    for i in range(0, len(ids), IN_BLOCK):
        block = ids[i : i + IN_BLOCK]
        for sn in (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.game_id.in_(block), OddsSnapshot.market == market)
            .all()
        ):
            snaps[sn.game_id].append(sn)
    out = []
    for gid in ids:
        sn = snaps.get(gid)
        if not sn:
            continue
        g = meta[gid]
        kick = g.start_date
        closes = book_closes(sn, kick)
        early = early_line(sn, kick)
        rec = {
            "game_id": gid,
            "season": g.season,
            "season_type": g.season_type or "regular",
            "week": g.week,
            "kickoff": kick,
            "early": early,
            "close": consensus_close_line(closes, kick),
            "total": realized_total(g, market),
        }
        for side in ("under", "over"):
            # the judge's half-point table is keyed by the SNAPSHOT market
            # ('1H_total' / 'full_game_total'), as picks read it through SNAP_MARKET
            r = read_at_terms(closes, kick, market, early, side, STANDARD_PRICE, table)
            rec[side] = {"ev": r.ev, "excluded": r.excluded, "books": r.books}
        out.append(rec)
    return out


def exclusion_counts(
    recs: Iterable[dict], sides: Sequence[str] = ("under", "over")
) -> Dict[str, int]:
    """Why each bet had no reading, by reason -- so a run that reads nothing
    says why instead of printing an empty table."""
    out: Dict[str, int] = defaultdict(int)
    for r in recs:
        for side in sides:
            if r[side]["ev"] is None:
                out[
                    "no_early_line" if r["early"] is None else (r[side]["excluded"] or "no_ev")
                ] += 1
    return dict(out)


def week_key(rec: dict) -> tuple:
    """Bowls are filed as week 1: key on the season type too."""
    return (rec["season"], rec["season_type"], rec["week"])


def bootstrap_mean_ci(
    groups: Sequence[Sequence[float]], reps: int = 2000, seed: int = 11
) -> Optional[tuple]:
    """Percentile 95% interval of the pooled mean, resampling whole weeks."""
    import random

    gs = [list(g) for g in groups if g]
    if len(gs) < 2:
        return None
    rnd = random.Random(seed)
    means = []
    for _ in range(reps):
        sample = [gs[rnd.randrange(len(gs))] for _ in gs]
        flat = [x for g in sample for x in g]
        means.append(sum(flat) / len(flat))
    means.sort()
    return (means[int(0.025 * reps)], means[int(0.975 * reps) - 1])
