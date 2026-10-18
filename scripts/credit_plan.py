#!/usr/bin/env python
"""The Odds API credit budget controller's command line (beatvegas/credit_plan.py).

    python scripts/credit_plan.py report
    python scripts/credit_plan.py allow --purpose midweek_1h --estimate 165
    python scripts/credit_plan.py allow --purpose archive_pinnacle_2026 --estimate 2600
    python scripts/credit_plan.py set-reset 2026-11-05T05:00:00
    python scripts/credit_plan.py set-floor 1500
    python scripts/credit_plan.py set-recurring 450

`allow` is what every optional pull calls before it pays: exit 0 when the
allowance (balance - floor - recurring need to min(reset, season end)) covers the
estimate, exit 1 with a one-line reason when not. An `archive_*` purpose also
needs a set reset date, the last four days of the cycle and last Saturday's
closes captured (`--drain` waives the window for the end-of-season drain after
the last kickoff, plan C-D13). `report` also writes the `odds_projected_end`
gauge. `set-*` write `app_settings` through `ops.record_gauge`, so
`app_settings_log` keeps the history. Read-only toward the Odds API: spends
nothing. Timestamps are naive UTC.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Optional

from beatvegas import credit_plan as cp
from beatvegas import ops, protocol
from beatvegas.db.models import AppSetting
from beatvegas.db.store import session_scope, try_init_db


def _now(arg: Optional[str]) -> datetime:
    return cp.parse_utc(arg) if arg else datetime.utcnow()


def _read_state(now: datetime):
    """(settings, balance, recurring per week, 'measured'|'fallback', closes-in?)."""
    with session_scope() as s:
        st = cp.load_settings(s)
        bal_raw, _ = ops.read_gauge(s, ops.ODDS_CREDITS_REMAINING)
        measured = cp.measured_recurring(s, now)
        cov = s.get(AppSetting, ops.CLOSE_COVERAGE_PCT)
        cov_note = cov.note if cov is not None else None
    try:
        balance = int(float(bal_raw)) if bal_raw is not None else None
    except ValueError:
        balance = None
    per_week = st.recurring_fallback if measured is None else measured
    src = "fallback" if measured is None else "measured"
    return st, balance, per_week, src, cp.saturday_closes_in(cov_note, now)


def cmd_report(args) -> int:
    now = _now(args.now)
    st, balance, per_week, src, closes_in = _read_state(now)
    weeks = cp.remaining_weeks(now, st.reset_at)
    end = cp.cycle_end(st.reset_at, protocol.SEASON_LAST_KICKOFF)
    need = cp.recurring_need(now, st.reset_at, per_week)
    rows = [
        (
            "balance",
            f"{balance:,}" if balance is not None else "unknown (no odds_credits_remaining gauge)",
        ),
        (
            "cycle reset",
            st.reset_at.isoformat() if st.reset_at else "UNSET (counting to the season end)",
        ),
        ("counted to", f"{end.isoformat()} ({weeks:.2f} weeks)"),
        ("floor", f"{st.floor:,}"),
        ("recurring / week", f"{per_week:,} ({src})"),
        ("recurring need", f"{need:,}"),
    ]
    if balance is not None:
        allow_n = cp.allowance(balance, now, st.reset_at, st.floor, per_week)
        rows.append(("allowance", f"{allow_n:,}"))
        rows.append(("projected end balance", f"{balance - need:,}"))
    window = cp.archive_window_open(now, st.reset_at, st.archive_window_days, closes_in)
    rows.append(
        (
            "archive window open",
            f"{'yes' if window else 'no'} (last {st.archive_window_days} days before the reset; "
            f"last Saturday's closes {'in' if closes_in else 'not confirmed'})",
        )
    )
    text = "\n".join(f"{k:<24}{v}" for k, v in rows)
    print(text)
    if st.reset_at is None:
        print("note: odds_cycle_reset_at is unset; archive purposes are refused until `set-reset`.")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("### Odds API credit plan\n\n| | |\n|---|---|\n")
            f.writelines(f"| {k} | {v} |\n" for k, v in rows)
    if balance is not None:
        ok = ops.record_gauge(
            ops.ODDS_PROJECTED_END_BALANCE, balance - need, note=f"recurring={per_week} {src}"
        )
        print(
            f"gauge {ops.ODDS_PROJECTED_END_BALANCE}: {'written' if ok else 'not written (no DATABASE_URL)'}"
        )
    return 0


def cmd_allow(args) -> int:
    now = _now(args.now)
    purpose, est = args.purpose, args.estimate
    st, balance, per_week, src, closes_in = _read_state(now)

    def deny(reason: str) -> int:
        print(f"DENY {purpose} est={est}: {reason}")
        return 1

    if balance is None:
        return deny("balance unknown (no odds_credits_remaining gauge)")
    if purpose.startswith("archive_"):
        if st.reset_at is None:
            return deny("reset date unset (python scripts/credit_plan.py set-reset <ISO>)")
        if not args.drain and not cp.archive_window_open(
            now, st.reset_at, st.archive_window_days, closes_in
        ):
            return deny(
                f"archive window closed (opens {st.archive_window_days} days before "
                f"{st.reset_at.isoformat()}, once last Saturday's closes are captured)"
            )
    allow_n = cp.allowance(balance, now, st.reset_at, st.floor, per_week)
    if allow_n < est:
        return deny(
            f"allowance {allow_n:,} < estimate (balance {balance:,}, floor {st.floor:,}, "
            f"recurring {per_week:,}/wk {src} x {cp.remaining_weeks(now, st.reset_at):.2f} wk)"
        )
    print(f"ALLOW {purpose} est={est}: allowance {allow_n:,} (balance {balance:,})")
    return 0


def _set(key: str, new: str, args) -> int:
    with session_scope() as s:
        row = s.get(AppSetting, key)
        old = row.value if row is not None else None
        ok = ops.record_gauge(
            key,
            new,
            note=f"credit_plan set {datetime.utcnow().isoformat(timespec='seconds')}",
            session=s,
        )
    if not ok:
        print(f"[credit_plan] {key} NOT written")
        return 1
    print(f"{key}: {old if old is not None else '(unset)'} -> {new}")
    return 0


def cmd_set_reset(args) -> int:
    d = cp.parse_utc(args.value)
    if d is None:
        print(f"[credit_plan] not an ISO timestamp: {args.value!r}")
        return 1
    return _set(cp.RESET_AT_KEY, d.isoformat(), args)


def _nonneg_int(key: str, raw: str, args) -> int:
    try:
        n = int(raw)
        if n < 0:
            raise ValueError
    except ValueError:
        print(f"[credit_plan] {key} needs a non-negative integer, got {raw!r}")
        return 1
    return _set(key, str(n), args)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--now", help="override the clock (naive UTC ISO; tests and what-ifs)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("report")
    a = sub.add_parser("allow")
    a.add_argument("--purpose", required=True)
    a.add_argument("--estimate", type=int, required=True)
    a.add_argument(
        "--drain", action="store_true", help="archive purposes: waive the last-4-days window"
    )
    sub.add_parser("set-reset").add_argument("value")
    sub.add_parser("set-floor").add_argument("value")
    sub.add_parser("set-recurring").add_argument("value")
    args = p.parse_args(argv)
    if not try_init_db():
        print("[credit_plan] DB unreachable -- nothing read.")
        return 1 if args.cmd == "allow" else 0
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "allow":
        return cmd_allow(args)
    if args.cmd == "set-reset":
        return cmd_set_reset(args)
    key = cp.FLOOR_KEY if args.cmd == "set-floor" else cp.RECURRING_FALLBACK_KEY
    return _nonneg_int(key, args.value, args)


if __name__ == "__main__":
    sys.exit(main())
