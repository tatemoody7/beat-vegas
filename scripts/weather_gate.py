#!/usr/bin/env python
"""Blast radius of the repaired weather, for the ACTIVATION decision.

    PYTHONPATH=. python scripts/weather_gate.py --train-seasons 2023 2024 \
        --test-season 2025 --out reports/weather_gate [--arms legacy 0 24 72]

The weather values in the legacy table are wrong -- keyed with a UTC hour against
a local-time series -- and the repair is verified against ground truth by
`scripts/weather_validate.py`, not here. This report exists to answer a different
question: WHEN does the live model start reading the repaired values, given that
there is real money on a card most weeks.

Pre-registered before the first run: promote before the next card if few enough
games cross BET_GAP_PTS that each mover can be looked at individually; otherwise
promote once that card settles. The fix lands either way.

Do NOT read a flat or worse MAE as a reason to leave the wrong values in place.
MAE is near-blind to a change of this size against ~11 points of per-game spread
-- that is the documented level-anchor lesson (docs/LEVEL_ANCHOR.md).

Writes <out>_<UTC>.md, .json and .csv, appends the markdown to
$GITHUB_STEP_SUMMARY when set, and exits 0 whatever the numbers say: it is a
report, not a CI gate. Needs the database. Spends no Odds API credits.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from beatvegas.backtest.residual_gate import GateNotEvaluable
from beatvegas.backtest.weather_gate import (
    WEATHER_ARMS,
    evaluate,
    render_markdown,
)
from beatvegas.db.models import Game
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.features import build_feature_frame
from beatvegas.lines import REAL_1H_CLOSE_WINDOW_H, real_closes

# Reuse the residual gate's output plumbing rather than restating it -- same
# stamped triple, same step-summary behaviour, so the reports are siblings.
from scripts.residual_gate import append_step_summary, report_paths


def _arm(token: str) -> Optional[int]:
    return None if token.lower() in ("legacy", "none") else int(token)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--train-seasons", type=int, nargs="+", default=[2023, 2024])
    p.add_argument("--test-season", type=int, default=2025)
    p.add_argument(
        "--arms",
        nargs="+",
        default=[("legacy" if x is None else str(x)) for x in WEATHER_ARMS],
        help="weather leads to compare; must include 'legacy' (the incumbent arm)",
    )
    p.add_argument("--min-games", type=int, default=0)
    p.add_argument("--out", default="reports/weather_gate")
    p.add_argument("--all-divisions", action="store_true", help="drop the FBS-vs-FBS filter")
    p.add_argument(
        "--no-closes",
        action="store_true",
        help="skip the crossing table (no DB read for real 1H closes)",
    )
    return p.parse_args(argv)


def load_closes(game_ids: Sequence[int]) -> Dict[int, float]:
    """Real captured pre-kick 1H closes for the test season's games.

    Only for the crossing table: how the repair moves games across BET_GAP_PTS.
    Never used to grade a prediction, and a game without one is absent rather
    than filled with a proxy."""
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
    arms: List[Optional[int]] = [_arm(a) for a in args.arms]
    if None not in arms:
        print("--arms must include 'legacy' (the incumbent arm)", file=sys.stderr)
        return 2
    try_init_db()

    fbs_only = not args.all_divisions
    frames = {
        ("legacy" if lead is None else f"lead{lead}"): build_feature_frame(
            min_games=args.min_games, fbs_only=fbs_only, weather_lead=lead
        )
        for lead in arms
    }

    closes: Dict[int, float] = {}
    if not args.no_closes:
        base = frames["legacy"]
        closes = load_closes(base.loc[base["season"] == args.test_season, "id"].tolist())

    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    md_path, json_path, csv_path = report_paths(args.out, stamp)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        res = evaluate(
            args.train_seasons,
            args.test_season,
            arms=arms,
            min_games=args.min_games,
            fbs_only=fbs_only,
            frames=frames,
            closes=closes or None,
        )
    except GateNotEvaluable as e:
        # A coverage problem is a report that says so, not a traceback. Anything
        # else is a defect and must fail loudly -- the same split residual_gate makes.
        md = f"# Weather gate — NOT EVALUATED\n\n{e}\n"
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
    print(
        "ACTIVATION IS A SEPARATE DECISION: set etl/features.py::WEATHER_OBS_LEAD_HOURS only on the owner's call."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
