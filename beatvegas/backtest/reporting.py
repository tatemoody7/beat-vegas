"""Where a study's report goes and how it reaches the run page.

`report_paths` and `append_step_summary` lived in scripts/residual_gate.py from
2026-09-08 and every later gate imported them from there through a sys.path
shim. They are library code, not script code, so they live here now; the
script re-exports both so its own callers are unchanged.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from ..config import REPO_ROOT

__all__ = ["append_step_summary", "report_paths", "utc_stamp"]


def utc_stamp(now: Optional[datetime] = None) -> str:
    """`20260923T141500Z` -- the stamp every report triple shares."""
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ")


def report_paths(out: str, stamp: Optional[str] = None) -> Tuple[Path, Path, Path]:
    """(markdown, json, per-game csv) for one run, sharing a UTC stamp."""
    stamp = stamp or utc_stamp()
    base = Path(out)
    if not base.is_absolute():
        base = REPO_ROOT / base
    return tuple(base.with_name(f"{base.name}_{stamp}.{ext}") for ext in ("md", "json", "csv"))


def append_step_summary(md: str) -> None:
    """Append markdown to $GITHUB_STEP_SUMMARY when set (a no-op off the runner)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(md if md.endswith("\n") else md + "\n")
