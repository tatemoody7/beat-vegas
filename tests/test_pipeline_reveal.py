"""beatvegas.pipeline._grade_manual_picks — the week-sim "reveal" grader used
by scripts/simulate_week.py. Mirrors scripts/pick.py cmd_grade: a paper pick
logged with a NULL price (unpriced Hard Rock line) must grade without raising
(units stay None), and must have its price filled from Hard Rock's own
pre-kick close when the per-game close polls captured one."""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, ManualPick, OddsSnapshot
from beatvegas.pipeline import _grade_manual_picks

KICK = datetime(2026, 9, 19, 19, 30)


def _engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


def _game(gid: int) -> Game:
    return Game(
        id=gid,
        season=2026,
        week=3,
        home_team=f"H{gid}",
        away_team=f"A{gid}",
        start_date=KICK,
        home_points=30,
        away_points=10,
        first_half_total=20,
        first_half_source="pbp",
    )


def _snap(gid: int, line: float, under_price, hrs: float) -> OddsSnapshot:
    return OddsSnapshot(
        game_id=gid,
        book="hardrockbet",
        market="1H_total",
        line=line,
        over_price=-110,
        under_price=under_price,
        captured_at=KICK - timedelta(hours=hrs),
    )


def _pick(gid: int) -> ManualPick:
    return ManualPick(
        game_id=gid,
        season=2026,
        week=3,
        home_team=f"H{gid}",
        away_team=f"A{gid}",
        side="under",
        market="1H",
        line=24.5,
        price=None,
        stake=1.0,
        is_paper=True,
        book="hardrockbet",
        graded=False,
        placed_at=KICK - timedelta(days=1),
    )


def test_null_price_grades_without_raising_when_no_priced_hr_snapshot():
    """Game 3: Hard Rock never priced the under before kickoff (both pre-kick
    snapshots carry under_price=None). Grading must not raise TypeError, the
    result must still land, and units must stay None."""
    eng = _engine()
    with Session(eng) as s:
        s.add(_game(3))
        s.add_all([_snap(3, 24.5, None, 30), _snap(3, 24.0, None, 1)])
        s.add(_pick(3))
        s.commit()

        graded = _grade_manual_picks(s, 2026)
        s.commit()

    assert graded == 1
    with Session(eng) as s:
        row = s.query(ManualPick).filter(ManualPick.game_id == 3).one()
    assert row.graded is True
    assert row.price is None
    assert row.result == "under"
    assert row.units is None


def test_the_close_lands_in_closing_price_and_never_in_price():
    """Game 2: Hard Rock opened unpriced, then priced -108 pre-kick (a -130
    snapshot after kickoff must not count).

    The close is captured into `closing_price`; `price` -- the price at the
    DECISION -- stays NULL because it was never known. Writing the close into
    `price`, as this did until 2026-09-14, makes price CLV identically zero by
    construction and leaves no way to tell such a row from a real one."""
    eng = _engine()
    with Session(eng) as s:
        s.add(_game(2))
        s.add_all(
            [
                _snap(2, 24.5, None, 30),
                _snap(2, 24.5, -108, 1),
                _snap(2, 24.5, -130, -1),
            ]
        )
        s.add(_pick(2))
        s.commit()

        graded = _grade_manual_picks(s, 2026)
        s.commit()

    assert graded == 1
    with Session(eng) as s:
        row = s.query(ManualPick).filter(ManualPick.game_id == 2).one()
    assert row.graded is True
    assert row.price is None
    assert row.closing_price == -108
    assert row.result == "under"
    assert row.units is None  # no decision price, so no units


def test_every_clone_table_has_a_model_behind_it():
    """_CLONE_TABLES and the model map in _clone_inputs are two hand-kept lists,
    and `weather_obs` reached the first without the second on 2026-09-14 -- so
    scripts/simulate_week.py has raised KeyError('weather_obs') ever since, and
    the offseason dry-run has been unusable. Nothing else exercised this path.
    Read the mapped tablenames out of the function's own source rather than
    running it (it needs a live Postgres sandbox)."""
    import inspect
    import re

    from beatvegas import pipeline
    from beatvegas.db import models as M

    src = inspect.getsource(pipeline._clone_inputs)
    body = src[src.index("by_table = {") : src.index("src = create_engine")]
    mapped = {
        getattr(M, name).__tablename__
        for name in re.findall(r"M\.([A-Za-z]\w+)", body)
        if hasattr(getattr(M, name, None), "__tablename__")
    }
    missing = set(pipeline._CLONE_TABLES) - mapped
    assert not missing, f"_CLONE_TABLES names tables with no model in by_table: {missing}"


def test_the_clone_migrates_the_source_sqlite_before_reading_it():
    """The real SQLite file is written only by local runs, so it lags the models by
    every table and column added since; the ORM then SELECTs one that is not there
    and the clone dies ("no such table: weather_obs", "no such column:
    games.full_game_total_source"). The fix is the additive, idempotent pair
    store.init_db() already runs."""
    import inspect

    from beatvegas import pipeline

    src = inspect.getsource(pipeline._clone_inputs)
    for call in ("M.Base.metadata.create_all(src)", "_apply_migrations(src)"):
        assert call in src, call
        assert src.index(call) < src.index("with SrcS()"), call
