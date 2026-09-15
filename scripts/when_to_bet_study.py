#!/usr/bin/env python
"""H6 -- when to bet: grade each stored build's BET and EDGE lists at Hard Rock's own
close and at the consensus close.

A REPORT, NOT A BET. Weekly runs are descriptive; the one confirmatory look
(matched games, paired bootstrap, Holm across the six pairs of the four decision
builds) is refused before 2026-12-07 -- see beatvegas/backtest/when_to_bet.py and
docs/HYPOTHESES.md row H6.

    PYTHONPATH=. python scripts/when_to_bet_study.py --season 2026 --out reports/when_to_bet
    PYTHONPATH=. python scripts/when_to_bet_study.py --season 2026 --confirmatory   # after 2026-12-07

Reads Neon (cards, games, odds_snapshots); writes <out>_<UTC>.{md,json,csv}; appends the
markdown to $GITHUB_STEP_SUMMARY when set; exits 0 whatever the numbers say.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from residual_gate import append_step_summary, report_paths  # noqa: E402

from beatvegas import snapshots  # noqa: E402
from beatvegas.backtest import when_to_bet as W  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402
from beatvegas.season import current_season  # noqa: E402


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=None, help="default: the current season")
    ap.add_argument("--out", default="reports/when_to_bet")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument(
        "--confirmatory",
        action="store_true",
        help="run the ONE pre-registered test (refused before 2026-12-07)",
    )
    ap.add_argument("--today", default=None, help="override today's date (tests only)")
    return ap.parse_args(argv)


def run(df, season: int, n_boot: int, confirmatory: bool, today: Optional[date]) -> Dict[str, Any]:
    conf = (
        W.confirmatory(df, n_boot=n_boot, today=today)
        if confirmatory
        else {
            "ran": False,
            "verdict": "NOT YET EVALUABLE",
            "reasons": ["descriptive run; the confirmatory look is a separate, dated invocation"],
            "pairs": [],
            "rule": W.RULE,
        }
    )
    priced = df[df["hr_line"].notna()]
    return {
        "season": season,
        "n_cards": int(df["card_id"].nunique()) if len(df) else 0,
        "n_rows": int(len(df)),
        "n_priced": int(len(priced)),
        "n_graded": int(priced["fh"].notna().sum()) if len(priced) else 0,
        "per_build": W.per_build(df, n_boot=n_boot),
        "first_qualified": W.first_qualified(df).to_dict("records"),
        "confirmatory": conf,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[when_to_bet] DB unreachable — skipped.")
        return 0
    season = args.season or current_season()
    with session_scope() as s:
        df = snapshots.build_rows(s, season)
    today = date.fromisoformat(args.today) if args.today else None
    r = run(df, season, args.n_boot, args.confirmatory, today)
    md = W.render_markdown(r)
    md_path, json_path, csv_path = report_paths(args.out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)
    json_path.write_text(json.dumps(r, indent=1, default=str))
    W.grade(df).to_csv(csv_path, index=False)
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
