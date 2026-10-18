"""scripts/archive/ keeps the closed studies runnable for the record (final-2026
PR-19, 2026-10-18): every file there still compiles, the README names each one,
and nothing live reaches back into the archive."""

import py_compile
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "scripts" / "archive"
ARCHIVED = sorted(p for p in ARCHIVE.glob("*.py"))


def test_the_archive_is_not_empty():
    assert len(ARCHIVED) >= 27


@pytest.mark.parametrize("path", ARCHIVED, ids=lambda p: p.name)
def test_every_archived_script_compiles(path, tmp_path):
    py_compile.compile(str(path), cfile=str(tmp_path / "out.pyc"), doraise=True)


def test_the_readme_names_every_archived_script():
    readme = (ARCHIVE / "README.md").read_text()
    missing = [p.name for p in ARCHIVED if f"`{p.name}`" not in readme]
    assert not missing, f"scripts/archive/README.md lacks a row for: {missing}"
    named = set(re.findall(r"^\| `([a-z0-9_]+\.py)`", readme, re.M))
    assert named <= {p.name for p in ARCHIVED}, "the README names a script that is not archived"


def test_nothing_live_imports_from_the_archive():
    live = list((ROOT / "beatvegas").rglob("*.py")) + list((ROOT / "scripts").glob("*.py"))
    assert live
    pattern = re.compile(r"^\s*(from|import)\s+scripts\.archive\b", re.M)
    names = "|".join(p.stem for p in ARCHIVED)
    bare = re.compile(rf"^\s*(from|import)\s+({names})\b", re.M)
    offenders = [
        str(p.relative_to(ROOT))
        for p in live
        if pattern.search(p.read_text()) or bare.search(p.read_text())
    ]
    assert not offenders, f"live code imports a closed study's script: {offenders}"
