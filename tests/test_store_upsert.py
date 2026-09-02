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
