#!/usr/bin/env python
"""Build the week's bet card and publish it to the Board (`cards` table).

Runs in GitHub Actions (`.github/workflows/card.yml`, Friday 6pm ET + Saturday
11am ET refresh) — the Mac routine it replaces slept through the card. Pure
rules live in beatvegas/card.py; this script only loads the inputs, writes one
`cards` row per build (history; the newest row is the live card) and logs every
BET as a PAPER pick through the same code path as `pick.py add`
(beatvegas.picks.add_pick), never twice for one game.

    python scripts/build_card.py                      # active season/week
    python scripts/build_card.py --season 2026 --week 3
    python scripts/build_card.py --dry-run            # print the payload, write nothing

Exit 1 when the Hard Rock universe has games but the card came out empty (every
game already kicked off, or the inputs are missing) so the run goes red instead
of publishing nothing quietly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set

from beatvegas.card import REFERENCE_MODEL_VERSION, build_card
from beatvegas.db.models import Card, Game, GamePreview, OddsSnapshot, Prediction
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.hardrock import HR_BOOK_KEY
from beatvegas.model.score import BET_GAP_PTS, MODEL_VERSION
from beatvegas.picks import add_pick, existing_pick


def hr_universe(session, season: int, week: int) -> List[Dict]:
    """The week's games Hard Rock has priced a full-game total on, as card rows."""
    ids: Set[int] = {
        r[0]
        for r in (
            session.query(OddsSnapshot.game_id)
            .join(Game, Game.id == OddsSnapshot.game_id)
            .filter(
                Game.season == season,
                Game.week == week,
                OddsSnapshot.market == "full_game_total",
                OddsSnapshot.book == HR_BOOK_KEY,
            )
            .distinct()
            .all()
        )
    }
    if not ids:
        return []
    rows = session.query(Game).filter(Game.id.in_(ids)).order_by(Game.start_date, Game.id).all()
    return [
        {"game_id": g.id, "away": g.away_team, "home": g.home_team, "kick": g.start_date}
        for g in rows
    ]


def load_inputs(session, game_ids: List[int]) -> tuple:
    """(snapshots, predictions, previews) as the plain dicts build_card takes."""
    if not game_ids:
        return [], [], []
    snaps = [
        {
            "game_id": s.game_id,
            "book": s.book,
            "line": s.line,
            "over_price": s.over_price,
            "under_price": s.under_price,
            "captured_at": s.captured_at,
        }
        for s in session.query(OddsSnapshot)
        .filter(OddsSnapshot.game_id.in_(game_ids), OddsSnapshot.market == "1H_total")
        .all()
    ]
    preds = [
        {
            "game_id": p.game_id,
            "model_version": p.model_version,
            "bv_line": p.bv_line,
            "under_score": p.under_score,
            "line_used": p.line_used,
        }
        for p in session.query(Prediction)
        .filter(
            Prediction.game_id.in_(game_ids),
            Prediction.model_version.in_([MODEL_VERSION, REFERENCE_MODEL_VERSION]),
        )
        .all()
    ]
    previews = [
        {"game_id": p.game_id, "qb_out": p.qb_out, "qb_out_detail": p.qb_out_detail}
        for p in session.query(GamePreview).filter(GamePreview.game_id.in_(game_ids)).all()
    ]
    return snaps, preds, previews


def log_paper_picks(session, card: Dict, now: datetime) -> int:
    """Insert one PAPER pick per BET item that has no pick on the game yet
    (any 1H pick — paper or real — counts as logged). Marks `paper_logged` on
    the items. Returns the number inserted."""
    inserted = 0
    for it in card["items"]:
        if it["tier"] != "BET":
            continue
        gid = it["game_id"]
        if existing_pick(session, gid, "1H") is not None:
            it["paper_logged"] = True
            continue
        reason = "model_gap" if it["gap"] is not None and it["gap"] >= BET_GAP_PTS else "price_edge"
        add_pick(
            session,
            game_id=gid,
            season=card["season"],
            week=card["week"],
            home_team=it["home"],
            away_team=it["away"],
            market="1H",
            line=it["hr_line"],
            price=it["hr_price"] if it["hr_price"] is not None else -110,
            is_paper=True,
            book=HR_BOOK_KEY,
            note=f"card {now:%Y-%m-%d}: {it['action']}",
            reason=reason,
            verdict="BET",
            gap=it["gap"],
            ev=it["ev"],
            hr_line=it["hr_line"],
            placed_at=now,
        )
        it["paper_logged"] = True
        inserted += 1
    return inserted


def summary_lines(card: Dict, universe: int, picks_added: int) -> List[str]:
    c = card["counts"]
    out = [
        f"Card {card['season']} wk{card['week']} built {card['built_at']}: "
        f"{c['bet']} BET / {c['edge']} EDGE / {c['pass']} PASS "
        f"({len(card['items'])} of {universe} Hard Rock games still to kick off; "
        f"model read: {'yes' if card['model_read'] else 'no'}; paper picks added: {picks_added})"
    ]
    for it in card["items"]:
        if it["tier"] == "BET":
            price = f" {it['hr_price']:+d}" if it["hr_price"] is not None else ""
            out.append(
                f"  BET  {it['away']} @ {it['home']}: 1H under {it['hr_line']}{price} "
                f"(gap {it['gap']:+.2f}, ev {it['ev'] if it['ev'] is not None else 'n/a'})"
            )
    for it in card["items"]:
        if it["tier"] == "EDGE":
            out.append(f"  EDGE {it['away']} @ {it['home']} [{it['blocker']}]: {it['action']}")
    for n in card["notes"]:
        out.append(f"  note: {n}")
    return out


def write_step_summary(card: Dict, lines: List[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    c = card["counts"]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"## Bet card {card['season']} wk{card['week']}\n\n")
        fh.write(f"**{c['bet']} BET · {c['edge']} EDGE · {c['pass']} PASS**\n\n")
        for it in card["items"]:
            if it["tier"] == "BET":
                fh.write(f"- {it['action']} ({it['away']} @ {it['home']})\n")
        if c["bet"] == 0:
            fh.write("- No bets this week.\n")
        for n in card["notes"]:
            fh.write(f"\n_{n}_\n")


def run(
    season: Optional[int], week: Optional[int], dry_run: bool, now: Optional[datetime] = None
) -> int:
    """Build + persist; returns the process exit code."""
    now = now or datetime.utcnow()
    if season is None or week is None:
        from beatvegas.season import active

        s, w = active(now)
        season = season or s
        week = week if week is not None else w
    if week is None:
        print(f"[card] no active week for {season} — nothing to build")
        return 0

    with session_scope() as s:
        games = hr_universe(s, season, week)
        snaps, preds, previews = load_inputs(s, [g["game_id"] for g in games])
        card = build_card(games, snaps, preds, previews, season=season, week=week, now=now)
        picks_added = 0
        if not dry_run and card["items"]:
            picks_added = log_paper_picks(s, card, now)
            s.add(
                Card(
                    season=season,
                    week=week,
                    built_at=now,
                    payload=json.dumps(card, ensure_ascii=False, allow_nan=False),
                )
            )

    lines = summary_lines(card, len(games), picks_added)
    print("\n".join(lines))
    if dry_run:
        print(json.dumps(card, indent=2, ensure_ascii=False, allow_nan=False))
    write_step_summary(card, lines)
    if games and not card["items"]:
        print(
            f"[card] ERROR: {len(games)} Hard Rock games this week but zero card items "
            "(all kicked off, or inputs missing) — not publishing an empty card."
        )
        return 1
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, help="default: the current season")
    ap.add_argument("--week", type=int, help="default: beatvegas.season.active()")
    ap.add_argument("--dry-run", action="store_true", help="print the payload; write nothing")
    args = ap.parse_args()
    if not try_init_db():
        return
    sys.exit(run(args.season, args.week, args.dry_run))


if __name__ == "__main__":
    main()
