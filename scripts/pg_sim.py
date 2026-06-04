#!/usr/bin/env python
"""Throwaway LOCAL Postgres for the week simulation (scripts/simulate_week.py).

Uses the Postgres binaries bundled in the `pgserver` wheel (no system install,
no brew/docker). Runs a real Postgres 16 on 127.0.0.1 so BOTH the Python engine
(SQLAlchemy/psycopg3) and the Next.js app (Prisma) can connect over TCP with an
ordinary postgresql:// URL — the same provider as Neon, so the web app renders
the sim unchanged.

The data dir lives OUTSIDE the project (~/.cache/beatvegas/pg_sim) because the
project path contains a space ("Beat Vegas") and pgserver's socket-dir argument
isn't quoted. This is a sim-only sandbox; it never touches Neon.

    python scripts/pg_sim.py start     # init (first run) + start, print the URI
    python scripts/pg_sim.py uri       # print the connection URI
    python scripts/pg_sim.py status    # running?
    python scripts/pg_sim.py stop      # stop the server
    python scripts/pg_sim.py reset     # stop + wipe the data dir (clean slate)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PORT = int(os.environ.get("BV_SIM_PG_PORT", "54329"))
DBNAME = os.environ.get("BV_SIM_PG_DB", "beatvegas_sim")
USER = "postgres"
HOST = "127.0.0.1"
# Space-free path: pgserver's bundled pg_ctl doesn't quote the -k socket dir.
PGDATA = Path.home() / ".cache" / "beatvegas" / "pg_sim"


def _bin(name: str) -> str:
    import pgserver

    bindir = Path(pgserver.postgres_server.__file__).parent / "pginstall" / "bin"
    return str(bindir / name)


def uri(database: str = DBNAME) -> str:
    return f"postgresql://{USER}@{HOST}:{PORT}/{database}"


def is_running() -> bool:
    try:
        out = subprocess.run(
            [_bin("pg_isready"), "-h", HOST, "-p", str(PORT)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.returncode == 0
    except Exception:
        return False


def _initialized() -> bool:
    return (PGDATA / "PG_VERSION").exists()


def start() -> str:
    """Idempotent: initdb on first run, start if not already up, ensure the DB
    exists. Returns the connection URI."""
    if is_running():
        _ensure_db()
        return uri()
    PGDATA.mkdir(parents=True, exist_ok=True)
    if not _initialized():
        subprocess.run(
            [_bin("initdb"), "-D", str(PGDATA), "-U", USER, "--auth=trust", "--encoding=utf8"],
            check=True,
            capture_output=True,
            text=True,
        )
    subprocess.run(
        [
            _bin("pg_ctl"),
            "-D",
            str(PGDATA),
            "-o",
            f"-h {HOST} -p {PORT} -k {PGDATA}",
            "-l",
            str(PGDATA / "server.log"),
            "-w",
            "start",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    _ensure_db()
    return uri()


def _ensure_db() -> None:
    """Create the sim database if it doesn't exist yet."""
    check = subprocess.run(
        [
            _bin("psql"),
            uri("postgres"),
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname='{DBNAME}'",
        ],
        capture_output=True,
        text=True,
    )
    if check.stdout.strip() != "1":
        subprocess.run(
            [_bin("createdb"), "-h", HOST, "-p", str(PORT), "-U", USER, DBNAME],
            check=True,
            capture_output=True,
            text=True,
        )


def stop() -> None:
    if _initialized():
        subprocess.run(
            [_bin("pg_ctl"), "-D", str(PGDATA), "-w", "-m", "fast", "stop"],
            capture_output=True,
            text=True,
        )


def reset() -> None:
    """Stop and wipe — next start() is a clean slate."""
    stop()
    import shutil

    if PGDATA.exists():
        shutil.rmtree(PGDATA)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        print(start())
    elif cmd == "uri":
        print(uri())
    elif cmd == "status":
        print("running" if is_running() else "stopped", uri())
    elif cmd == "stop":
        stop()
        print("stopped")
    elif cmd == "reset":
        reset()
        print("reset (data dir wiped)")
    else:
        raise SystemExit(f"unknown command: {cmd}")


if __name__ == "__main__":
    main()
