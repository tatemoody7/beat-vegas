"""The real-money pause: one row, read strictly, toggled by one script, and honoured by
pick.py's add path outside --force while paper still logs."""

from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import AppSetting, Base
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
