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
import platform
from datetime import datetime, timezone
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from beatvegas.etl.features import build_feature_frame


def fingerprint(df: pd.DataFrame) -> dict:
    """Per-column non-null count, mean and std (numeric columns), so two frames
    can be diffed without shipping either."""
    import sklearn

    cols = {}
    for c in sorted(df.columns):
        s = df[c]
        entry = {"non_null": int(s.notna().sum()), "dtype": str(s.dtype)}
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            v = pd.to_numeric(s, errors="coerce")
            entry["mean"] = None if v.notna().sum() == 0 else float(np.nanmean(v))
            entry["std"] = None if v.notna().sum() < 2 else float(np.nanstd(v))
        cols[c] = entry
    return {
        "rows": int(len(df)),
        "by_season": {int(k): int(v) for k, v in df["season"].value_counts().sort_index().items()},
        "platform": platform.platform(),
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "columns": cols,
    }


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
