"""Read docs/HYPOTHESES.md as data.

The registry is the one place a hypothesis's status, its pre-registered
criterion and its result document sit together (docs/HYPOTHESES.md, "Why it
exists"). The measurement harness (backtest/harness.py) refuses to run for a
row that is not in a runnable state, so a study cannot be re-run against a row
that was already decided, and it quotes the criterion cell VERBATIM in its
report so the reader compares the numbers against the words that were written
before them.

The table parser is the SAME rule tests/test_hypotheses_registry.py applies
(split on an unescaped `|`, drop the header and the rule line); a row that
parses differently there than here would be a bug in one of them, and
tests/test_registry.py checks they agree on every row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from .config import REPO_ROOT

__all__ = [
    "COLUMNS",
    "REGISTRY_PATH",
    "RUNNABLE_STATUSES",
    "STATUSES",
    "HarnessRefusal",
    "RegistryRow",
    "find_row",
    "parse_registry",
    "require_runnable_row",
]

REGISTRY_PATH = REPO_ROOT / "docs" / "HYPOTHESES.md"

# The vocabulary in docs/HYPOTHESES.md; tests/test_hypotheses_registry.py::STATUSES
# is the same set and the registry test enforces it on every row.
STATUSES = frozenset(
    {
        "pre-registered",
        "exploratory",
        "tested-null",
        "tested-positive",
        "live-tracking",
        "rejected",
        "adopted",
    }
)
# A harness run may only measure a row whose decision is still open: a
# criterion written and not yet judged, or counts-and-intervals-only. Every
# other status has been decided (or is tracking live decisions) and a re-run
# against it would be a second look at data the row already spent.
RUNNABLE_STATUSES = frozenset({"pre-registered", "exploratory"})

COLUMNS = (
    "id",
    "question",
    "status",
    "family",
    "data",
    "n",
    "comparisons",
    "criterion",
    "doc",
)

_CELL_SPLIT = re.compile(r"(?<!\\)\|")


class HarnessRefusal(ValueError):
    """The harness will not run: the registry row is missing, not in a
    runnable status, or has no criterion. Raised BEFORE any database read;
    scripts/harness_report.py turns it into exit code 2."""


@dataclass(frozen=True)
class RegistryRow:
    id: str
    question: str
    status: str
    family: str
    data: str
    n: str
    comparisons: str
    criterion: str
    doc: str

    @property
    def runnable(self) -> bool:
        return self.status in RUNNABLE_STATUSES and bool(self.criterion.strip())


def _table_cells(text: str) -> List[List[str]]:
    """Every data line of every table, split into cells (the registry test's
    `_table_lines`, verbatim in rule): header and rule lines dropped, an
    escaped `\\|` kept inside its cell."""
    out: List[List[str]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in _CELL_SPLIT.split(line.strip().strip("|"))]
        if cells[0] in ("id", "") or set(cells[0]) <= {"-"}:
            continue
        out.append(cells)
    return out


def parse_registry(path: Optional[Path] = None) -> List[RegistryRow]:
    """Every well-formed row of the registry (exactly len(COLUMNS) cells), in
    file order. A malformed row -- an unescaped `|` inside a cell -- is left
    out here and caught by tests/test_hypotheses_registry.py, which fails the
    build on it; the harness must not guess at which cell split."""
    p = Path(path) if path is not None else REGISTRY_PATH
    text = p.read_text(encoding="utf-8")
    rows: List[RegistryRow] = []
    for cells in _table_cells(text):
        if len(cells) != len(COLUMNS):
            continue
        rows.append(RegistryRow(*cells))
    return rows


def find_row(rows: Sequence[RegistryRow], row_id: str) -> Optional[RegistryRow]:
    """The row whose id matches exactly (ids are case-sensitive in the file)."""
    for r in rows:
        if r.id == row_id:
            return r
    return None


def require_runnable_row(row_id: str, path: Optional[Path] = None) -> RegistryRow:
    """The registry row the harness may measure, or HarnessRefusal naming why not:
    unknown id, a status outside RUNNABLE_STATUSES, or an empty criterion cell.
    Reads the registry file only -- never the database."""
    rows = parse_registry(path)
    row = find_row(rows, row_id)
    if row is None:
        known = ", ".join(r.id for r in rows)
        raise HarnessRefusal(
            f"registry row {row_id!r} not found in {path or REGISTRY_PATH} ({known})"
        )
    if row.status not in RUNNABLE_STATUSES:
        raise HarnessRefusal(
            f"registry row {row_id} has status {row.status!r}, which is not runnable "
            f"(runnable: {', '.join(sorted(RUNNABLE_STATUSES))}); a decided row is not re-run"
        )
    if not row.criterion.strip():
        raise HarnessRefusal(
            f"registry row {row_id} has an empty pass-criterion cell; write the criterion "
            "before the numbers are read"
        )
    return row
