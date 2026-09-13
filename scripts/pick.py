#!/usr/bin/env python
"""Log and grade your own first-half under bets, by team name.

# log a bet (resolves the game by name within the season):
python scripts/pick.py add --home "Ohio State" --away "Michigan" --line 24.5
python scripts/pick.py add --home Bama --away LSU --line 27 --price -105 --stake 2 --book dk
# record WHY (board verdict + numbers at log time) so hit rate splits by reason:
python scripts/pick.py add --home LSU --away Clemson --line 24.5 --reason model_gap \
    --verdict BET --gap 2.25 --ev 0.03 --hr-line 24.5
python scripts/pick.py add ... --paper           # paper: one flat unit, own record

python scripts/pick.py list                 # show logged picks
python scripts/pick.py grade --season 2026  # grade completed picks (vs result + CLV)
python scripts/pick.py summary              # your hit rate, units, avg CLV
"""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import List, Optional

from beatvegas.db.models import Game, ManualPick
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import resolve_game
from beatvegas.picks import (
    add_pick,
    existing_pick,
    grade_pick,
    graded_pick_fields,
    model_read,
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


def cmd_add(args) -> None:
    season = args.season or _default_season()
    market = "full" if args.market == "full" else "1H"
    with session_scope() as s:
        games = _season_games(s, season)
        gid, score, n, candidates = resolve_game(args.home, args.away, games, week=args.week)
        if gid is None:
            print(
                f"No game found for '{args.away} @ {args.home}' in {season}. "
                "Check spelling, or run backfill --season for this year. "
                "You can still log it; it just won't grade until matched."
            )
        elif n > 1 and not args.force:
            print(f"REFUSED: {n} games match '{args.away} @ {args.home}' in {season}:")
            for c in candidates:
                print(f"  wk{c.get('week')}: {c.get('away_team')} @ {c.get('home_team')}")
            print(
                "Pass --week to pin the game, or --force to accept the best guess — "
                "a real-money pick must not attach to a guessed game."
            )
            return
        g = next((x for x in games if x["id"] == gid), None)

        # Real-money integrity guards (override with --force if intentional).
        if gid is not None and not args.force:
            start = (g or {}).get("start_date")
            if start is not None and start <= datetime.utcnow():
                print(
                    f"REFUSED: {args.away} @ {args.home} already kicked off "
                    f"({start} UTC) — a post-kickoff pick isn't a real bet. "
                    "Pass --force if you genuinely placed it pre-game."
                )
                return
            # Per ledger: the card's PAPER pick on a game never blocks a real
            # ticket on it (the paper ledger now logs every qualifying game).
            dup = existing_pick(s, gid, market, is_paper=bool(args.paper))
            if dup is not None:
                print(
                    f"REFUSED: {'paper ' if args.paper else ''}pick #{dup.id} already logged "
                    f"on this game/market (UNDER {dup.line}). Pass --force to log a second bet on it."
                )
                return

        # Freeze OUR number and the model's score onto the ticket, the same read
        # the website's own log takes (web/lib/picks.ts createPick) — without it
        # a terminal pick sits outside decision-quality's agreed/against split.
        model_line, model_score = model_read(s, gid, market)
        # Paper pick: one flat unit so it grades as +/-1u on its own record
        # (is_paper keeps it out of the real ledger); CLV/result grade normally.
        # The insert itself is beatvegas.picks.add_pick, shared with the cloud card.
        pick = add_pick(
            s,
            game_id=gid,
            season=season,
            week=(g or {}).get("week") if g else args.week,
            home_team=(g or {}).get("home_team", args.home) if g else args.home,
            away_team=(g or {}).get("away_team", args.away) if g else args.away,
            market=market,
            line=args.line,
            price=args.price,
            stake=args.stake,
            is_paper=bool(args.paper),
            book=args.book,
            note=args.note,
            reason=args.reason or "manual",
            verdict=args.verdict,
            gap=args.gap,
            ev=args.ev,
            hr_line=args.hr_line,
            model_line=model_line,
            model_score=model_score,
        )
        why = pick.reason + (f"/{pick.verdict_at_pick}" if pick.verdict_at_pick else "")
        print(
            f"logged {'PAPER ' if args.paper else ''}pick #{pick.id}: {market} UNDER "
            f"{args.line} ({args.price}) {pick.away_team} @ {pick.home_team} "
            f"[{season} wk{pick.week}] stake={pick.stake}u reason={why}"
            + (f" (game {gid})" if gid else " (UNMATCHED)")
        )


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
        # every field from the game and the snapshots, so it is idempotent.
        if not regrade:
            q = q.filter(ManualPick.graded == False)  # noqa: E712
        picks = q.all()
        for p in picks:
            g = s.query(Game).filter(Game.id == p.game_id).one_or_none()
            if g is None:
                continue
            # per-pick rules (trusted 1H, pre-kick close, Hard Rock's own close,
            # NULL-price fill) live in beatvegas.picks.grade_pick
            if grade_pick(s, p, g):
                graded += 1
    print(f"graded {graded} pick(s) for {season}")
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

    a = sub.add_parser("add", help="log a first-half under bet")
    a.add_argument("--home", required=True)
    a.add_argument("--away", required=True)
    a.add_argument("--line", type=float, required=True)
    a.add_argument("--price", type=int, default=-110)
    a.add_argument("--stake", type=float, default=1.0)
    a.add_argument("--book")
    a.add_argument("--season", type=int)
    a.add_argument("--week", type=int)
    a.add_argument("--note")
    a.add_argument(
        "--market",
        choices=("1h", "full"),
        default="1h",
        help="which total the bet is on: 1h (default) or full game",
    )
    a.add_argument(
        "--paper",
        action="store_true",
        help="paper pick: nothing at risk, staked one flat unit so it grades +/-1u "
        "on its own PAPER record",
    )
    a.add_argument(
        "--reason",
        choices=("model_gap", "price_edge", "manual"),
        default="manual",
        help="why the bet: the model gap, a Hard Rock price edge, or your own read",
    )
    a.add_argument(
        "--verdict",
        choices=("BET", "WATCH", "PASS"),
        help="the board's verdict at log time (frozen for later review)",
    )
    a.add_argument("--gap", type=float, help="bv_gap in points shown at log time")
    a.add_argument("--ev", type=float, help="no-vig EV of the under at log time")
    a.add_argument("--hr-line", type=float, dest="hr_line", help="Hard Rock's line at log time")
    a.add_argument(
        "--force",
        action="store_true",
        help=(
            "log even if a pick already exists on this game/market, kickoff has "
            "passed, or the game match is ambiguous"
        ),
    )
    a.set_defaults(func=cmd_add)

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
