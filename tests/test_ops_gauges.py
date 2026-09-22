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


def test_the_trigger_gauge_is_written_by_the_route_and_read_by_the_board():
    """last_dispatch_<job> is the one gauge Python never writes; the web route
    does, and the board must read the same prefix or the row is write-only
    (it was, 2026-09-22)."""
    root = os.path.join(os.path.dirname(__file__), "..", "web")
    route = open(os.path.join(root, "app", "api", "cron", "[job]", "route.ts")).read()
    board = open(os.path.join(root, "lib", "boardHealth.ts")).read()
    assert f"`{ops.LAST_DISPATCH_PREFIX}${{id}}`" in route
    assert f'DISPATCH_GAUGE_PREFIX = "{ops.LAST_DISPATCH_PREFIX}"' in board
    assert "lastDispatch" in board
    # Every job id in the trigger table fits app_settings.key (String(32)).
    cron = open(os.path.join(root, "lib", "cronJobs.ts")).read()
    for job_id in ("card-tue-pm", "card-thu-pm", "card-fri-pm", "card-sat-am", "sunday", "grade"):
        assert job_id in cron
        assert len(ops.last_dispatch_key(job_id)) <= 32
