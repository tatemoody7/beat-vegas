"""CLAUDE.md is the brief, not the changelog -- and it must not rot.

Audited 2026-09-28: the file had grown to 1,470 lines (72% dated history), stated the
same fact with two different numbers twice, carried a resolved billing hold as live, and
pointed at thirteen files or symbols that did not exist where it said. The history moved
to `docs/HISTORY.md`; this test keeps the brief short and its pointers real, the way
`test_docs_parity.py` keeps the money docs honest.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEF = ROOT / "CLAUDE.md"
HISTORY = ROOT / "docs" / "HISTORY.md"
WORKFLOWS = ROOT / ".github" / "workflows"

LINE_CAP = 400

# Directories a bare file name in the brief may resolve against.
SEARCH_DIRS = [
    "",
    "docs",
    "scripts",
    "scripts/hooks",
    "tests",
    "tests/fixtures",
    "web",
    "web/lib",
    "web/app",
    "web/scripts",
    "web/e2e",
    "web/e2e/fixture",
    "beatvegas",
    "beatvegas/model",
    "beatvegas/etl",
    "beatvegas/sources",
    "beatvegas/db",
    "beatvegas/backtest",
    ".github",
    ".github/workflows",
    "data",
    "requirements",
]
# Names the brief mentions that are, by design, not in the tree.
NOT_IN_TREE = {
    "config.yaml",  # gitignored keys
    "AGENTS.md",  # what Next would write if agentRules were on
}
PATH_RE = re.compile(r"`([\w./\-\[\]]+\.(?:py|ts|tsx|yml|yaml|md|json|sql|sh|css|mjs|txt))")


def _brief() -> str:
    return BRIEF.read_text()


def test_the_brief_stays_under_the_cap():
    n = len(_brief().splitlines())
    assert n <= LINE_CAP, (
        f"CLAUDE.md is {n} lines (cap {LINE_CAP}). Move the episode to docs/HISTORY.md and "
        "edit the brief in place -- it is a brief, not a changelog."
    )


def test_history_exists_and_the_brief_points_at_it():
    assert HISTORY.exists()
    assert "docs/HISTORY.md" in _brief()


def test_every_file_the_brief_names_exists():
    missing = []
    for name in sorted(set(PATH_RE.findall(_brief()))):
        if name in NOT_IN_TREE or "<" in name:
            continue
        if not any((ROOT / d / name).exists() for d in SEARCH_DIRS):
            missing.append(name)
    assert not missing, f"CLAUDE.md names files that do not exist: {missing}"


def test_every_study_doc_in_read_first_exists():
    body = _brief()
    section = body[body.index("## Read first") : body.index("## Where we are")]
    for name in re.findall(r"`([A-Z0-9_]+)`", section):
        assert (ROOT / "docs" / f"{name}.md").exists(), f"docs/{name}.md"


def test_every_workflow_is_in_the_brief():
    body = _brief()
    table = body[body.index("### Workflows") : body.index("### Scripts")]
    missing = sorted(f.name for f in WORKFLOWS.glob("*.yml") if f.name not in table)
    assert not missing, f"workflows absent from CLAUDE.md's table: {missing}"


def test_every_script_is_in_the_brief():
    body = _brief()
    section = body[body.index("### Scripts") : body.index("## Money path")]
    named = set(re.findall(r"`([a-z_0-9]+)", section))
    missing = sorted(p.stem for p in (ROOT / "scripts").glob("*.py") if p.stem not in named)
    assert not missing, f"scripts absent from CLAUDE.md: {missing}"


def test_the_brief_does_not_restate_history():
    """A dated episode heading belongs in HISTORY; the brief dates only its open items."""
    body = _brief()
    dated_bullets = re.findall(r"^- \*\*20\d\d-\d\d(?:-\d\d)? \(", body, flags=re.M)
    assert not dated_bullets, f"dated changelog bullets in CLAUDE.md: {dated_bullets[:3]}"
