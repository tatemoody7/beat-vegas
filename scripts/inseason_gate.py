#!/usr/bin/env python
"""Walk-forward gate for an IN-SEASON calibration intercept: the report that
answers H-INSEASON in docs/HYPOTHESES.md.

`score_slate` trains on `season < target_season` strictly, so the current
season's completed games reach neither the fit nor the calibration intercept.
H-INTERCEPT showed that shrinking the prior-season intercept cannot help --
2025 needs MORE correction while 2026 needs less, so no constant multiplier
serves both (docs/MODEL_LEVEL_2026.md). Each arm here blends the prior-season
intercept with the season's OWN realized bias,
`c_t = (1-w)*c_prior + w*c_season` at `w = n/(n+k)`, under an as-of window that
closes strictly before the game being scored. See
beatvegas/backtest/inseason.py for the rule, frozen before the script existed.

    python scripts/inseason_gate.py --out reports/inseason \
        [--test-seasons 2024 2025 2026] [--grid 25 50 100 200] [--no-closes]

Writes <out>_<UTC>.md, .json and .csv (the per-game frame, so the tables can be
interrogated without re-running), appends the markdown to $GITHUB_STEP_SUMMARY
when set, and exits 0 whatever the numbers say: it is a report, not a CI gate.
Needs the database and the CFBD cache; `--no-closes` skips the DB read for real
1H closes and still produces the primary tables. Spends no Odds API credits, and
no CFBD calls for any season whose priors are already cached.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import List, Optional, Sequence

from beatvegas.backtest.inseason import K_GRID, TEST_SEASONS, evaluate, render_markdown
from beatvegas.backtest.residual_gate import GateNotEvaluable
from beatvegas.db.store import try_init_db
from beatvegas.etl.features import build_feature_frame

# The sibling gates' plumbing, not a second copy of it: same stamped triple, same
# step-summary behaviour, same real-close lookup, so the reports stay comparable.
from scripts.level_anchor_gate import load_closes
from scripts.residual_gate import append_step_summary, report_paths


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--test-seasons", type=int, nargs="+", default=list(TEST_SEASONS))
    p.add_argument(
        "--grid",
        type=float,
        nargs="+",
        default=list(K_GRID),
        help="in-season half-weights k; the incumbent (w=0) is always added",
    )
    # The live board scores from a min_games=0 frame (scripts/weekly_update.py),
    # and build_feature_frame's own default is 2. This gate follows the board.
    p.add_argument("--min-games", type=int, default=0)
    p.add_argument("--out", default="reports/inseason")
    p.add_argument("--all-divisions", action="store_true", help="drop the FBS-vs-FBS filter")
    p.add_argument(
        "--no-closes",
        action="store_true",
        help="skip the secondary selection table (no DB read for real 1H closes)",
    )
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try_init_db()

    frame = build_feature_frame(min_games=args.min_games, fbs_only=not args.all_divisions)

    closes = {}
    if not args.no_closes:
        ids = frame.loc[frame["season"].isin([int(s) for s in args.test_seasons]), "id"].tolist()
        closes = load_closes(ids)

    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    md_path, json_path, csv_path = report_paths(args.out, stamp)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        res = evaluate(
            frame,
            test_seasons=[int(s) for s in args.test_seasons],
            grid=[float(x) for x in args.grid],
            closes=closes or None,
            min_games=args.min_games,
            fbs_only=not args.all_divisions,
        )
    except GateNotEvaluable as e:
        # A coverage problem is a report that says so, not a traceback. Anything
        # else is a defect and must fail loudly -- the split residual_gate makes.
        md = f"# In-season intercept gate — NOT EVALUATED\n\n{e}\n"
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

    adopted: List[str] = [a["label"] for a in res.report["arms"] if a["verdict"]["adopt"]]
    print(f"ADOPT: {adopted}" if adopted else "ADOPT: none — the intercept stays as it is")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
