"""cmd_add real-money guards: a rematch-ambiguous name match must refuse to log
(S8) — a pick attaching to a guessed game corrupts the season's real-money record."""

import importlib.util
from argparse import Namespace
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, ManualPick

_ROOT = Path(__file__).resolve().parent.parent


def _load(script_name: str):
    path = _ROOT / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(script_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _args(**kw) -> Namespace:
    base = dict(
        home="Michigan",
        away="Ohio State",
        line=24.5,
        price=-110,
        stake=1.0,
        book=None,
        season=2026,
        week=None,
        note=None,
        market="1h",
        force=False,
    )
    base.update(kw)
    return Namespace(**base)


def _pick_module_with_rematch():
    """pick.py wired to an isolated sqlite holding an OSU-Michigan rematch."""
    pick = _load("pick")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    future = datetime.utcnow() + timedelta(days=30)
    with Session(eng) as s:
        s.add_all(
            [
                Game(
                    id=1,
                    season=2026,
                    week=13,
                    home_team="Ohio State",
                    away_team="Michigan",
                    start_date=future,
                ),
                Game(
                    id=2,
                    season=2026,
                    week=15,
                    home_team="Michigan",
                    away_team="Ohio State",
                    start_date=future,
                ),
            ]
        )
        s.commit()

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    pick.session_scope = scope
    return pick, eng


def _n_picks(eng) -> int:
    with Session(eng) as s:
        return s.query(ManualPick).count()


def test_ambiguous_rematch_refused(capsys):
    pick, eng = _pick_module_with_rematch()
    pick.cmd_add(_args())
    assert _n_picks(eng) == 0
    out = capsys.readouterr().out
    assert "REFUSED" in out and "wk13" in out and "wk15" in out


def test_week_pins_the_rematch():
    pick, eng = _pick_module_with_rematch()
    pick.cmd_add(_args(week=15))
    with Session(eng) as s:
        rows = s.query(ManualPick).all()
        assert len(rows) == 1 and rows[0].game_id == 2


def test_force_accepts_best_guess():
    pick, eng = _pick_module_with_rematch()
    pick.cmd_add(_args(force=True))
    assert _n_picks(eng) == 1
