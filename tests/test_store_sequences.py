"""Sequence resync must never move an id sequence backwards.

Every GHA job calls init_db(), which resyncs each table's id sequence to MAX(id)
(the Neon explicit-id gotcha). Two Neon writers can now overlap (30-minute close
polls, card builds, grading). If writer A has allocated ids past MAX(id) and
writer B resyncs, B must NOT lower the sequence under A — that collision is what
crashed the 2023 opener pull. Rule: raise to MAX(id) when behind, otherwise leave
it alone; serialize concurrent resyncs with an advisory lock."""

import pytest
from sqlalchemy import text

from beatvegas.db.models import Game

pytestmark = pytest.mark.integration


def _seq_state(conn):
    row = conn.execute(text("SELECT last_value, is_called FROM games_id_seq")).one()
    return int(row.last_value), bool(row.is_called)


def _seed_games(conn):
    conn.execute(text("TRUNCATE predictions, games RESTART IDENTITY CASCADE"))
    for gid in (1, 2, 3):
        conn.execute(
            text(
                "INSERT INTO games (id, season, week, home_team, away_team) "
                "VALUES (:id, 2026, 3, 'H', 'A')"
            ),
            {"id": gid},
        )


def test_resync_raises_a_sequence_that_fell_behind(pg_sandbox):
    store = pg_sandbox
    eng = store.get_engine()
    with eng.begin() as conn:
        _seed_games(conn)
        conn.execute(text("SELECT setval('games_id_seq', 1, false)"))  # behind MAX(id)=3
    store._resync_sequences(eng)
    with eng.begin() as conn:
        last, called = _seq_state(conn)
    assert (last, called) == (3, True)
    # and the next ORM insert does not collide
    with store.session_scope() as s:
        s.add(Game(season=2026, week=3, home_team="X", away_team="Y"))
    with eng.begin() as conn:
        assert conn.execute(text("SELECT MAX(id) FROM games")).scalar() == 4


def test_resync_never_lowers_a_sequence_ahead_of_the_data(pg_sandbox):
    """A concurrent writer may hold ids 4..50 uncommitted; MAX(id) visible here is 3."""
    store = pg_sandbox
    eng = store.get_engine()
    with eng.begin() as conn:
        _seed_games(conn)
        conn.execute(text("SELECT setval('games_id_seq', 50)"))
    store._resync_sequences(eng)
    with eng.begin() as conn:
        assert _seq_state(conn) == (50, True)


def test_resync_helper_is_shared_with_post_mortem_writer(pg_sandbox, load_script):
    """scripts/post_mortem.py used its own setval(MAX+1); it must use the store rule."""
    store = pg_sandbox
    eng = store.get_engine()
    with eng.begin() as conn:
        _seed_games(conn)
        conn.execute(text("SELECT setval('games_id_seq', 50)"))
    pm = load_script("post_mortem")
    with store.session_scope() as s:
        pm._resync_sequence(s, Game)
    with eng.begin() as conn:
        assert _seq_state(conn) == (50, True)
    with eng.begin() as conn:
        conn.execute(text("SELECT setval('games_id_seq', 1, false)"))
    with store.session_scope() as s:
        pm._resync_sequence(s, Game)
    with eng.begin() as conn:
        assert _seq_state(conn) == (3, True)
