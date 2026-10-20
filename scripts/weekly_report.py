#!/usr/bin/env python
"""The Sunday report (final-2026 plan D3/D4 build 3; Tate's calls 2026-10-20).

    python scripts/weekly_report.py --runs "$RUNNER_TEMP/runs.json" --out docs/reads \
        --status-file "$RUNNER_TEMP/weekly_status.json"
    python scripts/weekly_report.py --no-site --out /tmp/reads      # local, no network

One page a week, generated from the database and the GitHub runs list -- no
Claude, no paid API, no Odds or CFBD call. It opens with five lines Tate can read
in a minute (status, what we learned, problems, credits, anything needed from
him), then the detail: A systems, B research, C data and credits, D the site,
E problems and what can wait, F next week. Every table names its source in the
Sources list at the bottom, with its row count. Every statement is one of:

  VERIFIED     read from a table, a gauge or the runs list just now
  PENDING      not yet knowable (a pick not graded, a pick the judge has not read);
               it is listed by id and carried into next week's report
  NOT CHECKED  the source was unavailable to this run (said, never guessed)

The arms' official positions are the Monday read's rows (`arm_positions`); the
report also shows each arm's position as it would stand if this week enters
unchanged at Monday's read (protocol p1.2 R2), marked PROVISIONAL. Nothing here
writes to the database; the workflow commits the page as docs/reads/<season>-wNN.md
and opens a GitHub issue with the same text (GitHub emails the repo's owner).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from beatvegas import credit_plan as cp  # noqa: E402
from beatvegas import health, ops  # noqa: E402
from beatvegas import protocol as P  # noqa: E402
from beatvegas.db.models import (  # noqa: E402
    AppSetting,
    AppSettingLog,
    ArmPosition,
    ChallengerPick,
    Game,
    OddsSpend,
    ResearchSnapshot,
)
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402

SITE = "https://beat-vegas.vercel.app"
SITE_PATHS = ("/", "/research", "/results", "/records")
PLAN_CREDITS = 20_000  # The Odds API plan: 20,000 credits a cycle, no rollover

# Account dates the report reminds Tate of when they fall within the next 14 days
# (docs/OPS_ACCOUNTS.md, the dated runbook). Tate clicks every one of them.
OPS_DATES: Tuple[Tuple[str, str], ...] = (
    (
        "2026-11-05",
        "The Odds API credits reset (confirm the date on the dashboard; the controller holds it as odds_cycle_reset_at)",
    ),
    (
        "2026-11-05",
        "CFBD drops to the free tier (1,000 calls a month); no hand season reload after this",
    ),
    ("2026-11-28", "Last Saturday of paid capture (week 13)"),
    ("2026-11-30", "The final read (protocol p1.3) and the season export"),
    ("2026-12-04", "Cancel The Odds API before the ~Dec 5 renewal (after the archive window)"),
)

SCHEDULE = (
    ("Tue", "card build tue_pm (3:45-5:15pm ET)"),
    ("Thu", "card build thu_pm (3:45-5:15pm ET)"),
    ("Fri", "card build fri_pm (3:45-5:15pm ET)"),
    ("Sat", "card build sat_am (7:45-9:15am ET); hourly close polls 10am-midnight ET"),
    ("Sun", "grading 6am ET; this report 11am ET; Sunday refit and opener capture 2-4pm ET"),
    ("Mon", "the official Monday read 8am ET (arm positions)"),
)

STATUS_HEALTHY, STATUS_ATTENTION, STATUS_BROKEN = "HEALTHY", "ATTENTION", "BROKEN"


class Report:
    """The week being reported and what the sections collect as they run."""

    def __init__(
        self, now: datetime, season: int, week: Optional[int], saturday: datetime, since: datetime
    ):
        self.now, self.season, self.week, self.saturday, self.since = (
            now,
            season,
            week,
            saturday,
            since,
        )
        self.sources: List[str] = []
        self.problems_urgent: List[str] = []
        self.problems_wait: List[str] = []
        self.pending: List[str] = []

    def src(self, text: str) -> str:
        self.sources.append(text)
        return f"Q{len(self.sources)}"


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
def load_runs(path: Optional[str]) -> Optional[List[dict]]:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    runs = data.get("runs") if isinstance(data, dict) else data
    return runs if isinstance(runs, list) else None


def report_week(session, saturday: datetime, season: int) -> Optional[int]:
    """The CFBD week of the games kicking off on `saturday` (ET) or the next UTC
    day (late kickoffs), the most common one."""
    lo, hi = saturday + timedelta(hours=4), saturday + timedelta(hours=4 + 24 + 6)
    weeks = Counter(
        w
        for (w,) in session.query(Game.week)
        .filter(Game.season == season, Game.start_date >= lo, Game.start_date < hi)
        .all()
    )
    return weeks.most_common(1)[0][0] if weeks else None


def _gauge(session, key: str) -> Tuple[Optional[str], Optional[str], Optional[datetime]]:
    row = session.get(AppSetting, key)
    return (None, None, None) if row is None else (row.value, row.note, row.updated_at)


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x * 100:+.1f}%"


def _et(d: Optional[datetime]) -> str:
    if d is None:
        return "—"
    # Display edge only: naive UTC -> ET (EDT until 2026-11-01 06:00 UTC, then EST).
    off = 4 if d < datetime(2026, 11, 1, 6) else 5
    return (d - timedelta(hours=off)).strftime("%a %b %-d %-I:%M %p ET")


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
def systems(
    r: Report, session, runs: Optional[List[dict]]
) -> Tuple[List[str], Optional[str], List[str]]:
    """(markdown, digest verdict, digest misses)."""
    out = ["## A. Systems", ""]
    if runs is None:
        out.append("Workflow runs: NOT CHECKED (the runs list was not available to this run).")
    else:
        since = r.since.strftime("%Y-%m-%dT%H:%M:%SZ")
        week_runs = [x for x in runs if (x.get("createdAt") or "") >= since]
        q = r.src(
            f"GitHub runs list (`gh run list --limit 200`), created since {since}: {len(week_runs)} runs"
        )
        by: Dict[str, Counter] = defaultdict(Counter)
        for x in week_runs:
            by[x.get("workflowName") or "?"][x.get("conclusion") or x.get("status") or "?"] += 1
        out += [
            f"Workflow runs this week ({q}, VERIFIED):",
            "",
            "| Workflow | Runs | Success | Failed | Cancelled |",
            "|---|---|---|---|---|",
        ]
        for wf in sorted(by, key=lambda k: -sum(by[k].values())):
            c = by[wf]
            out.append(
                f"| {wf} | {sum(c.values())} | {c['success']} | {c['failure']} | {c['cancelled']} |"
            )
        failed = [x for x in week_runs if x.get("conclusion") == "failure"]
        for x in failed:
            later = any(
                y.get("workflowName") == x.get("workflowName")
                and (y.get("createdAt") or "") > (x.get("createdAt") or "")
                and y.get("conclusion") == "success"
                for y in week_runs
            )
            msg = (
                f"{x.get('workflowName')} run {x.get('databaseId')} failed at {x.get('createdAt')}"
            )
            (r.problems_wait if later else r.problems_urgent).append(
                msg + (" (a later run succeeded)" if later else " (no later success)")
            )
        out.append("")
    # Health verdicts as they stand.
    q = r.src("app_settings last_health_<job> rows (one per scheduled job)")
    out += [
        f"Each job's last health verdict ({q}, VERIFIED):",
        "",
        "| Job | Verdict | Written |",
        "|---|---|---|",
    ]
    for job in ops.HEALTH_JOBS:
        v, _note, at = _gauge(session, ops.health_key(job))
        out.append(f"| {job} | {v or 'never'} | {_et(at)} |")
    out.append("")
    # The digest's checks, evaluated now (beatvegas/health.py `digest`).
    verdict, misses = None, []
    contract = health.CONTRACTS.get("digest")
    if contract is None:
        out.append("The daily digest's checks: NOT CHECKED (no digest contract in this build).")
    else:
        ctx = health.Ctx(
            session=session,
            now=r.now,
            job="digest",
            run_started_at=r.now,
            status_files={"runs": {"runs": runs or []}},
        )
        verdict, results = health.evaluate(contract, ctx)
        q = r.src(
            "the daily digest's nine checks (beatvegas/health.py `digest`), evaluated at report time"
        )
        out += [f"The daily digest's checks right now ({q}, VERIFIED): **{verdict}**", ""]
        for c, res in results:
            out.append(f"- {'ok' if res.ok else 'MISS'} `{c.id}`: {res.detail}")
            if not res.ok:
                misses.append(f"{c.id}: {res.detail}")
        out.append("")
    r.problems_urgent.extend(misses)
    return out, verdict, misses


def _arm_week_rows(session, arm: str, spec: Dict[str, Any], season: int, week: int) -> List[Any]:
    from protocol_position import arm_rows  # scripts/protocol_position.py

    return [x for x in arm_rows(session, arm, spec) if x.season == season and x.week == week]


def _wlp(rows: Sequence[Any]) -> str:
    w = sum(1 for x in rows if x.graded and (x.units or 0) > 0)
    lo = sum(1 for x in rows if x.graded and (x.units or 0) < 0)
    p = sum(1 for x in rows if x.graded and x.units == 0)
    return f"{w}-{lo}-{p}"


def research(r: Report, session) -> Tuple[List[str], str]:
    """(markdown, the one-sentence summary for the top)."""
    from protocol_position import arm_rows, read_arm, with_games

    out = ["## B. Research", ""]
    if r.week is None:
        out.append("No regular-season games found for the last Saturday: NOT CHECKED.")
        return out, "No games this week."
    monday = (r.now + timedelta(days=(7 - r.now.weekday()) % 7 or 7)).replace(
        hour=12, minute=1, second=0, microsecond=0
    )
    newest = {}
    for row in session.query(ArmPosition).order_by(ArmPosition.read_date.asc()).all():
        newest[row.hypothesis] = row
    q_week = r.src(
        f"paper picks of the registered arms in season {r.season} week {r.week} (manual_picks arm H-ARM-1HU, challenger_picks the other five), each arm's market/side/start filter as protocol_position.arm_rows"
    )
    q_off = r.src("arm_positions, newest row per hypothesis (the official Monday read)")
    q_prov = r.src(
        f"protocol_position.read_arm over each arm's picks as of {monday:%Y-%m-%d %H:%M} UTC (the coming Monday read, PROVISIONAL)"
    )
    out += [
        f"Week {r.week} by arm ({q_week}; positions {q_off} and {q_prov}). EV is per unit at the logged Hard Rock price against the consensus close; the stop line is LLR {P.LOWER:.3f}, promotion {P.UPPER:.3f}; no decision before 30 readings over 3 weeks.",
        "",
        "| Arm | Logged | Graded W-L-P | Judge read | Mean EV this week | Official (Monday) | Provisional (if this week enters) |",
        "|---|---|---|---|---|---|---|",
    ]
    learned: List[str] = []
    below_stop = 0
    any_positive = False
    for arm, spec in P.ARMS.items():
        rows = _arm_week_rows(session, arm, spec, r.season, r.week)
        read = [x for x in rows if x.ev_cons is not None]
        ev = sum(float(x.ev_cons) for x in read) / len(read) if read else None
        any_positive = any_positive or (ev is not None and ev > 0)
        for x in rows:
            if not x.graded:
                r.pending.append(f"{arm} pick {x.id} (game {x.game_id}) not graded yet")
            elif x.ev_cons is None and not x.cons_excluded:
                r.pending.append(f"{arm} pick {x.id} (game {x.game_id}) not read by the judge yet")
        excl = Counter(x.cons_excluded for x in rows if x.cons_excluded)
        off = newest.get(arm)
        off_txt = (
            "—"
            if off is None
            else f"{off.read_date}: {off.readings} readings, LLR {off.llr if off.llr is not None else '—'}, {off.state}"
        )
        prov = read_arm(with_games(session, arm_rows(session, arm, spec)), False, monday)
        prov_txt = f"{prov['readings']} readings / {len(prov['completed_weeks'])} wk, LLR {prov['llr']}, mean {_pct(prov['mean_ev'])} ({_pct(prov['ev_lo'])} to {_pct(prov['ev_hi'])})"
        if prov["llr"] <= P.LOWER:
            below_stop += 1
        ex_txt = (
            f"; excluded {sum(excl.values())} ({', '.join(f'{k} {v}' for k, v in excl.items())})"
            if excl
            else ""
        )
        out.append(
            f"| {arm} | {len(rows)} | {_wlp(rows)} | {len(read)}{ex_txt} | {_pct(ev)} | {off_txt} | {prov_txt} |"
        )
        if prov["state"] not in ("running", None):
            learned.append(f"{arm} reached a protocol decision: {prov['label']}.")
    out.append("")
    # Pricing study and the exploratory collector.
    pr = newest.get("H-PRICE-HR")
    if pr is not None:
        q = r.src("arm_positions newest H-PRICE-HR row (pricing study, rule pv1)")
        out.append(
            f"Hard Rock pricing study ({q}, VERIFIED): {pr.readings} forward readings of the {pr.needed} it needs, mean {_pct(pr.mean_ev)}; state {pr.state}."
        )
    evp_n = (
        session.query(ChallengerPick)
        .filter(
            ChallengerPick.arm == "H-ARM-EVP",
            ChallengerPick.season == r.season,
            ChallengerPick.week == r.week,
        )
        .count()
    )
    q = r.src(f"challenger_picks arm H-ARM-EVP, week {r.week}: {evp_n} rows")
    out += [
        f"Exploratory EV collector ({q}, VERIFIED): {evp_n} picks this week (it logs only at +2% or more at Hard Rock's price).",
        "",
    ]
    n_arms = len(P.ARMS)
    if not learned:
        learned.append(
            f"{below_stop} of {n_arms} arms sit at or below the stop line if this week enters; "
            + (
                "one or more arms read positive this week; "
                if any_positive
                else "no arm read positive this week; "
            )
            + "no arm can be decided before 30 readings over 3 weeks."
        )
    out += (
        ["What the numbers say (rule-based, from the table above):", ""]
        + [f"- {x}" for x in learned]
        + [""]
    )
    return out, learned[0]


def data_and_credits(r: Report, session) -> Tuple[List[str], str]:
    out = ["## C. Data collection and credits", ""]
    bal, _n, bal_at = _gauge(session, ops.ODDS_CREDITS_REMAINING)
    spend = (
        session.query(OddsSpend.job, OddsSpend.purpose, OddsSpend.credits)
        .filter(OddsSpend.spent_at >= r.since)
        .all()
    )
    by_job: Counter = Counter()
    for job, purpose, credits in spend:
        by_job[f"{job or '?'}{' / ' + purpose if purpose else ''}"] += int(credits or 0)
    used = sum(by_job.values())
    q = r.src(f"odds_spend rows since {r.since:%Y-%m-%d %H:%M} UTC: {len(spend)} calls")
    st = cp.load_settings(session)
    measured = cp.measured_recurring(session, r.now)
    per_week = measured if measured is not None else st.recurring_fallback
    allow = cp.allowance(int(bal), r.now, st.reset_at, st.floor, per_week) if bal else None
    q2 = r.src(
        "app_settings odds_credits_remaining, odds_cycle_reset_at, odds_credit_floor; credit_plan.allowance"
    )
    left_pct = f"{int(bal) / PLAN_CREDITS:.0%}" if bal else "—"
    out += [
        f"Odds API ({q}, {q2}, VERIFIED): **{used:,} credits used this week**; balance {int(bal):,} ({left_pct} of the 20,000 plan) as of {_et(bal_at)}; "
        f"reset {st.reset_at.date() if st.reset_at else 'UNSET'}; headroom above the {st.floor:,} floor after the recurring need: {allow if allow is not None else '—'}.",
        "",
    ]
    if by_job:
        out += (
            ["| Spent by (job / purpose) | Credits |", "|---|---|"]
            + [f"| {k} | {v:,} |" for k, v in by_job.most_common()]
            + [""]
        )
    # CFBD calls this week from the gauge history.
    rows = (
        session.query(AppSettingLog.value)
        .filter(AppSettingLog.key == ops.CFBD_CALLS_REMAINING, AppSettingLog.written_at >= r.since)
        .order_by(AppSettingLog.written_at.asc())
        .all()
    )
    vals = [int(v) for (v,) in rows if str(v).isdigit()]
    q = r.src(
        f"app_settings_log cfbd_calls_remaining since {r.since:%Y-%m-%d}: {len(vals)} readings"
    )
    cfbd_used = (vals[0] - vals[-1]) if len(vals) >= 2 and vals[0] >= vals[-1] else None
    out += [
        f"CFBD ({q}, VERIFIED): {cfbd_used if cfbd_used is not None else '—'} calls this week; {vals[-1] if vals else '—'} left.",
        "",
    ]
    # Research capture this week.
    rs = Counter(
        p
        for (p,) in session.query(ResearchSnapshot.purpose)
        .filter(ResearchSnapshot.captured_at >= r.since)
        .all()
    )
    q = r.src(f"research_snapshots rows captured since {r.since:%Y-%m-%d}, by purpose")
    out.append(
        f"Research capture ({q}, VERIFIED): "
        + (", ".join(f"{k} {v:,} rows" for k, v in rs.most_common()) or "none this week")
        + "."
    )
    out.append("")
    summary = (
        f"{used:,} credits this week; {int(bal):,} left ({left_pct} of the plan)"
        if bal
        else f"{used:,} credits this week"
    )
    return out, summary


def site(r: Report, check: bool) -> Tuple[List[str], bool]:
    out = ["## D. Website", ""]
    if not check:
        out += ["Pages: NOT CHECKED (run with the site check off).", ""]
        return out, True
    ok = True
    rows = []
    for path in SITE_PATHS:
        try:
            with urllib.request.urlopen(SITE + path, timeout=20) as resp:
                rows.append((path, resp.status))
                ok = ok and resp.status == 200
        except Exception as e:  # noqa: BLE001 - a page that will not load is the finding
            rows.append((path, f"error {type(e).__name__}"))
            ok = False
    warn: List[str] = []
    try:
        with urllib.request.urlopen(SITE + "/api/health", timeout=20) as resp:
            body = json.loads(resp.read().decode())
        warn = list(body.get("warnings") or [])
        health_ok = bool(body.get("ok"))
    except Exception as e:  # noqa: BLE001
        health_ok = False
        warn = [f"/api/health unreadable: {type(e).__name__}"]
    q = r.src(f"GET {SITE} pages {', '.join(SITE_PATHS)} and /api/health at report time")
    out += [
        f"Pages ({q}, VERIFIED): "
        + ", ".join(f"{p} {s}" for p, s in rows)
        + f"; /api/health ok={health_ok}.",
        "",
    ]
    if warn:
        out += ["Warnings the site shows its readers:", ""] + [f"- {w}" for w in warn] + [""]
    if not ok or not health_ok:
        r.problems_urgent.append(
            "the site: " + ", ".join(f"{p} {s}" for p, s in rows if s != 200)
            or "the site's health endpoint"
        )
    for w in warn:
        r.problems_wait.append(f"site warning: {w}")
    return out, ok and health_ok


def next_week(r: Report) -> List[str]:
    out = ["## F. Next week", ""]
    out += ["Scheduled (all automatic):", ""] + [f"- {d}: {t}" for d, t in SCHEDULE] + [""]
    soon = [
        (d, t)
        for d, t in OPS_DATES
        if r.now.date().isoformat() <= d <= (r.now + timedelta(days=14)).date().isoformat()
    ]
    if soon:
        out += ["Dates in the next 14 days:", ""] + [f"- {d}: {t}" for d, t in soon] + [""]
    left = (datetime.fromisoformat(P.SEASON_LAST_KICKOFF) - r.now).days
    out.append(
        f"Paid capture ends after Sat 2026-11-28 ({max(left, 0)} days from now); the final read is Mon 2026-11-30."
    )
    out.append("")
    return out


def needs_from_tate(r: Report) -> List[str]:
    out = []
    for d, t in OPS_DATES:
        if r.now.date().isoformat() <= d <= (r.now + timedelta(days=7)).date().isoformat():
            out.append(f"{d}: {t}")
    return out


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #
def build(
    session, now: datetime, runs: Optional[List[dict]], check_site: bool
) -> Tuple[str, Dict[str, Any]]:
    saturday = health._last_saturday_et(now)
    season = saturday.year
    # The report's week runs from the previous report (Sunday 15:00 UTC) to now.
    since = now - timedelta(days=7)
    r = Report(
        now=now,
        season=season,
        week=report_week(session, saturday, season),
        saturday=saturday,
        since=since,
    )
    sys_md, digest_verdict, _misses = systems(r, session, runs)
    res_md, learned = research(r, session)
    data_md, costs = data_and_credits(r, session)
    site_md, site_ok = site(r, check_site)
    nxt_md = next_week(r)
    needs = needs_from_tate(r)

    if r.problems_urgent:
        status = STATUS_BROKEN
    elif r.problems_wait or r.pending or digest_verdict not in ("ok", None):
        status = STATUS_ATTENTION
    else:
        status = STATUS_HEALTHY
    wk = f"week {r.week}" if r.week is not None else "no games"
    title = f"Week {r.week if r.week is not None else '?'} report — {status}"
    problems_line = (
        f"{len(r.problems_urgent)} urgent, {len(r.problems_wait)} that can wait, {len(r.pending)} pending"
        + (
            f" — first: {(r.problems_urgent or r.problems_wait or r.pending)[0]}"
            if (r.problems_urgent or r.problems_wait or r.pending)
            else ""
        )
    )
    head = [
        f"# Beat Vegas — {season} {wk} report ({now:%Y-%m-%d})",
        "",
        f"Generated {_et(now)} from the database and the GitHub runs list by `scripts/weekly_report.py` (no person, no AI). "
        "VERIFIED = read just now; PENDING = not knowable yet, carried to next week; NOT CHECKED = source unavailable.",
        "",
        "## Summary",
        "",
        f"1. **Status: {status}.**"
        + (" Everything checked holds." if status == STATUS_HEALTHY else ""),
        f"2. **Research:** {learned}",
        f"3. **Problems:** {problems_line}.",
        f"4. **Credits:** {costs}.",
        "5. **Needed from Tate:** " + ("; ".join(needs) if needs else "nothing this week."),
        "",
    ]
    prob = ["## E. Problems and what can wait", ""]
    prob += (
        ["Urgent (fix before next weekend):", ""]
        + ([f"- {x}" for x in r.problems_urgent] or ["- none"])
        + [""]
    )
    prob += ["Can wait:", ""] + ([f"- {x}" for x in r.problems_wait] or ["- none"]) + [""]
    prob += (
        ["Pending (carried into next week's report):", ""]
        + ([f"- {x}" for x in r.pending] or ["- none"])
        + [""]
    )
    sources = ["## Sources", ""] + [f"- Q{i}: {s}" for i, s in enumerate(r.sources, 1)] + [""]
    md = "\n".join(head + sys_md + res_md + data_md + site_md + prob + nxt_md + sources)
    meta = {
        "title": title,
        "status": status,
        "season": season,
        "week": r.week,
        "urgent": len(r.problems_urgent),
        "wait": len(r.problems_wait),
        "pending": len(r.pending),
        "site_ok": site_ok,
    }
    return md, meta


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--runs", help="gh run list JSON ({'runs': [...]}); omitted = NOT CHECKED")
    ap.add_argument("--out", default="docs/reads")
    ap.add_argument("--status-file")
    ap.add_argument("--now", help="naive UTC ISO (tests and what-ifs)")
    ap.add_argument("--no-site", action="store_true", help="skip the production page checks")
    args = ap.parse_args(argv)
    if not try_init_db():
        print("[weekly] DB unreachable", file=sys.stderr)
        return 1
    now = datetime.fromisoformat(args.now) if args.now else datetime.utcnow()
    with session_scope() as s:
        md, meta = build(s, now, load_runs(args.runs), not args.no_site)
    out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = (
        f"{meta['season']}-w{meta['week']:02d}.md"
        if meta["week"] is not None
        else f"{now:%Y-%m-%d}.md"
    )
    path = out / name
    path.write_text(md + "\n")
    meta["path"] = str(path.relative_to(ROOT)) if str(path).startswith(str(ROOT)) else str(path)
    if args.status_file:
        Path(args.status_file).write_text(json.dumps(meta))
    print(md)
    print(f"[weekly] wrote {meta['path']} ({meta['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
