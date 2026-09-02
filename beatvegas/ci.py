"""GitHub Actions surface for non-fatal conditions.

`warn` prints a `::warning::` annotation (shows on the run page) and, when the
job exposes `$GITHUB_STEP_SUMMARY`, appends one line to the run summary. On a
local shell it is just a print. Failures are not handled here: a red run is
reported by GitHub's failed-workflow email and re-checked by the Claude routines.
"""

from __future__ import annotations

import os


def warn(message: str) -> None:
    print(f"::warning::{message}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"WARNING: {message}\n")
