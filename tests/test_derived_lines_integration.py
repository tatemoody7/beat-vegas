"""Integration tests for the derived-1H line writer, against a real Postgres
sandbox (not SQLite — SQLite is too loose to catch text/int 500s).

Asserts the three things that mattered in production:
  1. derived rows are actually WRITTEN to Postgres (not just printed),
  2. the season-scoped board query (mirrored from web/lib/board.ts) returns
     the new 2026 rows,
  3. persisted column types coerce correctly and the season filter runs with
     no text/int operator mismatch (the class of bug behind the picks 500).
"""

import json
from datetime import datetime

import pytest
from sqlalchemy import text

from beatvegas.db.models import Game

pytestmark = pytest.mark.integration

SEASON = 2026

# CFBD-shaped opener rows (carry game_id directly — no name matching needed).
FETCHED = [
    {"game_id": 1, "line": 50.5, "spread": -10.5},
    {"game_id": 2, "line": 59.5, "spread": -6.5},
]


def _seed_games(store):
    with store.session_scope() as s:
        s.add(Game(id=1, season=SEASON, week=1, home_team="LSU", away_team="Clemson",
                   full_game_total=50.5))
        s.add(Game(id=2, season=SEASON, week=1, home_team="Auburn", away_team="Baylor",
                   full_game_total=59.5))


def _gmeta(store):
    with store.session_scope() as s:
        return {
            g.id: {"week": g.week, "home": g.home_team, "away": g.away_team}
            for g in s.query(Game).filter(Game.season == SEASON).all()
        }


# Mirror of the core season-scoped predictions query in web/lib/board.ts
# (getBoard). Keep in sync with that file.
_BOARD_SQL = text(
    """
    SELECT p.game_id, p.rank, p.factors_json, p.line_used
    FROM predictions p JOIN games g ON g.id = p.game_id
    WHERE g.season = :season
      AND p.model_version = (
        SELECT p2.model_version FROM predictions p2
        JOIN games g2 ON g2.id = p2.game_id
        WHERE g2.season = :season
        ORDER BY p2.created_at DESC LIMIT 1)
    ORDER BY p.rank
    """
)


def test_writer_persists_rows(db, load_script):
    store = db
    mod = load_script("post_derived_lines")
    _seed_games(store)

    with store.session_scope() as s:
        n = mod.write_derived_rows(s, FETCHED, _gmeta(store), week=1, now=datetime.utcnow())
    assert n == 2

    # Actually in Postgres, not just printed.
    with store.get_engine().connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM predictions WHERE model_version='derived_lines'")
        ).scalar_one()
    assert count == 2

    # Idempotent: a second run replaces, does not duplicate.
    with store.session_scope() as s:
        mod.write_derived_rows(s, FETCHED, _gmeta(store), week=1, now=datetime.utcnow())
    with store.get_engine().connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM predictions WHERE model_version='derived_lines'")
        ).scalar_one()
    assert count == 2


def test_board_query_returns_derived_2026_rows(db, load_script):
    store = db
    mod = load_script("post_derived_lines")
    _seed_games(store)
    with store.session_scope() as s:
        mod.write_derived_rows(s, FETCHED, _gmeta(store), week=1, now=datetime.utcnow())

    with store.get_engine().connect() as conn:
        rows = conn.execute(_BOARD_SQL, {"season": SEASON}).mappings().all()

    assert len(rows) == 2
    assert [r["game_id"] for r in rows] == [1, 2]  # ranked low->high derived 1H
    f = json.loads(rows[0]["factors_json"])
    assert f["line_kind"] == "derived_fg"


def test_postgres_type_coercion(db, load_script):
    store = db
    mod = load_script("post_derived_lines")
    _seed_games(store)
    with store.session_scope() as s:
        mod.write_derived_rows(s, FETCHED, _gmeta(store), week=1, now=datetime.utcnow())

    with store.get_engine().connect() as conn:
        t = conn.execute(
            text(
                "SELECT pg_typeof(rank) rank_t, pg_typeof(line_used) line_t, "
                "pg_typeof(created_at) ts_t, factors_json "
                "FROM predictions WHERE model_version='derived_lines' LIMIT 1"
            )
        ).mappings().one()

    assert t["rank_t"] == "integer"
    assert t["line_t"] == "double precision"
    assert t["ts_t"].startswith("timestamp")
    json.loads(t["factors_json"])  # valid JSON, stored as text

    # The season filter compares int<->int — no text/int operator mismatch
    # (the 500 class). Passing a Python int must not raise.
    with store.get_engine().connect() as conn:
        conn.execute(_BOARD_SQL, {"season": SEASON}).mappings().all()


def test_empty_fetch_never_wipes_existing_rows(db, load_script):
    # An empty fetch (DK 403 + CFBD not posted yet) must preserve the board's
    # existing derived cards instead of deleting them and inserting nothing.
    store = db
    mod = load_script("post_derived_lines")
    _seed_games(store)

    with store.session_scope() as s:
        assert mod.write_derived_rows(s, FETCHED, _gmeta(store), week=1, now=datetime.utcnow()) == 2
    with store.session_scope() as s:
        assert mod.write_derived_rows(s, [], _gmeta(store), week=1, now=datetime.utcnow()) == 0

    with store.get_engine().connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM predictions WHERE model_version='derived_lines'")
        ).scalar_one()
    assert count == 2
