#!/usr/bin/env python
"""Poll The Odds API for current first-half totals and store snapshots.

Each run captures the current totals_h1 line per (game, book). New snapshots are
written only when the line/prices changed vs the last observation, so the table
becomes a compact movement history; the earliest row per game = posting time.

Run this once or twice a day during the season (later: schedule it).

    python scripts/poll_lines.py
    python scripts/poll_lines.py --season 2025
"""

from __future__ import annotations

import argparse
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from beatvegas.alerts.detect import (
    detect_first_half_posted,
    detect_line_alerts,
    format_alert,
    format_posted_summary,
)
from beatvegas.alerts.imessage import send_imessage
from beatvegas.alerts.push import send_push
from beatvegas.config import load_config
from beatvegas.db.models import Game, OddsSnapshot, Prediction
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import _parse_dt, match_event
from beatvegas.hardrock import BOARD_URL, HR_BOOK_KEYS, pick_hr_line
from beatvegas.lines import consensus_open_close
from beatvegas.season import current_season
from beatvegas.sources.odds import OddsAPIClient, normalize_first_half


def _candidate_games(session, season: int) -> List[Dict]:
    rows = (
        session.query(Game.id, Game.home_team, Game.away_team, Game.start_date)
        .filter(Game.season == season)
        .all()
    )
    return [{"id": r[0], "home_team": r[1], "away_team": r[2], "start_date": r[3]} for r in rows]


def _latest_snapshot(session, game_id: int, book: str):
    return (
        session.query(OddsSnapshot)
        .filter(
            OddsSnapshot.game_id == game_id,
            OddsSnapshot.book == book,
            OddsSnapshot.market == "1H_total",
        )
        .order_by(OddsSnapshot.captured_at.desc())
        .first()
    )


def _changed(prev, line, over, under) -> bool:
    if prev is None:
        return True
    return prev.line != line or prev.over_price != over or prev.under_price != under


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument(
        "--days-ahead",
        type=int,
        default=8,
        help="only pull odds for events kicking off within N days "
        "(conserves credits; 1H totals only post game-week)",
    )
    ap.add_argument(
        "--max-events",
        type=int,
        default=80,
        help="hard cap on per-event odds calls (credit safety)",
    )
    ap.add_argument(
        "--dry-run-alerts", action="store_true", help="print alerts instead of sending iMessages"
    )
    ap.add_argument("--no-alerts", action="store_true", help="disable alerts")
    ap.add_argument(
        "--push",
        action="store_true",
        help="send a cloud push when Hard Rock POSTS new 1H lines (the mid-week trigger)",
    )
    args = ap.parse_args()

    if not try_init_db():
        return
    cfg = load_config().get("odds_api", {}) or {}
    client = OddsAPIClient()

    # 1) Free: list events, then keep only those in the upcoming window.
    now = datetime.utcnow()
    horizon = now + timedelta(days=args.days_ahead)
    all_events = client.list_events()
    in_window = []
    for ev in all_events:
        dt = _parse_dt(ev.get("commence_time"))
        if dt is None or now - timedelta(days=1) <= dt <= horizon:
            in_window.append(ev)
    in_window = in_window[: args.max_events]

    # 2) Paid (1 credit/event): fetch totals_h1 per event, normalize.
    rows = []
    for ev in in_window:
        data = client.event_first_half_totals(ev["id"])
        if data:
            rows.extend(normalize_first_half([data], books=cfg.get("books") or None))
    written = matched = unmatched = skipped = 0
    unmatched_names = []
    this_poll_lines: Dict[int, List[float]] = {}
    prev_consensus: Dict[int, Optional[float]] = {}
    hr_rows: Dict[int, Dict[str, float]] = {}  # gid -> {hr_book: 1H line}
    matchups: Dict[int, str] = {}
    scores: Dict[int, int] = {}
    alert_msgs: List[str] = []

    with session_scope() as s:
        games = _candidate_games(s, args.season)
        meta = {g["id"]: g for g in games}
        # Games that ALREADY had a Hard Rock 1H line (first-appearance detection).
        hr_prev_ids = {
            gid
            for (gid,) in s.query(OddsSnapshot.game_id)
            .filter(
                OddsSnapshot.market == "1H_total",
                OddsSnapshot.book.in_(HR_BOOK_KEYS),
            )
            .distinct()
        }
        for r in rows:
            gid, _score = match_event(r["home_team"], r["away_team"], r["commence_time"], games)
            if gid is None:
                unmatched += 1
                unmatched_names.append(f"{r['away_team']} @ {r['home_team']}")
                continue
            matched += 1
            # consensus-before-this-poll (latest per book), computed once per game
            if gid not in prev_consensus:
                existing = (
                    s.query(OddsSnapshot)
                    .filter(OddsSnapshot.game_id == gid, OddsSnapshot.market == "1H_total")
                    .all()
                )
                prev_consensus[gid] = consensus_open_close(existing)[1]
                g = meta.get(gid, {})
                matchups[gid] = f"{g.get('away_team')} @ {g.get('home_team')}"
                pred = (
                    s.query(Prediction.under_score)
                    .filter(Prediction.game_id == gid)
                    .order_by(Prediction.created_at.desc())
                    .first()
                )
                if pred and pred[0] is not None:
                    scores[gid] = int(pred[0])
            this_poll_lines.setdefault(gid, []).append(r["line"])
            if r["book"] in HR_BOOK_KEYS:
                hr_rows.setdefault(gid, {})[r["book"]] = r["line"]

            prev = _latest_snapshot(s, gid, r["book"])
            if not _changed(prev, r["line"], r["over_price"], r["under_price"]):
                skipped += 1
                continue
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book=r["book"],
                    market="1H_total",
                    line=r["line"],
                    over_price=r["over_price"],
                    under_price=r["under_price"],
                    captured_at=now,
                )
            )
            written += 1

    # --- alerts: newly-posted + significant consensus moves ---
    new_consensus = {gid: statistics.median(ls) for gid, ls in this_poll_lines.items() if ls}
    acfg = load_config().get("alerts", {}) or {}
    threshold = float(acfg.get("line_move_threshold", 1.0))
    recipient = acfg.get("imessage_to", "")
    if not args.no_alerts:
        alerts = detect_line_alerts(
            prev_consensus, new_consensus, matchups, threshold=threshold, scores=scores
        )
        for a in alerts:
            msg = format_alert(a)
            alert_msgs.append(msg)
            if args.dry_run_alerts or not recipient:
                print(f"[alert] {msg}" + ("" if recipient else "  (no recipient set)"))
            else:
                ok, detail = send_imessage(recipient, msg)
                print(f"[alert {'sent' if ok else 'FAILED: ' + detail}] {msg}")

    # --- cloud push: Hard Rock 1H lines newly posted (the mid-week trigger) ---
    if args.push:
        hr_new = {
            gid: line for gid, bl in hr_rows.items() if (line := pick_hr_line(bl)) is not None
        }
        posted = detect_first_half_posted(hr_prev_ids, hr_new, matchups)
        pmsg = format_posted_summary(posted)
        if not pmsg:
            print(f"[push] no newly-posted Hard Rock 1H lines ({len(hr_new)} HR lines seen)")
        elif args.dry_run_alerts:
            print(f"[push] {pmsg}")
        else:
            ok, detail = send_push("Beat Vegas", pmsg, url=BOARD_URL)
            print(f"[push {'sent' if ok else 'FAILED: ' + detail}] {pmsg}")

    c = client.last_credits
    print(
        f"events_total={len(all_events)} in_window={len(in_window)} "
        f"odds_rows={len(rows)} matched={matched} unmatched={unmatched} "
        f"new_snapshots={written} unchanged={skipped} alerts={len(alert_msgs)}"
    )
    if c:
        print(f"credits: remaining={c.remaining} used={c.used} last_cost={c.last_cost}")
    if unmatched_names:
        uniq = sorted(set(unmatched_names))
        print(f"unmatched events ({len(uniq)}): {uniq[:10]}" + (" ..." if len(uniq) > 10 else ""))
        if not games:
            print(
                "  (no games loaded for this season yet — run backfill --season "
                f"{args.season} first)"
            )


if __name__ == "__main__":
    main()
