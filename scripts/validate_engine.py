#!/usr/bin/env python
"""Validation gate for the predict-the-1H-total engine (Phase 3).

Compares the new BV-regressor gap ranking (gbm_v2) to the existing classifier
(gbm_v1) on the same walk-forward proxy grade, and runs a MAE ablation: does the
PBP/pace/matchup factor family actually improve 1H-total prediction accuracy
(the genuine, proxy-immune win)? Logs a model_runs row.

    python scripts/validate_engine.py
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

from beatvegas.backtest.bv_engine import mae_ablation, run_bv_backtest
from beatvegas.backtest.engine import run_backtest
from beatvegas.db.models import ModelRun
from beatvegas.db.store import init_db, session_scope
from beatvegas.etl.features import (
    FH_FACTOR_COLS, MATCHUP_COLS, build_feature_frame,
)
from beatvegas.model.bv_line import BV_FEATURE_COLS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first-test-season", type=int, default=2018)
    ap.add_argument("--top-frac", type=float, default=0.20)
    ap.add_argument("--no-store", action="store_true")
    args = ap.parse_args()

    df = build_feature_frame(min_games=2)

    clf = run_backtest(df, first_test_season=args.first_test_season,
                       top_frac=args.top_frac).summary
    bv = run_bv_backtest(df, first_test_season=args.first_test_season,
                         top_frac=args.top_frac)

    pbp_family = set(FH_FACTOR_COLS) | set(MATCHUP_COLS)
    without_pbp = [c for c in BV_FEATURE_COLS if c not in pbp_family]
    mae_full = mae_ablation(df, BV_FEATURE_COLS, args.first_test_season)
    mae_base = mae_ablation(df, without_pbp, args.first_test_season)

    print(f"\n--- selection (top {int(args.top_frac*100)}%, proxy-graded, "
          f"OOS {args.first_test_season}+, breakeven 52.4%) ---")
    print(f"  gbm_v1 classifier : under {clf['top_under_pct']}%  roi {clf['top_roi']}")
    print(f"  gbm_v2 BV-gap     : under {bv.summary['top_under_pct']}%  "
          f"roi {bv.summary['top_roi']}")
    print(f"\n--- 1H-total prediction accuracy (BV regressor MAE) ---")
    print(f"  full feature set        : MAE {mae_full:.3f}")
    print(f"  WITHOUT pbp/matchup     : MAE {mae_base:.3f}")
    delta = mae_base - mae_full
    print(f"  PBP/pace/matchup family : {'improves' if delta > 0 else 'does NOT improve'} "
          f"MAE by {delta:+.3f} pts")
    print(f"\n  BV by-season:\n{bv.by_season.to_string(index=False)}")

    promote = (bv.summary["top_roi"] >= clf["top_roi"]) and (bv.summary["top_under_pct"] >= 52.4)
    print(f"\nPROMOTION GATE: gbm_v2 {'PASSES' if promote else 'does NOT pass'} "
          f"(>= classifier roi AND > breakeven)")

    if args.no_store:
        return
    init_db()
    metrics = {"classifier": clf, "bv_gap": bv.summary,
               "mae_full": round(mae_full, 3), "mae_without_pbp": round(mae_base, 3),
               "mae_delta_pbp": round(delta, 3), "promote": bool(promote)}
    with session_scope() as s:
        s.add(ModelRun(version="gbm_v2_engine",
                       train_window=f"{sorted(df['season'].unique())[0]}-{sorted(df['season'].unique())[-1]}",
                       test_window=f"{args.first_test_season}+",
                       metrics_json=json.dumps(metrics),
                       notes="predict-total engine validation",
                       created_at=datetime.utcnow()))
    print("\nlogged model_run gbm_v2_engine")


if __name__ == "__main__":
    main()
