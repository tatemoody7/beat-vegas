#!/usr/bin/env python
"""Walk-forward gate for `bv_line`'s GLOBAL CALIBRATION INTERCEPT: the report
that closes H-INTERCEPT in docs/HYPOTHESES.md.

`bv_line_for_slate` adds `bias_corrections(train)["global"]` to every prediction.
docs/MODEL_LEVEL_2026.md measured what that did in 2026: -1.81 applied where the
season needed +1.09, and that 2.90-point gap is the entire level deficit which
took the fixed 1.75-point bar from selecting ~15% of the board to ~half of it.
Each arm scales the intercept by lambda, so lambda=1 reproduces the live number
exactly and lambda=0 drops it. See beatvegas/backtest/intercept.py for the
adoption rule, quoted from the registry row and applied verbatim.

    python scripts/intercept_gate.py --out reports/intercept \
        [--test-seasons 2024 2025 2026] [--grid 0 0.25 0.5 0.75 1] [--no-closes]

Writes <out>_<UTC>.md, .json and .csv (the per-game frame, so the tables can be
interrogated without re-running), appends the markdown to $GITHUB_STEP_SUMMARY
when set, and exits 0 whatever the numbers say: it is a report, not a CI gate.
Needs the database and the CFBD cache; `--no-closes` skips the DB read and still
produces the primary table. Spends no Odds API credits, and no CFBD calls for any
season whose priors are already cached.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from beatvegas.backtest.harness import HarnessSpec, incumbent_arm, load_frame
from beatvegas.backtest.intercept import (
    INCUMBENT_LAMBDA,
    LAMBDA_GRID,
    TEST_SEASONS,
    evaluate,
    render_markdown,
)
from beatvegas.backtest.residual_gate import GateNotEvaluable
from beatvegas.db.store import try_init_db
from beatvegas.etl.features import apply_min_games
from beatvegas.registry import HarnessRefusal

# Run as `python scripts/<name>.py` (the workflows do), sys.path holds scripts/
# and not the repo root, so `from scripts.x import` fails with
# ModuleNotFoundError -- which is how intercept_gate.yml died on the runner on
# 2026-09-22 without anyone noticing the study had only ever run on a laptop.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
        default=list(LAMBDA_GRID),
        help="intercept multipliers to try; must include 1.0 (the incumbent arm)",
    )
    # The live board scores from a min_games=0 frame (scripts/weekly_update.py),
    # and build_feature_frame's own default is 2. This gate follows the board.
    p.add_argument("--min-games", type=int, default=0)
    p.add_argument(
        "--frame",
        default=None,
        help="a scripts/frame_snapshot.py pickle (carrying attrs['build']) to re-cut at "
        "--min-games instead of building the frame",
    )
    p.add_argument("--out", default="reports/intercept")
    p.add_argument("--all-divisions", action="store_true", help="drop the FBS-vs-FBS filter")
    p.add_argument(
        "--no-closes",
        action="store_true",
        help="skip the secondary selection table (no DB read for real 1H closes)",
    )
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if INCUMBENT_LAMBDA not in [float(x) for x in args.grid]:
        print("--grid must include 1.0 (the incumbent arm)", file=sys.stderr)
        return 2
    try_init_db()

    # The frame comes through the shared harness loader (beatvegas/backtest/harness.py):
    # built at --min-games as before, or a --frame snapshot (scripts/frame_snapshot.py,
    # with attrs["build"]) re-cut at it. Either way the fingerprint -- WHICH snapshot
    # of CFBD's reference tables this run was judged on (docs/MODEL_LEVEL_2026.md,
    # Reconciliation) -- is written beside the report as <stem>_frame.json before
    # anything is scored.
    md_path, _json_path, _csv = report_paths(args.out)
    spec = HarnessSpec(
        row_id="H-INTERCEPT",
        arms=(incumbent_arm(),),
        test_seasons=tuple(int(s) for s in args.test_seasons),
        min_games_train=args.min_games,
        min_games_score=args.min_games,
        fbs_only=not args.all_divisions,
    )
    try:
        frame, fp = load_frame(
            Path(args.frame) if args.frame else None,
            spec,
            md_path.with_name(md_path.stem + "_frame.json"),
        )
    except HarnessRefusal as e:
        print(f"::error::{e}", file=sys.stderr)
        return 2
    # A snapshot may be finer than --min-games; a built frame is already at it (no-op).
    frame = apply_min_games(frame, args.min_games).reset_index(drop=True)
    print(
        f"[gate] frame fingerprint: rows={fp['rows']} by_season={fp['by_season']} sklearn={fp['sklearn']}"
    )

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
        md = f"# Intercept gate — NOT EVALUATED\n\n{e}\n"
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

    adopted: List[float] = [a["lambda"] for a in res.report["arms"] if a["verdict"]["adopt"]]
    print(f"ADOPT: {adopted}" if adopted else "ADOPT: none — the intercept stays as it is")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
