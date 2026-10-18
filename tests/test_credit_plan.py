"""The credit budget controller (final-2026 PR-C3): allowance arithmetic at the
cycle edges, the archive window, the measured recurring need from the
`odds_spend` ledger, and the `allow` exit codes."""

from datetime import datetime, timedelta

import pytest
from conftest import _load_script, _sqlite_scope

from beatvegas import credit_plan as cp
from beatvegas import ops, protocol
from beatvegas.db.models import AppSetting, OddsSpend

NOW = datetime(2026, 10, 26, 12, 0, 0)
SEASON_END = datetime(2026, 11, 29, 4, 0, 0)


def test_remaining_weeks_counts_to_the_reset_when_it_comes_first():
    assert cp.remaining_weeks(NOW, NOW + timedelta(days=14), SEASON_END) == pytest.approx(2.0)


def test_remaining_weeks_caps_at_the_season_end_when_the_reset_is_later():
    reset = datetime(2026, 12, 5, 5, 0, 0)
    expected = (SEASON_END - NOW).total_seconds() / (7 * 86400)
    assert cp.remaining_weeks(NOW, reset, SEASON_END) == pytest.approx(expected)
    # the default season end is protocol.SEASON_LAST_KICKOFF
    assert cp.remaining_weeks(NOW, reset) == pytest.approx(expected)
    assert protocol.SEASON_LAST_KICKOFF == "2026-11-29T04:00:00"


def test_remaining_weeks_is_never_negative_and_unset_reset_counts_to_season_end():
    assert cp.remaining_weeks(SEASON_END + timedelta(days=3), None, SEASON_END) == 0.0
    assert cp.remaining_weeks(NOW, NOW - timedelta(days=1), SEASON_END) == 0.0
    expected = (SEASON_END - NOW).total_seconds() / (7 * 86400)
    assert cp.remaining_weeks(NOW, None, SEASON_END) == pytest.approx(expected)


def test_allowance_reset_in_ten_days_with_two_weeks_of_recurring():
    reset = NOW + timedelta(days=10)
    weeks = 10 / 7
    got = cp.allowance(6000, NOW, reset, 1500, 840, SEASON_END)
    assert got == int(round(6000 - 1500 - 840 * weeks))
    assert got == 3300  # 840 x 10/7 = 1,200 of recurring


def test_allowance_two_full_weeks():
    assert (
        cp.allowance(5000, NOW, NOW + timedelta(days=14), 1500, 450, SEASON_END)
        == 5000 - 1500 - 900
    )


def test_allowance_can_go_negative():
    assert cp.allowance(2000, NOW, NOW + timedelta(days=14), 1500, 840, SEASON_END) < 0


def test_allowance_after_the_season_is_balance_minus_floor():
    after = SEASON_END + timedelta(days=2)
    assert cp.allowance(4000, after, datetime(2026, 12, 5, 5), 1500, 840, SEASON_END) == 2500


def test_archive_window_is_open_only_in_the_last_four_days():
    reset = datetime(2026, 11, 5, 5, 0, 0)
    assert not cp.archive_window_open(reset - timedelta(days=4, seconds=1), reset)
    assert cp.archive_window_open(reset - timedelta(days=4), reset)
    assert cp.archive_window_open(reset - timedelta(hours=1), reset)
    assert not cp.archive_window_open(reset, reset)
    assert not cp.archive_window_open(reset + timedelta(hours=1), reset)
    assert not cp.archive_window_open(reset - timedelta(days=2), None)


def test_archive_window_needs_last_saturdays_closes():
    reset = datetime(2026, 11, 5, 5, 0, 0)
    assert not cp.archive_window_open(reset - timedelta(days=2), reset, last_saturday_closed=False)


def test_saturday_closes_in_names_the_latest_finished_saturday():
    sunday = datetime(2026, 11, 1, 15, 0, 0)  # Sun; the Saturday is 10-31
    assert cp.saturday_closes_in("sat=2026-10-31 games=50 covered=48", sunday)
    assert not cp.saturday_closes_in("sat=2026-10-24 games=50 covered=48", sunday)
    assert not cp.saturday_closes_in("sat=2026-10-31 games=50 covered=0", sunday)
    assert not cp.saturday_closes_in(None, sunday)
    # on the Saturday itself the closes are not in yet; last week's gauge counts
    sat = datetime(2026, 10, 31, 18, 0, 0)
    assert not cp.saturday_closes_in("sat=2026-10-31 games=50 covered=10", sat)


def _spend(s, at, job, credits):
    s.add(OddsSpend(spent_at=at, job=job, endpoint="events", credits=credits))


def test_measured_recurring_sums_recurring_jobs_and_ignores_research_and_archive():
    eng, scope = _sqlite_scope()
    with scope() as s:
        _spend(s, NOW - timedelta(days=9), "card", 5)  # old row: proves 7+ days of ledger
        _spend(s, NOW - timedelta(days=6), "card", 100)
        _spend(s, NOW - timedelta(days=5), "lines_watch", 300)
        _spend(s, NOW - timedelta(days=1), "sunday", 50)
        _spend(s, NOW - timedelta(days=2), "research", 999)
        _spend(s, NOW - timedelta(days=3), "archive", 5000)
        _spend(s, NOW - timedelta(days=8), "card", 700)  # outside the window
    with scope() as s:
        assert cp.measured_recurring(s, NOW) == 450


def test_measured_recurring_scales_a_shorter_window_to_a_week():
    eng, scope = _sqlite_scope()
    with scope() as s:
        _spend(s, NOW - timedelta(days=20), "card", 1)
        _spend(s, NOW - timedelta(days=1), "lines_watch", 100)
    with scope() as s:
        assert cp.measured_recurring(s, NOW, days=3) == 233  # 100 * 7/3


def test_measured_recurring_is_none_under_seven_days_of_ledger():
    eng, scope = _sqlite_scope()
    with scope() as s:
        assert cp.measured_recurring(s, NOW) is None  # empty
        _spend(s, NOW - timedelta(days=6), "card", 400)
    with scope() as s:
        assert cp.measured_recurring(s, NOW) is None


def test_load_settings_defaults_and_overrides():
    eng, scope = _sqlite_scope()
    with scope() as s:
        st = cp.load_settings(s)
        assert (st.reset_at, st.floor, st.archive_window_days, st.recurring_fallback) == (
            None,
            1500,
            4,
            840,
        )
        s.add(AppSetting(key=cp.RESET_AT_KEY, value="2026-11-05T05:00:00"))
        s.add(AppSetting(key=cp.FLOOR_KEY, value="2000"))
        s.add(AppSetting(key=cp.RECURRING_FALLBACK_KEY, value="450"))
        s.add(AppSetting(key=cp.ARCHIVE_WINDOW_KEY, value="junk"))
    with scope() as s:
        st = cp.load_settings(s)
        assert st.reset_at == datetime(2026, 11, 5, 5)
        assert (st.floor, st.archive_window_days, st.recurring_fallback) == (2000, 4, 450)


def test_setting_keys_fit_app_settings_key_and_gauge_is_registered():
    for k in (cp.RESET_AT_KEY, cp.FLOOR_KEY, cp.ARCHIVE_WINDOW_KEY, cp.RECURRING_FALLBACK_KEY):
        assert len(k) <= 32
    assert len(ops.ODDS_PROJECTED_END_BALANCE) <= 32
    assert ops.ODDS_PROJECTED_END_BALANCE in ops.GAUGE_KEYS


def test_plan_has_the_registered_purposes():
    assert cp.PLAN["recurring"] == 450 and cp.PLAN["team_totals"] == 550
    assert sum(cp.PLAN.values()) == 450 + 35 + 40 + 65 + 150 + 100 + 165 + 550


# --- the script ------------------------------------------------------------

SAT_NOTE = "sat=2026-10-31 games=50 covered=48"


@pytest.fixture
def script(monkeypatch):
    eng, scope = _sqlite_scope()
    mod = _load_script("credit_plan")
    monkeypatch.setattr(mod, "session_scope", scope)
    monkeypatch.setattr(mod, "try_init_db", lambda: True)
    monkeypatch.setattr(mod.ops, "record_gauge", lambda *a, **k: True)  # never touches a real DB
    return mod, scope


def _seed(scope, balance=8000, reset="2026-11-05T05:00:00", cov=SAT_NOTE):
    with scope() as s:
        if balance is not None:
            s.add(AppSetting(key=ops.ODDS_CREDITS_REMAINING, value=str(balance)))
        if reset:
            s.add(AppSetting(key=cp.RESET_AT_KEY, value=reset))
        if cov:
            s.add(AppSetting(key=ops.CLOSE_COVERAGE_PCT, value="0.96", note=cov))


def _allow(mod, purpose, est, now, drain=False):
    return mod.main(
        ["--now", now, "allow", "--purpose", purpose, "--estimate", str(est)]
        + (["--drain"] if drain else [])
    )


def test_allow_exits_zero_within_the_allowance_and_one_over(script, capsys):
    mod, scope = script
    _seed(scope)
    # 4 days to the reset: 840 * 4/7 = 480 need; allowance = 8000 - 1500 - 480 = 6020
    assert _allow(mod, "midweek_1h", 6020, "2026-11-01T05:00:00") == 0
    assert "ALLOW" in capsys.readouterr().out
    assert _allow(mod, "midweek_1h", 6021, "2026-11-01T05:00:00") == 1
    out = capsys.readouterr().out
    assert (
        out.startswith("DENY midweek_1h")
        and "allowance 6,020" in out
        and len(out.strip().splitlines()) == 1
    )


def test_allow_with_no_reset_counts_to_the_season_end_and_refuses_archive(script, capsys):
    mod, scope = script
    _seed(scope, reset=None)
    assert _allow(mod, "midweek_1h", 100, "2026-11-01T05:00:00") == 0
    assert _allow(mod, "archive_pinnacle_2026", 1, "2026-11-01T05:00:00") == 1
    assert "reset date unset" in capsys.readouterr().out


def test_allow_archive_needs_the_window_and_drain_waives_it(script, capsys):
    mod, scope = script
    _seed(scope)
    assert _allow(mod, "archive_hr_ladder", 100, "2026-10-28T05:00:00") == 1  # a week out
    assert "window closed" in capsys.readouterr().out
    assert (
        _allow(mod, "archive_hr_ladder", 100, "2026-11-02T05:00:00") == 0
    )  # inside 4 days, closes in
    assert _allow(mod, "archive_hr_ladder", 100, "2026-10-28T05:00:00", drain=True) == 0


def test_allow_archive_refused_when_saturday_closes_are_not_in(script, capsys):
    mod, scope = script
    _seed(scope, cov="sat=2026-10-24 games=50 covered=48")
    assert _allow(mod, "archive_hr_ladder", 100, "2026-11-02T05:00:00") == 1


def test_allow_denies_without_a_balance(script, capsys):
    mod, scope = script
    _seed(scope, balance=None)
    assert _allow(mod, "midweek_1h", 1, "2026-11-01T05:00:00") == 1
    assert "balance unknown" in capsys.readouterr().out


def test_report_runs_without_a_reset_and_says_so(script, capsys, tmp_path, monkeypatch):
    mod, scope = script
    _seed(scope, reset=None)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert mod.main(["--now", "2026-10-26T12:00:00", "report"]) == 0
    out = capsys.readouterr().out
    assert "UNSET" in out and "fallback" in out and "allowance" in out
    assert "Odds API credit plan" in summary.read_text()


def test_report_writes_the_projected_end_gauge(script, monkeypatch):
    mod, scope = script
    _seed(scope)
    calls = []
    monkeypatch.setattr(mod.ops, "record_gauge", lambda *a, **k: calls.append(a) or True)
    assert mod.main(["--now", "2026-11-01T05:00:00", "report"]) == 0
    key, value = calls[0][0], calls[0][1]
    assert key == ops.ODDS_PROJECTED_END_BALANCE and value == 8000 - 480


def test_set_commands_write_through_the_gauge_and_print_old_and_new(script, monkeypatch, capsys):
    mod, scope = script
    written = []
    monkeypatch.setattr(
        mod.ops,
        "record_gauge",
        lambda key, value, note=None, session=None: written.append((key, value)) or True,
    )
    with scope() as s:
        s.add(AppSetting(key=cp.FLOOR_KEY, value="1500"))
    assert mod.main(["set-floor", "2000"]) == 0
    assert "odds_credit_floor: 1500 -> 2000" in capsys.readouterr().out
    assert mod.main(["set-reset", "2026-11-05T05:00:00"]) == 0
    assert "(unset) -> 2026-11-05T05:00:00" in capsys.readouterr().out
    assert mod.main(["set-recurring", "450"]) == 0
    assert written == [
        (cp.FLOOR_KEY, "2000"),
        (cp.RESET_AT_KEY, "2026-11-05T05:00:00"),
        (cp.RECURRING_FALLBACK_KEY, "450"),
    ]
    assert mod.main(["set-reset", "next tuesday"]) == 1
    assert mod.main(["set-floor", "-5"]) == 1
