#!/usr/bin/env python
"""Phase 0 GATE: walk-forward backtest of the FULL-GAME under edge.

Unlike the 1H engine (stuck on a 0.52x proxy line), full-game totals have REAL
historical opener+close numbers via CFBD /lines, so this is a genuine
walk-forward test rather than a proxy. We:

  1. Build the market-blind feature frame -- the SAME BV_FEATURE_COLS the 1H BV
     line uses, so the regressor sees NONE of Vegas's numbers.
  2. Train a gradient-boosted regressor to predict the ACTUAL full-game total
     (home_points + away_points), walk-forward (train on prior seasons only).
  3. Rank each season by gap = opener - our number; bet unders on the top slice.
  4. Grade vs the actual total AT THE OPENER, and measure opener->close CLV.

GATE: full-game unders must clear >52.4% under AND positive CLV on the held-out
final season (the last test season, normally 2025). If it does not, we DO NOT
build a betting loop around a non-edge -- we report honestly and stop.

    python scripts/backtest_full_game.py
    python scripts/backtest_full_game.py --first-test-season 2024 --top-frac 0.20
    python scripts/backtest_full_game.py --db-path data/beatvegas.db.bak-...   # other DB

NOTE: the local DB is the current scoring regime only (2023-2025), so the 2025
holdout trains on just two prior seasons -- a thin sample. Read the verdict as
directional, to be confirmed forward against real Hard Rock lines.
"""

from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

BREAKEVEN = 52.4
WIN_PROFIT = 100 / 110  # units won on a winning -110 bet
# top-fraction configurations we effectively explored — the trial set the
# overfitting controls deflate against.
TOP_FRAC_GRID = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
PBO_MAX = 0.5  # PBO at/above this = the selection is no better than chance
DSR_MIN = 0.95  # DSR below this = the edge isn't significant after deflation


def _reg() -> HistGradientBoostingRegressor:
    # Mirrors model/bv_line._new_regressor hyperparameters for consistency.
    return HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_depth=3,
        max_iter=300,
        l2_regularization=1.0,
        min_samples_leaf=40,
        random_state=7,
    )


def _global_bias(train: pd.DataFrame, target: str, feat, min_train: int = 300) -> float:
    """Global intercept correction from walk-forward OOF residuals on TRAIN only
    (leak-free w.r.t. the test season). Returns 0.0 when there is too little
    prior data to estimate it -- which is the case for the earliest fold."""
    res = []
    for ts in sorted(train["season"].unique()):
        tr = train[train["season"] < ts]
        te = train[train["season"] == ts]
        if len(tr) < min_train or te.empty:
            continue
        m = _reg()
        m.fit(tr[feat], tr[target])
        res.append(te[target].to_numpy(dtype=float) - m.predict(te[feat]))
    return float(np.mean(np.concatenate(res))) if res else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first-test-season", type=int, default=2024)
    ap.add_argument("--top-frac", type=float, default=0.20)
    ap.add_argument("--min-train", type=int, default=500)
    ap.add_argument("--db-path", default=None, help="point at a specific SQLite file (offline)")
    args = ap.parse_args()

    if args.db_path:
        os.environ["DATABASE_URL"] = f"sqlite:///{os.path.abspath(args.db_path)}"

    # Imported after the optional DB override so the lazy engine binds correctly.
    from beatvegas.backtest.engine import _roi, config_return_series
    from beatvegas.backtest.overfit import (
        deflated_sharpe_ratio,
        pbo,
        sr_variance_across_configs,
    )
    from beatvegas.etl.features import build_feature_frame
    from beatvegas.model.bv_line import BV_FEATURE_COLS, _assert_market_blind
    from beatvegas.sources.cfbd import CFBDClient
    from beatvegas.sources.cfbd_lines import open_close_lookup

    _assert_market_blind(BV_FEATURE_COLS)
    feat = BV_FEATURE_COLS

    df = build_feature_frame(min_games=2)
    df = df[df["season"] >= args.first_test_season - 2].copy()  # keep train seasons too

    # Real opener + close from CFBD /lines (the genuine "bet the Sunday opener").
    client = CFBDClient()
    lk = {}
    for season in sorted(df["season"].unique()):
        lk.update(open_close_lookup(client, int(season)))
    df["fg_open_cfbd"] = df["id"].map(lambda i: lk.get(int(i), (np.nan, np.nan, None))[0])
    df["fg_close"] = df["id"].map(lambda i: lk.get(int(i), (np.nan, np.nan, None))[1])
    # Bet line = CFBD opener; fall back to the stored full-game number if absent.
    df["fg_open"] = df["fg_open_cfbd"].fillna(df["full_game_total"])
    df["line_src"] = np.where(df["fg_open_cfbd"].notna(), "cfbd_open", "stored_fg")

    df["fg_actual"] = pd.to_numeric(df["home_points"], errors="coerce") + pd.to_numeric(
        df["away_points"], errors="coerce"
    )
    df = df[df["fg_open"].notna() & df["fg_actual"].notna()].copy()
    df = df[df["fg_actual"] != df["fg_open"]].copy()  # drop pushes at the bet line
    df["under"] = (df["fg_actual"] < df["fg_open"]).astype(int)
    df["clv_under"] = df["fg_open"] - df["fg_close"]  # + = line fell after we bet under = good

    cov_open = int((df["line_src"] == "cfbd_open").sum())
    cov_close = int(df["fg_close"].notna().sum())
    print(
        f"frame: {len(df)} gradable games {sorted(df['season'].unique())}  | "
        f"CFBD opener {cov_open}/{len(df)} ({100 * cov_open / len(df):.0f}%), "
        f"close-for-CLV {cov_close}/{len(df)} ({100 * cov_close / len(df):.0f}%)"
    )

    # --- walk-forward: train on prior seasons, predict the held-out season -----
    preds = []
    for ts in [s for s in sorted(df["season"].unique()) if s >= args.first_test_season]:
        train = df[df["season"] < ts]
        target = df[df["season"] == ts]
        if len(train) < args.min_train or target.empty:
            continue
        m = _reg()
        m.fit(train[feat], train["fg_actual"])
        bv = m.predict(target[feat]) + _global_bias(train, "fg_actual", feat)
        t = target[
            ["id", "season", "week", "fg_open", "fg_close", "fg_actual", "under", "clv_under"]
        ].copy()
        t["bv_line"] = bv
        t["gap"] = t["fg_open"] - t["bv_line"]  # +gap = opener ABOVE our number = under lean
        t["abs_err"] = (t["fg_actual"].astype(float) - t["bv_line"]).abs()
        preds.append(t)

    if not preds:
        print("no testable seasons (need prior-season training data) -- aborting.")
        return
    per_game = pd.concat(preds, ignore_index=True)

    pct = int(round(args.top_frac * 100))
    rows, tops = [], []
    for ts, g in per_game.groupby("season"):
        g = g.sort_values("gap", ascending=False)
        k = max(1, int(len(g) * args.top_frac))
        top = g.head(k)
        tops.append(top)
        clv = top["clv_under"].dropna()
        rows.append(
            {
                "season": int(ts),
                "games": len(g),
                "base_under%": round(100 * g["under"].mean(), 2),
                f"top{pct}_under%": round(100 * top["under"].mean(), 2),
                "top_roi": round(_roi(int(top["under"].sum()), len(top)), 4),
                "top_clv": round(float(clv.mean()), 3) if len(clv) else float("nan"),
                "mae": round(float(g["abs_err"].mean()), 3),
            }
        )
    by_season = pd.DataFrame(rows)
    pooled = pd.concat(tops, ignore_index=True)
    pooled_clv = pooled["clv_under"].dropna()

    print(f"\n--- full-game unders: top {pct}% by gap, real opener, OOS walk-forward ---")
    print(by_season.to_string(index=False))
    print(
        f"\npooled top {pct}%: under {round(100 * pooled['under'].mean(), 2)}%  "
        f"roi {round(_roi(int(pooled['under'].sum()), len(pooled)), 4)}  "
        f"clv {round(float(pooled_clv.mean()), 3) if len(pooled_clv) else float('nan')}  "
        f"(breakeven {BREAKEVEN}%)"
    )

    # --- overfitting controls (across all OOS seasons, pooled) ----------------
    # Each top-fraction is one configuration: PBO (CSCV) judges whether the
    # in-sample-best threshold holds up out-of-sample; DSR deflates the primary
    # config's bet-return Sharpe for the grid size + fat tails (doc Stage 3).
    matrix, bet_by_cfg = config_return_series(per_game, "gap", "under", TOP_FRAC_GRID, WIN_PROFIT)
    _, primary_bets = config_return_series(per_game, "gap", "under", [args.top_frac], WIN_PROFIT)
    pbo_v = pbo(matrix)
    dsr_v = deflated_sharpe_ratio(
        primary_bets[0], len(TOP_FRAC_GRID), sr_variance_across_configs(bet_by_cfg)
    )
    n_trials = len(TOP_FRAC_GRID)
    pbo_ok = (not np.isnan(pbo_v)) and pbo_v < PBO_MAX
    dsr_ok = (not np.isnan(dsr_v)) and dsr_v > DSR_MIN
    print(
        f"\noverfitting controls (grid of {n_trials} top-fraction configs): "
        f"PBO {pbo_v:.3f} ({'<' if pbo_ok else '>='} {PBO_MAX}) | "
        f"DSR {dsr_v:.3f} ({'>' if dsr_ok else '<='} {DSR_MIN})"
    )

    # --- GATE: the held-out final season + overfitting controls ---------------
    gate_season = int(by_season["season"].max())
    gr = by_season[by_season["season"] == gate_season].iloc[0]
    under_ok = gr[f"top{pct}_under%"] > BREAKEVEN
    clv_ok = (not np.isnan(gr["top_clv"])) and gr["top_clv"] > 0
    passes = bool(under_ok and clv_ok and pbo_ok and dsr_ok)
    print(
        f"\nGATE ({gate_season} holdout): under {gr[f'top{pct}_under%']}% "
        f"({'>' if under_ok else '<='} {BREAKEVEN}) "
        f"AND CLV {gr['top_clv']} ({'+' if clv_ok else 'not +'}) "
        f"AND PBO {'ok' if pbo_ok else 'FAIL'} AND DSR {'ok' if dsr_ok else 'FAIL'} "
        f"-> {'PASSES -- proceed to build the live workflow' if passes else 'does NOT pass'}"
    )
    print(
        "\nHONEST READ: current-regime DB only (2023-2025), so the holdout trains on a thin\n"
        "  2-season window. CLV (opener->close) is the truth metric, not win rate. This is\n"
        "  directional -- the real confirmation is forward vs live Hard Rock lines."
    )


if __name__ == "__main__":
    main()
