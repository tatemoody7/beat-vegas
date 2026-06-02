#!/usr/bin/env python
"""Run the walk-forward 1H-under backtest and print the verdict."""
from __future__ import annotations

import warnings

from beatvegas.backtest.engine import run_backtest, stress_test_lines
from beatvegas.etl.features import build_feature_frame

warnings.filterwarnings("ignore")


def main() -> None:
    df = build_feature_frame(min_games=2)
    for top_frac in (0.10, 0.20):
        res = run_backtest(df, top_frac=top_frac)
        print(f"\n===== TOP {int(top_frac*100)}% MOST-CONFIDENT UNDERS =====")
        print("summary:", res.summary)
        print(res.by_season.round(2).to_string(index=False))
        if top_frac == 0.20:
            print("\nline stress test (top 20%):")
            print(stress_test_lines(res.per_game, [-1.5, -1.0, 0.0, 1.0, 1.5])
                  .to_string(index=False))


if __name__ == "__main__":
    main()
