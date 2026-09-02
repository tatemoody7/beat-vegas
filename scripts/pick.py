#!/usr/bin/env python
"""Log and grade your own first-half under bets, by team name.

# log a bet (resolves the game by name within the season):
python scripts/pick.py add --home "Ohio State" --away "Michigan" --line 24.5
python scripts/pick.py add --home Bama --away LSU --line 27 --price -105 --stake 2 --book dk

python scripts/pick.py list                 # show logged picks
python scripts/pick.py grade --season 2026  # grade completed picks (vs result + CLV)
python scripts/pick.py summary              # your hit rate, units, avg CLV
"""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import List, Optional

from beatvegas.db.models import Game, ManualPick, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import resolve_game
from beatvegas.grading import (
    clv_under,
    price_clv_under,
    trusted_first_half_total,
    under_result,
    units_won,
)
from beatvegas.lines import closing_before_kickoff, fair_under_before_kickoff


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
            dup = (
                s.query(ManualPick)
                .filter(ManualPick.game_id == gid, ManualPick.side == "under")
                .filter((ManualPick.market == market) | (ManualPick.market.is_(None)))
                .first()
            )
            if dup is not None:
                print(
                    f"REFUSED: pick #{dup.id} already logged on this game/market "
                    f"(UNDER {dup.line}). Pass --force to log a second bet on it."
                )
                return

        # Paper pick: stake forced to 0 so units math stays clean; CLV/result
        # still grade normally.
        stake = 0.0 if args.paper else args.stake
        pick = ManualPick(
            game_id=gid,
            season=season,
            week=(g or {}).get("week") if g else args.week,
            home_team=(g or {}).get("home_team", args.home) if g else args.home,
            away_team=(g or {}).get("away_team", args.away) if g else args.away,
            side="under",
            market=market,
            line=args.line,
            price=args.price,
            stake=stake,
            is_paper=bool(args.paper),
            book=args.book,
            placed_at=datetime.utcnow(),
            note=args.note,
            graded=False,
        )
        s.add(pick)
        s.flush()
        print(
            f"logged {'PAPER ' if args.paper else ''}pick #{pick.id}: {market} UNDER "
            f"{args.line} ({args.price}) {pick.away_team} @ {pick.home_team} "
            f"[{season} wk{pick.week}] stake={stake}u"
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
            status = f"{p.result} ({p.units:+.2f}u, CLV {p.clv:+.1f})" if p.graded else "pending"
            tag = "[PAPER] " if p.is_paper else ""
            print(
                f"#{p.id} {tag}[{p.season} wk{p.week}] UNDER {p.line} {p.price} "
                f"{p.away_team} @ {p.home_team} stake={p.stake}u -> {status}"
            )


def graded_pick_fields(
    actual_first_half, line, price, stake, opening, closing, fair_open=None, fair_close=None
) -> dict:
    """Pure: the graded ManualPick fields for one pick + its line snapshots."""
    return {
        "actual_first_half_total": actual_first_half,
        "result": under_result(actual_first_half, line),
        "units": stake * units_won(actual_first_half, line, price),
        "opening_line": opening,
        "closing_line": closing,
        "clv": clv_under(line, closing) if closing is not None else None,
        "clv_prob": price_clv_under(fair_open, fair_close),
    }


def cmd_grade(args) -> None:
    season = args.season or _default_season()
    graded = 0
    with session_scope() as s:
        picks = (
            s.query(ManualPick)
            .filter(
                ManualPick.season == season,
                ManualPick.graded == False,  # noqa: E712
                ManualPick.game_id.isnot(None),
            )
            .all()
        )
        for p in picks:
            g = s.query(Game).filter(Game.id == p.game_id).one_or_none()
            if g is None:
                continue
            is_full = (p.market or "1H") == "full"
            if is_full:
                if g.home_points is None or g.away_points is None:
                    continue  # game not finished
                actual = g.home_points + g.away_points
                snap_market = "full_game_total"
            else:
                actual = trusted_first_half_total(
                    g.first_half_total, g.home_points, g.away_points, g.first_half_source
                )
                if actual is None:
                    continue  # not finished, or a known-false 0 — never grade it
                snap_market = "1H_total"
            snaps = (
                s.query(OddsSnapshot)
                .filter(OddsSnapshot.game_id == p.game_id, OddsSnapshot.market == snap_market)
                .all()
            )
            # Pre-kickoff snapshots only (mirrors grade.py): a poll that ran
            # after the game started must not pollute your closing line / CLV.
            opening, closing, _closing_at = closing_before_kickoff(snaps, g.start_date)
            fair_open, fair_close = fair_under_before_kickoff(snaps, g.start_date)
            for k, v in graded_pick_fields(
                actual, p.line, p.price, p.stake, opening, closing, fair_open, fair_close
            ).items():
                setattr(p, k, v)
            p.graded = True
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
        # Real and paper picks are separate records: paper has no stake, so its
        # ROI is meaningless and its wins must not flatter the real ledger.
        for label, subset in (
            ("YOUR RECORD", [p for p in rows if not p.is_paper]),
            ("PAPER RECORD", [p for p in rows if p.is_paper]),
        ):
            if not subset:
                continue
            n = len(subset)
            wins = sum(1 for p in subset if p.result == "under")
            pushes = sum(1 for p in subset if p.result == "push")
            units = sum(p.units for p in subset)
            staked = sum(p.stake for p in subset)
            clvs = [p.clv for p in subset if p.clv is not None]
            decided = n - pushes
            hit = f"{100 * wins / decided:.1f}%" if decided else "n/a"
            roi = f"{100 * units / staked:+.1f}%" if staked else "n/a"
            print(
                f"{label}: {wins}-{decided - wins}"
                + (f"-{pushes}P" if pushes else "")
                + f"  hit={hit}  units={units:+.2f}  ROI={roi}"
                + (f"  avg CLV={sum(clvs) / len(clvs):+.2f}" if clvs else "")
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
        help="paper pick: tracked for record + CLV with nothing at risk (stake forced to 0)",
    )
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
    gr.set_defaults(func=cmd_grade)

    su = sub.add_parser("summary", help="your record / ROI / CLV")
    su.add_argument("--season", type=int)
    su.set_defaults(func=cmd_summary)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
