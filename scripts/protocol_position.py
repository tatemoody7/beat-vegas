#!/usr/bin/env python
"""Where each registered arm stands under the 2026 Statistical Protocol (p1.1).

The Monday program review reads this (docs/PROTOCOL_2026.md). For every arm in
`beatvegas.protocol.ARMS` (docs/HYPOTHESES.md H-ARM-*): its paper picks -- the
arm's table, its `arm` tag, market and side, placed on or after the arms' start
-- grouped by week. Only COMPLETED weeks enter: a week counts once every one of
the arm's picks in it is graded. Each graded pick with an `ev_cons` reading is
one reading (EV at the wager's exact terms against the consensus close, at the
logged Hard Rock price); a pick without one is an exclusion, counted by its
`cons_excluded` reason and never an observation. The readings go to
`protocol.position`, which applies the weekly SPRT, the 30-readings-over-3-weeks
guard and the 200-reading timeout.

Read-only: nothing here writes, and no position it prints moves real money.

    PYTHONPATH=. python scripts/protocol_position.py --out reports/protocol
    PYTHONPATH=. python scripts/protocol_position.py --season-over   # the final read
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from residual_gate import append_step_summary, report_paths  # noqa: E402

from beatvegas import protocol as P  # noqa: E402
from beatvegas.db.models import ChallengerPick, Game, ManualPick  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402
from beatvegas.positions import arm_position, mean_ci, upsert_position  # noqa: E402


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports/protocol")
    ap.add_argument(
        "--write",
        action="store_true",
        help="upsert one arm_positions row per arm (the Monday workflow only; a study dispatch never writes)",
    )
    ap.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID") or "-")
    ap.add_argument(
        "--season-over", action="store_true", help="the season has ended: running arms time out"
    )
    return ap.parse_args(argv)


def arm_rows(session, arm: str, spec: Dict[str, Any], since: Optional[str] = None) -> List[Any]:
    """The arm's paper picks placed on or after `since` (default: the arm's
    clock start), placed order. Never a real ticket."""
    start = datetime.fromisoformat(since or P.arm_start(arm))
    model = ManualPick if spec["table"] == "manual_picks" else ChallengerPick
    q = session.query(model).filter(
        model.arm == arm,
        model.market == spec["market"],
        model.side == spec["side"],
        model.placed_at >= start,
    )
    if model is ManualPick:
        q = q.filter(ManualPick.is_paper.is_(True))
    return q.order_by(model.placed_at, model.id).all()


# --- p1.2 (Tate, 2026-10-14): the reading unit and when a week is complete ----------


def reading_key(row: Any) -> Tuple[int, int, int, int]:
    """R1: a regular-season pick reads in (season, CFBD week); a postseason pick
    (`games.season_type = 'postseason'`, which CFBD files as week 1) reads in the
    ISO week (Monday-Sunday, UTC) of its kickoff, which is defined across New Year,
    so bowl season yields several readings in order and the season stays put."""
    season = int(getattr(row, "season", 0) or 0)
    kick = getattr(row, "kickoff", None)
    if getattr(row, "season_type", None) == "postseason" and kick is not None:
        iso = kick.isocalendar()
        return (season, 1, int(iso[0]), int(iso[1]))
    return (season, 0, int(getattr(row, "week", 0) or 0), 0)


def key_label(key: Tuple[int, int, int, int]) -> str:
    season, post, a, b = key
    return f"{season}-post-{a}W{b:02d}" if post else f"{season}-w{a}"


def week_closes_at(latest_kickoff: datetime) -> datetime:
    """R2: the earliest Monday 12:00 UTC strictly after the week's latest kickoff
    (naive UTC). Grading has landed by then (grade.yml runs at the 10Z tick)."""
    t = datetime(latest_kickoff.year, latest_kickoff.month, latest_kickoff.day, 12)
    t += timedelta(days=(0 - t.weekday()) % 7)
    if t <= latest_kickoff:
        t += timedelta(days=7)
    return t


def with_games(session, rows: Sequence[Any]) -> List[Any]:
    """Each pick as the reader needs it: its own fields plus its game's kickoff
    and season type (R1/R2). Copies, so nothing is written back."""
    ids = {int(r.game_id) for r in rows if r.game_id is not None}
    games = (
        {int(g.id): g for g in session.query(Game).filter(Game.id.in_(list(ids))).all()}
        if ids
        else {}
    )
    out = []
    for r in rows:
        g = games.get(int(r.game_id)) if r.game_id is not None else None
        out.append(
            SimpleNamespace(
                season=r.season,
                week=r.week,
                graded=r.graded,
                ev_cons=r.ev_cons,
                cons_excluded=r.cons_excluded,
                cons_books=getattr(r, "cons_books", None),
                kickoff=None if g is None else g.start_date,
                season_type=None if g is None else g.season_type,
            )
        )
    return out


def completed(rows: Sequence[Any], now: Optional[datetime] = None) -> List[Any]:
    """The rows of the reading weeks that are complete (R2): every pick in the
    week graded AND, when `now` is given, the read runs at or after the Monday
    12:00 UTC following the week's latest kickoff. Rows come back in reading-week
    order (R1), placed order within a week."""
    by_week: Dict[Any, List[Any]] = defaultdict(list)
    for r in rows:
        by_week[reading_key(r)].append(r)
    done: List[Any] = []
    for key in sorted(by_week):
        rs = by_week[key]
        if not rs or not all(bool(r.graded) for r in rs):
            continue
        if now is not None:
            kicks = [getattr(r, "kickoff", None) for r in rs]
            if any(k is None for k in kicks) or now < week_closes_at(max(kicks)):
                continue
        done.extend(rs)
    return done


def read_arm(
    rows: Sequence[Any], season_over: bool = False, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """Pure: the arm's position over its complete reading weeks, plus its tallies.
    `now` turns on R2's Monday rule (the Monday workflow passes its clock)."""
    done = completed(rows, now)
    obs = [(key_label(reading_key(r)), float(r.ev_cons)) for r in done if r.ev_cons is not None]
    excluded = sum(1 for r in done if r.ev_cons is None)
    pos = P.position(obs, season_over=season_over)
    reasons = Counter(r.cons_excluded or "unexplained" for r in done if r.ev_cons is None)
    # Programme 4.2 (Tate, 2026-10-14): exclusions by the close's book count, a
    # report line beside the arm. The judge needs 3+ books inside 2 h of kickoff.
    books = Counter(str(getattr(r, "cons_books", None)) for r in done if r.ev_cons is None)
    weeks = sorted({reading_key(r) for r in done})
    _m, lo, hi = mean_ci(e for _, e in obs)
    return {
        "logged": len(rows),
        "pending": len(rows) - len(done),
        "completed_weeks": [key_label(k) for k in weeks],
        "readings": pos.n,
        "excluded": excluded,
        "excluded_by_reason": dict(reasons),
        "excluded_by_books": dict(books),
        "weeks": pos.weeks,
        "llr": round(pos.llr, 3),
        "state": pos.state,
        "label": P.label(pos.state),
        "decided_at_week": pos.decided_at_week,
        "mean_ev": round(sum(e for _, e in obs) / len(obs), 4) if obs else None,
        "ev_lo": None if lo is None else round(lo, 4),
        "ev_hi": None if hi is None else round(hi, 4),
    }


def paused_arm(logged: int) -> Dict[str, Any]:
    """Pure: a paused arm's line -- no readings, whatever it has logged."""
    return {
        "logged": logged,
        "pending": 0,
        "completed_weeks": [],
        "readings": 0,
        "excluded": 0,
        "excluded_by_reason": {},
        "excluded_by_books": {},
        "weeks": 0,
        "llr": 0.0,
        "state": P.PAUSED,
        "label": P.label(P.PAUSED),
        "decided_at_week": None,
        "mean_ev": None,
        "ev_lo": None,
        "ev_hi": None,
    }


def render(result: Dict[str, Any]) -> str:
    L = [
        f"# Protocol {P.PROTOCOL_VERSION}: the registered arms",
        "",
        f"Generated {result['generated_at']}. Boundaries: PROMOTE at LLR >= {P.UPPER:.3f}, "
        f"STOP at LLR <= {P.LOWER:.3f}; no decision before {P.MIN_OBS} readings over "
        f"{P.MIN_WEEKS}+ weeks; timeout {P.MAX_OBS} readings or season end. A reading week "
        "(regular season: the CFBD week; postseason: the ISO week of kickoff) enters only when every "
        "pick in it is graded and the read runs at or after the Monday 12:00 UTC after its last "
        "kickoff (p1.2); an exclusion is counted, never an observation.",
        "",
    ]
    if any(r["state"] == P.PAUSED for r in result["arms"].values()):
        L += [
            "**Clocks paused** since 2026-10-09 (p1.1, roadmap v1.5) for the arms marked "
            "PAUSED: no reading counts until the first card built on the leak-fixed model; "
            "the picks they log meanwhile (`logged`) are development evidence.",
            "",
        ]
    L += [
        "| arm | slot | state | logged | readings | weeks | LLR | mean EV | excluded | pending |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm, r in result["arms"].items():
        ev = "—" if r["mean_ev"] is None else f"{r['mean_ev']:+.4f}"
        L.append(
            f"| {arm} | {r['slot']} | {r['label']} | {r['logged']} | {r['readings']} | {r['weeks']} | "
            f"{r['llr']:+.3f} | {ev} | {r['excluded']} | {r['pending']} |"
        )
    L.append("")
    for arm, r in result["arms"].items():
        if r["excluded_by_reason"]:
            why = ", ".join(f"{k} {v}" for k, v in sorted(r["excluded_by_reason"].items()))
            L.append(f"- {arm} exclusions: {why}")
        if r.get("excluded_by_books"):
            nb = ", ".join(f"{k} books {v}" for k, v in sorted(r["excluded_by_books"].items()))
            L.append(f"- {arm} exclusions by close book count (the judge needs 3+): {nb}")
    return "\n".join(L) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        return 1
    arms: Dict[str, Dict[str, Any]] = {}
    now = datetime.utcnow()
    with session_scope() as s:
        for arm, spec in P.ARMS.items():
            start = P.arm_start(arm)
            if start is None:
                line = paused_arm(len(arm_rows(s, arm, spec, since=P.ARMS_TAGGED_FROM)))
            else:
                line = read_arm(
                    with_games(s, arm_rows(s, arm, spec, since=start)), args.season_over, now
                )
            arms[arm] = {**line, "slot": spec["slot"]}
    result = {"generated_at": now.isoformat() + "Z", "arms": arms}
    if args.write:
        with session_scope() as s:
            for arm, line in arms.items():
                upsert_position(s, arm_position(arm, line, now, args.run_id))
        result["written"] = {"run_id": args.run_id, "read_date": now.strftime("%Y-%m-%d")}
        print(f"[protocol] wrote {len(arms)} arm_positions rows (run {args.run_id})")
    md = render(result)
    md_path, json_path, _csv = report_paths(args.out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)
    json_path.write_text(json.dumps(result, indent=1, default=str))
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
