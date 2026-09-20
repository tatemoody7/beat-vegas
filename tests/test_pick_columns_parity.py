"""The manual_picks ledger has two writers -- beatvegas/picks.py::add_pick (card,
pick.py) and web/lib/picks.ts::createPick (the site) -- and nothing pinned their
column sets together. That is how the web lane went a whole season without
writing `book` or `price_provenance`: every real 2026 ticket was stored at an
invented -110 with no provenance and, because grade_pick computes closing_price
only when `book` is set, never entered the price-CLV read.

This reads the TypeScript by regex, the way tests/test_gate_parity.py reads the
gate constants, so a column added on one side without the other fails CI."""

from __future__ import annotations

import re
from pathlib import Path

from beatvegas.db.models import ManualPick
from beatvegas.hardrock import HR_BOOK_KEY

ROOT = Path(__file__).resolve().parent.parent
PICKS_TS = ROOT / "web" / "lib" / "picks.ts"
BOOKS_TS = ROOT / "web" / "lib" / "books.ts"

# Columns the Python writer sets on every insert that the web writer must too.
# (add_pick also writes placed_at-derived fields; these are the ones whose
# absence silently changes what the ledger can be graded on.)
SHARED_ON_INSERT = {"book", "price", "price_provenance", "line", "is_paper", "market", "stake"}


def _insert_column_lists(src: str) -> list[set[str]]:
    out = []
    for m in re.finditer(r"INSERT INTO manual_picks\s*\(([^)]*)\)", src):
        out.append({c.strip() for c in m.group(1).replace("\n", " ").split(",") if c.strip()})
    return out


def test_every_web_insert_names_only_real_columns():
    lists = _insert_column_lists(PICKS_TS.read_text())
    assert len(lists) >= 2, "expected the primary insert and its legacy-schema fallback"
    model_cols = set(ManualPick.__table__.columns.keys())
    for cols in lists:
        assert cols <= model_cols, cols - model_cols


def test_the_primary_web_insert_carries_book_and_price_provenance():
    primary = _insert_column_lists(PICKS_TS.read_text())[0]
    assert SHARED_ON_INSERT <= primary, SHARED_ON_INSERT - primary


def test_the_legacy_fallback_insert_still_carries_book():
    # The fallback targets the pre-tracking schema; `book` predates it and is
    # what closing_price hangs off, so it goes in there too.
    fallback = _insert_column_lists(PICKS_TS.read_text())[1]
    assert "book" in fallback
    assert "price_provenance" not in fallback  # a tracking-era column


def test_web_hard_rock_key_matches_python():
    m = re.search(r'export\s+const\s+HR_BOOK_KEY\s*=\s*"([a-z_]+)"\s*;', BOOKS_TS.read_text())
    assert m, "web/lib/books.ts must export HR_BOOK_KEY"
    assert m.group(1) == HR_BOOK_KEY


def test_the_web_writer_does_not_invent_a_price():
    src = PICKS_TS.read_text()
    assert "input.price ?? -110" not in src
    assert "?? -110" not in src
