#!/usr/bin/env python
"""Deep-dive a factor or combination: per-season, era/decay, segments, stress.

    python scripts/inspect_combo.py --factors away_fh_off_explosive,away_fh_off_turnovers
    python scripts/inspect_combo.py --factors home_revenge,away_fh_off_explosive,away_fh_off_turnovers
    python scripts/inspect_combo.py --factors wx_wind        # show why it's unproven
"""
from __future__ import annotations

import argparse
import json

from beatvegas.etl.features import build_feature_frame
from beatvegas.factors.inspect import inspect_combo


def _line(d, keys):
    return "  ".join(f"{k}={d.get(k)}" for k in keys)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--factors", required=True, help="comma-separated factor names")
    ap.add_argument("--top-frac", type=float, default=0.20)
    ap.add_argument("--first-test-season", type=int, default=2018)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cols = [c.strip() for c in args.factors.split(",") if c.strip()]
    df = build_feature_frame(min_games=2)
    rep = inspect_combo(df, cols, top_frac=args.top_frac,
                        first_test_season=args.first_test_season)
    if args.json:
        print(json.dumps(rep, indent=2)); return
    if "error" in rep:
        print("ERROR:", rep["error"]); return

    print(f"\nFACTORS: {' + '.join(rep['factors'])}   (top {int(args.top_frac*100)}%)")
    print(f"OVERALL: {_line(rep['overall'], ['n','under_pct','roi'])}  "
          f"(breakeven 52.4%)")
    print("\nBy season:")
    for r in rep["by_season"]:
        print(f"  {r['season']}: {_line(r, ['n','under_pct','roi'])}")
    print("\nEra / decay:")
    for k, v in rep["by_era"].items():
        print(f"  {k:18s}: {_line(v, ['n','under_pct','roi'])}")
    print("\nSegments:")
    for seg, m in rep["by_segment"].items():
        parts = "  |  ".join(f"{kk}: {vv['under_pct']}% roi={vv['roi']} n={vv['n']}"
                             for kk, vv in m.items())
        print(f"  {seg}: {parts}")
    print("\nProxy-line stress (same picks, line +/- delta):")
    for r in rep["proxy_stress"]:
        print(f"  {r['delta']:+.1f}: {_line(r, ['n','under_pct','roi'])}")
    print("\nDirection (selected-pick mean vs full-pool mean):")
    for c, v in rep["direction"].items():
        arrow = "LOWER" if v["selected_mean"] < v["pool_mean"] else "HIGHER"
        print(f"  {c}: selected={v['selected_mean']} pool={v['pool_mean']} -> picks lean {arrow}")


if __name__ == "__main__":
    main()
