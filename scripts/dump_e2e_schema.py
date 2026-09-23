#!/usr/bin/env python
"""Regenerate web/e2e/fixture/schema.sql -- the Postgres schema the Playwright
e2e lane seeds into a throwaway database.

The app raw-queries fourteen tables and only seven of them are in
web/prisma/schema.prisma, so the Prisma schema cannot be the fixture's DDL. The
truth is beatvegas/db/models.py as `store.init_db()` applies it: `create_all`,
then `_MIGRATIONS` (the ALTER TABLE ADD COLUMN ladder) and the expression
indexes `_apply_migrations` creates (uq_manual_pick_per_ledger and friends --
the web's duplicate-pick 409 relies on one of them).

So this script boots the local pgserver sandbox (scripts/pg_sim.py), runs the
REAL `init_db()` against a fresh database, and dumps it with the bundled
`pg_dump --schema-only`. The dump is committed so the CI job needs no Python:
it applies the file with `psql -f` against a postgres:16 service.
tests/test_e2e_schema_parity.py fails when models.py or `_MIGRATIONS` gains a
table or column that the committed dump lacks -- the reminder to re-run this.

    PYTHONPATH=. .venv/bin/python scripts/dump_e2e_schema.py

Writes the file in place and prints its path. Never touches Neon: the URL is
the sandbox's, and a DATABASE_URL in the environment is ignored on purpose.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "web" / "e2e" / "fixture" / "schema.sql"
DUMP_DB = "beatvegas_schema_dump"

HEADER = """-- GENERATED FILE -- do not edit by hand.
--
-- The Postgres schema the e2e lane seeds (web/e2e/fixture/seed.mjs), dumped
-- from beatvegas/db/models.py as beatvegas.db.store.init_db() applies it
-- (create_all + _MIGRATIONS + the expression indexes) by
-- scripts/dump_e2e_schema.py, using the pgserver-bundled pg_dump.
--
-- Regenerate after any change to models.py or store._MIGRATIONS:
--     PYTHONPATH=. .venv/bin/python scripts/dump_e2e_schema.py
-- tests/test_e2e_schema_parity.py fails until you do.
--
-- Applied with `psql -v ON_ERROR_STOP=1 -f` against an EMPTY database or one
-- that only ever held this schema: the DROP/CREATE SCHEMA below wipes it.

DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;

"""

# pg_dump prints its own and the server's version; both change with the wheel
# and neither is part of the schema, so they are stripped for a stable diff.
VOLATILE = re.compile(r"^-- Dumped (from|by) ")


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def main() -> None:
    import pg_sim  # scripts/pg_sim.py

    pg_sim.start()  # idempotent: initdb on first use, then pg_ctl start
    admin = pg_sim.uri("postgres")
    _run(
        [
            pg_sim._bin("psql"),
            admin,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f"DROP DATABASE IF EXISTS {DUMP_DB}",
        ]
    )
    _run([pg_sim._bin("psql"), admin, "-v", "ON_ERROR_STOP=1", "-c", f"CREATE DATABASE {DUMP_DB}"])
    url = pg_sim.uri(DUMP_DB)

    # The real init path, in a subprocess so the store's module-level engine
    # cache starts empty and DATABASE_URL is exactly the sandbox.
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    env["DATABASE_URL"] = url
    env["PYTHONPATH"] = str(ROOT)
    _run(
        [sys.executable, "-c", "from beatvegas.db.store import init_db; init_db()"],
        env=env,
        cwd=str(ROOT),
    )

    dump = _run(
        [
            pg_sim._bin("pg_dump"),
            "--schema-only",
            "--no-owner",
            "--no-privileges",
            "--no-comments",
            url,
        ]
    ).stdout
    body = "\n".join(line for line in dump.splitlines() if not VOLATILE.match(line))
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HEADER + body)
    _run(
        [
            pg_sim._bin("psql"),
            admin,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f"DROP DATABASE IF EXISTS {DUMP_DB}",
        ]
    )
    tables = re.findall(r"^CREATE TABLE public\.(\w+)", body, re.M)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(tables)} tables)")


if __name__ == "__main__":
    main()
