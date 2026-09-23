"""web/e2e/fixture/schema.sql is a GENERATED dump of the schema init_db() builds
(scripts/dump_e2e_schema.py). It is committed so the CI e2e job can `psql -f`
it against a bare postgres:16 service without Python, which means it can go
stale the moment models.py or store._MIGRATIONS gains a table or column. No
database here: the check is textual, both directions the dump can drift.

When this fails, regenerate:  PYTHONPATH=. .venv/bin/python scripts/dump_e2e_schema.py
"""

import re
from pathlib import Path

from beatvegas.db.models import Base
from beatvegas.db.store import _MIGRATIONS

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "web" / "e2e" / "fixture" / "schema.sql"

# The tables the web app raw-queries (web/lib/*.ts, app/api/*). Every one must
# exist in the fixture or a page 500s against it.
WEB_TABLES = {
    "games",
    "teams",
    "manual_picks",
    "predictions",
    "odds_snapshots",
    "cards",
    "app_settings",
    "game_records",
    "game_previews",
    "results",
    "postmortem_runs",
    "postmortem_buckets",
    "model_runs",
    "factor_ledger",
    "bv_adjustments",
}


def _tables(sql: str) -> dict:
    """table -> set of column names, parsed out of the CREATE TABLE blocks."""
    out = {}
    for m in re.finditer(r"^CREATE TABLE public\.(\w+) \((.*?)^\);", sql, re.M | re.S):
        cols = set()
        for line in m.group(2).splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith(("CONSTRAINT", "PRIMARY KEY", "UNIQUE", "FOREIGN KEY")):
                continue
            cols.add(line.split()[0].strip('"'))
        out[m.group(1)] = cols
    return out


def test_schema_dump_exists_and_is_marked_generated():
    assert SCHEMA.exists(), "run scripts/dump_e2e_schema.py"
    head = SCHEMA.read_text().splitlines()[0]
    assert "GENERATED" in head
    assert "dump_e2e_schema.py" in SCHEMA.read_text()


def test_every_model_table_and_column_is_in_the_dump():
    dumped = _tables(SCHEMA.read_text())
    missing = []
    for table in Base.metadata.sorted_tables:
        cols = dumped.get(table.name)
        if cols is None:
            missing.append(f"table {table.name}")
            continue
        for col in table.columns:
            if col.name not in cols:
                missing.append(f"{table.name}.{col.name}")
    assert not missing, f"schema.sql is stale (regenerate): {missing}"


def test_every_migration_column_is_in_the_dump():
    dumped = _tables(SCHEMA.read_text())
    missing = [
        f"{table}.{col}"
        for table, cols in _MIGRATIONS.items()
        for col in cols
        if col not in dumped.get(table, set())
    ]
    assert not missing, f"schema.sql lacks a _MIGRATIONS column (regenerate): {missing}"


def test_the_dump_holds_every_table_the_web_app_reads():
    dumped = set(_tables(SCHEMA.read_text()))
    assert WEB_TABLES <= dumped, sorted(WEB_TABLES - dumped)


def test_the_expression_indexes_the_app_relies_on_are_in_the_dump():
    sql = SCHEMA.read_text()
    # web/lib/picks.ts::isDuplicatePick turns this constraint's violation into a 409.
    assert "uq_manual_pick_per_ledger" in sql
    assert "uq_odds_snapshot" in sql


def test_the_dump_carries_no_dump_version_lines():
    """The pg_dump/server version comments change with the wheel and are
    stripped so a regenerate on another machine is a clean diff."""
    assert not re.search(r"^-- Dumped (from|by) ", SCHEMA.read_text(), re.M)
