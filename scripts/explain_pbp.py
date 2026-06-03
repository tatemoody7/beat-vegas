#!/usr/bin/env python
"""Explain WHY away (low-turnover / explosive) offenses flag 1H unders.

The key worry: under = 1H_total < 0.52*full_total, so an "under" can come from
genuinely LOW 1H scoring OR from a HIGH full-game total inflating the proxy. If
the PBP-pair edge just rides high full totals, it's a PROXY ARTIFACT that would
vanish against real 1H lines. This dissects:
  A. univariate quantile relationship of each factor to under% / actual 1H /
     full total / 1H-share ratio;
  B. how the OOS-selected picks differ from the pool on actual 1H vs full total.
"""
from __future__ import annotations

import pandas as pd

from beatvegas.etl.features import build_feature_frame
from beatvegas.factors.inspect import _oof_preds, _top

COLS = ["away_fh_off_explosive", "away_fh_off_turnovers"]


def main() -> None:
    df = build_feature_frame(min_games=2)
    df = df.dropna(subset=COLS + ["first_half_total", "full_game_total", "proxy_line"])
    df = df[df["full_game_total"] > 0].copy()
    df["ratio"] = df["first_half_total"] / df["full_game_total"]

    print(f"sample: {len(df)} games | overall under {100*df['under'].mean():.1f}% | "
          f"mean 1H {df['first_half_total'].mean():.1f} | mean full "
          f"{df['full_game_total'].mean():.1f} | mean ratio {df['ratio'].mean():.3f}")

    print("\n=== A. univariate quartile relationship ===")
    for col in COLS:
        df["q"] = pd.qcut(df[col], 4, labels=["Q1(low)", "Q2", "Q3", "Q4(high)"])
        g = df.groupby("q", observed=True).agg(
            n=("under", "size"),
            under_pct=("under", lambda s: round(100 * s.mean(), 1)),
            actual_1H=("first_half_total", "mean"),
            full_total=("full_game_total", "mean"),
            ratio=("ratio", "mean"))
        print(f"\n[{col}]")
        print(g.round(2).to_string())

    print("\n=== B. OOS-selected picks vs pool ===")
    pg = _oof_preds(df, COLS)
    sel = _top(pg, 0.20)
    def m(frame, c):
        return round(float(frame[c].mean()), 3)
    print(f"{'metric':16s} {'selected':>10s} {'pool':>10s}")
    for c in ["under", "first_half_total", "full_game_total",
              "away_fh_off_explosive", "away_fh_off_turnovers"]:
        if c in pg.columns:
            print(f"{c:16s} {m(sel, c):>10} {m(pg, c):>10}")
    # the artifact test: is the under driven by low actual 1H, or high full total?
    sel_ratio = (sel["first_half_total"] / sel["full_game_total"]).mean()
    pool_ratio = (pg["first_half_total"] / pg["full_game_total"]).mean()
    print(f"\n1H-share ratio   selected={sel_ratio:.3f}  pool={pool_ratio:.3f}")
    print("If selected full_total >> pool but actual_1H ~ pool -> PROXY ARTIFACT.")
    print("If selected actual_1H < pool (lower real 1H scoring) -> REAL 1H edge.")


if __name__ == "__main__":
    main()
