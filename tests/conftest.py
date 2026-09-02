"""Shared fixtures. `pg_sandbox` boots the throwaway local PG16 sandbox
(scripts/pg_sim.py) and repoints the SQLAlchemy engine at it, so integration
tests get real Postgres type-strictness without ever touching production Neon.
Skips cleanly when the pg binaries aren't available."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))


def _load_script(name: str):
    path = _ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def pg_sandbox():
    """Start the local PG sandbox once, point the store engine at it."""
    try:
        import pg_sim  # from scripts/ (on sys.path above)

        uri = pg_sim.start()
    except Exception as e:  # missing binaries, initdb failure, etc.
        pytest.skip(f"pg_sim sandbox unavailable: {e}")

    from beatvegas.db import store

    prev_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = uri
    store._engine = None  # bust the cached SQLite/Neon engine
    store._Session = None
    store.init_db()

    yield store

    store._engine = None
    store._Session = None
    if prev_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = prev_url


@pytest.fixture
def db(pg_sandbox):
    """Clean predictions+games before each test; yield the store module."""
    from sqlalchemy import text

    store = pg_sandbox
    with store.get_engine().begin() as conn:
        conn.execute(text("TRUNCATE predictions, games RESTART IDENTITY CASCADE"))
    yield store


@pytest.fixture
def load_script():
    return _load_script


@pytest.fixture(autouse=True)
def _flat_proxy_unless_opted_in(request, monkeypatch):
    """Tests run as if no multiplier had been adopted (flat 0.52), so they do not
    depend on whatever data/multiplier.json says today. A test that wants the
    real on-disk multiplier marks itself with @pytest.mark.real_multiplier."""
    if "real_multiplier" in request.keywords:
        return
    from beatvegas.etl import proxy_line

    monkeypatch.setattr(proxy_line, "_load_share_coeffs", lambda: None)
