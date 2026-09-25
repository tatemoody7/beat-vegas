"""scripts/health_check.py -- the workflow step around beatvegas/health.py:
env -> Ctx, the gauge write, the annotations and the exit codes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from conftest import _load_script
from sqlalchemy.orm import Session

from beatvegas import ops
from beatvegas.db.models import AppSetting, Card, ManualPick
from tests.conftest import _sqlite_scope

SEASON, WEEK = 2026, 4
STARTED = datetime(2026, 9, 25, 20, 5, 0)  # Friday 4:05pm ET


@pytest.fixture
def mod(monkeypatch):
    """The script bound to an in-memory SQLite. Returns (module, engine)."""
    m = _load_script("health_check")
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(m, "try_init_db", lambda: True)
    monkeypatch.setattr(m, "session_scope", scope)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return m, eng


def _env(**kw):
    base = {
        "RUN_STARTED_AT": STARTED.isoformat(timespec="seconds") + "Z",
        "SEASON": str(SEASON),
        "WEEK": str(WEEK),
        "SLOT": "fri_pm",
        "OUTCOME_SWEEP": "success",
        "OUTCOME_PREVIEW": "skipped",
        "OUTCOME_BUILD": "success",
        "GITHUB_RUN_ID": "777",
        "GITHUB_EVENT_NAME": "schedule",
    }
    base.update(kw)
    return base


def _card(eng, n_hr=12):
    items = [
        {
            "game_id": g,
            "qualifies": g == 1,
            "hr_line": 24.5,
            "kick": (STARTED + timedelta(days=1)).isoformat(timespec="seconds") + "Z",
            "tier": "BET" if g == 1 else "PASS",
            "blocker": None,
        }
        for g in range(1, n_hr + 1)
    ]
    payload = {
        "slot": "fri_pm",
        "status": "final",
        "degraded": [],
        "counts": {"bet": 1},
        "items": items,
    }
    with Session(eng) as s:
        s.add(
            Card(
                season=SEASON,
                week=WEEK,
                built_at=STARTED + timedelta(minutes=9),
                payload=json.dumps(payload),
            )
        )
        s.add(
            ManualPick(
                game_id=1,
                season=SEASON,
                week=WEEK,
                side="under",
                market="1H",
                line=24.5,
                is_paper=True,
                placed_at=STARTED + timedelta(minutes=9),
            )
        )
        s.commit()


def _sweep_file(tmp_path, **over):
    st = {"complete": True, "events_in_window": 12, "events_polled": 12, "credits_spent": 12}
    st.update(over)
    p = tmp_path / "sweep_status.json"
    p.write_text(json.dumps(st))
    return str(p)


def _gauge(eng):
    with Session(eng) as s:
        return s.get(AppSetting, ops.health_key("card"))


# --------------------------------------------------------------------------- #
# env -> Ctx
# --------------------------------------------------------------------------- #
def test_ctx_from_env_parses_every_field(mod):
    m, eng = mod
    env = _env(WEEK="", MARKET="1h_close", NEED_SCORE="true")
    with Session(eng) as s:
        ctx, notices = m.ctx_from_env("card", env, session=s, now=STARTED + timedelta(minutes=10))
    assert notices == []
    assert ctx.run_started_at == STARTED and ctx.run_started_at.tzinfo is None
    assert ctx.season == SEASON and ctx.week is None  # '' -> None
    assert ctx.slot == "fri_pm" and ctx.market == "1h_close"
    assert ctx.outcomes == {"sweep": "success", "preview": "skipped", "build": "success"}
    assert ctx.env["NEED_SCORE"] == "true"
    assert ctx.status_files == {}


def test_parse_utc_accepts_date_u_output_and_offsets(mod):
    m, _eng = mod
    assert m.parse_utc("2026-09-25T20:05:00Z") == STARTED
    assert m.parse_utc("2026-09-25T16:05:00-04:00") == STARTED
    assert m.parse_utc("2026-09-25T20:05:00") == STARTED
    assert m.parse_utc("") is None and m.parse_utc("garbage") is None


def test_a_missing_run_start_is_noticed_and_defaults_to_a_lookback(mod):
    m, eng = mod
    now = STARTED + timedelta(minutes=10)
    with Session(eng) as s:
        ctx, notices = m.ctx_from_env("card", _env(RUN_STARTED_AT=""), session=s, now=now)
    assert ctx.run_started_at == now - timedelta(hours=m.DEFAULT_LOOKBACK_HOURS)
    assert len(notices) == 1 and "RUN_STARTED_AT" in notices[0]


def test_status_files_are_loaded_only_when_present_and_valid(mod, tmp_path):
    m, _eng = mod
    good = _sweep_file(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    files = m.load_status_files(
        {"sweep": good, "close": str(tmp_path / "missing.json"), "bad": str(bad), "none": None}
    )
    assert set(files) == {"sweep"}
    assert files["sweep"]["events_polled"] == 12


# --------------------------------------------------------------------------- #
# exit codes + the gauge
# --------------------------------------------------------------------------- #
def test_a_clean_card_run_writes_ok_and_exits_0(mod, tmp_path, capsys):
    m, eng = mod
    _card(eng)
    rc = m.run(m.parse_args(["--job", "card", "--sweep-status", _sweep_file(tmp_path)]), _env())
    assert rc == 0
    row = _gauge(eng)
    assert row.value == "ok"
    assert (
        row.note
        == "run=777 event=schedule slot=fri_pm info=bets=1 early_season_held=0 hr_alt_ignored=0 preview=skipped sweep=success"
    )
    out = capsys.readouterr().out
    assert "ok   card.row_this_run" in out and "::warning::" not in out


def test_a_degraded_run_warns_and_exits_0(mod, tmp_path, capsys):
    m, eng = mod
    _card(eng, n_hr=3)  # under HR_PRICED_FLOOR
    rc = m.run(m.parse_args(["--job", "card", "--sweep-status", _sweep_file(tmp_path)]), _env())
    assert rc == 0
    row = _gauge(eng)
    assert row.value == "degraded"
    assert "miss=card.hr_priced_floor(3 Hard Rock-priced items" in row.note
    out = capsys.readouterr().out
    assert "::warning::card.hr_priced_floor:" in out and "::error::" not in out


def test_a_failed_run_errors_and_exits_1_unless_told_never(mod, tmp_path, capsys):
    m, eng = mod  # no card row at all
    args = ["--job", "card", "--sweep-status", _sweep_file(tmp_path)]
    assert m.run(m.parse_args(args), _env()) == 1
    row = _gauge(eng)
    assert row.value == "failed"
    assert "miss=card.row_this_run(no cards row" in row.note
    out = capsys.readouterr().out
    assert "::error::card.row_this_run:" in out
    # The dependent checks miss too, but only the failed-severity one is an error.
    assert "::warning::card.status_clean:" in out
    assert m.run(m.parse_args(args + ["--fail-on", "never"]), _env()) == 0
    assert _gauge(eng).value == "failed"  # the verdict is still recorded honestly


def test_a_skipped_run_writes_nothing_and_exits_0(mod, capsys):
    m, eng = mod
    rc = m.run(m.parse_args(["--job", "card"]), _env(SKIPPED="true"))
    assert rc == 0
    assert _gauge(eng) is None
    assert "skipped run, no verdict" in capsys.readouterr().out


def test_an_unreachable_db_exits_0_without_a_verdict(mod, monkeypatch, capsys):
    m, eng = mod
    monkeypatch.setattr(m, "try_init_db", lambda: False)
    assert m.run(m.parse_args(["--job", "grade"]), _env()) == 0
    assert _gauge(eng) is None
    assert "DB unreachable" in capsys.readouterr().out


def test_the_step_summary_carries_the_verdict_line(mod, tmp_path, monkeypatch):
    m, eng = mod
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    _card(eng)
    m.run(m.parse_args(["--job", "card", "--sweep-status", _sweep_file(tmp_path)]), _env())
    assert summary.read_text().startswith("HEALTH: ok run=777 event=schedule slot=fri_pm")


def test_the_job_choices_are_the_contracts(mod):
    m, _eng = mod
    from beatvegas import health

    with pytest.raises(SystemExit):
        m.parse_args(["--job", "nope"])
    for job in health.CONTRACTS:
        assert m.parse_args(["--job", job]).job == job
