#!/usr/bin/env python
"""Manually nudge the BV line for a game (display-only override you control).

Use when you know something the model can't see (a confirmed QB-out, late
weather). The nudge shifts the BV line + gap shown on the card, clearly labeled —
it never touches the model or the Under Score. Latest entry per game wins.

    python scripts/bv_adjust.py set --game 401752875 --delta -3 --reason "starter QB out"
    python scripts/bv_adjust.py list
    python scripts/bv_adjust.py clear --game 401752875
"""

from __future__ import annotations

import argparse
from datetime import datetime

from beatvegas.db.models import BvAdjustment, Game
from beatvegas.db.store import init_db, session_scope


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set", help="set/replace a game's BV adjustment")
    s.add_argument("--game", type=int, required=True)
    s.add_argument(
        "--delta",
        type=float,
        required=True,
        help="points added to the BV line (negative = expect lower scoring)",
    )
    s.add_argument("--reason", default="")
    c = sub.add_parser("clear", help="remove a game's BV adjustment")
    c.add_argument("--game", type=int, required=True)
    sub.add_parser("list", help="show current adjustments")
    args = ap.parse_args()
    init_db()

    with session_scope() as sess:
        if args.cmd == "set":
            sess.query(BvAdjustment).filter(BvAdjustment.game_id == args.game).delete()
            sess.add(
                BvAdjustment(
                    game_id=args.game,
                    delta_pts=args.delta,
                    reason=args.reason,
                    created_at=datetime.utcnow(),
                )
            )
            print(f"set game {args.game}: BV {args.delta:+g} ({args.reason or 'no reason'})")
        elif args.cmd == "clear":
            n = sess.query(BvAdjustment).filter(BvAdjustment.game_id == args.game).delete()
            print(f"cleared {n} adjustment(s) for game {args.game}")
        else:
            rows = (
                sess.query(BvAdjustment, Game)
                .outerjoin(Game, Game.id == BvAdjustment.game_id)
                .order_by(BvAdjustment.created_at.desc())
                .all()
            )
            if not rows:
                print("no adjustments set")
            for adj, g in rows:
                matchup = f"{g.away_team} @ {g.home_team}" if g else "?"
                print(f"  game {adj.game_id} ({matchup}): {adj.delta_pts:+g} — {adj.reason or ''}")


if __name__ == "__main__":
    main()
