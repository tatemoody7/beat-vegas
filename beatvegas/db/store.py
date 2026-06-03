"""Engine/session management + simple upsert helpers."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import database_url, db_path
from .models import Base

# New columns added after first release; ALTER existing tables idempotently.
_MIGRATIONS = {
    "predictions": {"under_score": "INTEGER", "factors_json": "TEXT",
                    "bv_line": "FLOAT", "bv_gap": "FLOAT",
                    "bv_lo": "FLOAT", "bv_hi": "FLOAT", "bv_sigma": "FLOAT"},
    "results": {"closing_captured_at": "TIMESTAMP"},
    "manual_picks": {"model_score_at_pick": "INTEGER", "model_line_at_pick": "FLOAT"},
    "venues": {"elevation": "FLOAT", "grass": "BOOLEAN", "capacity": "INTEGER"},
    "fh_team_game": {"redzone_td": "FLOAT", "fourth_go": "FLOAT"},
}

_engine = None
_Session: Optional[sessionmaker] = None


def get_engine(path: Optional[Path] = None):
    global _engine, _Session
    if _engine is None:
        if path is not None:                      # explicit SQLite path (tests/demo/snapshot)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{path}"
        else:
            url = database_url()                  # DATABASE_URL (Postgres) or config SQLite
            if url.startswith("sqlite:///"):
                Path(url[len("sqlite:///"):]).parent.mkdir(parents=True, exist_ok=True)
        # pool_pre_ping keeps serverless Postgres (Neon) connections healthy.
        _engine = create_engine(url, future=True, pool_pre_ping=True)
        _Session = sessionmaker(bind=_engine, future=True)
    return _engine


def init_db(path: Optional[Path] = None) -> None:
    engine = get_engine(path)
    Base.metadata.create_all(engine)
    _apply_migrations(engine)


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
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {col} {sqltype}"))


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
