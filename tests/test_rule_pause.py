"""The real-money pause: one row, read strictly, toggled by one script, and honoured by
pick.py's add path outside --force while paper still logs."""

from __future__ import annotations

import importlib.util
from argparse import Namespace
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import AppSetting, Base, Game, ManualPick
from beatvegas.picks import RULE_PAUSED_KEY, rule_paused, set_rule_paused

_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    path = _ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


def _scope(eng):
    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    return scope


def test_rule_paused_reads_only_the_exact_string_true():
    eng = _engine()
    with Session(eng) as s:
        assert rule_paused(s) is None  # no row = never switched on
        s.add(AppSetting(key=RULE_PAUSED_KEY, value="TRUE"))
        s.commit()
        assert rule_paused(s) is None  # the writer controls the value; nothing else counts
        set_rule_paused(s, True, note="week 6 boundary")
        s.commit()
        assert rule_paused(s) == "week 6 boundary"
        set_rule_paused(s, False)
        s.commit()
        assert rule_paused(s) is None
        assert s.query(AppSetting).count() == 1  # replaced in place, never a second row


def test_script_toggles_and_reports_status(capsys):
    mod = _load("rule_pause")
    eng = _engine()
    mod.session_scope = _scope(eng)
    mod.try_init_db = lambda: True
    assert mod.main(["status"]) == 0
    assert mod.main(["on", "--note", "drawdown review"]) == 0
    assert mod.main(["on", "--note", "drawdown review"]) == 0  # idempotent
    assert mod.main(["status"]) == 2
    out = capsys.readouterr().out
    assert "PAUSED" in out and "drawdown review" in out
    with Session(eng) as s:
        assert s.query(AppSetting).count() == 1
    assert mod.main(["off"]) == 0
    assert mod.main(["status"]) == 0


def _pick_module_paused(paused: bool):
    pick = _load("pick")
    eng = _engine()
    future = datetime.utcnow() + timedelta(days=3)
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=4,
                home_team="Ohio State",
                away_team="Michigan",
                start_date=future,
            )
        )
        if paused:
            set_rule_paused(s, True, note="boundary crossed")
        s.commit()
    pick.session_scope = _scope(eng)
    return pick, eng


def _args(**kw) -> Namespace:
    base = dict(
        home="Ohio State",
        away="Michigan",
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


def _n_picks(eng) -> int:
    with Session(eng) as s:
        return s.query(ManualPick).count()


def test_cmd_add_refuses_real_money_while_paused_even_with_force(capsys):
    """Since 2026-09-22 the CLI is paper-only, so real money is refused before
    the pause is even consulted -- and --force changes nothing. The pause itself
    is still enforced on the site's write path (pickRules.checkPolicy) and read
    fail-closed there; scripts/rule_pause.py remains its only writer."""
    pick, eng = _pick_module_paused(True)
    pick.cmd_add(_args())
    assert _n_picks(eng) == 0
    pick.cmd_add(_args(force=True))
    assert _n_picks(eng) == 0
    out = capsys.readouterr().out
    assert "REFUSED" in out and "paper-only" in out


def test_cmd_add_still_logs_paper_while_paused_and_never_real():
    pick, eng = _pick_module_paused(True)
    pick.cmd_add(_args(paper=True))
    assert _n_picks(eng) == 1  # the pause is about money; paper keeps accruing
    pick2, eng2 = _pick_module_paused(False)
    pick2.cmd_add(_args())
    assert _n_picks(eng2) == 0  # real money is logged on the site, never here
