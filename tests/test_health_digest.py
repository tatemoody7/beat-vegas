"""The daily digest contract (beatvegas/health.py `digest`; final-2026 plan D4 build 2).

The digest is the one contract whose job is to make noise: every check is
failed-severity, so any miss reddens the run and GitHub emails Tate. These
tests seed a healthy system on a Sunday morning, prove the verdict is `ok`,
then break one fact at a time and prove the matching check -- and only it --
misses. The cancelled-run case (2026-10-18) is excused only when a later run of
the same workflow succeeded.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from beatvegas import health
from beatvegas.db.models import (
    AppSetting,
    AppSettingLog,
    ArmPosition,
    ChallengerPick,
    ManualPick,
    OddsSpend,
)
from tests.conftest import _sqlite_scope

# Sunday 2026-10-25 13:30 UTC (9:30am EDT), the day after week 8's Saturday.
NOW = datetime(2026, 10, 25, 13, 30)


def _set(s, key, value, at, note=None):
    row = s.get(AppSetting, key)
    if row is None:
        s.add(AppSetting(key=key, value=str(value), note=note, updated_at=at))
    else:
        row.value, row.note, row.updated_at = str(value), note, at


def _healthy(s):
    for job, age_h in (
        ("card", 25),
        ("grade", 3),
        ("sunday", 7 * 24 - 2),
        ("monday", 6 * 24),
        ("lines_watch", 10),
    ):
        _set(
            s,
            f"last_health_{job}",
            "ok",
            NOW - timedelta(hours=age_h),
            note=f"run={job}-1 event=schedule",
        )
    _set(
        s,
        "last_grade_completed_at",
        (NOW - timedelta(hours=3)).isoformat(timespec="seconds"),
        NOW - timedelta(hours=3),
    )
    _set(
        s,
        "close_coverage_pct",
        "0.980",
        NOW - timedelta(hours=3),
        note="sat=2026-10-24 games=50 covered=49",
    )
    _set(s, "odds_credits_remaining", "9000", NOW - timedelta(hours=10))
    _set(s, "cfbd_calls_remaining", "70000", NOW - timedelta(hours=3))
    _set(s, "odds_cycle_reset_at", "2026-11-05T00:00:00", NOW - timedelta(days=7))
    s.add(
        ArmPosition(
            hypothesis="H-ARM-1HU",
            standard="sprt",
            read_date="2026-10-19",
            read_at=datetime(2026, 10, 19, 12, 40),
            state="running",
        )
    )
    s.add(
        ManualPick(
            arm="H-ARM-1HU", is_paper=True, season=2026, week=8, placed_at=NOW - timedelta(days=2)
        )
    )
    s.add(ChallengerPick(arm="H-ARM-FGU", season=2026, week=8, placed_at=NOW - timedelta(days=2)))
    # Two balance readings and the ledger between them: 9,100 -> 9,000 and 100 spent.
    s.add(
        AppSettingLog(
            key="odds_credits_remaining", value="9100", written_at=NOW - timedelta(days=2)
        )
    )
    s.add(
        AppSettingLog(
            key="odds_credits_remaining", value="9000", written_at=NOW - timedelta(hours=10)
        )
    )
    s.add(
        OddsSpend(
            spent_at=NOW - timedelta(days=1), endpoint="event_odds", credits=100, job="lines_watch"
        )
    )


@pytest.fixture
def db():
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        _healthy(s)
        s.commit()
    return eng


def _run(eng, now=NOW, runs=None):
    with Session(eng) as s:
        ctx = health.Ctx(
            session=s,
            now=now,
            job="digest",
            run_started_at=now,
            status_files={"runs": {"runs": runs or []}},
            env={"GITHUB_RUN_ID": "9", "GITHUB_EVENT_NAME": "schedule"},
        )
        verdict, results = health.evaluate(health.CONTRACTS["digest"], ctx)
        return verdict, {c.id: r for c, r in results}


def test_every_digest_check_is_failed_severity():
    assert all(c.severity == "failed" for c in health.CONTRACTS["digest"].checks)


def test_a_healthy_system_is_ok_and_silent(db):
    verdict, res = _run(db)
    misses = {k: r.detail for k, r in res.items() if not r.ok}
    assert verdict == "ok", misses


@pytest.mark.parametrize(
    "key,value,age_h,check",
    [
        ("last_health_card", "ok", 100, "digest.jobs_fresh"),
        ("last_health_grade", "ok", 31, "digest.jobs_fresh"),
        ("last_health_monday", "ok", 9 * 24, "digest.jobs_fresh"),
        ("last_health_lines_watch", "failed", 2, "digest.jobs_not_failed"),
        ("cfbd_calls_remaining", "250", 1, "digest.cfbd_calls"),
        ("odds_credits_remaining", "1200", 1, "digest.odds_budget"),
    ],
)
def test_one_broken_fact_reddens_its_own_check(db, key, value, age_h, check):
    with Session(db) as s:
        _set(s, key, value, NOW - timedelta(hours=age_h), note="run=77 event=schedule")
        s.commit()
    verdict, res = _run(db)
    assert verdict == "failed"
    assert not res[check].ok, res[check].detail
    others = [k for k, r in res.items() if not r.ok and k != check]
    assert others == [], others


def test_a_cancelled_run_superseded_by_a_success_is_excused(db):
    with Session(db) as s:
        _set(
            s,
            "last_health_grade",
            "failed",
            NOW - timedelta(hours=2),
            note="run=555 event=workflow_dispatch",
        )
        s.commit()
    runs = [
        {
            "databaseId": 555,
            "workflowName": "Daily grading",
            "conclusion": "cancelled",
            "createdAt": "2026-10-25T11:00:00Z",
        },
        {
            "databaseId": 556,
            "workflowName": "Daily grading",
            "conclusion": "success",
            "createdAt": "2026-10-25T11:30:00Z",
        },
    ]
    verdict, res = _run(db, runs=runs)
    assert res["digest.jobs_not_failed"].ok and "cancelled" in res["digest.jobs_not_failed"].detail
    # Without the later success the same cancelled run is a miss.
    verdict, res = _run(db, runs=runs[:1])
    assert not res["digest.jobs_not_failed"].ok and verdict == "failed"


def test_grading_that_lapsed_is_a_miss(db):
    with Session(db) as s:
        _set(
            s,
            "last_grade_completed_at",
            (NOW - timedelta(hours=40)).isoformat(timespec="seconds"),
            NOW - timedelta(hours=40),
        )
        s.commit()
    _, res = _run(db)
    assert not res["digest.grade_recent"].ok


def test_saturday_coverage_must_name_last_saturday_and_reach_90(db):
    with Session(db) as s:
        _set(s, "close_coverage_pct", "1.000", NOW, note="sat=2026-10-17 games=50 covered=50")
        s.commit()
    _, res = _run(db)
    assert (
        not res["digest.saturday_closes"].ok
        and "2026-10-24" in res["digest.saturday_closes"].detail
    )
    with Session(db) as s:
        _set(s, "close_coverage_pct", "0.800", NOW, note="sat=2026-10-24 games=50 covered=40")
        s.commit()
    _, res = _run(db)
    assert not res["digest.saturday_closes"].ok


def test_a_stale_monday_read_is_a_miss(db):
    later = NOW + timedelta(days=9)
    _, res = _run(db, now=later)
    assert not res["digest.positions_fresh"].ok


def test_no_arm_pick_in_a_week_is_a_miss_on_sunday_only(db):
    quiet = NOW + timedelta(days=7)  # the next Sunday, no new picks
    _, res = _run(db, now=quiet)
    assert not res["digest.arms_logging"].ok
    wednesday = NOW + timedelta(days=3)
    _, res = _run(db, now=wednesday)
    assert res["digest.arms_logging"].ok


def test_spend_outside_the_ledger_is_a_miss(db):
    with Session(db) as s:
        s.add(
            AppSettingLog(
                key="odds_credits_remaining", value="8000", written_at=NOW - timedelta(hours=1)
            )
        )
        s.commit()
    _, res = _run(db)
    assert (
        not res["digest.ledger_matches_gauge"].ok
        and "1,100" in res["digest.ledger_matches_gauge"].detail
    )


def test_the_digest_is_off_after_the_season():
    assert health.digest_in_season(datetime(2026, 11, 30, 13, 0))
    assert not health.digest_in_season(datetime(2026, 12, 3, 13, 0))
