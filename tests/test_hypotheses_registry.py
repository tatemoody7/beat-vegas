"""Every study must have a row in docs/HYPOTHESES.md, and every row must be honest.

Nine studies had read the same 1,902 real-close games by 2026-09-15 and the count of
looks lived nowhere. The registry is the one place a comparison count, a status and a
pre-registered criterion sit together. This test keeps the vocabulary fixed, keeps every
study document pointed at from a row, and refuses an invented integer where the honest
value is `unknown`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "docs" / "HYPOTHESES.md"

STATUSES = {
    "pre-registered",
    "exploratory",
    "tested-null",
    "tested-positive",
    "live-tracking",
    "rejected",
    "adopted",
}

# Documents that hold a study result. Each must be named by at least one row.
STUDY_DOCS = [
    "docs/LEVEL_ANCHOR.md",
    "docs/CENSORING_STUDY.md",
    "docs/TWO_SIDED.md",
    "docs/HR_LAG.md",
    "docs/WEATHER_STYLE.md",
    "docs/WEATHER.md",
    "docs/MODEL_LEVEL_2026.md",
]

# Results that live only on the machine that ran them (`/research/` is gitignored).
# The row must exist and must say so; the file cannot be required.
LOCAL_ONLY_ROWS = {"R01", "R02"}

COMPARISONS = re.compile(
    r"^(\d+|≥\s?\d+( splits| per season)?|unknown|n/a( \([^)]*\))?|"
    r"\d+ \([^)]*\)|\d+ clocks?, budget split)"
    r"( \(retrospective\))?$"
)

COLUMNS = [
    "id",
    "question",
    "status",
    "family",
    "data",
    "n",
    "comparisons",
    "criterion",
    "doc",
]


def _table_lines() -> list[list[str]]:
    """Every data line of the registry tables, split into cells, wrong width and all.

    A cell containing a bare `|` -- `|mean bias|` was the real case -- splits into
    extra columns. Until 2026-09-20 `_rows()` dropped such a line silently, so the
    two rows that had one (H-LEVEL, H-INTERCEPT) were the only rows in the file
    their own honesty guard never read, and they rendered with phantom columns on
    GitHub. Widths are now checked, not skipped: write `\\|` inside a cell.
    """
    if not REGISTRY.exists():  # pragma: no cover - the registry is checked in
        pytest.skip("docs/HYPOTHESES.md not present in this checkout")
    out = []
    for line in REGISTRY.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if cells[0] in ("id", "") or set(cells[0]) <= {"-"}:
            continue
        out.append(cells)
    assert out, "no registry rows parsed"
    return out


def test_every_row_has_the_expected_number_of_columns():
    """The width check that makes every other test in this file reachable."""
    bad = {c[0]: len(c) for c in _table_lines() if len(c) != len(COLUMNS)}
    assert not bad, f"unescaped `|` inside a cell (write `\\|`): {bad}"


def _rows() -> list[dict]:
    return [dict(zip(COLUMNS, c)) for c in _table_lines() if len(c) == len(COLUMNS)]


def test_ids_are_unique():
    ids = [r["id"] for r in _rows()]
    assert len(ids) == len(set(ids)), ids


def test_every_status_is_in_the_vocabulary():
    bad = {r["id"]: r["status"] for r in _rows() if r["status"] not in STATUSES}
    assert not bad, bad


def test_comparisons_run_is_an_integer_a_bound_or_an_honest_unknown():
    bad = {r["id"]: r["comparisons"] for r in _rows() if not COMPARISONS.match(r["comparisons"])}
    assert not bad, bad


def test_every_study_doc_has_a_row():
    text = REGISTRY.read_text()
    missing = [d for d in STUDY_DOCS if f"`{d}`" not in text]
    assert not missing, missing


def test_local_only_results_say_so():
    rows = {r["id"]: r for r in _rows()}
    for rid in LOCAL_ONLY_ROWS:
        assert rid in rows, rid
        assert "gitignored" in rows[rid]["doc"], rows[rid]["doc"]


def test_every_committed_result_doc_resolves():
    """A row may point at a doc a later PR will write (marked `(PR n)`) or at a
    gitignored local result (says `gitignored`); every other repo path named in the
    result-doc cell must exist."""
    missing = []
    for r in _rows():
        if "(PR " in r["doc"] or "gitignored" in r["doc"]:
            continue
        for path in re.findall(r"`([^`]+\.(?:md|py))`", r["doc"]):
            if not (ROOT / path).exists():
                missing.append((r["id"], path))
    assert not missing, missing


def test_pre_registered_rows_carry_a_criterion():
    thin = [
        r["id"]
        for r in _rows()
        if r["status"] == "pre-registered"
        and (len(r["criterion"]) < 40 or "tbd" in r["criterion"].lower())
    ]
    assert not thin, thin


def test_exploratory_rows_promise_no_adoption():
    """An exploratory row is counts and intervals; its criterion cell must say so."""
    bad = [
        r["id"]
        for r in _rows()
        if r["status"] == "exploratory" and not r["criterion"].startswith("None")
    ]
    assert not bad, bad
