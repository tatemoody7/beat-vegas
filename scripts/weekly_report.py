#!/usr/bin/env python
"""Generate a weekly 1H-under report from the predict-the-total engine.

Ranks the slate by the gap between the book line and our predicted 1H total
(gbm_v2), flags opportunities (gap >= 0.5 residual-sigma), and prints a readable
report with the genuine-signal context (pace, weather, 1H efficiency). Honest by
construction: notes the proxy caveat when no real line is supplied.

    python scripts/weekly_report.py --season 2025 --week 8
    python scripts/weekly_report.py --season 2025 --week 8 --out report.md
"""
from __future__ import annotations

import argparse

import pandas as pd

from beatvegas.etl.features import build_feature_frame
from beatvegas.model.score import _pace_str, _weather_str, score_slate


def _reason(r: pd.Series) -> str:
    bits = []
    pace = _pace_str(r)
    wx = _weather_str(r)
    if pace:
        bits.append(pace)
    if wx and wx != "Dome":
        bits.append(wx)
    elif wx == "Dome":
        bits.append("dome")
    he, ae = r.get("home_fh_off_epa"), r.get("away_fh_off_epa")
    if pd.notna(he) and pd.notna(ae):
        bits.append(f"1H EPA/play {he:+.2f}/{ae:+.2f}")
    return " · ".join(bits) if bits else "—"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--out")
    args = ap.parse_args()

    df = build_feature_frame(min_games=2)
    s = score_slate(args.season, target_week=args.week, df=df)
    if s.empty:
        print("no games scored"); return
    s = s.head(args.top)

    lines = [f"# 1H Under Board — {args.season} Week {args.week}", ""]
    n_opp = int(s["is_opportunity"].sum())
    lines.append(f"_{len(s)} games shown, {n_opp} flagged opportunities "
                 f"(gap ≥ 0.5σ). Ranked by gap = line − our predicted 1H total. "
                 f"Lines are the 0.52× proxy unless a real book line was supplied — "
                 f"directional until graded vs real DraftKings lines._")
    lines.append("")
    lines.append("| # | Matchup | Line | Our 1H | Gap | σ-gap | Opp | Lean | Why |")
    lines.append("|--:|---|--:|--:|--:|--:|:-:|--:|---|")
    for r in s.itertuples(index=False):
        rd = pd.Series(r._asdict())
        opp = "✅" if rd.get("is_opportunity") else ""
        z = rd.get("bv_gap_z")
        lines.append(
            f"| {int(rd['rank'])} | {rd['away_team']} @ {rd['home_team']} | "
            f"{rd['line']:.1f} | {rd['bv_line']:.1f} | {rd['bv_gap']:+.1f} | "
            f"{(f'{z:.1f}' if pd.notna(z) else '—')} | {opp} | "
            f"{int(rd['under_score'])} | {_reason(rd)} |")
    report = "\n".join(lines)

    if args.out:
        with open(args.out, "w") as f:
            f.write(report + "\n")
        print(f"wrote {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
