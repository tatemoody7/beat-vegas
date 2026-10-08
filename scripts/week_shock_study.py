#!/usr/bin/env python
"""WEEK-SHOCK (docs/HYPOTHESES.md): how much of line value is shared by every
bet in a week? Sizes the Statistical Protocol (docs/PROTOCOL_2026.md).

For every FBS-vs-FBS game with a first-half (and, separately, full-game) opener
and close on file, one standard bet -- the UNDER at the median opening line of
the counted books, priced -110 -- is read by the consensus engine
(beatvegas/consensus.py, cv1) against the consensus close. The EVs are grouped
by week and split into a week-wide component (`between`) and a game component
(`within`) by beatvegas.protocol.variance_components, with a week-resampled
interval. 2023-25 and 2026 are reported separately. READ-ONLY; writes
reports/week_shock_<UTC>.{md,json}. Runs through study.yml.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from beatvegas.consensus import EXCLUDED_BOOKS, HalfPointTable, consensus_reading
from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.devig import is_centred_quote
from beatvegas.etl.fbs import filter_fbs_games, load_fbs_teams
from beatvegas.protocol import bootstrap_between, variance_components

ROOT = Path(__file__).resolve().parent.parent
MARKETS = ("1H_total", "full_game_total")
IN_BLOCK = 1000


def opening_line(snaps, kickoff):
    """Median of each counted book's EARLIEST centred line before kickoff, on
    the half-point grid; None without one."""
    first = {}
    for s in snaps:
        b = (s.book or "").lower()
        if not b or b in EXCLUDED_BOOKS or s.captured_at is None or s.captured_at > kickoff:
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports")
    args = ap.parse_args(argv)
    if not try_init_db():
        return 1
    table = HalfPointTable.load()
    results = {}
    with session_scope() as s:
        games = (
            s.query(Game)
            .filter(Game.season >= 2023, Game.season <= 2026, Game.start_date.isnot(None))
            .all()
        )
        df = pd.DataFrame(
            [
                {"id": g.id, "season": g.season, "home_team": g.home_team, "away_team": g.away_team}
                for g in games
            ]
        )
        keep = set(filter_fbs_games(df, load_fbs_teams())["id"])
        meta = {g.id: g for g in games if g.id in keep}
        ids = sorted(meta)
        snaps = defaultdict(list)
        for i in range(0, len(ids), IN_BLOCK):
            block = ids[i : i + IN_BLOCK]
            for sn in (
                s.query(OddsSnapshot)
                .filter(OddsSnapshot.game_id.in_(block), OddsSnapshot.market.in_(MARKETS))
                .all()
            ):
                snaps[(sn.game_id, sn.market)].append(sn)
        for market in MARKETS:
            for era, seasons in (("2023-25", {2023, 2024, 2025}), ("2026", {2026})):
                weeks = defaultdict(list)
                excluded = Counter()
                for gid in ids:
                    g = meta[gid]
                    if g.season not in seasons:
                        continue
                    sn = snaps.get((gid, market))
                    if not sn:
                        continue
                    line = opening_line(sn, g.start_date)
                    if line is None:
                        excluded["no_opener"] += 1
                        continue
                    r = consensus_reading(sn, g.start_date, market, line, "under", -110, table)
                    if r.ev is None:
                        excluded[r.excluded or "no_ev"] += 1
                        continue
                    weeks[(g.season, g.season_type or "regular", g.week)].append(r.ev)
                groups = list(weeks.values())
                vc = variance_components(groups)
                ci = bootstrap_between(groups) if vc["between"] is not None else None
                sizes = [len(x) for x in groups]
                results[f"{market}|{era}"] = {
                    **vc,
                    "between_ci_2.5_5_95_97.5": ci,
                    "weeks": len(groups),
                    "games_per_week_median": statistics.median(sizes) if sizes else None,
                    "excluded": dict(excluded),
                }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md = [
        f"# WEEK-SHOCK ({stamp})",
        "",
        "Standard bet: the under at the median opening line, priced -110, read by the consensus engine (cv1)",
        "against the close. `week sd` is the component every bet in a week shares; `game sd` the rest.",
        "",
        "| market | era | games | weeks | games/week (median) | mean EV | total sd | week sd (95% interval) | game sd | share of variance from the week | excluded |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key, r in results.items():
        m, era = key.split("|")
        if r["between"] is None:
            md.append(
                f"| {m} | {era} | {r['n']} | {r['weeks']} | — | — | — | — | — | — | {r['excluded']} |"
            )
            continue
        ci = r["between_ci_2.5_5_95_97.5"]
        md.append(
            f"| {m} | {era} | {r['n']} | {r['weeks']} | {r['games_per_week_median']} | {r['mean']:+.3f} | {r['total']:.3f} | "
            f"{r['between']:.3f} ({ci[0]:.3f}–{ci[3]:.3f}) | {r['within']:.3f} | {r['icc']:.3f} | {r['excluded']} |"
        )
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"week_shock_{stamp}.md").write_text("\n".join(md) + "\n")
    (outdir / f"week_shock_{stamp}.json").write_text(json.dumps(results, indent=1, default=str))
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
