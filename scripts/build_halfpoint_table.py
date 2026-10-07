#!/usr/bin/env python
"""Build the half-point value table the consensus engine converts lines with
(docs/CONSENSUS.md, beatvegas/halfpoint.py).

Reads FBS-vs-FBS games 2013-2025 -- closing full-game total, closing spread,
the trusted first-half total, the final -- and writes
reports/halfpoint_hp1_<UTC>.json plus a short .md summary. READ-ONLY: it writes
no table. Runs where Neon is reachable, so on campus through study.yml:

    gh workflow run study.yml --ref <branch> -f script=build_halfpoint_table

The committed data/halfpoint_hp1.json is the downloaded artifact, frozen: the
engine's version names it, and a change is a new version, never an edit.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from beatvegas.db.models import Game
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.fbs import filter_fbs_games, load_fbs_teams
from beatvegas.grading import trusted_first_half_total
from beatvegas.halfpoint import (
    MIN_N,
    SPAN_PTS,
    WINDOW_PTS,
    market_table,
    pairs_from_rows,
    push_rates,
)

ROOT = Path(__file__).resolve().parent.parent
FIRST_SEASON, LAST_SEASON = 2013, 2025


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports")
    args = ap.parse_args(argv)
    if not try_init_db():
        return 1
    mult = json.loads((ROOT / "data" / "multiplier.json").read_text())
    with session_scope() as s:
        games = (
            s.query(Game)
            .filter(Game.season >= FIRST_SEASON, Game.season <= LAST_SEASON)
            .filter(Game.home_points.isnot(None), Game.away_points.isnot(None))
            .all()
        )
        df = pd.DataFrame(
            [
                {
                    "id": g.id,
                    "season": g.season,
                    "home_team": g.home_team,
                    "away_team": g.away_team,
                    "full_game_total": g.full_game_total,
                    "spread": g.spread,
                    "fh_trusted": trusted_first_half_total(
                        g.first_half_total, g.home_points, g.away_points, g.first_half_source
                    ),
                    "final_total": g.home_points + g.away_points,
                }
                for g in games
            ]
        )
    n_all = len(df)
    df = filter_fbs_games(df, load_fbs_teams())
    rows = df.where(pd.notna(df), None).to_dict("records")
    fh, fg = pairs_from_rows(rows, mult["base"], mult["blowout"], mult["cut"])
    t_fh = market_table(fh)
    t_fg = market_table(fg)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {
        "version": "hp1",
        "built_at": stamp,
        "seasons": [FIRST_SEASON, LAST_SEASON],
        "filters": "FBS-vs-FBS (data/fbs_teams.json), played, trusted first-half total for 1H",
        "window_pts": WINDOW_PTS,
        "span_pts": SPAN_PTS,
        "min_n": MIN_N,
        "first_half_expectation": {
            "proxy": "closing full-game total x step share",
            "base": mult["base"],
            "blowout": mult["blowout"],
            "cut": mult["cut"],
        },
        "games": {
            "read": n_all,
            "fbs": len(df),
            "first_half_pairs": len(fh),
            "full_game_pairs": len(fg),
        },
        "markets": {
            "1H_total": {"centers": t_fh},
            "full_game_total": {"centers": t_fg},
        },
    }
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    jp = outdir / f"halfpoint_hp1_{stamp}.json"
    jp.write_text(json.dumps(out, indent=1, sort_keys=True))
    lines = [
        f"# Half-point table hp1 ({stamp})",
        "",
        f"Games read {n_all}, FBS-vs-FBS {len(df)}; first-half pairs {len(fh)}, full-game pairs {len(fg)}.",
        "",
    ]
    for name, t in (("1H_total", t_fh), ("full_game_total", t_fg)):
        cs = sorted(float(c) for c in t)
        lines.append(
            f"## {name}: {len(t)} centers" + (f", {cs[0]:.1f} to {cs[-1]:.1f}" if cs else "")
        )
        lines.append("")
        lines.append("| integer center | games | push rate |")
        lines.append("|---|---|---|")
        for c, p in sorted(push_rates(t).items(), key=lambda kv: float(kv[0])):
            lines.append(f"| {c} | {t[c]['n']} | {p:.3f} |")
        lines.append("")
    (outdir / f"halfpoint_hp1_{stamp}.md").write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"wrote {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
