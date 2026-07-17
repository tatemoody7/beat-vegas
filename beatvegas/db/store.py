"""Engine/session management + simple upsert helpers."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from ..config import database_url
from .models import Base

# New columns added after first release; ALTER existing tables idempotently.
_MIGRATIONS = {
    "predictions": {
        "under_score": "INTEGER",
        "factors_json": "TEXT",
        "bv_line": "FLOAT",
        "bv_gap": "FLOAT",
        "bv_lo": "FLOAT",
        "bv_hi": "FLOAT",
        "bv_sigma": "FLOAT",
    },
    "results": {
        "closing_captured_at": "TIMESTAMP",
        "market": "VARCHAR",
        "clv_prob": "FLOAT",
    },
    "manual_picks": {
        "model_score_at_pick": "INTEGER",
        "model_line_at_pick": "FLOAT",
        "factors_json_at_pick": "TEXT",
        "opening_line": "FLOAT",
        "market": "VARCHAR",
        "clv_prob": "FLOAT",
    },
    "venues": {"elevation": "FLOAT", "grass": "BOOLEAN", "capacity": "INTEGER"},
    "fh_team_game": {"redzone_td": "FLOAT", "fourth_go": "FLOAT"},
    "games": {"spread": "FLOAT"},
    "odds_snapshots": {"spread": "FLOAT"},
}

_engine = None
_Session: Optional[sessionmaker] = None


def get_engine(path: Optional[Path] = None):
    global _engine, _Session
    if _engine is None:
        if path is not None:  # explicit SQLite path (tests/demo/snapshot)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{path}"
        else:
            url = database_url()  # DATABASE_URL (Postgres) or config SQLite
            if url.startswith("sqlite:///"):
                Path(url[len("sqlite:///") :]).parent.mkdir(parents=True, exist_ok=True)
        # pool_pre_ping keeps serverless Postgres (Neon) connections healthy.
        # A generous connect_timeout lets a SUSPENDED Neon compute finish waking
        # (the always-on pooler accepts the TCP connection immediately, but the
        # compute behind it can take several seconds to resume).
        connect_args = {}
        if not url.startswith("sqlite"):
            connect_args["connect_timeout"] = 20
        _engine = create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
        _Session = sessionmaker(bind=_engine, future=True)
    return _engine


def wait_for_db(engine=None, retries: int = 6, base_delay: float = 2.0) -> None:
    """Block until a `SELECT 1` succeeds, with exponential backoff. No-op for
    SQLite; for Neon it absorbs the cold-start window so the first real query
    doesn't fail on a still-resuming compute."""
    engine = engine or get_engine()
    if engine.url.get_backend_name().startswith("sqlite"):
        return
    last = None
    for i in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError as e:
            last = e
            time.sleep(base_delay * (2**i))
    if last is not None:
        raise last


def init_db(path: Optional[Path] = None) -> None:
    engine = get_engine(path)
    wait_for_db(engine)  # absorb Neon cold-start before any DDL
    Base.metadata.create_all(engine)
    _apply_migrations(engine)
    _resync_sequences(engine)


def try_init_db(path: Optional[Path] = None) -> bool:
    """init_db that degrades gracefully when the DB is unreachable.

    On a network that can't carry the Postgres connection (e.g. the campus
    network where Neon's 5432 is filtered), log one clear line and return False
    so the caller can exit cleanly instead of dumping a raw traceback. Returns
    True on success. SQLite never fails this way.

    In GitHub Actions this re-raises instead: a GHA runner can always reach
    Neon, so "unreachable" there is a real failure (bad secret, outage) and a
    green no-op run would silently skip the capture the user bets off."""
    try:
        init_db(path)
        return True
    except OperationalError:
        if os.environ.get("GITHUB_ACTIONS"):
            print("[db] database unreachable from GitHub Actions — failing the run.")
            raise
        print(
            "[db] database unreachable from this network — skipping this run. "
            "(If this is the local Mac on a blocked network, the cloud job "
            "handles Neon; see .github/workflows/sunday.yml.)"
        )
        return False


def _resync_sequences(engine) -> None:
    """Postgres only: bump each table's id sequence to MAX(id).

    Rows deployed from SQLite carry explicit ids that never advance the serial
    sequence, so the next ORM insert would collide on the pkey (the Neon
    id-sequence gotcha). Running this on every init makes any writer safe to
    start after an explicit-id deploy."""
    if engine.url.get_backend_name().startswith("sqlite"):
        return
    with engine.begin() as conn:
        seqs = conn.execute(
            text("SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'")
        ).scalars()
        for seq in seqs:
            if not seq.endswith("_id_seq"):
                continue
            table = seq[: -len("_id_seq")]
            max_id = conn.execute(text(f'SELECT MAX(id) FROM "{table}"')).scalar()
            if max_id is not None:
                conn.execute(
                    text("SELECT setval(pg_get_serial_sequence(:t, 'id'), :n)"),
                    {"t": table, "n": max_id},
                )


def _apply_migrations(engine) -> None:
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in _MIGRATIONS.items():
            if table not in existing:
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for col, sqltype in cols.items():
                if col not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {sqltype}"))
    # Dedup backstop on the movement history (models.py uq_odds_snapshot covers
    # fresh DBs; this covers existing ones). Fail-soft: if a legacy DB already
    # holds duplicates, warn and keep running — the backstop is best-effort.
    if "odds_snapshots" in existing:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_odds_snapshot "
                        "ON odds_snapshots (game_id, book, market, captured_at)"
                    )
                )
        except Exception as e:  # noqa: BLE001 - duplicate rows in a legacy DB
            print(f"[db] WARNING: could not add uq_odds_snapshot index: {e}")


@contextmanager
def session_scope() -> Iterator[Session]:
    if _Session is None:
        get_engine()
    assert _Session is not None
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def upsert(session: Session, model, rows: Iterable[dict], pk_fields) -> int:
    """Insert-or-update rows by primary-key fields. Returns count processed."""
    if isinstance(pk_fields, str):
        pk_fields = [pk_fields]
    n = 0
    for row in rows:
        key = {f: row[f] for f in pk_fields}
        obj = session.query(model).filter_by(**key).one_or_none()
        if obj is None:
            session.add(model(**row))
        else:
            for k, v in row.items():
                setattr(obj, k, v)
        n += 1
    return n
