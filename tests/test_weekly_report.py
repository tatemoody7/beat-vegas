"""The Sunday report (scripts/weekly_report.py; final-2026 plan D4 build 3).

Builds a whole report from an in-memory week: games on Saturday 2026-10-24
(week 8), two arms' paper picks (one graded and read, one graded and excluded,
one not graded yet), the Monday read's rows, the gauges and the credit ledger.
The report must open with the five summary lines, say PENDING for the pick it
cannot know yet, carry its sources, and never call the system HEALTHY while a
pick is pending or the digest misses.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from conftest import _load_script, _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.db.models import (
    AppSetting,
    AppSettingLog,
    ArmPosition,
    ChallengerPick,
    Game,
    ManualPick,
    OddsSpend,
    ResearchSnapshot,
)

NOW = datetime(2026, 10, 25, 15, 5)  # Sunday 11:05am EDT
SAT = datetime(2026, 10, 24, 16, 0)


def _set(s, key, value, at, note=None):
    s.add(AppSetting(key=key, value=str(value), note=note, updated_at=at))


@pytest.fixture
def week():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        for gid in (1, 2, 3):
            s.add(
                Game(
                    id=gid,
                    season=2026,
                    week=8,
                    home_team=f"H{gid}",
                    away_team=f"A{gid}",
                    start_date=SAT + timedelta(hours=gid),
                )
            )
        placed = datetime(2026, 10, 22, 21, 0)
        s.add(
            ManualPick(
                id=10,
                game_id=1,
                season=2026,
                week=8,
                arm="H-ARM-1HU",
                is_paper=True,
                market="1H",
                side="under",
                line=27.5,
                price=-110,
                placed_at=placed,
                graded=True,
                units=0.91,
                ev_cons=-0.031,
                cons_version="cv1",
            )
        )
        s.add(
            ChallengerPick(
                id=20,
                arm="H-ARM-FGU",
                game_id=2,
                season=2026,
                week=8,
                market="full",
                side="under",
                line=52.5,
                price=-110,
                placed_at=placed,
                graded=True,
                units=-1.0,
                ev_cons=None,
                cons_excluded="far_lines",
            )
        )
        s.add(
            ChallengerPick(
                id=21,
                arm="H-ARM-FGU",
                game_id=3,
                season=2026,
                week=8,
                market="full",
                side="under",
                line=55.5,
                price=-110,
                placed_at=placed,
                graded=False,
            )
        )
        s.add(
            ArmPosition(
                hypothesis="H-ARM-1HU",
                standard="sprt",
                read_date="2026-10-19",
                read_at=datetime(2026, 10, 19, 12, 40),
                state="running",
                readings=11,
                llr=-2.425,
            )
        )
        s.add(
            ArmPosition(
                hypothesis="H-PRICE-HR",
                standard="pricing",
                read_date="2026-10-19",
                read_at=datetime(2026, 10, 19, 12, 40),
                state="insufficient",
                readings=2,
                needed=40,
                mean_ev=0.0403,
            )
        )
        for job in ("card", "grade", "sunday", "monday", "lines_watch", "digest"):
            _set(
                s,
                f"last_health_{job}",
                "ok",
                NOW - timedelta(hours=5),
                note=f"run={job} event=schedule",
            )
        _set(
            s,
            "last_grade_completed_at",
            (NOW - timedelta(hours=5)).isoformat(timespec="seconds"),
            NOW - timedelta(hours=5),
        )
        _set(
            s,
            "close_coverage_pct",
            "1.000",
            NOW - timedelta(hours=5),
            note="sat=2026-10-24 games=3 covered=3",
        )
        _set(s, "odds_credits_remaining", "8800", NOW - timedelta(hours=9))
        _set(s, "cfbd_calls_remaining", "73000", NOW - timedelta(hours=5))
        _set(s, "odds_cycle_reset_at", "2026-11-05T00:00:00", NOW - timedelta(days=6))
        s.add(
            AppSettingLog(
                key="cfbd_calls_remaining", value="73250", written_at=NOW - timedelta(days=6)
            )
        )
        s.add(
            AppSettingLog(
                key="cfbd_calls_remaining", value="73000", written_at=NOW - timedelta(hours=5)
            )
        )
        s.add(
            OddsSpend(
                spent_at=NOW - timedelta(days=2),
                endpoint="event_odds",
                credits=320,
                job="lines_watch",
            )
        )
        s.add(
            OddsSpend(
                spent_at=NOW - timedelta(days=4),
                endpoint="odds",
                credits=2,
                job="card",
                purpose="sharp_eu",
            )
        )
        s.add(
            ResearchSnapshot(
                book="pinnacle",
                market="full_game_total",
                purpose="sharp_eu",
                captured_at=NOW - timedelta(days=4),
                source="live",
                team="",
            )
        )
        s.commit()
    return eng, scope


def _build(week_db, runs=None):
    eng, scope = week_db
    m = _load_script("weekly_report")
    with scope() as s:
        return m.build(s, NOW, runs, check_site=False)


def test_the_report_opens_with_the_five_summary_lines(week):
    md, meta = _build(week)
    head = md.split("## A. Systems")[0]
    for n in (
        "1. **Status:",
        "2. **Research:**",
        "3. **Problems:**",
        "4. **Credits:**",
        "5. **Needed from Tate:**",
    ):
        assert n in head, n
    assert meta["week"] == 8 and meta["title"].startswith("Week 8 report")


def test_an_ungraded_pick_is_pending_and_the_status_is_not_healthy(week):
    md, meta = _build(week)
    assert "H-ARM-FGU pick 21 (game 3) not graded yet" in md
    assert meta["pending"] == 1
    assert meta["status"] != "HEALTHY"


def test_the_arm_table_counts_the_week(week):
    md, _ = _build(week)
    row = next(line for line in md.splitlines() if line.startswith("| H-ARM-1HU |"))
    assert "| 1 | 1-0-0 | 1 |" in row and "-3.1%" in row
    fgu = next(line for line in md.splitlines() if line.startswith("| H-ARM-FGU |"))
    assert "| 2 | 0-1-0 | 0; excluded 1 (far_lines 1) |" in fgu


def test_credits_and_research_capture_are_reported_from_the_ledger(week):
    md, meta = _build(week)
    assert "**322 credits used this week**" in md
    assert "8,800 (44% of the 20,000 plan)" in md
    assert "sharp_eu 1 rows" in md
    assert "CFBD" in md and "250 calls this week" in md


def test_without_the_runs_list_the_systems_line_says_not_checked(week):
    md, _ = _build(week, runs=None)
    assert "Workflow runs: NOT CHECKED" in md


def test_a_failed_run_with_no_later_success_is_urgent(week):
    runs = [
        {
            "databaseId": 7,
            "workflowName": "Bet card (cloud)",
            "conclusion": "failure",
            "createdAt": "2026-10-23T20:00:00Z",
        }
    ]
    md, meta = _build(week, runs=runs)
    assert meta["status"] == "BROKEN"
    assert "Bet card (cloud) run 7 failed" in md and "(no later success)" in md


def test_every_source_is_listed(week):
    md, _ = _build(week)
    sources = md.split("## Sources")[1]
    refs = {int(x) for x in __import__("re").findall(r"\(Q(\d+)", md.split("## Sources")[0])}
    for q in refs:
        assert f"- Q{q}:" in sources, q


def test_the_workflow_commits_opens_an_issue_and_checks_itself():
    import yaml
    from conftest import _ROOT as ROOT

    wf = yaml.safe_load((ROOT / ".github/workflows/weekly_report.yml").read_text())
    assert wf["permissions"] == {"contents": "write", "issues": "write", "actions": "read"}
    steps = wf["jobs"]["report"]["steps"]
    names = [s.get("name", "") for s in steps]
    commit = steps[names.index("Commit the page")]
    issue = steps[names.index("Open (or comment on) this week's issue")]
    for s in (commit, issue):
        assert "steps.clock.outputs.dry != 'true'" in s["if"]
    assert "git pull --rebase origin main" in commit["run"]
    assert "gh issue comment" in issue["run"] and "gh issue create" in issue["run"]
    health = steps[-1]
    assert health["if"] == "always()" and "--job weekly" in health["run"]


def test_the_weekly_contract_fails_on_a_missed_step(tmp_path):
    from beatvegas import health

    page = tmp_path / "2026-w08.md"
    page.write_text("x")
    st = {"path": str(page), "status": "HEALTHY", "week": 8}
    ok = health.Ctx(
        session=None,
        now=NOW,
        job="weekly",
        run_started_at=NOW,
        status_files={"weekly": st},
        outcomes={"report": "success", "commit": "success", "issue": "success"},
    )
    assert health.evaluate(health.CONTRACTS["weekly"], ok)[0] == "ok"
    bad = health.Ctx(
        session=None,
        now=NOW,
        job="weekly",
        run_started_at=NOW,
        status_files={"weekly": st},
        outcomes={"report": "success", "commit": "success", "issue": "failure"},
    )
    assert health.evaluate(health.CONTRACTS["weekly"], bad)[0] == "failed"


def test_ci_runs_and_superseded_failures_are_not_problems(week):
    runs = [
        {
            "databaseId": 1,
            "workflowName": "CI",
            "conclusion": "failure",
            "createdAt": "2026-10-23T20:00:00Z",
        },
        {
            "databaseId": 2,
            "workflowName": "Daily grading",
            "conclusion": "failure",
            "createdAt": "2026-10-23T10:00:00Z",
        },
        {
            "databaseId": 3,
            "workflowName": "Daily grading",
            "conclusion": "success",
            "createdAt": "2026-10-23T11:00:00Z",
        },
    ]
    md, meta = _build(week, runs=runs)
    assert meta["urgent"] == 0 and meta["wait"] == 0
    assert "Resolved this week" in md and "Daily grading run 2 failed" in md
    assert "| CI |" not in md and "1 of them pull-request checks" in md


def test_the_balance_fall_is_shown_beside_the_ledger(week):
    eng, _ = week
    with Session(eng) as s:
        s.add(
            AppSettingLog(
                key="odds_credits_remaining",
                value="9200",
                written_at=NOW - timedelta(days=7, hours=1),
            )
        )
        s.add(
            AppSettingLog(
                key="odds_credits_remaining", value="8800", written_at=NOW - timedelta(hours=9)
            )
        )
        s.commit()
    md, _ = _build(week)
    assert "fell 400 (9,200 -> 8,800); the ledger explains 322, leaving 78 spent outside it" in md


def test_the_balance_comparison_starts_at_the_ledgers_first_row(week):
    # A purchase before the ledger existed (the 2026-10-15 history study) is not "outside the ledger".
    eng, _ = week
    with Session(eng) as s:
        for v, at in (
            ("19000", NOW - timedelta(days=6)),
            ("9150", NOW - timedelta(days=4, hours=1)),
        ):
            s.add(AppSettingLog(key="odds_credits_remaining", value=v, written_at=at))
        s.add(
            AppSettingLog(
                key="odds_credits_remaining", value="8800", written_at=NOW - timedelta(hours=9)
            )
        )
        s.commit()
    md, _ = _build(week)
    assert "fell 350 (9,150 -> 8,800); the ledger explains 322, leaving 28 spent outside it" in md
    assert "(the balance fell 350)" in md.split("## A. Systems")[0]
