#!/usr/bin/env python
"""Run the shared measurement harness for ONE registry row and write its report.

    python scripts/harness_report.py --row H-X --test-seasons 2024 2025 2026 \
        [--frame reports/frame_snapshot_<UTC>.pkl] \
        [--min-games-train 0] [--min-games-score 0] \
        [--candidate beatvegas.some.module:fn --candidate-name plus1]... \
        [--criterion beatvegas.some.module:fn] \
        [--decision-rule "consensus_as_of(fri_pm)"] [--out reports/harness_<ID>] [--all-divisions]

Order of operations, and why it matters (docs/HARNESS.md):

1. The registry row is checked FIRST (beatvegas/registry.py). A row that is
   unknown, whose status is not `pre-registered` / `exploratory`, or whose
   criterion cell is empty is refused with exit 2 BEFORE the database is opened
   -- a refused run leaves no trace but one stderr line and a step-summary line.
2. Candidate and criterion functions are resolved from dotted `module:fn`
   paths and must live under `beatvegas.`; anything else is refused (exit 2).
3. Only then: `try_init_db`, the feature frame (built at the finer min_games
   knob, or a `--frame` snapshot re-cut), its fingerprint (`<stem>_frame.json`,
   written before anything is scored), the real closes and the decision lines
   out of `odds_snapshots`, and one `harness.run`.
4. A test season with zero real closes is a NOT EVALUABLE report and exit 0.

It measures. It writes no table and no `model_runs` row, spends no Odds API
credits, and runs ONCE per registered row on the runner (`study.yml`).
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

from beatvegas.backtest import harness as H
from beatvegas.backtest.reporting import append_step_summary, report_paths, utc_stamp
from beatvegas.backtest.residual_gate import GateNotEvaluable
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.registry import HarnessRefusal, require_runnable_row
from beatvegas.snapshots import (
    DEFAULT_DECISION_RULE,
    consensus_closes,
    decision_lines,
    hr_close_prices,
    hr_closes,
    kickoffs_for,
    parse_decision_rule,
)

ALLOWED_MODULE_PREFIX = "beatvegas."
REFUSED = 2


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--row", required=True, help="docs/HYPOTHESES.md row id this run measures")
    ap.add_argument("--test-seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    ap.add_argument(
        "--frame",
        default=None,
        help="a scripts/frame_snapshot.py pickle to re-cut instead of building the frame",
    )
    # The live board scores from a min_games=0 frame (scripts/weekly_update.py ->
    # score_slate trains on whatever frame it is handed), so both default to 0.
    ap.add_argument("--min-games-train", type=int, default=0)
    ap.add_argument("--min-games-score", type=int, default=0)
    ap.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="beatvegas.module.path:function with the bv_line_for_slate contract; repeatable",
    )
    ap.add_argument(
        "--candidate-name",
        action="append",
        default=[],
        help="display name for the --candidate in the same position (default: the function name)",
    )
    ap.add_argument(
        "--criterion",
        default=None,
        help="beatvegas.module.path:function(report) -> True | False | None (pre-registered rows only)",
    )
    ap.add_argument("--decision-rule", default=DEFAULT_DECISION_RULE)
    ap.add_argument(
        "--out", default=None, help="report path prefix (default reports/harness_<ROW>)"
    )
    ap.add_argument(
        "--all-divisions",
        dest="fbs_only",
        action="store_false",
        help="include non-FBS games in the feature frame (default: FBS-only, as production)",
    )
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    return ap.parse_args(argv)


def resolve_callable(dotted: str) -> Callable[..., Any]:
    """`beatvegas.x.y:fn` -> the function. Refuses anything outside `beatvegas.`
    so a dispatch argument cannot import arbitrary code on a runner holding
    the database secret."""
    if ":" not in dotted:
        raise HarnessRefusal(f"expected module:function, got {dotted!r}")
    mod_name, fn_name = dotted.split(":", 1)
    if not mod_name.startswith(ALLOWED_MODULE_PREFIX):
        raise HarnessRefusal(
            f"candidate/criterion module must start with {ALLOWED_MODULE_PREFIX!r}, got {mod_name!r}"
        )
    try:
        mod = importlib.import_module(mod_name)
    except ImportError as e:
        raise HarnessRefusal(f"cannot import {mod_name!r}: {e}") from e
    fn = getattr(mod, fn_name, None)
    if fn is None or not callable(fn):
        raise HarnessRefusal(f"{mod_name!r} has no callable {fn_name!r}")
    return fn


def build_arms(args: argparse.Namespace) -> List[H.Arm]:
    arms = [H.incumbent_arm()]
    if len(args.candidate_name) > len(args.candidate):
        raise HarnessRefusal("more --candidate-name values than --candidate values")
    for i, dotted in enumerate(args.candidate):
        fn = resolve_callable(dotted)
        name = args.candidate_name[i] if i < len(args.candidate_name) else dotted.split(":", 1)[1]
        arms.append(H.Arm(name, fn))
    return arms


def _refuse(msg: str) -> int:
    line = f"HARNESS REFUSED: {msg}"
    print(f"::error::{line}", file=sys.stderr)
    append_step_summary(f"**{line}**")
    return REFUSED


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    # 1. registry first, no database yet
    try:
        row = require_runnable_row(args.row)
        parse_decision_rule(args.decision_rule)
        arms = build_arms(args)
        criterion = resolve_callable(args.criterion) if args.criterion else None
        spec = H.HarnessSpec(
            row_id=row.id,
            arms=tuple(arms),
            test_seasons=tuple(args.test_seasons),
            min_games_train=args.min_games_train,
            min_games_score=args.min_games_score,
            fbs_only=args.fbs_only,
            n_boot=args.n_boot,
            seed=args.seed,
            criterion=criterion,
        )
        if row.status == "exploratory" and criterion is not None:
            raise HarnessRefusal(
                f"row {row.id} is exploratory (measurement only); --criterion is refused"
            )
    except (HarnessRefusal, ValueError) as e:
        return _refuse(str(e))

    print(
        f"[harness] row {row.id} ({row.status}) · test seasons {list(spec.test_seasons)} · "
        f"arms {[a.name for a in spec.arms]} · min_games train/score "
        f"{spec.min_games_train}/{spec.min_games_score} · decision rule {args.decision_rule}"
    )

    # 2. database
    if not try_init_db():
        print("[harness] database unreachable; nothing computed", file=sys.stderr)
        return 0

    out = args.out or f"reports/harness_{row.id}"
    stamp = utc_stamp()
    md_path, _json_path, _csv_path = report_paths(out, stamp)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    fp_path = md_path.with_name(md_path.stem + "_frame.json")

    try:
        frame, fp = H.load_frame(Path(args.frame) if args.frame else None, spec, fp_path)
    except HarnessRefusal as e:
        return _refuse(str(e))
    print(
        f"[harness] frame rows={fp['rows']} by_season={fp['by_season']} sklearn={fp['sklearn']} "
        f"-> {fp_path.name}"
    )

    # 3. real closes and decision lines for the test seasons' played games
    test_rows = frame[frame["season"].isin(list(spec.test_seasons))]
    ids = [int(g) for g in test_rows.loc[test_rows["first_half_total"].notna(), "id"].tolist()]
    with session_scope() as session:
        kicks = kickoffs_for(session, ids)
        grading = H.Grading(
            closes=consensus_closes(session, ids, kicks),
            hr_closes=hr_closes(session, ids, kicks),
            hr_prices=hr_close_prices(session, ids, kicks),
            decision_lines=decision_lines(session, ids, kicks, rule=args.decision_rule),
            decision_rule=args.decision_rule,
        )
    print(
        f"[harness] real closes {len(grading.closes)} / HR closes {len(grading.hr_closes)} / "
        f"HR prices {len(grading.hr_prices)} / decision lines {len(grading.decision_lines)} "
        f"over {len(ids)} played test-season games"
    )

    # 4. measure
    try:
        result = H.run(frame, grading, spec, row, fp)
    except GateNotEvaluable as e:
        md = "\n".join(
            [
                f"# Measurement harness — {row.id}: NOT EVALUABLE",
                "",
                f"`{type(e).__name__}: {e}`",
                "",
                "A test season carries no real 1H close inside the window, so nothing was graded "
                "and no proxy line was read. Nothing was decided.",
                "",
                f"Frame fingerprint: `{fp_path}`",
            ]
        )
        md_path.write_text(md, encoding="utf-8")
        append_step_summary(md)
        print(f"::warning::{e}", file=sys.stderr)
        print(f"[harness] wrote {md_path}")
        return 0
    except HarnessRefusal as e:
        return _refuse(str(e))

    md_path, json_path, csv_path = H.write_report(result, out, stamp)
    print(f"[harness] wrote {md_path}, {json_path.name} and {csv_path.name}")
    v = result.report["verdict"]
    print(f"VERDICT ({row.id}, {row.status}): {v['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
