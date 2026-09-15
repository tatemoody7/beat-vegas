#!/usr/bin/env python
"""H4 -- grade the gates (EXPLORATORY). What did each blocker stop on the decision
builds, how did those games do at Hard Rock's number, and would a fixed -115 ceiling
or a trust-adjusted cap have picked differently?

Counts and intervals only; no gate verdict comes from this script (see
beatvegas/backtest/gates.py and docs/HYPOTHESES.md rows H4G / H4P / H4C).

    PYTHONPATH=. python scripts/gates_study.py --season 2026 --out reports/gates

Reads Neon (cards, games, odds_snapshots, postmortem_games); writes <out>_<UTC>.{md,json,csv};
appends the markdown to $GITHUB_STEP_SUMMARY when set; exits 0 whatever the numbers say.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from residual_gate import append_step_summary, report_paths  # noqa: E402

from beatvegas import snapshots  # noqa: E402
from beatvegas.backtest import gates as G  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402
from beatvegas.season import current_season  # noqa: E402


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--hist-seasons", type=int, nargs="+", default=[2023, 2024, 2025])
    ap.add_argument("--out", default="reports/gates")
    ap.add_argument("--n-boot", type=int, default=2000)
    return ap.parse_args(argv)


def run(rows, hist_rows, season: int, n_boot: int) -> Dict[str, Any]:
    cut = G.primary_cut(rows)
    fl = G.flags(cut) if len(cut) else cut
    fl_all = G.flags(rows[rows["hr_line"].notna()]) if len(rows) else rows
    trusts = {
        "trust_2325": G.trust_factors(G.residual_frame_hist(hist_rows)),
        "trust_2026": G.trust_factors(G.residual_frame_2026(cut)),
    }
    weeks = sorted(int(w) for w in cut["week"].dropna().unique()) if len(cut) else []
    return {
        "season": season,
        "weeks": weeks,
        "n_cut": int(len(cut)),
        "n_qualifying": int(fl["qualifies"].sum()) if len(fl) else 0,
        "n_graded": int(fl["fh"].notna().sum()) if len(fl) else 0,
        "status_word": "EXPLORATORY — no gate verdict",
        "gates": G.gate_records(fl, n_boot) if len(fl) else [],
        "fixed": G.fixed_ceiling_records(fl, n_boot) if len(fl) else None,
        "trusts": trusts,
        "cap": G.cap_rankings(cut, trusts, n_boot=n_boot) if len(cut) else [],
        "per_build": G.per_build_alone(fl_all) if len(fl_all) else [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[gates] DB unreachable — skipped.")
        return 0
    season = args.season or current_season()
    with session_scope() as s:
        rows = snapshots.build_rows(s, season)
        hist = snapshots.postmortem_hist_rows(s, args.hist_seasons)
    print(f"[gates] {len(rows)} build rows, {len(hist)} 2023-25 stored rows")
    r = run(rows, hist, season, args.n_boot)
    md = G.render_markdown(r)
    md_path, json_path, csv_path = report_paths(args.out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)
    json_path.write_text(json.dumps(r, indent=1, default=str))
    (G.flags(G.primary_cut(rows)) if len(rows) else rows).to_csv(csv_path, index=False)
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
