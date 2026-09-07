#!/usr/bin/env python
"""Build the week's bet card and publish it to the Board (`cards` table).

Runs in GitHub Actions (`.github/workflows/card.yml`: weeknight + Friday preview
builds, then the Saturday-morning FINAL ~8:05-8:45am ET; slots in
beatvegas/ci.py). Pure rules live in beatvegas/card.py; this script only loads
the inputs, writes one `cards` row per build (history; the newest row is the
live card) and logs every QUALIFYING game (Hard Rock's 1H line >= BET_GAP_PTS
above ours, any tier) as a PAPER pick tagged with its blocker, through the same
code path as `pick.py add` (beatvegas.picks.add_pick), never twice for one game.

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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from beatvegas.card import REFERENCE_MODEL_VERSION, build_card
from beatvegas.db.models import Card, Game, GamePreview, ManualPick, OddsSnapshot, Prediction
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.hardrock import HR_BOOK_KEY, hr_universe_game_ids
from beatvegas.model.score import MODEL_VERSION
from beatvegas.picks import add_pick, existing_pick


def hr_universe(session, season: int, week: int) -> List[Dict]:
    """The week's games Hard Rock has priced a full-game total on, as card rows."""
    ids = hr_universe_game_ids(session, season, week)
    if not ids:
        return []
    rows = session.query(Game).filter(Game.id.in_(ids)).order_by(Game.start_date, Game.id).all()
    return [
        {
            "game_id": g.id,
            "away": g.away_team,
            "home": g.home_team,
            "kick": g.start_date,
            "total": g.full_game_total,
            "spread": g.spread,
        }
        for g in rows
    ]


def bet_slots_this_week(session, season: int, week: int) -> Set[int]:
    """Game ids with a BET-verdict 1H pick already logged this week (paper or
    real; over-cap paper picks excluded). They hold their cap slot."""
    rows = (
        session.query(ManualPick.game_id)
        .filter(
            ManualPick.season == season,
            ManualPick.week == week,
            (ManualPick.market == "1H") | (ManualPick.market.is_(None)),
            ManualPick.verdict_at_pick == "BET",
            (ManualPick.blocker.is_(None)) | (ManualPick.blocker == "none"),
            ManualPick.game_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def real_bets_this_week(session, season: int, week: int) -> Set[int]:
    """Game ids with a REAL (is_paper False, or legacy NULL) 1H pick this week.
    Passed to build_card as prior_bet_game_ids: a real ticket on a game NOT on
    this card (a Thursday game already played) consumes a weekly-cap slot;
    apply_weekly_cap ignores ids that are on the card (they rank via `held`)."""
    rows = (
        session.query(ManualPick.game_id)
        .filter(
            ManualPick.season == season,
            ManualPick.week == week,
            (ManualPick.is_paper.is_(False)) | (ManualPick.is_paper.is_(None)),
            (ManualPick.market == "1H") | (ManualPick.market.is_(None)),
            ManualPick.game_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


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


PAPER_VERDICT = {"BET": "BET", "EDGE": "WATCH", "PASS": "PASS"}


def log_paper_picks(
    session, card: Dict, now: datetime, window_hours: Optional[float] = None
) -> int:
    """Insert one PAPER pick per QUALIFYING item (Hard Rock's 1H line >=
    BET_GAP_PTS above ours — any tier) that has no paper pick yet, tagged with
    the gate that blocked a real bet (`blocker`: none = BET, price, off_market,
    no_fair_price, qb_out, cap). Tate's real ticket on the same game never blocks it and is
    never blocked by it (per-ledger guard). `window_hours` restricts logging to
    games kicking off within that many hours (the DECISION build for that game:
    Thursday/Friday evening for weeknight games, Saturday morning for the
    Saturday slate). Marks `paper_logged`. Returns the number inserted."""
    inserted = 0
    for it in card["items"]:
        if not it.get("qualifies"):
            continue
        if window_hours is not None and it.get("kick"):
            kick = datetime.fromisoformat(it["kick"].replace("Z", "+00:00")).replace(tzinfo=None)
            if kick - now > timedelta(hours=window_hours):
                continue
        gid = it["game_id"]
        if existing_pick(session, gid, "1H", is_paper=True) is not None:
            it["paper_logged"] = True
            continue
        blocker = "cap" if it.get("over_cap") else (it.get("paper_blocker") or "none")
        # Display chips + the market read frozen at the pick, so the post-mortem
        # can slice by them even after the lines move (never gates).
        chips = {
            k: it.get(k)
            for k in (
                "total_band",
                "hook_side",
                "key_dist",
                "full_game_total",
                "spread",
                "hr_vs_market",
                "fair_source",
                "fair_under",
                "market_line",
            )
        }
        chips.update({"tier": it["tier"], "cap_rank": it.get("cap_rank")})
        add_pick(
            session,
            game_id=gid,
            season=card["season"],
            week=card["week"],
            home_team=it["home"],
            away_team=it["away"],
            market="1H",
            line=it["hr_line"],
            price=it["hr_price"],  # None when Hard Rock has not priced the line yet
            is_paper=True,
            book=HR_BOOK_KEY,
            note=f"card {now:%Y-%m-%d} [{blocker}]: {it['action']}",
            reason="model_gap",
            verdict=PAPER_VERDICT[it["tier"]],
            gap=it["gap"],
            ev=it["ev"],
            hr_line=it["hr_line"],
            placed_at=now,
            blocker=blocker,
            factors_json=json.dumps(chips, ensure_ascii=False, allow_nan=False),
        )
        it["paper_logged"] = True
        inserted += 1
    return inserted


def _kill_text(it: Dict) -> str:
    parts = []
    if it.get("kill_line") is not None:
        parts.append(f"below u{it['kill_line']}")
    if it.get("kill_price") is not None:
        parts.append(f"worse than {it['kill_price']:+d}")
    return f" | kill: {' or '.join(parts)}" if parts else ""


def summary_lines(card: Dict, universe: int, picks_added: int) -> List[str]:
    c = card["counts"]
    paper = card.get("paper", {})
    out = [
        f"Card {card['season']} wk{card['week']} built {card['built_at']}: "
        f"{c['bet']} BET / {c['edge']} EDGE / {c['pass']} PASS "
        f"({len(card['items'])} of {universe} Hard Rock games still to kick off; "
        f"model read: {'yes' if card['model_read'] else 'no'}; "
        f"qualifying: {paper.get('qualifying', 0)}; paper picks added: {picks_added})"
    ]
    for it in card["items"]:
        if it["tier"] == "BET" and not it.get("over_cap"):
            price = f" {it['hr_price']:+d}" if it["hr_price"] is not None else ""
            out.append(
                f"  BET #{it.get('cap_rank')}  {it['away']} @ {it['home']}: 1H under {it['hr_line']}{price} "
                f"(gap {it['gap']:+.2f}, ev {it['ev'] if it['ev'] is not None else 'n/a'})"
                f"{_kill_text(it)}"
            )
    for it in card["items"]:
        if it.get("over_cap"):
            out.append(
                f"  OVER CAP #{it.get('cap_rank')} {it['away']} @ {it['home']}: 1H under "
                f"{it['hr_line']} (gap {it['gap']:+.2f}) — paper only"
            )
    for it in card["items"]:
        if it["tier"] == "EDGE":
            out.append(f"  EDGE {it['away']} @ {it['home']} [{it['blocker']}]: {it['action']}")
    logged = [it for it in card["items"] if it.get("paper_logged")]
    if logged:
        out.append("  PAPER (qualifying games logged, by blocker):")
        for it in logged:
            b = "cap" if it.get("over_cap") else (it.get("paper_blocker") or "none")
            out.append(
                f"    [{b}] {it['away']} @ {it['home']} u{it['hr_line']} gap {it['gap']:+.2f}"
            )
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
            if it["tier"] == "BET" and not it.get("over_cap"):
                fh.write(f"- {it['action']} ({it['away']} @ {it['home']}){_kill_text(it)}\n")
        if c["bet"] == 0:
            fh.write("- No bets this week.\n")
        over = [it for it in card["items"] if it.get("over_cap")]
        if over:
            fh.write("\nOver the weekly cap (paper only): ")
            fh.write(", ".join(f"{it['away']} @ {it['home']} u{it['hr_line']}" for it in over))
            fh.write("\n")
        for n in card["notes"]:
            fh.write(f"\n_{n}_\n")


def run(
    season: Optional[int],
    week: Optional[int],
    dry_run: bool,
    now: Optional[datetime] = None,
    *,
    paper_window_hours: Optional[float] = None,
    no_paper: bool = False,
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
        held = bet_slots_this_week(s, season, week)
        real = real_bets_this_week(s, season, week)
        card = build_card(
            games,
            snaps,
            preds,
            previews,
            season=season,
            week=week,
            now=now,
            held_game_ids=held,
            prior_bet_game_ids=real,
        )
        picks_added = 0
        if not dry_run and card["items"]:
            if not no_paper:
                picks_added = log_paper_picks(s, card, now, window_hours=paper_window_hours)
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
    ap.add_argument(
        "--paper-log-window-hours",
        type=float,
        default=None,
        dest="paper_window_hours",
        help="paper-log only qualifying games kicking off within N hours (the decision "
        "build for those games); default: every upcoming qualifying game",
    )
    ap.add_argument(
        "--no-paper",
        action="store_true",
        dest="no_paper",
        help="publish the card without logging paper picks (preview builds)",
    )
    args = ap.parse_args()
    if not try_init_db():
        return
    sys.exit(
        run(
            args.season,
            args.week,
            args.dry_run,
            paper_window_hours=args.paper_window_hours,
            no_paper=args.no_paper,
        )
    )


if __name__ == "__main__":
    main()
