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
from beatvegas.db.store import init_db, session_scope
from beatvegas.etl.match import resolve_game
from beatvegas.grading import clv_under, under_result, units_won
from beatvegas.lines import consensus_open_close


def _season_games(s, season: int) -> List[dict]:
    rows = (
        s.query(Game.id, Game.week, Game.home_team, Game.away_team)
        .filter(Game.season == season)
        .all()
    )
    return [{"id": r[0], "week": r[1], "home_team": r[2], "away_team": r[3]} for r in rows]


def _default_season(now: Optional[datetime] = None) -> int:
    now = now or datetime.utcnow()
    return now.year if now.month >= 6 else now.year - 1


def cmd_add(args) -> None:
    season = args.season or _default_season()
    with session_scope() as s:
        games = _season_games(s, season)
        gid, score, n = resolve_game(args.home, args.away, games, week=args.week)
        if gid is None:
            print(
                f"No game found for '{args.away} @ {args.home}' in {season}. "
                "Check spelling, or run backfill --season for this year. "
                "You can still log it; it just won't grade until matched."
            )
        elif n > 1:
            print(f"[warn] {n} games match (rematch?). Picked best; pass --week to be exact.")
        g = next((x for x in games if x["id"] == gid), None)
        pick = ManualPick(
            game_id=gid,
            season=season,
            week=(g or {}).get("week") if g else args.week,
            home_team=(g or {}).get("home_team", args.home) if g else args.home,
            away_team=(g or {}).get("away_team", args.away) if g else args.away,
            side="under",
            line=args.line,
            price=args.price,
            stake=args.stake,
            book=args.book,
            placed_at=datetime.utcnow(),
            note=args.note,
            graded=False,
        )
        s.add(pick)
        s.flush()
        print(
            f"logged pick #{pick.id}: UNDER {args.line} ({args.price}) "
            f"{pick.away_team} @ {pick.home_team} [{season} wk{pick.week}] "
            f"stake={args.stake}u" + (f" (game {gid})" if gid else " (UNMATCHED)")
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
            print(
                f"#{p.id} [{p.season} wk{p.week}] UNDER {p.line} {p.price} "
                f"{p.away_team} @ {p.home_team} stake={p.stake}u -> {status}"
            )


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
            if g is None or g.first_half_total is None:
                continue  # game not finished / no result yet
            snaps = (
                s.query(OddsSnapshot)
                .filter(OddsSnapshot.game_id == p.game_id, OddsSnapshot.market == "1H_total")
                .all()
            )
            _open, closing = consensus_open_close(snaps)
            p.actual_first_half_total = g.first_half_total
            p.result = under_result(g.first_half_total, p.line)
            p.units = p.stake * units_won(g.first_half_total, p.line, p.price)
            p.closing_line = closing
            p.clv = clv_under(p.line, closing) if closing is not None else None
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
        n = len(rows)
        wins = sum(1 for p in rows if p.result == "under")
        pushes = sum(1 for p in rows if p.result == "push")
        units = sum(p.units for p in rows)
        staked = sum(p.stake for p in rows)
        clvs = [p.clv for p in rows if p.clv is not None]
        decided = n - pushes
        hit = f"{100 * wins / decided:.1f}%" if decided else "n/a"
        roi = f"{100 * units / staked:+.1f}%" if staked else "n/a"
        print(
            f"YOUR RECORD: {wins}-{decided - wins}"
            + (f"-{pushes}P" if pushes else "")
            + f"  hit={hit}  units={units:+.2f}  ROI={roi}"
            + (f"  avg CLV={sum(clvs) / len(clvs):+.2f}" if clvs else "")
        )


def main() -> None:
    init_db()
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
