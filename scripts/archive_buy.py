#!/usr/bin/env python
"""The archive queue: expiring Odds API credits become permanent datasets
(final-2026 plan, sections C11-C12; Tate's decisions C-D5, C-D9, C-D13).

    python scripts/archive_buy.py status                 # the queue, spent vs cap
    python scripts/archive_buy.py probe --game-id 401858250 [--live] [--max-credits 40]
    python scripts/archive_buy.py auto [--dry-run]       # the end-of-cycle runner (items land in PR-C10)

Credits do not roll over, so in the last four days of each billing cycle the
runner walks ARCHIVE_QUEUE in Tate's order and spends what the budget controller
allows (`beatvegas/credit_plan.py`: balance - floor - the recurring need left in
the cycle) on historical captures that go to `research_snapshots`, never to
`odds_snapshots`. Every call is logged in `odds_spend` by the client itself
(job `archive`); each item's `spent` is read back from that ledger, so a rerun
never pays twice for the same item beyond its cap.

This PR (C6) ships the framework and the PROBE: before the Hard Rock ladder item
is sized, one historical event-odds call asks whether the archive carries
`alternate_totals_h1`, `team_totals` and `team_totals_h1` for a Hard Rock
game of week 5 (10 credits per market RETURNED, 0 when empty), plus the 1-credit
historical events list that finds the event id; `--live` adds one live call for
the next Hard Rock game (<= 3 credits) to see which books post those markets
today. The probe writes nothing to the database beyond the ledger; its finding
goes to reports/ and HISTORY. Hard caps: `--max-credits` (default 40) and the
controller's allowance, checked before every paid call.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional

from beatvegas import credit_plan as cp
from beatvegas import ops
from beatvegas.db.models import AppSetting, Game, OddsSnapshot, OddsSpend
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import match_event
from beatvegas.hardrock import HR_BOOK_KEY
from beatvegas.sources.odds import OddsAPIClient

ROOT = Path(__file__).resolve().parent.parent

PROBE_MARKETS = "alternate_totals_h1,team_totals,team_totals_h1"
PROBE_LIVE_BOOKS = ["hardrockbet", "draftkings", "fanduel", "betmgm"]
PROBE_LEAD_MIN = 30  # the archive wave: kickoff minus 30 minutes, like the close backfills
DEFAULT_PROBE_GAME = (
    401858250  # Notre Dame @ North Carolina, 2026-10-03 16:00Z (week 5, 11 HR rows)
)


class ArchiveItem(NamedTuple):
    name: str
    purpose: str  # research_snapshots.purpose / odds_spend.purpose
    cap: int  # credits, Tate's cap (plan C12)
    run: Optional[Callable[..., int]]  # None until PR-C10 builds it


# Tate's order when credits run short (C-D9, extended C-D17): the first item is
# bought first; an item's cap is the most it may ever spend across every run.
ARCHIVE_QUEUE: List[ArchiveItem] = [
    ArchiveItem("pinnacle_2026_closes", "archive_pinnacle_2026", 1500, None),
    ArchiveItem("hr_ladder_close_2026", "archive_hr_ladder", 3900, None),
    ArchiveItem("fg_paths_2026", "archive_fg_paths", 3000, None),
    ArchiveItem("hr_release_2026", "archive_hr_release", 6000, None),
    ArchiveItem("pinnacle_2025_closes", "archive_pinnacle_2025", 2100, None),
    ArchiveItem("hr_ladder_close_2025", "archive_hr_ladder_2025", 4500, None),
    ArchiveItem("fg_paths_2026_us2", "archive_fg_paths_us2", 2500, None),
    ArchiveItem("pinnacle_2024_closes", "archive_pinnacle_2024", 2600, None),
]


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def spent(session, purpose: str) -> int:
    """Credits the ledger says this purpose has spent, across every run."""
    total = 0
    for (c,) in session.query(OddsSpend.credits).filter(OddsSpend.purpose == purpose).all():
        total += int(c or 0)
    return total


def allowance_now(session, now: datetime) -> Dict[str, Any]:
    """The controller's view: balance, floor, recurring, allowance, window."""
    st = cp.load_settings(session)
    bal_raw, _note = ops.read_gauge(session, ops.ODDS_CREDITS_REMAINING)
    balance = int(bal_raw) if bal_raw not in (None, "") else None
    measured = cp.measured_recurring(session, now)
    per_week = measured if measured is not None else st.recurring_fallback
    cov_row = session.get(AppSetting, ops.CLOSE_COVERAGE_PCT)
    closes_in = cp.saturday_closes_in(cov_row.note if cov_row is not None else None, now)
    allow = None if balance is None else cp.allowance(balance, now, st.reset_at, st.floor, per_week)
    return {
        "balance": balance,
        "floor": st.floor,
        "reset_at": st.reset_at.isoformat() if st.reset_at else None,
        "recurring_per_week": per_week,
        "recurring_source": "measured" if measured is not None else "fallback setting",
        "allowance": allow,
        "window_open": cp.archive_window_open(now, st.reset_at, st.archive_window_days, closes_in),
    }


class Budget:
    """The probe's own hard cap, counted from the provider's `x-requests-last`."""

    def __init__(self, cap: int, allowance: Optional[int]):
        self.cap = cap
        self.allowance = allowance
        self.spent = 0

    def check(self, estimate: int, what: str) -> None:
        if self.spent + estimate > self.cap:
            raise SystemExit(
                f"[archive] refusing {what}: {self.spent} spent + {estimate} estimated > cap {self.cap}"
            )
        if self.allowance is not None and self.allowance - self.spent < estimate:
            raise SystemExit(
                f"[archive] refusing {what}: controller allowance {self.allowance} - {self.spent} "
                f"spent < {estimate} estimated"
            )

    def note(self, client: OddsAPIClient) -> int:
        c = client.last_credits
        cost = int(c.last_cost) if c is not None and c.last_cost is not None else 0
        self.spent += cost
        return cost


def _market_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Which markets the answer carried, per book, with outcome counts and samples."""
    out: Dict[str, Any] = {}
    for bk in payload.get("bookmakers") or []:
        book = bk.get("key")
        for mk in bk.get("markets") or []:
            key = mk.get("key")
            outcomes = mk.get("outcomes") or []
            entry = out.setdefault(key, {"books": [], "outcomes": {}, "sample": {}})
            if book not in entry["books"]:
                entry["books"].append(book)
            entry["outcomes"][book] = len(outcomes)
            entry["sample"][book] = [
                {
                    k: o.get(k)
                    for k in ("name", "description", "point", "price")
                    if o.get(k) is not None
                }
                for o in outcomes[:8]
            ]
    return out


def cmd_probe(args, client: Optional[OddsAPIClient] = None) -> int:
    now = datetime.utcnow()
    client = client or OddsAPIClient(job="archive", purpose="probe")
    with session_scope() as s:
        g = s.get(Game, int(args.game_id))
        if g is None or g.start_date is None:
            print(f"[archive] game {args.game_id} not found or has no kickoff")
            return 1
        ctl = allowance_now(s, now)
        game = {
            "id": int(g.id),
            "home_team": g.home_team,
            "away_team": g.away_team,
            "start_date": g.start_date,
        }
        live_event = None
        if args.live:
            live_event = args.live_event_id or _next_hr_event(s, now)
    budget = Budget(int(args.max_credits), ctl["allowance"])
    report: Dict[str, Any] = {
        "probe": "alternate_totals_h1 / team_totals / team_totals_h1 in the archive and live",
        "at": _iso_z(now),
        "controller": ctl,
        "game": {**game, "start_date": _iso_z(game["start_date"])},
        "historical": {},
        "live": {},
        "credits": {},
    }

    # (1) the historical events list as of kickoff - 30 min: 1 credit.
    wave = game["start_date"] - timedelta(minutes=PROBE_LEAD_MIN)
    budget.check(1, "historical events list")
    events = client.list_historical_events(_iso_z(wave))
    report["credits"]["hist_events"] = budget.note(client)
    event_id = None
    best = -1.0
    for ev in events:
        gid, score = match_event(
            ev.get("home_team"), ev.get("away_team"), ev.get("commence_time"), [game]
        )
        if gid == game["id"] and score > best:
            event_id, best = ev.get("id"), score
    report["historical"]["events_listed"] = len(events)
    report["historical"]["event_id"] = event_id
    if event_id is None:
        report["historical"]["finding"] = "the game was not in the archive's event list"
    else:
        # (2) the event's odds for the three markets, Hard Rock only: 10 per market
        # RETURNED (<= 30), 0 for an empty answer.
        budget.check(30, "historical event odds")
        payload = client.historical_event_odds(event_id, _iso_z(wave), PROBE_MARKETS, [HR_BOOK_KEY])
        report["credits"]["hist_event_odds"] = budget.note(client)
        summary = _market_summary(payload or {})
        report["historical"]["markets"] = summary
        report["historical"]["finding"] = (
            "the archive carries: " + ", ".join(sorted(summary)) if summary else "nothing returned"
        )
    # (3) optional live check: the next Hard Rock game, four books, <= 3 credits.
    if args.live:
        if not live_event:
            report["live"]["finding"] = "no upcoming Hard Rock event id on file"
        else:
            budget.check(3, "live event odds")
            payload = client.event_odds_raw(live_event, PROBE_MARKETS, PROBE_LIVE_BOOKS)
            report["credits"]["live_event_odds"] = budget.note(client)
            summary = _market_summary(payload or {})
            report["live"] = {
                "event_id": live_event,
                "markets": summary,
                "finding": "posted today by: "
                + "; ".join(f"{m}: {', '.join(v['books'])}" for m, v in sorted(summary.items()))
                if summary
                else "none of the three markets is posted by the four books",
            }
    report["credits"]["total"] = budget.spent
    _write_report(args.out, "archive_probe", report)
    print(json.dumps(report, indent=1, default=str))
    return 0


def _next_hr_event(session, now: datetime) -> Optional[str]:
    row = (
        session.query(OddsSnapshot.event_id)
        .join(Game, Game.id == OddsSnapshot.game_id)
        .filter(
            OddsSnapshot.book == HR_BOOK_KEY,
            OddsSnapshot.event_id.isnot(None),
            Game.start_date > now,
        )
        .order_by(Game.start_date.asc())
        .first()
    )
    return row[0] if row else None


def cmd_status(args) -> int:
    now = datetime.utcnow()
    with session_scope() as s:
        ctl = allowance_now(s, now)
        rows = [
            (it.name, it.purpose, it.cap, spent(s, it.purpose), it.run is not None)
            for it in ARCHIVE_QUEUE
        ]
    lines = [
        f"# Archive queue ({_iso_z(now)})",
        "",
        f"balance {ctl['balance']}, floor {ctl['floor']}, reset {ctl['reset_at'] or 'UNSET'}, "
        f"recurring {ctl['recurring_per_week']}/wk ({ctl['recurring_source']}), "
        f"allowance {ctl['allowance']}, window {'OPEN' if ctl['window_open'] else 'closed'}",
        "",
        "| # | item | purpose | spent | cap | built |",
        "|---|---|---|---|---|---|",
    ]
    for i, (name, purpose, cap, sp, built) in enumerate(rows, 1):
        lines.append(
            f"| {i} | {name} | {purpose} | {sp} | {cap} | {'yes' if built else 'PR-C10'} |"
        )
    md = "\n".join(lines)
    print(md)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a") as fh:
            fh.write(md + "\n")
    return 0


def cmd_auto(args) -> int:
    """The end-of-cycle runner. Walks the queue in order inside the archive window
    and spends what the controller allows on each unfinished, built item. Until
    PR-C10 lands the items, it only reports what it would do."""
    now = datetime.utcnow()
    with session_scope() as s:
        ctl = allowance_now(s, now)
        plan = []
        for it in ARCHIVE_QUEUE:
            sp = spent(s, it.purpose)
            plan.append((it, sp))
    if ctl["reset_at"] is None:
        print(
            "[archive] reset date unset: nothing runs (python scripts/credit_plan.py set-reset <ISO>)"
        )
        return 0
    if not ctl["window_open"]:
        print(f"[archive] window closed (reset {ctl['reset_at']}); nothing runs")
        return 0
    room = ctl["allowance"] or 0
    for it, sp in plan:
        left = it.cap - sp
        if left <= 0 or room <= 0:
            continue
        chunk = min(left, room)
        if it.run is None:
            print(f"[archive] {it.name}: would spend up to {chunk} (not built yet, PR-C10)")
            continue
        if args.dry_run:
            print(f"[archive] {it.name}: DRY RUN, would spend up to {chunk}")
            continue
        used = it.run(max_credits=chunk)
        room -= used
    return 0


def _write_report(outdir: str, stem: str, report: Dict[str, Any]) -> Path:
    out = ROOT / outdir
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out / f"{stem}_{stamp}.json"
    path.write_text(json.dumps(report, indent=1, default=str))
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("probe")
    p.add_argument("--game-id", type=int, default=DEFAULT_PROBE_GAME)
    p.add_argument(
        "--live", action="store_true", help="also ask the next Hard Rock game live (<= 3 credits)"
    )
    p.add_argument("--live-event-id", default=None)
    p.add_argument("--max-credits", type=int, default=40)
    a = sub.add_parser("auto")
    a.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not try_init_db():
        print("[archive] DB unreachable", file=sys.stderr)
        return 1
    return {"status": cmd_status, "probe": cmd_probe, "auto": cmd_auto}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
