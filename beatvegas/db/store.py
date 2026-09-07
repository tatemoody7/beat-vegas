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
    # post-mortem: the real-close grading column (2026-09-06, after the tables existed)
    "postmortem_games": {
        "line_real": "FLOAT",
        "gap_real": "FLOAT",
        "outcome_real": "VARCHAR",
        "units_real": "FLOAT",
    },
    "manual_picks": {
        "model_score_at_pick": "INTEGER",
        "model_line_at_pick": "FLOAT",
        "factors_json_at_pick": "TEXT",
        "opening_line": "FLOAT",
        "market": "VARCHAR",
        "clv_prob": "FLOAT",
        "is_paper": "BOOLEAN",
        "verdict_at_pick": "VARCHAR(8)",
        "reason": "VARCHAR(16)",
        "gap_at_pick": "FLOAT",
        "ev_at_pick": "FLOAT",
        "hr_line_at_pick": "FLOAT",
    },
    "venues": {"elevation": "FLOAT", "grass": "BOOLEAN", "capacity": "INTEGER"},
    "fh_team_game": {"redzone_td": "FLOAT", "fourth_go": "FLOAT"},
    "games": {"spread": "FLOAT"},
    "odds_snapshots": {"spread": "FLOAT"},
}

# One-off data fixes, (table, SQL); each must be idempotent and valid on BOTH
# Postgres and SQLite (plain SQL-92 only). Run after the column migrations.
_DATA_MIGRATIONS = [
    # CFBD provider strings ("DraftKings") and Odds API keys ("draftkings") both
    # landed in `book`, double-counting a book in medians. New writes go through
    # hardrock.normalize_book; this folds the legacy rows onto lowercase.
    ("odds_snapshots", "UPDATE odds_snapshots SET book = lower(book) WHERE book <> lower(book)"),
]

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


_RESYNC_LOCK_KEY = "beatvegas_resync_sequences"


def resync_table_sequence(executor, table: str) -> bool:
    """Postgres only: raise `table`'s id sequence to MAX(id) when it has fallen
    behind the data, and NEVER lower it. Returns True when it moved.

    Rows deployed from SQLite carry explicit ids that never advance the serial
    sequence, so the next ORM insert would collide on the pkey (the Neon
    id-sequence gotcha). But a concurrent writer may already hold ids past the
    MAX(id) visible here (uncommitted rows), so lowering the sequence to MAX(id)
    hands out ids that writer owns — that collision crashed the 2023 opener
    pull. Callers must hold a transaction; `executor` is a Connection or Session.
    Concurrent resyncs are serialized by a transaction-scoped advisory lock."""
    executor.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": _RESYNC_LOCK_KEY})
    seq = executor.execute(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table}).scalar()
    if not seq:
        return False
    max_id = executor.execute(text(f'SELECT MAX(id) FROM "{table}"')).scalar()
    if max_id is None:
        return False
    row = executor.execute(text(f"SELECT last_value, is_called FROM {seq}")).one()
    current = int(row.last_value) if row.is_called else 0
    if max_id <= current:
        return False
    executor.execute(text("SELECT setval(:s, :n)"), {"s": seq, "n": int(max_id)})
    return True


def _resync_sequences(engine) -> None:
    """Postgres only: bring every table's id sequence up to MAX(id) (never down).
    Running this on every init makes any writer safe to start after an
    explicit-id deploy; see resync_table_sequence for the concurrency rule."""
    if engine.url.get_backend_name().startswith("sqlite"):
        return
    with engine.begin() as conn:
        seqs = conn.execute(
            text("SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'")
        ).scalars()
        for seq in list(seqs):
            if not seq.endswith("_id_seq"):
                continue
            resync_table_sequence(conn, seq[: -len("_id_seq")])


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
    for table, sql in _DATA_MIGRATIONS:
        if table not in existing:
            continue
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as e:  # noqa: BLE001 - never block startup on a data fix
            print(f"[db] WARNING: data migration failed ({sql[:40]}...): {e}")
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


def upsert(
    session: Session, model, rows: Iterable[dict], pk_fields, overwrite_none: bool = False
) -> int:
    """Insert-or-update rows by primary-key fields. Returns count processed.

    On UPDATE, keys whose value is None are skipped unless `overwrite_none` —
    a source that lacks a field (CFBD has no line yet for an upcoming game) must
    not erase a value another job already stored (the Sunday opener's
    Game.spread / full_game_total). Inserts set every key as given."""
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
                if v is None and not overwrite_none:
                    continue
                setattr(obj, k, v)
        n += 1
    return n
