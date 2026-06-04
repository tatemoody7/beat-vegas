#!/usr/bin/env python
"""Rank every factor by its out-of-sample relationship to the 1H-under outcome.

The research-spike centerpiece: evaluate each factor walk-forward (single-feature
GBM), attach permutation importance from the full model, scan combinations of the
strongest factors, then write the ranking to the `factor_scores` table and a
summary `model_runs` row. Pace + weather should land near the top as a sanity
check (the existing backtest already credits them with the signal).

    python scripts/rank_factors.py                 # rank, store, print
    python scripts/rank_factors.py --no-store       # print only
    python scripts/rank_factors.py --top-frac 0.10  # tighter selection

Diagnostics (per-season stability, sample size) are reported, never used to
filter factors out — breadth is the goal; the human judges fragility.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from beatvegas.db.models import FactorScore, ModelRun
from beatvegas.db.store import init_db, session_scope
from beatvegas.etl.features import build_feature_frame
from beatvegas.factors import evaluable_factors, rank_factors


def _run_id() -> str:
    return "factors_" + datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _print_table(title: str, rows, cols) -> None:
    print(f"\n=== {title} ===")
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols} if rows else {}
    print("  ".join(c.ljust(widths.get(c, len(c))) for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths.get(c, len(c))) for c in cols))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first-test-season", type=int, default=2023)
    ap.add_argument("--top-frac", type=float, default=0.20)
    ap.add_argument("--combo-top-k", type=int, default=8)
    ap.add_argument("--min-games", type=int, default=2)
    ap.add_argument("--no-store", action="store_true")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    df = build_feature_frame(min_games=args.min_games)
    factors = evaluable_factors(df)
    result = rank_factors(
        df,
        factors,
        top_frac=args.top_frac,
        first_test_season=args.first_test_season,
        combo_top_k=args.combo_top_k,
    )
    uni, combos, baseline = result["univariate"], result["combos"], result["baseline"]

    print(
        f"\nbaseline: {baseline['n']} games, {baseline['under_pct']}% under "
        f"(breakeven {baseline['breakeven_roi_under_pct']}%), "
        f"top_frac={baseline['top_frac']}, OOS {baseline['first_test_season']}+"
    )
    cols = [
        "rank",
        "factor",
        "family",
        "top_under_pct",
        "top_roi",
        "auc",
        "corr_1h",
        "perm_importance",
        "stability_std",
        "n",
        "market",
    ]
    _print_table("Univariate factor ranking (by OOS top-fraction ROI)", uni, cols)
    ccols = ["rank", "factor", "top_under_pct", "top_roi", "auc", "stability_std", "n"]
    _print_table("Top factor combinations", combos[:15], ccols)

    if args.no_store:
        print("\n(--no-store: nothing written)")
        return

    init_db()
    run_id = _run_id()
    now = datetime.utcnow()
    with session_scope() as s:
        for r in uni:
            s.add(
                FactorScore(
                    run_id=run_id,
                    kind="univariate",
                    factor=r["factor"],
                    family=r["family"],
                    leak_free=r["leak_free"],
                    market=r["market"],
                    forward_only=r["forward_only"],
                    n=r["n"],
                    top_under_pct=r["top_under_pct"],
                    top_roi=r["top_roi"],
                    auc=r["auc"],
                    corr=r["corr"],
                    perm_importance=r.get("perm_importance"),
                    stability_std=r["stability_std"],
                    rank=r["rank"],
                    metrics_json=json.dumps(r),
                    created_at=now,
                )
            )
        for c in combos:
            s.add(
                FactorScore(
                    run_id=run_id,
                    kind="combo",
                    factor=c["factor"],
                    family="combo",
                    leak_free=True,
                    market=False,
                    forward_only=False,
                    n=c["n"],
                    top_under_pct=c["top_under_pct"],
                    top_roi=c["top_roi"],
                    auc=c["auc"],
                    corr=None,
                    perm_importance=None,
                    stability_std=c["stability_std"],
                    rank=c["rank"],
                    metrics_json=json.dumps(c),
                    created_at=now,
                )
            )
        s.add(
            ModelRun(
                version="factor_rank_v1",
                train_window=f"{sorted(df['season'].unique())[0]}-{sorted(df['season'].unique())[-1]}",
                test_window=f"{args.first_test_season}+",
                metrics_json=json.dumps(
                    {
                        "baseline": baseline,
                        "run_id": run_id,
                        "n_factors": len(uni),
                        "n_combos": len(combos),
                    }
                ),
                notes=args.notes,
                created_at=now,
            )
        )
    print(f"\nstored {len(uni)} univariate + {len(combos)} combo rows (run_id={run_id})")


if __name__ == "__main__":
    main()
