#!/usr/bin/env python
"""Walk-forward gate for the market-residual 1H engine: the report the owner
reads to decide whether it replaces the incumbent BV line (config model.engine).

Fits the residual engine on the training seasons' rows that carry a real
pre-kick 1H close (us-region consensus, lines.REAL_1H_CLOSE_WINDOW_H), refits
the incumbent the way production does (every played prior season), and grades
both on the held-out test season at that same close — plus the incumbent's
predictions already stored under its model_version tag, which ties the report
back to the published post-mortem headline. See beatvegas/backtest/residual_gate.py.

    python scripts/residual_gate.py --train-seasons 2023 2024 --test-season 2025 \
        --out reports/residual_gate [--write-model-run] [--bv-train-seasons all|match]

Writes <out>_<UTC>.md, .json and .csv (the per-game frame: picks, outcomes and
gaps per engine, so the tables can be interrogated without re-running the
one-shot test), appends the markdown to $GITHUB_STEP_SUMMARY
when set, and exits 0 whatever the numbers say: it is a report, not a CI gate.
Needs the CFBD key (the feature-frame builder fetches the quality priors even
though the residual feature set drops them) and the database. Spends no Odds
API credits.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from beatvegas.backtest import residual_gate as G

# report_paths / append_step_summary moved to beatvegas/backtest/reporting.py
# (2026-09-23); re-exported from here because level_anchor_gate, intercept_gate,
# inseason_gate, blend_gate and censoring_study import them from this module.
from beatvegas.backtest.reporting import append_step_summary, report_paths
from beatvegas.backtest.residual_gate import GateNotEvaluable
from beatvegas.db.models import Game, ModelRun, Prediction
from beatvegas.db.store import resync_table_sequence, session_scope, try_init_db
from beatvegas.etl.features import build_feature_frame, training_frame
from beatvegas.lines import REAL_1H_CLOSE_WINDOW_H, real_closes
from beatvegas.model.residual import ResidualFitError
from beatvegas.model.score import MODEL_VERSION
from beatvegas.postmortem import created_order, engine_of

RUN_VERSION = "resid_gate"  # model_runs.version for --write-model-run
# Only these are data-coverage states worth a soft "NOT EVALUATED" report and
# exit 0. Anything else (a NaN season, a length mismatch) is a defect and must
# fail the run with its traceback, not be blamed on coverage.
SOFT_FAILURES = (ResidualFitError, GateNotEvaluable)

__all__ = ["append_step_summary", "main", "parse_args", "report_paths"]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--train-seasons", type=int, nargs="+", default=[2023, 2024])
    ap.add_argument("--test-season", type=int, default=2025)
    ap.add_argument(
        "--out",
        default="reports/residual_gate",
        help="report path prefix; _<UTC stamp>.md and .json are appended",
    )
    ap.add_argument(
        "--write-model-run",
        action="store_true",
        help=f"also add a model_runs row (version {RUN_VERSION}) carrying the report",
    )
    ap.add_argument(
        "--bv-train-seasons",
        choices=("all", "match"),
        default="all",
        help="incumbent training rows: every played prior season (production) or the "
        "residual's training seasons only",
    )
    ap.add_argument(
        "--all-divisions",
        dest="fbs_only",
        action="store_false",
        help="include non-FBS games in the feature frame (default: FBS-only, as production)",
    )
    return ap.parse_args(argv)


# ---------------------------------------------------------------- loaders


def load_played_frame(fbs_only: bool = True):
    """Played games only: the frame also carries the unplayed upcoming slate."""
    return training_frame(build_feature_frame(min_games=2, fbs_only=fbs_only))


def load_closes(session, game_ids: Sequence[int]) -> Dict[int, float]:
    """game_id -> real pre-kick 1H close inside the 2-hour window, kickoffs
    from the games table (the same lookup the post-mortem uses)."""
    ids = [int(g) for g in game_ids]
    kicks: Dict[int, datetime] = {}
    for i in range(0, len(ids), 1000):
        for gid, start in (
            session.query(Game.id, Game.start_date).filter(Game.id.in_(ids[i : i + 1000])).all()
        ):
            if start is not None:
                kicks[gid] = start
    return real_closes(session, ids, kicks, within_hours=REAL_1H_CLOSE_WINDOW_H)


def load_stored_bv(session, game_ids: Sequence[int]) -> Dict[int, float]:
    """game_id -> the incumbent's stored bv_line (model_version MODEL_VERSION);
    the newest row per game wins (a NULL created_at counts as oldest — see
    postmortem.created_order). Rows tagged `factors_json.engine == "residual"`
    are excluded — the gate's "stored" column stands in for the incumbent, so a
    future engine flip to residual must not contaminate it with its own output."""
    ids = [int(g) for g in game_ids]
    out: Dict[int, float] = {}
    for i in range(0, len(ids), 1000):
        rows = (
            session.query(Prediction)
            .filter(
                Prediction.model_version == MODEL_VERSION, Prediction.game_id.in_(ids[i : i + 1000])
            )
            .all()
        )
        for p in sorted(rows, key=created_order):
            if p.bv_line is not None and engine_of(p.factors_json) != "residual":
                out[p.game_id] = float(p.bv_line)
    return out


# ---------------------------------------------------------------- outputs


def write_model_run(session, report: Dict, args: argparse.Namespace) -> None:
    if session.bind.dialect.name == "postgresql":
        resync_table_sequence(session, ModelRun.__tablename__)
    session.add(
        ModelRun(
            version=RUN_VERSION,
            train_window=" ".join(str(s) for s in args.train_seasons),
            test_window=str(args.test_season),
            metrics_json=json.dumps(report),
            notes=f"bv_train_seasons={args.bv_train_seasons}",
            created_at=datetime.utcnow(),
        )
    )


def cap5_line(report: Dict, engine: str) -> str:
    r = report["engines"][engine]["selections"]["cap5"]
    hit = "—" if r["hit_rate"] is None else f"{100 * r['hit_rate']:.1f}%"
    ci = "—" if r["ci_lo"] is None else f"{100 * r['ci_lo']:.1f}–{100 * r['ci_hi']:.1f}%"
    roi = "—" if r["roi"] is None else f"{100 * r['roi']:+.1f}%"
    return (
        f"cap5 {engine}: {r['wins']}-{r['losses']}-{r['pushes']}P over {r['n']} · {hit} "
        f"(95% CI {ci}) · {r['units']:+.1f} units · ROI {roi}"
    )


def _failure_markdown(args: argparse.Namespace, err: Exception) -> str:
    return "\n".join(
        [
            f"# Residual engine gate — test season {args.test_season}: NOT EVALUATED",
            "",
            f"`{type(err).__name__}: {err}`",
            "",
            "The gate could not be computed on what the database holds (too few real-close "
            "training rows, or no test-season game with a real close). Nothing was decided.",
        ]
    )


# ---------------------------------------------------------------- main


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[residual_gate] database unreachable; nothing computed", file=sys.stderr)
        return 0

    seasons: List[int] = sorted(set(args.train_seasons) | {args.test_season})
    df = load_played_frame(fbs_only=args.fbs_only)
    df = df[df["season"] <= args.test_season]
    print(
        f"[residual_gate] played feature frame: {len(df)} rows, seasons {sorted(df['season'].unique())}"
    )

    md_path, json_path, csv_path = report_paths(args.out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with session_scope() as session:
        in_scope = df[df["season"].isin(seasons)]["id"].tolist()
        closes = load_closes(session, in_scope)
        test_ids = df[df["season"] == args.test_season]["id"].tolist()
        stored = load_stored_bv(session, test_ids)
        print(
            f"[residual_gate] real 1H closes ({REAL_1H_CLOSE_WINDOW_H:g} h window): {len(closes)} of "
            f"{len(in_scope)} games in {seasons}; stored {MODEL_VERSION} predictions: "
            f"{len(stored)} of {len(test_ids)} test-season games"
        )
        try:
            result = G.evaluate(
                df,
                closes,
                args.train_seasons,
                args.test_season,
                stored_bv=stored,  # {} -> the report says why 'stored' is absent
                bv_train_seasons=args.bv_train_seasons,
            )
        except SOFT_FAILURES as err:
            print(f"::error::residual gate not evaluated: {err}", file=sys.stderr)
            md = _failure_markdown(args, err)
            md_path.write_text(md, encoding="utf-8")
            append_step_summary(md)
            print(f"[residual_gate] wrote {md_path}")
            return 0

        md = G.render_markdown(result.report)
        md_path.write_text(md, encoding="utf-8")
        json_path.write_text(json.dumps(result.report, indent=2), encoding="utf-8")
        result.per_game.to_csv(csv_path, index=False)
        append_step_summary(md)
        print(f"[residual_gate] wrote {md_path}, {json_path.name} and {csv_path.name}")
        if args.write_model_run:
            write_model_run(session, result.report, args)
            print(f"[residual_gate] model_runs row added (version {RUN_VERSION})")

    print(cap5_line(result.report, "residual"))
    print(cap5_line(result.report, "incumbent"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
