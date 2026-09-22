#!/usr/bin/env python
"""Walk-forward gate for the prior-season LEVEL ANCHOR: the report the owner
reads to decide whether etl.features.PRIOR_SEASON_WEIGHT should be anything
other than 0.

`_season_to_date` computes a team's form as an expanding mean over its prior
games THIS season, so game 1 of every season is NaN. The change seeds that
window with k synthetic games of the team's prior-season mean. Because the seed
changes FEATURE_COLS values on every historical row -- not just the early-season
ones it targets -- it moves bv_line in weeks 3+ where nothing is currently
broken, and so it needs a gate rather than a merge.

k=0 reproduces the unseeded frame exactly, so the incumbent is an ARM of this
experiment rather than a separate code path. Every comparison is PAIRED on the
same games. See beatvegas/backtest/level_anchor.py for the adoption rule, which
was fixed before the first run, and for what that run found.

    python scripts/level_anchor_gate.py --train-seasons 2023 --test-season 2024 \
        --out reports/level_anchor [--grid 0 0.5 1 2 3] [--no-closes]

Writes <out>_<UTC>.md, .json and .csv (the per-game frame, so the tables can be
interrogated without re-running), appends the markdown to $GITHUB_STEP_SUMMARY
when set, and exits 0 whatever the numbers say: it is a report, not a CI gate.
Needs the database and the CFBD cache. Spends no Odds API credits, and no CFBD
calls for any season whose priors are already cached.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from beatvegas.backtest.level_anchor import (
    PRIOR_WEIGHT_GRID,
    evaluate,
    render_markdown,
)
from beatvegas.backtest.residual_gate import GateNotEvaluable
from beatvegas.db.models import Game
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.features import build_feature_frame
from beatvegas.lines import REAL_1H_CLOSE_WINDOW_H, real_closes

# Run as `python scripts/<name>.py` (the workflows do), sys.path holds scripts/
# and not the repo root, so `from scripts.x import` fails with
# ModuleNotFoundError -- which is how intercept_gate.yml died on the runner on
# 2026-09-22 without anyone noticing the study had only ever run on a laptop.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Reuse the residual gate's output plumbing rather than restating it -- same
# stamped triple, same step-summary behaviour, so the two reports are siblings.
from scripts.residual_gate import append_step_summary, report_paths


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--train-seasons", type=int, nargs="+", default=[2023])
    p.add_argument("--test-season", type=int, default=2024)
    p.add_argument(
        "--grid",
        type=float,
        nargs="+",
        default=list(PRIOR_WEIGHT_GRID),
        help="prior-season weights to try; must include 0 (the incumbent arm)",
    )
    p.add_argument("--min-games", type=int, default=0)
    p.add_argument("--out", default="reports/level_anchor")
    p.add_argument("--all-divisions", action="store_true", help="drop the FBS-vs-FBS filter")
    p.add_argument(
        "--no-closes",
        action="store_true",
        help="skip the selection table (no DB read for real 1H closes)",
    )
    return p.parse_args(argv)


def load_closes(game_ids: Sequence[int]) -> Dict[int, float]:
    """Real captured pre-kick 1H closes for the test season's games.

    Only for the SELECTION table: how a level shift moves games across
    BET_GAP_PTS. Never used to grade a prediction, and games without one are
    absent rather than filled with a proxy."""
    if not game_ids:
        return {}
    with session_scope() as s:
        kicks = {
            g.id: g.start_date for g in s.query(Game).filter(Game.id.in_(list(game_ids))).all()
        }
        return real_closes(
            s, list(game_ids), kicks, market="1H_total", within_hours=REAL_1H_CLOSE_WINDOW_H
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if 0.0 not in [float(k) for k in args.grid]:
        print("--grid must include 0 (the incumbent arm)", file=sys.stderr)
        return 2
    try_init_db()

    ks = [float(k) for k in args.grid]
    frames = {
        k: build_feature_frame(
            min_games=args.min_games, fbs_only=not args.all_divisions, prior_weight=k
        )
        for k in ks
    }

    closes: Dict[int, float] = {}
    if not args.no_closes:
        test_ids = frames[0.0].loc[frames[0.0]["season"] == args.test_season, "id"].tolist()
        closes = load_closes(test_ids)

    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    md_path, json_path, csv_path = report_paths(args.out, stamp)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        res = evaluate(
            args.train_seasons,
            args.test_season,
            prior_weights=ks,
            min_games=args.min_games,
            fbs_only=not args.all_divisions,
            frames=frames,
            closes=closes or None,
        )
    except GateNotEvaluable as e:
        # A coverage problem is a report that says so, not a traceback. Anything
        # else is a defect and must fail loudly -- same split residual_gate makes.
        md = f"# Level-anchor gate — NOT EVALUATED\n\n{e}\n"
        md_path.write_text(md)
        append_step_summary(md)
        print(md)
        return 0

    md = render_markdown(res.report)
    md_path.write_text(md)
    json_path.write_text(json.dumps(res.report, indent=2))
    res.per_game.to_csv(csv_path, index=False)
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path.name}, {json_path.name}, {csv_path.name}")

    adopted: List[float] = [a["prior_weight"] for a in res.report["arms"] if a["verdict"]["adopt"]]
    print(f"ADOPT: {adopted}" if adopted else "ADOPT: none — PRIOR_SEASON_WEIGHT stays 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
