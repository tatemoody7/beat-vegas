"""beatvegas/ops.py -- the gauges the board reads. Written where they are
learned, never raising, and only where DATABASE_URL is set."""

import os

from sqlalchemy.orm import Session

from beatvegas import ops
from beatvegas.db.models import AppSetting
from tests.conftest import _sqlite_scope


def test_no_database_url_means_no_write(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert ops.gauges_enabled() is False
    assert ops.record_gauge(ops.CFBD_CALLS_REMAINING, 1974) is False


def test_record_and_read_through_a_session():
    eng, scope = _sqlite_scope()
    with scope() as s:
        assert ops.record_gauge(ops.ODDS_CREDITS_REMAINING, 53946, session=s) is True
        assert ops.record_gauge(ops.ODDS_CREDITS_REMAINING, 53900, session=s) is True
    with Session(eng) as s:
        row = s.get(AppSetting, ops.ODDS_CREDITS_REMAINING)
        assert row.value == "53900" and row.updated_at is not None
        assert ops.read_gauge(s, ops.ODDS_CREDITS_REMAINING)[0] == "53900"
        assert ops.read_gauge(s, "nope") == (None, None)


def test_a_failing_write_never_raises(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    class Boom:
        def get(self, *a):
            raise RuntimeError("db down")

    assert ops.record_gauge(ops.LAST_GRADE_COMPLETED_AT, "x", session=Boom()) is False
    assert "not recorded" in capsys.readouterr().out


def test_gauge_keys_are_the_ones_the_board_reads():
    web = open(os.path.join(os.path.dirname(__file__), "..", "web", "lib", "boardHealth.ts")).read()
    for k in ops.GAUGE_KEYS:
        assert k in web, f"web/lib/boardHealth.ts does not read gauge {k}"
