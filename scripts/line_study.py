#!/usr/bin/env python
"""Rank how often the 1H under cashed last season, by opening-line value.

    python scripts/line_study.py --season 2025
    python scripts/line_study.py --season 2025 --min-games 40 --highlight 24.5

Uses real consensus opening lines where captured, else the proxy (0.52*full),
labeled per row. Breakeven vs -110 = 52.4%.
"""
from __future__ import annotations

import argparse

from beatvegas.analysis.line_study import BREAKEVEN_PCT, line_study
from beatvegas.db.store import init_db


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--min-games", type=int, default=15)
    ap.add_argument("--highlight", type=float, default=24.5)
    args = ap.parse_args()
    init_db()

    df = line_study(args.season, min_games=args.min_games)
    if df.empty:
        print(f"No line buckets with >= {args.min_games} games for {args.season}.")
        return

    sources = df["line_source"].value_counts().to_dict()
    src_note = "real opening lines" if sources.get("real_open") else "PROXY lines (0.52*full)"
    print(f"{args.season} 1H under-rate by opening line "
          f"[{src_note}], min {args.min_games} games, ranked:")
    print(df[["line", "games", "under", "push", "under_pct", "line_source"]]
          .to_string(index=False))
    print(f"\nbreakeven to beat -110 = {BREAKEVEN_PCT}%")

    hl = df[df["line"] == args.highlight]
    if not hl.empty:
        r = hl.iloc[0]
        verdict = "BEATS" if r["under_pct"] >= BREAKEVEN_PCT else "below"
        print(f"\nyour {args.highlight}: under {r['under_pct']}% "
              f"({int(r['under'])}/{int(r['games'])}) — {verdict} breakeven")
    else:
        print(f"\n{args.highlight}: no bucket with >= {args.min_games} games")


if __name__ == "__main__":
    main()
