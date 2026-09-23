#!/usr/bin/env python
"""Pickle the min_games=0 feature frame this platform builds, plus a fingerprint.

Why: on 2026-09-22 the same frozen gate produced three different calibration
intercepts in three environments (Mac / scikit-learn 1.6.1: -1.809; Mac /
1.9.1: -1.912; the GitHub runner / 1.9.1: -1.236). The library version moves the
number, but not by enough to explain the runner, so the runner's FRAME has to be
compared with a laptop's column by column. Dispatched through study.yml, which
uploads reports/* as an artifact. Read-only.

    python scripts/frame_snapshot.py --out reports/frame_snapshot
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Optional, Sequence

from beatvegas.etl.features import (
    PRIOR_SEASON_WEIGHT,
    WEATHER_OBS_LEAD_HOURS,
    build_feature_frame,
)
from beatvegas.etl.frame_fingerprint import fingerprint


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports/frame_snapshot")
    ap.add_argument("--min-games", type=int, default=0)
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    df = build_feature_frame(min_games=args.min_games)
    # Declare the cut so a consumer (harness.load_frame) can verify it instead of
    # inferring it from the rows; a pickle without this is refused there.
    df.attrs["build"] = {
        "fbs_only": True,
        "min_games": int(args.min_games),
        "prior_weight": PRIOR_SEASON_WEIGHT,
        "weather_lead": WEATHER_OBS_LEAD_HOURS,
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    from pathlib import Path

    out = Path(f"{args.out}_{stamp}")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(f"{out}.pkl")
    fp = fingerprint(df)
    Path(f"{out}.json").write_text(json.dumps(fp, indent=1))
    print(
        f"frame rows={fp['rows']} by_season={fp['by_season']} sklearn={fp['sklearn']} -> {out}.pkl"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
