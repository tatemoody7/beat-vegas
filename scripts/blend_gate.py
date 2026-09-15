#!/usr/bin/env python
"""H3a -- the blend gate: one global weight w on the close against the market-blind
bv_line, judged walk-forward by MAE against the realized first-half total.

A REPORT, NOT A GATE CHANGE. Fits w on the training seasons, reports the held-out
season for 2023->2024 and 2023-24->2025, then (with --freeze) fits the final w once on
all of 2023-25 and writes data/blend.json -- a file nothing reads. Bucket weights are
reported as their own pre-registered family. See beatvegas/backtest/blend.py and
docs/HYPOTHESES.md rows H3A / H3B.

    PYTHONPATH=. python scripts/blend_gate.py --out reports/blend --freeze

Reads Neon (feature frame + odds_snapshots + cards); writes <out>_<UTC>.{md,json,csv};
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

from residual_gate import (  # noqa: E402
    append_step_summary,
    load_closes,
    load_played_frame,
    report_paths,
)

from beatvegas import snapshots  # noqa: E402
from beatvegas.backtest import blend as B  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024, 2025])
    ap.add_argument("--live-season", type=int, default=2026)
    ap.add_argument("--out", default="reports/blend")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument(
        "--freeze",
        action="store_true",
        help="after the splits, fit the final w on every season and write data/blend.json",
    )
    ap.add_argument("--no-live", action="store_true", help="skip the 2026 decision-time block")
    return ap.parse_args(argv)


def run(pg, live_rows, seasons, n_boot: int, do_freeze: bool) -> Dict[str, Any]:
    splits = [
        B.evaluate_split(pg, tr, te, n_boot=n_boot)
        for tr, te in B.SPLITS
        if te in seasons and all(s in seasons for s in tr)
    ]
    frozen = B.freeze(pg, seasons) if do_freeze else None
    w_live = (
        frozen["w"]
        if frozen
        else (splits[-1]["w"] if splits and splits[-1].get("evaluated") else None)
    )
    lf = B.live_frame(live_rows) if live_rows is not None else None
    return {
        "seasons": [int(s) for s in seasons],
        "n_rows": int(len(pg)),
        "splits": splits,
        "verdict": B.verdict(splits),
        "bucket_verdict": B.bucket_verdict(splits),
        "freeze": frozen,
        "live": B.live_summary(lf, w_live) if lf is not None else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[blend] DB unreachable — skipped.")
        return 0
    df = load_played_frame(fbs_only=True)
    df = df[df["season"] <= max(args.seasons)]
    print(f"[blend] played feature frame: {len(df)} rows, seasons {sorted(df['season'].unique())}")
    with session_scope() as s:
        ids = df[df["season"].isin(args.seasons)]["id"].tolist()
        closes = load_closes(s, ids)
        print(f"[blend] real 1H closes: {len(closes)} of {len(ids)} games in {args.seasons}")
        pg = B.per_game_frame(df, closes, args.seasons)
        live_rows = None if args.no_live else snapshots.build_rows(s, args.live_season)
    r = run(pg, live_rows, args.seasons, args.n_boot, args.freeze)
    if r["freeze"]:
        print(f"[blend] frozen w written to {B.write_freeze(r['freeze'])}")
    md = B.render_markdown(r)
    md_path, json_path, csv_path = report_paths(args.out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)
    json_path.write_text(json.dumps(r, indent=1, default=str))
    pg.to_csv(csv_path, index=False)
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
