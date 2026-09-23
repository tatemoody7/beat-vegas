#!/usr/bin/env bash
# Boot the local Postgres sandbox for the e2e lane and load the fixture:
#
#   npm run e2e:db          # from web/
#
# Uses the pgserver-bundled Postgres 16 the Python side already relies on
# (scripts/pg_sim.py) on port 54329, with its OWN database, beatvegas_e2e, beside
# the week-simulation one -- same server, separate data. Then applies the
# committed schema dump (e2e/fixture/schema.sql, regenerate with
# scripts/dump_e2e_schema.py) and runs seed.mjs. Idempotent: run it again to
# reset the fixture to a clean state.
#
# Never Neon: the URL is hard-wired to 127.0.0.1, and seed.mjs refuses any
# neon.tech URL on its own.
set -euo pipefail

WEB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$WEB_DIR/.." && pwd)"
# The venv lives in the MAIN checkout even when this is a worktree.
# `--git-common-dir` answers RELATIVE to the cwd of the git process ("`.git`"
# from the main checkout), so resolve it from $ROOT, not from wherever npm ran us.
MAIN="$(cd "$ROOT" && cd "$(git rev-parse --git-common-dir)/.." && pwd)"
PY="${BV_PYTHON:-$MAIN/.venv/bin/python}"
if [ ! -x "$PY" ]; then
  echo "e2e-db: no python at $PY (set BV_PYTHON to the venv's interpreter)" >&2
  exit 1
fi

export BV_SIM_PG_PORT="${BV_E2E_PG_PORT:-54329}"
export BV_SIM_PG_DB="beatvegas_e2e"
URL="$(cd "$ROOT" && PYTHONPATH="$ROOT" "$PY" scripts/pg_sim.py start)"
PSQL="$("$PY" -c 'import pathlib, pgserver; print(pathlib.Path(pgserver.postgres_server.__file__).parent / "pginstall" / "bin" / "psql")')"

echo "e2e-db: sandbox up at $URL"
PGOPTIONS="-c client_min_messages=warning" "$PSQL" "$URL" -v ON_ERROR_STOP=1 -q -f "$WEB_DIR/e2e/fixture/schema.sql" >/dev/null
echo "e2e-db: schema applied"
cd "$WEB_DIR" && DATABASE_URL="$URL" node e2e/fixture/seed.mjs
echo "e2e-db: done. DATABASE_URL=$URL"
