#!/usr/bin/env python
"""Poll for full-game totals + spreads and store snapshots (the OPENER engine).

Full-game totals open Sunday; retail 1H totals post later. We capture the
full-game opener (earliest snapshot per game/book/market = a genuine opener) and
keep Game.spread/full_game_total current so the slate can be scored + ranked
before the retail 1H market exists.

Sources (`--source`):
  dk      — DraftKings hidden API (free, fresh; may 403 datacenter IPs)
  cfbd    — CFBD /lines (key-based, reachable from anywhere incl. GitHub Actions)
  oddsapi — The Odds API bulk /odds (MULTI-BOOK incl. Hard Rock; cloud-safe; the
            source for the HR-vs-market comparison + the HR-line-drop alert)
  auto    — try DK, fall back to CFBD if DK returns nothing (default)

    python scripts/poll_full_game.py                      # auto, local
    python scripts/poll_full_game.py --source cfbd        # cloud-safe, one book
    python scripts/poll_full_game.py --source oddsapi     # multi-book incl. Hard Rock
    python scripts/poll_full_game.py --season 2026 --notify

Pair with scripts/poll_lines.py (The Odds API) for cross-book 1H consensus + close.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from beatvegas.alerts.detect import detect_full_game_posted, format_posted_summary
from beatvegas.alerts.imessage import send_imessage
from beatvegas.alerts.push import push_configured, send_push
from beatvegas.config import load_config
from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import _parse_dt, match_event
from beatvegas.hardrock import BOARD_URL, HR_BOOK_KEYS, normalize_book, pick_hr_line
from beatvegas.season import current_season
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.cfbd_lines import full_game_rows as cfbd_full_game_rows
from beatvegas.sources.draftkings import (
    DraftKingsClient,
    normalize_first_half,
    normalize_full_game,
)
from beatvegas.sources.odds import OddsAPIClient
from beatvegas.sources.odds import normalize_full_game as oa_normalize_full_game


def _candidate_games(session, season: int) -> List[Dict]:
    rows = (
        session.query(Game.id, Game.home_team, Game.away_team, Game.start_date)
        .filter(Game.season == season)
        .all()
    )
    return [{"id": r[0], "home_team": r[1], "away_team": r[2], "start_date": r[3]} for r in rows]


def _latest_snapshot(session, game_id: int, book: str, market: str):
    return (
        session.query(OddsSnapshot)
        .filter(
            OddsSnapshot.game_id == game_id,
            OddsSnapshot.book == book,
            OddsSnapshot.market == market,
        )
        .order_by(OddsSnapshot.captured_at.desc())
        .first()
    )


def _changed(prev, line, spread, over, under) -> bool:
    if prev is None:
        return True
    # spread=None means the source doesn't carry one (Odds API totals rows), not
    # that it moved — otherwise every DK->oddsapi source switch would write a
    # redundant snapshot for an unchanged number.
    spread_moved = spread is not None and prev.spread != spread
    return prev.line != line or spread_moved or prev.over_price != over or prev.under_price != under


def _normalize_books(rows: List[Dict]) -> List[Dict]:
    """Canonical book key on every row before it can reach odds_snapshots
    (one spelling per book, or medians double-count it)."""
    for r in rows:
        if "book" in r:
            r["book"] = normalize_book(r["book"])
    return rows


def _fetch(
    source: str, season: int, regions: str = "us,us2", credit_floor: int = 60
) -> Tuple[List[Dict], List[Dict], str, int]:
    """Return (full_game_rows, first_half_rows, source_used, event_count)."""
    fg, h1, used, n = _fetch_raw(source, season, regions, credit_floor)
    return _normalize_books(fg), _normalize_books(h1), used, n


def _fetch_raw(
    source: str, season: int, regions: str, credit_floor: int
) -> Tuple[List[Dict], List[Dict], str, int]:
    dk_events = 0
    if source == "oddsapi":
        # Bulk /odds: multi-book full-game totals incl. Hard Rock (us2). The
        # rows carry team names + commence_time, so they match by name+time like
        # the DK path (no CFBD game id). 1H is captured separately (poll_lines).
        client = OddsAPIClient()
        # list_events is FREE but returns the credit headers: learn the balance
        # before the paid bulk call so a reserve floor can stop it.
        client.list_events()
        if client.credits_low(credit_floor):
            print(
                f"[credits] Odds API credits at reserve floor "
                f"({client.last_credits.remaining} <= {credit_floor}) — skipping the "
                "full-game pull. Pass --credit-floor 0 to override."
            )
            return [], [], "oddsapi", 0
        events = client.list_full_game_totals(regions=regions)
        return oa_normalize_full_game(events), [], "oddsapi", len(events)
    h1: List[Dict] = []
    if source in ("dk", "auto"):
        payload = DraftKingsClient().fetch_ncaaf()
        dk_events = len(payload.get("events", []) or [])
        fg = normalize_full_game(payload)
        h1 = normalize_first_half(payload)
        if fg or source == "dk":
            return fg, h1, "dk", dk_events
    # cfbd (explicit, or auto-fallback when DK returned no FULL-GAME rows).
    # Keep any DK 1H rows: they're already fetched and CFBD carries no 1H.
    fg = cfbd_full_game_rows(CFBDClient(), season)
    return fg, h1, "cfbd", dk_events


# Which book's number to trust for Game.full_game_total / Game.spread when one
# run carries several (multi-book oddsapi pulls): DK (sharp, fresh) beats CFBD's
# consensus, which beats everything else. Lowercased so it covers both DK-API
# "draftkings" and CFBD-provider "DraftKings" spellings.
_BOOK_PRIORITY = {"draftkings": 0, "consensus": 1}


def _book_rank(book: Optional[str]) -> int:
    return _BOOK_PRIORITY.get((book or "").lower(), len(_BOOK_PRIORITY))


def _resolve_gid(r: Dict, games: List[Dict], ids: set) -> Optional[int]:
    """CFBD rows carry the game id directly; DK rows match on name + time."""
    if r.get("game_id") is not None:
        return r["game_id"] if r["game_id"] in ids else None
    gid, _ = match_event(r["home_team"], r["away_team"], r["commence_time"], games)
    return gid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument(
        "--source",
        choices=("dk", "cfbd", "oddsapi", "auto"),
        default="auto",
        help="opener source; auto=DK then CFBD fallback; oddsapi=multi-book incl. Hard Rock",
    )
    ap.add_argument(
        "--regions",
        default="us,us2",
        help="Odds API regions for --source oddsapi (us2 carries Hard Rock FL)",
    )
    ap.add_argument(
        "--days-ahead", type=int, default=8, help="only store odds for events within N days"
    )
    ap.add_argument(
        "--credit-floor",
        type=int,
        default=60,
        help="--source oddsapi only: skip the paid pull once remaining monthly "
        "credits are at this floor (same reserve poll_lines honours); 0 disables",
    )
    ap.add_argument(
        "--notify",
        action="store_true",
        help="send a single 'DK fired' iMessage when done (no picks)",
    )
    ap.add_argument(
        "--push",
        action="store_true",
        help="send a cloud push when Hard Rock POSTS new full-game lines (the opener trigger)",
    )
    ap.add_argument(
        "--dry-run-alerts", action="store_true", help="print the notification instead of sending it"
    )
    args = ap.parse_args()

    # Preflight BEFORE spending API credits or writing snapshots: a --push run
    # with no working push config would consume the first-appearance alert
    # state and then silently fail to notify — the worst possible outcome.
    if args.push and not args.dry_run_alerts and not push_configured():
        print(
            "[push] FATAL: --push requested but push is not configured "
            "(set PUSHOVER_TOKEN/PUSHOVER_USER or config.yaml push:). "
            "Refusing to capture, so the alert can still fire once configured."
        )
        sys.exit(2)

    if not try_init_db():
        return

    fg_rows, h1_rows, source, dk_events = _fetch(
        args.source, args.season, args.regions, credit_floor=args.credit_floor
    )

    now = datetime.utcnow()
    horizon = now + timedelta(days=args.days_ahead)

    def _in_window(r) -> bool:
        dt = _parse_dt(r.get("commence_time"))
        return dt is None or now - timedelta(days=1) <= dt <= horizon

    fg_rows = [r for r in fg_rows if _in_window(r)]
    h1_rows = [r for r in h1_rows if _in_window(r)]

    written_fg = written_h1 = matched = unmatched = skipped = games_updated = 0
    unmatched_names: List[str] = []
    matched_gids = set()
    hr_rows: Dict[int, Dict[str, float]] = {}  # gid -> {hr_book: line}
    matchups: Dict[int, str] = {}
    best_row: Dict[int, Dict] = {}  # gid -> highest-priority book's row this run

    with session_scope() as s:
        games = _candidate_games(s, args.season)
        ids = {g["id"] for g in games}

        # Games that ALREADY had a Hard Rock full-game line (for first-appearance
        # detection) — captured before we insert this run's rows.
        hr_prev_ids = {
            gid
            for (gid,) in s.query(OddsSnapshot.game_id)
            .filter(
                OddsSnapshot.market == "full_game_total",
                OddsSnapshot.book.in_(HR_BOOK_KEYS),
            )
            .distinct()
        }

        # One snapshot per (game, book) per run: two feed events can resolve to
        # the same game (seen live with us_ex: Idaho @ Utah listed twice), and a
        # second row with the same captured_at violates uq_odds_snapshot.
        seen_fg: set = set()
        for r in fg_rows:
            gid = _resolve_gid(r, games, ids)
            if gid is None:
                unmatched += 1
                unmatched_names.append(f"{r['away_team']} @ {r['home_team']}")
                continue
            if (gid, r["book"]) in seen_fg:
                skipped += 1
                continue
            seen_fg.add((gid, r["book"]))
            matched += 1
            matched_gids.add(gid)
            if r["book"] in HR_BOOK_KEYS:
                hr_rows.setdefault(gid, {})[r["book"]] = r["line"]
                matchups[gid] = f"{r['away_team']} @ {r['home_team']}"
            prev = _latest_snapshot(s, gid, r["book"], "full_game_total")
            # A game's FIRST snapshot is its opener: prefer the source's true
            # opening number when it carries one (CFBD `overUnderOpen`) so the
            # fallback path doesn't mislabel a current/closing number as the
            # opener and corrupt open->close CLV. Later snapshots track current.
            line = r["line"]
            if prev is None and r.get("line_open") is not None:
                line = r["line_open"]
            if _changed(prev, line, r.get("spread"), r["over_price"], r["under_price"]):
                s.add(
                    OddsSnapshot(
                        game_id=gid,
                        book=r["book"],
                        market="full_game_total",
                        line=line,
                        spread=r.get("spread"),
                        over_price=r["over_price"],
                        under_price=r["under_price"],
                        captured_at=now,
                    )
                )
                written_fg += 1
            else:
                skipped += 1
            # Remember the best-book row per game (not feed order): the Game
            # update below must not depend on which book happened to come last.
            cur = best_row.get(gid)
            if cur is None or _book_rank(r["book"]) < _book_rank(cur["book"]):
                best_row[gid] = {**r, "line": line}

        # Keep each game's spread current and fill total only if missing, so an
        # upcoming slate is scorable before CFBD posts its closing number — from
        # the highest-priority book this run, not the last row iterated.
        for gid, r in best_row.items():
            g = s.query(Game).filter(Game.id == gid).one_or_none()
            if g is None:
                continue
            if r.get("spread") is not None:
                g.spread = r["spread"]
            if g.full_game_total is None:
                g.full_game_total = r["line"]
                g.full_game_total_book = r["book"]
            games_updated += 1

        seen_h1: set = set()
        for r in h1_rows:
            gid = _resolve_gid(r, games, ids)
            if gid is None or (gid, r["book"]) in seen_h1:
                continue
            seen_h1.add((gid, r["book"]))
            prev = _latest_snapshot(s, gid, r["book"], "1H_total")
            if _changed(prev, r["line"], None, r["over_price"], r["under_price"]):
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
                written_h1 += 1

    print(
        f"source={source} dk_events={dk_events} "
        f"fg_rows={len(fg_rows)} h1_rows={len(h1_rows)} matched={matched} "
        f"unmatched={unmatched} new_fg={written_fg} new_h1={written_h1} "
        f"unchanged={skipped} games_updated={games_updated}"
    )
    if unmatched_names:
        uniq = sorted(set(unmatched_names))
        print(f"unmatched events ({len(uniq)}): {uniq[:10]}" + (" ..." if len(uniq) > 10 else ""))

    if args.push:
        hr_new = {
            gid: line for gid, bl in hr_rows.items() if (line := pick_hr_line(bl)) is not None
        }
        alerts = detect_full_game_posted(hr_prev_ids, hr_new, matchups)
        msg = format_posted_summary(alerts)
        if not msg:
            print(f"[push] no newly-posted Hard Rock full-game lines ({len(hr_new)} HR lines seen)")
        elif args.dry_run_alerts:
            print(f"[push] {msg}")
        else:
            ok, detail = send_push("Beat Vegas", msg, url=BOARD_URL)
            print(f"[push {'sent' if ok else 'FAILED: ' + detail}] {msg}")
            if not ok:
                # Snapshots are already committed (capture must not be lost),
                # so this game won't re-alert — fail the run loudly instead of
                # letting the workflow show green with the alert dropped.
                sys.exit(1)

    if args.notify:
        acfg = load_config().get("alerts", {}) or {}
        recipient = acfg.get("imessage_to", "")
        msg = (
            f"DK poll done — {len(matched_gids)} games captured "
            f"({written_fg} new full-game lines). Board updated."
        )
        if args.dry_run_alerts or not recipient:
            print(f"[notify] {msg}" + ("" if recipient else "  (no recipient set)"))
        elif fg_rows:  # don't text on empty offseason pulls
            ok, detail = send_imessage(recipient, msg)
            print(f"[notify {'sent' if ok else 'FAILED: ' + detail}] {msg}")


if __name__ == "__main__":
    main()
