"""store.upsert must not null out columns the caller simply didn't have.

Monday's `backfill.py --season` re-upserts every game from CFBD; for upcoming
games CFBD carries no line yet, so the row arrives with spread/full_game_total
= None and used to overwrite the numbers the Sunday opener capture had stored."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game
from beatvegas.db.store import upsert


def _engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


def _seed(s):
    s.add(Game(id=1, season=2026, week=3, home_team="A", away_team="B", spread=-3.5))
    s.get(Game, 1).full_game_total = 51.0
    s.commit()


def test_update_skips_none_by_default():
    eng = _engine()
    with Session(eng) as s:
        _seed(s)
        n = upsert(
            s,
            Game,
            [
                {
                    "id": 1,
                    "season": 2026,
                    "week": 3,
                    "spread": None,
                    "full_game_total": None,
                    "home_points": 24,
                }
            ],
            "id",
        )
        s.commit()
        g = s.get(Game, 1)
        assert n == 1
        assert g.spread == -3.5 and g.full_game_total == 51.0  # preserved
        assert g.home_points == 24  # real values still land


def test_update_can_be_forced_to_null():
    eng = _engine()
    with Session(eng) as s:
        _seed(s)
        upsert(s, Game, [{"id": 1, "spread": None}], "id", overwrite_none=True)
        s.commit()
        assert s.get(Game, 1).spread is None


def test_insert_path_still_sets_none_columns():
    eng = _engine()
    with Session(eng) as s:
        upsert(s, Game, [{"id": 7, "season": 2026, "week": 1, "spread": None}], "id")
        s.commit()
        g = s.get(Game, 7)
        assert g is not None and g.spread is None


# --- batched existence check (2026-09-16): one IN-query per chunk, not one
# SELECT per row. Semantics must not move: None-skip on update, inserts as
# given, duplicate keys inside one call apply in order.

from beatvegas.db.models import TeamTempo  # noqa: E402  (composite-key model)


def test_many_rows_are_upserted_in_chunks_with_the_same_result():
    eng = _engine()
    with Session(eng) as s:
        _seed(s)
        rows = [{"id": i, "season": 2026, "week": 3, "spread": float(i)} for i in range(1, 1201)]
        n = upsert(s, Game, rows, "id", chunk=100)
        s.commit()
        assert n == 1200
        assert s.query(Game).count() == 1200
        g1 = s.get(Game, 1)
        assert g1.spread == 1.0 and g1.full_game_total == 51.0  # updated, other column kept
        assert s.get(Game, 1200).spread == 1200.0


def test_duplicate_keys_in_one_call_apply_in_order():
    eng = _engine()
    with Session(eng) as s:
        n = upsert(
            s,
            Game,
            [
                {"id": 9, "season": 2026, "week": 1, "spread": -1.0},
                {"id": 9, "season": 2026, "week": 1, "spread": -7.5, "full_game_total": None},
            ],
            "id",
        )
        s.commit()
        assert n == 2
        assert s.query(Game).filter(Game.id == 9).count() == 1
        g = s.get(Game, 9)
        assert g.spread == -7.5  # the second row won


def test_composite_key_uses_a_row_value_in_list():
    eng = _engine()
    with Session(eng) as s:
        upsert(
            s,
            TeamTempo,
            [
                {"season": 2026, "week": 3, "team": "Alabama", "seconds_per_play": 24.0},
                {"season": 2026, "week": 3, "team": "Georgia", "seconds_per_play": 27.0},
            ],
            ["season", "week", "team"],
        )
        s.commit()
        n = upsert(
            s,
            TeamTempo,
            [
                {"season": 2026, "week": 3, "team": "Alabama", "seconds_per_play": 25.5},
                {"season": 2026, "week": 3, "team": "LSU", "seconds_per_play": 26.0},
            ],
            ["season", "week", "team"],
            chunk=1,
        )
        s.commit()
        assert n == 2
        assert s.query(TeamTempo).count() == 3
        bama = s.query(TeamTempo).filter_by(season=2026, week=3, team="Alabama").one()
        assert bama.seconds_per_play == 25.5


def test_empty_rows_is_a_no_op():
    eng = _engine()
    with Session(eng) as s:
        assert upsert(s, Game, [], "id") == 0
