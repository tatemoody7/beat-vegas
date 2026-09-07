"""ManualPick decision-tracking columns (shared contract with the web lane —
names are exact): verdict_at_pick, reason, gap_at_pick, ev_at_pick,
hr_line_at_pick. pick.py add takes them as flags; --paper now stakes one flat
unit so paper picks grade as +/-1 (is_paper keeps them out of the real ledger)."""

from argparse import Namespace
from contextlib import contextmanager
from datetime import datetime, timedelta

from conftest import _load_script
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, ManualPick
from beatvegas.db.store import _MIGRATIONS, _apply_migrations

TRACKING_COLS = {
    "verdict_at_pick": "VARCHAR(8)",
    "reason": "VARCHAR(16)",
    "gap_at_pick": "FLOAT",
    "ev_at_pick": "FLOAT",
    "hr_line_at_pick": "FLOAT",
}


def test_model_and_migration_carry_the_tracking_columns():
    cols = ManualPick.__table__.columns
    for name in TRACKING_COLS:
        assert name in cols, name
    assert cols["verdict_at_pick"].type.length == 8
    assert cols["reason"].type.length == 16
    for name, sqltype in TRACKING_COLS.items():
        assert _MIGRATIONS["manual_picks"][name] == sqltype


def test_migration_adds_columns_to_a_legacy_table():
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE manual_picks (id INTEGER PRIMARY KEY, line FLOAT)"))
    _apply_migrations(eng)
    have = {col["name"] for col in inspect(eng).get_columns("manual_picks")}
    assert set(TRACKING_COLS) <= have


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
        paper=False,
        reason="manual",
        verdict=None,
        gap=None,
        ev=None,
        hr_line=None,
    )
    base.update(kw)
    return Namespace(**base)


def _pick_module():
    pick = _load_script("pick")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=13,
                home_team="Michigan",
                away_team="Ohio State",
                start_date=datetime.utcnow() + timedelta(days=30),
            )
        )
        s.commit()

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    pick.session_scope = scope
    return pick, eng


def test_add_stores_the_decision_snapshot():
    pick, eng = _pick_module()
    pick.cmd_add(
        _args(reason="model_gap", verdict="BET", gap=2.25, ev=0.031, hr_line=24.5, stake=2.0)
    )
    with Session(eng) as s:
        (row,) = s.query(ManualPick).all()
    assert row.reason == "model_gap"
    assert row.verdict_at_pick == "BET"
    assert row.gap_at_pick == 2.25
    assert row.ev_at_pick == 0.031
    assert row.hr_line_at_pick == 24.5
    assert row.stake == 2.0 and row.is_paper is False


def test_add_defaults_to_manual_reason_and_null_snapshot():
    pick, eng = _pick_module()
    pick.cmd_add(_args())
    with Session(eng) as s:
        (row,) = s.query(ManualPick).all()
    assert row.reason == "manual"
    assert row.verdict_at_pick is None and row.gap_at_pick is None
    assert row.ev_at_pick is None and row.hr_line_at_pick is None


def test_paper_pick_stakes_one_flat_unit():
    pick, eng = _pick_module()
    pick.cmd_add(_args(paper=True, stake=3.0))
    with Session(eng) as s:
        (row,) = s.query(ManualPick).all()
    assert row.is_paper is True
    assert row.stake == 1.0  # grades as +/-1u; is_paper keeps it off the real ledger


def test_paper_pick_grades_to_plus_minus_one_unit():
    fields = _load_script("pick").graded_pick_fields(20, 24.5, -110, 1.0, 25.0, 24.0)
    assert fields["result"] == "under" and round(fields["units"], 3) == 0.909
    fields = _load_script("pick").graded_pick_fields(30, 24.5, -110, 1.0, 25.0, 24.0)
    assert fields["result"] == "over" and fields["units"] == -1.0


def test_cli_parses_the_new_flags(monkeypatch):
    import sys

    pick = _load_script("pick")
    seen = {}
    monkeypatch.setattr(pick, "try_init_db", lambda: True)
    monkeypatch.setattr(pick, "cmd_add", lambda a: seen.update(vars(a)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pick.py",
            "add",
            "--home",
            "Michigan",
            "--away",
            "Ohio State",
            "--line",
            "24.5",
            "--reason",
            "price_edge",
            "--verdict",
            "WATCH",
            "--gap",
            "1.5",
            "--ev",
            "0.02",
            "--hr-line",
            "25",
            "--paper",
        ],
    )
    pick.main()
    assert seen["reason"] == "price_edge" and seen["verdict"] == "WATCH"
    assert seen["gap"] == 1.5 and seen["ev"] == 0.02 and seen["hr_line"] == 25.0
    assert seen["paper"] is True


# --- paper ledger vs real ledger (2026-09-07) ----------------------------------

from beatvegas.picks import add_pick, existing_pick  # noqa: E402


def test_blocker_column_and_migration():
    cols = ManualPick.__table__.columns
    assert "blocker" in cols and cols["blocker"].type.length == 16
    assert _MIGRATIONS["manual_picks"]["blocker"] == "VARCHAR(16)"


def _paper(s, gid=1, blocker="price"):
    return add_pick(
        s,
        game_id=gid,
        season=2026,
        week=13,
        home_team="Michigan",
        away_team="Ohio State",
        line=24.5,
        price=-125,
        is_paper=True,
        reason="model_gap",
        verdict="WATCH",
        gap=2.0,
        blocker=blocker,
        factors_json='{"total_band": "52–60"}',
    )


def test_null_price_persists_as_null():
    """An unpriced Hard Rock line logs price NULL — the ORM must not fall back
    to a -110 column default on INSERT (grade fills it from HR's close)."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        row = add_pick(
            s,
            game_id=1,
            season=2026,
            week=3,
            home_team="H",
            away_team="A",
            line=24.5,
            price=None,
            is_paper=True,
        )
        s.commit()
        rid = row.id
    with Session(eng) as s:
        assert s.get(ManualPick, rid).price is None


def test_add_pick_stores_blocker_and_chips():
    pick, eng = _pick_module()
    with Session(eng) as s:
        _paper(s)
        s.commit()
        (row,) = s.query(ManualPick).all()
    assert row.blocker == "price" and row.factors_json_at_pick == '{"total_band": "52–60"}'


def test_existing_pick_is_scoped_per_ledger():
    pick, eng = _pick_module()
    with Session(eng) as s:
        _paper(s)
        s.commit()
        assert existing_pick(s, 1, "1H") is not None  # any ledger (legacy)
        assert existing_pick(s, 1, "1H", is_paper=True) is not None
        assert existing_pick(s, 1, "1H", is_paper=False) is None  # real ledger is clear
        # a legacy row with NULL is_paper counts as real
        s.add(
            ManualPick(
                game_id=1,
                season=2026,
                week=13,
                side="under",
                market="1H",
                line=24.5,
                price=-110,
                stake=1.0,
                is_paper=None,
            )
        )
        s.commit()
        assert existing_pick(s, 1, "1H", is_paper=False) is not None


def test_real_ticket_is_not_refused_by_the_cards_paper_pick(capsys):
    pick, eng = _pick_module()
    with Session(eng) as s:
        _paper(s)
        s.commit()
    pick.cmd_add(_args(price=-110))  # Tate's real bet on the same game
    out = capsys.readouterr().out
    assert "REFUSED" not in out
    with Session(eng) as s:
        rows = s.query(ManualPick).order_by(ManualPick.id).all()
    assert [r.is_paper for r in rows] == [True, False]


def test_second_real_ticket_is_still_refused(capsys):
    pick, eng = _pick_module()
    pick.cmd_add(_args())
    pick.cmd_add(_args(price=-105))
    assert "REFUSED" in capsys.readouterr().out
    with Session(eng) as s:
        assert s.query(ManualPick).count() == 1


def test_second_paper_pick_is_refused(capsys):
    pick, eng = _pick_module()
    pick.cmd_add(_args(paper=True))
    pick.cmd_add(_args(paper=True))
    assert "REFUSED: paper pick" in capsys.readouterr().out


def test_grade_uses_hard_rocks_own_close_for_a_hard_rock_ticket():
    """The per-game close polls capture Hard Rock's pre-kick number; a Hard
    Rock ticket's CLV is against THAT, not the consensus close."""
    from datetime import datetime, timedelta

    from beatvegas.db.models import Game, OddsSnapshot

    pick, eng = _pick_module()
    kick = datetime(2026, 9, 19, 19, 30)
    with Session(eng) as s:
        s.add(
            Game(
                id=2,
                season=2026,
                week=3,
                home_team="Missouri",
                away_team="Kansas",
                start_date=kick,
                home_points=30,
                away_points=10,
                first_half_total=20,
                first_half_source="pbp",
            )
        )
        for book, line, hrs in (
            ("draftkings", 24.5, 30),
            ("draftkings", 26.5, 1),
            ("hardrockbet", 24.5, 30),
            ("hardrockbet", 23.5, 1),
            ("hardrockbet", 30.0, -1),
        ):  # last one is in-game
            s.add(
                OddsSnapshot(
                    game_id=2,
                    book=book,
                    market="1H_total",
                    line=line,
                    over_price=-110,
                    under_price=-110,
                    captured_at=kick - timedelta(hours=hrs),
                )
            )
        s.add(
            ManualPick(
                game_id=2,
                season=2026,
                week=3,
                home_team="Missouri",
                away_team="Kansas",
                side="under",
                market="1H",
                line=24.5,
                price=-110,
                stake=1.0,
                is_paper=False,
                book="hardrockbet",
                graded=False,
                placed_at=kick,
            )
        )
        s.add(
            ManualPick(
                game_id=2,
                season=2026,
                week=3,
                home_team="Missouri",
                away_team="Kansas",
                side="under",
                market="1H",
                line=24.5,
                price=-110,
                stake=1.0,
                is_paper=True,
                book=None,
                graded=False,
                placed_at=kick,
            )
        )
        s.commit()
    pick.cmd_grade(_args(season=2026))
    with Session(eng) as s:
        hr, other = (
            s.query(ManualPick).filter(ManualPick.game_id == 2).order_by(ManualPick.id).all()
        )
    assert hr.graded and hr.result == "under"
    assert hr.closing_line == 23.5 and hr.clv == -1.0  # Hard Rock's own pre-kick close
    assert other.closing_line == 25.0 and other.clv == 0.5  # consensus close (median of 26.5, 23.5)
