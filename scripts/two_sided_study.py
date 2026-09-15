#!/usr/bin/env python
"""Two-sided diagnostic: does a NEGATIVE gap carry over-side information?

A REPORT, NOT A BET (Tate, 2026-09-15: measurement only, first of the research
queue). Mirrors the under ladder on the over side at the real close, 2023-25 FBS,
plus the live 2026 weeks at Hard Rock's number. The decision rule lives in
beatvegas/backtest/two_sided.py::verdict and was written before any number was
read.

    PYTHONPATH=. python scripts/two_sided_study.py --out reports/two_sided

Writes <out>_<UTC>.md and .json, appends the markdown to $GITHUB_STEP_SUMMARY when
set, exits 0 whatever the numbers say. Reads Neon; writes nothing; spends no API
calls -- every input is already in postmortem_games.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import pandas as pd
from sqlalchemy import text

from beatvegas.backtest import two_sided as T
from beatvegas.db.store import session_scope, try_init_db

HIST_SCOPE = "hist_2023_25"
LIVE_SCOPE = "live_2026"


def _latest_run(session, scope: str) -> str:
    return session.execute(
        text(
            "select run_id from postmortem_runs where scope = :s order by computed_at desc limit 1"
        ),
        {"s": scope},
    ).scalar()


def load_frames(hist_scope: str, live_scope: str):
    with session_scope() as s:
        hist_run = _latest_run(s, hist_scope)
        live_run = _latest_run(s, live_scope)
        hist = pd.DataFrame(
            s.execute(
                text(
                    """
                select game_id, season, week, gap_real as gap, outcome_real as outcome, spread_abs
                from postmortem_games
                where run_id = :r and scope = :s and division = 'fbs'
                  and line_real is not null and outcome_real is not null
                """
                ),
                {"r": hist_run, "s": hist_scope},
            )
            .mappings()
            .all()
        )
        live = pd.DataFrame(
            s.execute(
                text(
                    """
                select game_id, season, week, gap, outcome_hr as outcome, spread_abs
                from postmortem_games
                where run_id = :r and scope = :s and hr_line is not null
                  and outcome_hr is not null and gap is not null and fh is not null
                """
                ),
                {"r": live_run, "s": live_scope},
            )
            .mappings()
            .all()
        )
    for df in (hist, live):
        for c in ("gap", "week", "season", "spread_abs"):
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    return hist, live, hist_run, live_run


def run(hist: pd.DataFrame, live: pd.DataFrame, n_boot: int) -> Dict[str, Any]:
    hist = hist.copy()
    hist["week_band"] = hist["week"].map(T.week_band)
    sym = T.symmetry(hist, "gap", "outcome")
    seasons = T.per_group(hist, "gap", "outcome", "season")
    return {
        "hist_scope": HIST_SCOPE,
        "live_scope": LIVE_SCOPE,
        "hist_n": int(len(hist)),
        "live_n": int(len(live)),
        "hist_ladder": T.ladder(hist, "gap", "outcome"),
        "hist_symmetry": sym,
        "hist_per_season": seasons,
        "hist_per_week_band": T.per_group(hist, "gap", "outcome", "week_band"),
        "hist_slope": T.gap_slope(hist, "gap", "outcome", n_boot=n_boot),
        "live_ladder": T.ladder(live, "gap", "outcome"),
        "live_symmetry": T.symmetry(live, "gap", "outcome"),
        "verdict": T.verdict(sym, seasons),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports/two_sided")
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args()
    if not try_init_db():
        print("[two_sided] DB unreachable — skipped.")
        return
    hist, live, hist_run, live_run = load_frames(HIST_SCOPE, LIVE_SCOPE)
    r = run(hist, live, args.n_boot)
    r["hist_run_id"], r["live_run_id"] = hist_run, live_run
    md = T.render_markdown(r)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(f"{args.out}_{stamp}.md", "w") as f:
        f.write(md)
    with open(f"{args.out}_{stamp}.json", "w") as f:
        json.dump(r, f, indent=1, default=str)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(md)
    print(md)
    print(f"wrote {args.out}_{stamp}.md")
    v = r["verdict"]
    print("VERDICT:", "OVER-SIDE SIGNAL" if v["over_side_signal"] else "NO OVER-SIDE FINDING")


if __name__ == "__main__":
    main()
