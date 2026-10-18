#!/usr/bin/env python
"""List, grade and summarise the logged picks.

python scripts/pick.py list                 # show logged picks
python scripts/pick.py grade --season 2026  # grade completed picks (vs result + CLV)
python scripts/pick.py summary              # your hit rate, units, avg CLV

There is no `add` (removed 2026-10-07). Real tickets are logged on the site
(the game page, POST /api/picks), where every policy gate runs; paper picks are
written by the card build only (scripts/build_card.py), one per qualifying game,
because the paper ledger is the stopping rule's observation stream and a hand
paper pick took a game's one slot before the build reached it.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import List, Optional

from beatvegas.challenger_picks import grade_challenger_picks
from beatvegas.db.models import Game, ManualPick
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.picks import (
    grade_pick,
    graded_pick_fields,
)

__all__ = ["graded_pick_fields"]  # re-exported from beatvegas.picks for existing importers


def _season_games(s, season: int) -> List[dict]:
    rows = (
        s.query(Game.id, Game.week, Game.home_team, Game.away_team, Game.start_date)
        .filter(Game.season == season)
        .all()
    )
    return [
        {"id": r[0], "week": r[1], "home_team": r[2], "away_team": r[3], "start_date": r[4]}
        for r in rows
    ]


def _default_season(now: Optional[datetime] = None) -> int:
    now = now or datetime.utcnow()
    return now.year if now.month >= 6 else now.year - 1


def cmd_list(args) -> None:
    with session_scope() as s:
        q = s.query(ManualPick).order_by(ManualPick.id)
        if args.season:
            q = q.filter(ManualPick.season == args.season)
        rows = q.all()
        if not rows:
            print("no picks logged yet")
            return
        for p in rows:
            units = "unpriced" if p.units is None else f"{p.units:+.2f}u"
            clv = "n/a" if p.clv is None else f"{p.clv:+.1f}"  # no closing captured
            status = f"{p.result} ({units}, CLV {clv})" if p.graded else "pending"
            tag = "[PAPER] " if p.is_paper else ""
            why = (p.reason or "manual") + (f"/{p.verdict_at_pick}" if p.verdict_at_pick else "")
            print(
                f"#{p.id} {tag}[{p.season} wk{p.week}] UNDER {p.line} {p.price} "
                f"{p.away_team} @ {p.home_team} stake={p.stake}u {why} -> {status}"
            )


def cmd_grade(args) -> None:
    season = args.season or _default_season()
    graded = 0
    regrade = bool(getattr(args, "regrade", False))
    with session_scope() as s:
        q = s.query(ManualPick).filter(
            ManualPick.season == season,
            ManualPick.game_id.isnot(None),
        )
        # Normally grade-once: a graded pick is a settled record and re-running
        # the job nightly must not churn it. --regrade is for the case where the
        # GRADING RULE itself changed -- 2026-09-13, when CLV stopped being
        # measured against Hard Rock's pre-kickoff rung. grade_pick recomputes
        # the result, units and CLV fields from the game and the snapshots; the
        # judge's columns (ev_cons and friends) are write-once, so a regrade
        # that would change them is audited (judge_reading_audit), not written.
        if not regrade:
            q = q.filter(ManualPick.graded == False)  # noqa: E712
        picks = q.all()
        reason = "regrade" if regrade else "grade"
        for p in picks:
            g = s.query(Game).filter(Game.id == p.game_id).one_or_none()
            if g is None:
                continue
            # per-pick rules (trusted 1H, pre-kick close, Hard Rock's own close,
            # NULL-price fill) live in beatvegas.picks.grade_pick
            if grade_pick(s, p, g, judge_reason=reason):
                graded += 1
    print(f"graded {graded} pick(s) for {season}")
    # The registered paper arms settle by the same rules, in their own table. This
    # is its own session so the champion ledger's grades above are already
    # committed when it runs; it is NOT wrapped in a try/except. An exception
    # propagates and fails the step (final-2026 plan PR-02): a swallowed warning
    # left the run green and the arms silently ungraded and unread.
    with session_scope() as s:
        n = grade_challenger_picks(s, season, regrade=regrade)
    print(f"graded {n} challenger observation(s) for {season}")
    cmd_summary(args)


def cmd_summary(args) -> None:
    with session_scope() as s:
        q = s.query(ManualPick).filter(ManualPick.graded == True)  # noqa: E712
        if args.season:
            q = q.filter(ManualPick.season == args.season)
        rows = q.all()
        if not rows:
            print("no graded picks yet")
            return
        # Real and paper picks are separate records: paper stakes one flat unit
        # with nothing at risk, so its wins must never flatter the real ledger.
        for label, subset in (
            ("YOUR RECORD", [p for p in rows if not p.is_paper]),
            ("PAPER RECORD", [p for p in rows if p.is_paper]),
        ):
            if not subset:
                continue
            n = len(subset)
            wins = sum(1 for p in subset if p.result == "under")
            pushes = sum(1 for p in subset if p.result == "push")
            # Unpriced picks (no Hard Rock close captured) count for the record
            # and hit rate but carry no units, so units/ROI sum the priced ones.
            priced = [p for p in subset if p.units is not None]
            unpriced = n - len(priced)
            units = sum(p.units for p in priced)
            staked = sum(p.stake for p in priced)
            clvs = [p.clv for p in subset if p.clv is not None]
            decided = n - pushes
            hit = f"{100 * wins / decided:.1f}%" if decided else "n/a"
            roi = f"{100 * units / staked:+.1f}%" if staked else "n/a"
            print(
                f"{label}: {wins}-{decided - wins}"
                + (f"-{pushes}P" if pushes else "")
                + f"  hit={hit}  units={units:+.2f}  ROI={roi}"
                + (f"  avg CLV={sum(clvs) / len(clvs):+.2f}" if clvs else "")
                + (f"  ({unpriced} unpriced)" if unpriced else "")
            )


def main() -> None:
    if not try_init_db():
        return
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    li = sub.add_parser("list", help="list logged picks")
    li.add_argument("--season", type=int)
    li.set_defaults(func=cmd_list)

    gr = sub.add_parser("grade", help="grade completed picks")
    gr.add_argument("--season", type=int)
    gr.add_argument(
        "--regrade",
        action="store_true",
        help="also re-grade picks already graded (use when the grading RULE changed)",
    )
    gr.set_defaults(func=cmd_grade)

    su = sub.add_parser("summary", help="your record / ROI / CLV")
    su.add_argument("--season", type=int)
    su.set_defaults(func=cmd_summary)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
