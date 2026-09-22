"""A fingerprint of a feature frame: per-column non-null count, mean and std,
plus the platform that built it.

Why: on 2026-09-22 one frozen gate gave two verdicts because the two runs had
built their frames from different snapshots of CFBD's reference tables (June
vs September; `season_stats._cached` has no expiry and the runner refetches
weekly). A registered run must be able to say WHICH inputs it was judged on,
so every gate writes this beside its report and two frames can be diffed
without shipping either.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd


def fingerprint(df: pd.DataFrame) -> Dict[str, Any]:
    import sklearn

    cols: Dict[str, Dict[str, Any]] = {}
    for c in sorted(df.columns):
        s = df[c]
        entry: Dict[str, Any] = {"non_null": int(s.notna().sum()), "dtype": str(s.dtype)}
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            v = pd.to_numeric(s, errors="coerce")
            n = int(v.notna().sum())
            entry["mean"] = None if n == 0 else float(np.nanmean(v))
            entry["std"] = None if n < 2 else float(np.nanstd(v))
        cols[c] = entry
    by_season = (
        {int(k): int(v) for k, v in df["season"].value_counts().sort_index().items()}
        if "season" in df
        else {}
    )
    return {
        "rows": int(len(df)),
        "by_season": by_season,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "columns": cols,
    }


def write_fingerprint(df: pd.DataFrame, path: Path) -> Dict[str, Any]:
    """Write the fingerprint JSON to `path` and return it. Gate scripts call this
    right after building their frame, with `<report stem>_frame.json`."""
    fp = fingerprint(df)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fp, indent=1))
    return fp


def diff_columns(
    a: Dict[str, Any], b: Dict[str, Any], tol: float = 1e-9
) -> Dict[str, Dict[str, Any]]:
    """Columns whose non-null count, mean or std differ between two fingerprints."""
    out: Dict[str, Dict[str, Any]] = {}
    ca, cb = a.get("columns", {}), b.get("columns", {})
    for c in sorted(set(ca) | set(cb)):
        x, y = ca.get(c), cb.get(c)
        if x is None or y is None:
            out[c] = {"only_in": "a" if y is None else "b"}
            continue
        changed = {}
        for k in ("non_null", "mean", "std"):
            u, v = x.get(k), y.get(k)
            if u is None and v is None:
                continue
            if u is None or v is None or abs(float(u) - float(v)) > tol:
                changed[k] = (u, v)
        if changed:
            out[c] = changed
    return out
