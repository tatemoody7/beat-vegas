#!/usr/bin/env python
"""Poll for full-game totals, spreads and moneylines and store snapshots (the OPENER engine).

Full-game totals open Sunday; retail 1H totals post later. We capture the
full-game opener (earliest snapshot per game/book/market = a genuine opener) and
keep Game.spread (cross-book median) current and fill Game.full_game_total once,
tagging both with the source so Monday's CFBD upsert leaves them alone
(beatvegas/line_sources.py). The slate is scorable before the retail 1H market
exists.

Sources (`--source`):
  dk      — DraftKings hidden API (free, fresh; may 403 datacenter IPs)
  cfbd    — CFBD /lines (key-based, reachable from anywhere incl. GitHub Actions)
  oddsapi — The Odds API bulk /odds, `totals,spreads,h2h` (MULTI-BOOK incl. Hard Rock;
            cloud-safe; the source for the HR-vs-market comparison; prod runs this
            from sunday.yml, the card-day refresh in card.yml and every close tick
            in lines_watch.yml). Besides the `full_game_total` rows it writes each
            book's spread (`full_game_spread`) and moneyline (`full_game_ml`) with
            both teams' prices (roadmap step 4, 2026-10-07).
  auto    — try DK, fall back to CFBD if DK returns nothing (default)

    python scripts/poll_full_game.py                      # auto, local
    python scripts/poll_full_game.py --source cfbd        # cloud-safe, one book
    python scripts/poll_full_game.py --source oddsapi     # multi-book incl. Hard Rock

Pair with scripts/poll_lines.py (The Odds API) for cross-book 1H consensus + close.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from beatvegas.ci import warn
from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import _parse_dt, match_event
from beatvegas.hardrock import normalize_book
from beatvegas.season import current_season
from beatvegas.snapshots_provenance import feed_stamp_for, note_reseen
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.cfbd_lines import full_game_rows as cfbd_full_game_rows
from beatvegas.sources.draftkings import (
    DraftKingsClient,
    normalize_first_half,
    normalize_full_game,
)
from beatvegas.sources.odds import SIDE_MARKETS, OddsAPIClient, normalize_full_game_sides
from beatvegas.sources.odds import normalize_full_game as oa_normalize_full_game


def _candidate_games(session, season: int) -> List[Dict]:
    rows = (
        session.query(Game.id, Game.home_team, Game.away_team, Game.start_date)
        .filter(Game.season == season)
        .all()
    )
    return [{"id": r[0], "home_team": r[1], "away_team": r[2], "start_date": r[3]} for r in rows]


# The bulk /odds markets every Odds API pull asks for: the Sunday opener, the
# card-day refresh and (since 2026-10-07, roadmap step 4) every close tick, so
# the spread and the moneyline have a multi-book close as well as the total.
# Billed (markets x regions) for the whole slate: 9 credits on us,us2,us_ex.
DEFAULT_MARKETS = "totals,spreads,h2h"


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


def _changed(prev, line, spread, over, under, home=None, away=None) -> bool:
    if prev is None:
        return True
    # spread=None means the source doesn't carry one (Odds API totals rows), not
    # that it moved — otherwise every DK->oddsapi source switch would write a
    # redundant snapshot for an unchanged number.
    spread_moved = spread is not None and prev.spread != spread
    # A side-market row (spread / moneyline) moves on either team's price; a
    # totals row carries neither, so both sides compare None == None.
    side_moved = (
        getattr(prev, "home_price", None) != home or getattr(prev, "away_price", None) != away
    )
    return (
        prev.line != line
        or spread_moved
        or prev.over_price != over
        or prev.under_price != under
        or side_moved
    )


def _normalize_books(rows: List[Dict]) -> List[Dict]:
    """Canonical book key on every row before it can reach odds_snapshots
    (one spelling per book, or medians double-count it)."""
    for r in rows:
        if "book" in r:
            r["book"] = normalize_book(r["book"])
    return rows


def _fetch(
    source: str,
    season: int,
    regions: str = "us,us2",
    credit_floor: int = 60,
    markets: str = DEFAULT_MARKETS,
) -> Tuple[List[Dict], List[Dict], str, int]:
    """Return (full_game_rows, first_half_rows, source_used, event_count).

    The Odds API's full-game rows also carry the side-market rows (spread,
    moneyline), told apart by their `market` key; main() splits them."""
    fg, h1, used, n = _fetch_raw(source, season, regions, credit_floor, markets)
    return _normalize_books(fg), _normalize_books(h1), used, n


def _fetch_raw(
    source: str, season: int, regions: str, credit_floor: int, markets: str = DEFAULT_MARKETS
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
            warn(
                f"Odds API credits at reserve floor "
                f"({client.last_credits.remaining} <= {credit_floor}) — skipping the "
                "full-game pull. Pass --credit-floor 0 to override."
            )
            return [], [], "oddsapi", 0
        # Billed (markets x regions) for the whole slate: `totals,spreads,h2h`
        # x `us,us2,us_ex` = 9 credits (the Sunday opener, the card-day refresh
        # and every close tick since 2026-10-07).
        events = client.list_full_game_odds(regions=regions, markets=markets)
        c = getattr(client, "last_credits", None)
        if c is not None:
            print(
                f"credits: markets={markets} regions={regions} "
                f"spent={c.last_cost if c.last_cost is not None else 'unknown'} "
                f"remaining={c.remaining if c.remaining is not None else 'unknown'}"
            )
        rows = oa_normalize_full_game(events) + normalize_full_game_sides(events)
        return rows, [], "oddsapi", len(events)
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


def _consensus_spread(rows: List[Dict]) -> Optional[float]:
    """Median home-relative spread across this run's books for one game; None
    when no book carried one (single-book sources still work: median of one)."""
    vals = [float(r["spread"]) for r in rows if r.get("spread") is not None]
    return statistics.median(vals) if vals else None


def _resolve_gid(r: Dict, games: List[Dict], ids: set) -> Optional[int]:
    """CFBD rows carry the game id directly; DK rows match on name + time."""
    if r.get("game_id") is not None:
        return r["game_id"] if r["game_id"] in ids else None
    gid, _ = match_event(r["home_team"], r["away_team"], r["commence_time"], games)
    return gid


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
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
        "--markets",
        default=DEFAULT_MARKETS,
        help="--source oddsapi only: bulk /odds markets, billed (markets x regions) "
        "for the whole slate; `totals` alone halves a close tick's cost",
    )
    ap.add_argument(
        "--kickoff-within-min",
        type=int,
        default=None,
        help="keep only events kicking off within N minutes from now (the Saturday "
        "full-game close ticks: 180 = lines.REAL_FG_CLOSE_WINDOW_H); the bulk "
        "response is the whole slate, so the filter costs nothing",
    )
    ap.add_argument(
        "--allow-empty",
        action="store_true",
        help="exit 0 when no row was captured (a close tick with no full-game event "
        "due is a normal state inside the 1H close job, not a dead feed)",
    )
    args = ap.parse_args(argv)

    if not try_init_db():
        return

    fg_rows, h1_rows, source, dk_events = _fetch(
        args.source,
        args.season,
        args.regions,
        credit_floor=args.credit_floor,
        markets=args.markets,
    )

    now = datetime.utcnow()
    horizon = now + timedelta(days=args.days_ahead)
    if args.kickoff_within_min is not None:
        horizon = min(horizon, now + timedelta(minutes=args.kickoff_within_min))

    def _in_window(r) -> bool:
        dt = _parse_dt(r.get("commence_time"))
        if dt is None:
            return True
        lo = now if args.kickoff_within_min is not None else now - timedelta(days=1)
        return lo <= dt <= horizon

    fg_rows = [r for r in fg_rows if _in_window(r)]
    h1_rows = [r for r in h1_rows if _in_window(r)]
    # The side markets ride in the same list from the Odds API (tagged with
    # `market`); the totals rows below never carry one.
    side_rows = [r for r in fg_rows if r.get("market") in SIDE_MARKETS.values()]
    fg_rows = [r for r in fg_rows if r.get("market") is None]

    written_fg = written_h1 = matched = unmatched = skipped = games_updated = 0
    written_side = {m: 0 for m in SIDE_MARKETS.values()}
    unmatched_names: List[str] = []
    best_row: Dict[int, Dict] = {}  # gid -> highest-priority book's row this run
    rows_by_gid: Dict[int, List[Dict]] = {}  # gid -> every matched book row this run

    with session_scope() as s:
        games = _candidate_games(s, args.season)
        ids = {g["id"] for g in games}

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
            prev = _latest_snapshot(s, gid, r["book"], "full_game_total")
            # A game's FIRST snapshot is its opener: prefer the source's true
            # opening number when it carries one (CFBD `overUnderOpen`) so the
            # fallback path doesn't mislabel a current/closing number as the
            # opener and corrupt open->close CLV. Later snapshots track current.
            line = r["line"]
            if prev is None and r.get("line_open") is not None:
                line = r["line_open"]
            stamp = feed_stamp_for(r, now)
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
                        event_id=r.get("event_id"),
                        feed_updated_at=stamp,
                    )
                )
                written_fg += 1
            else:
                # An unchanged number is a CONFIRMATION of the line at `now`:
                # stamp it (poll_lines does the same) so a Saturday close tick
                # that finds Sunday's number still standing turns that row into
                # a real pre-kick close (lines.closing_before_kickoff reads
                # last_seen_at; grade._closings_fg and lines.real_closes window
                # on it). Without this, an unmoved full-game line could never
                # grade as a close inside REAL_FG_CLOSE_WINDOW_H.
                prev.last_seen_at = now
                note_reseen(prev, stamp)
                skipped += 1
            # Remember the best-book row per game (not feed order): the Game
            # update below must not depend on which book happened to come last.
            cur = best_row.get(gid)
            if cur is None or _book_rank(r["book"]) < _book_rank(cur["book"]):
                best_row[gid] = {**r, "line": line}
            rows_by_gid.setdefault(gid, []).append(r)

        # Keep each game's spread current (cross-book median this run) and fill
        # the total only if missing, so an upcoming slate is scorable before
        # CFBD posts its closing number — the total comes from the
        # highest-priority book this run, not the last row iterated. Both are
        # tagged with `source` so Monday's CFBD upsert leaves them alone.
        for gid, r in best_row.items():
            g = s.query(Game).filter(Game.id == gid).one_or_none()
            if g is None:
                continue
            sp = _consensus_spread(rows_by_gid.get(gid, []))
            if sp is not None:
                g.spread = sp
                g.spread_source = source
            if g.full_game_total is None:
                g.full_game_total = r["line"]
                g.full_game_total_book = r["book"]
                g.full_game_total_source = source
            games_updated += 1

        # Spread and moneyline rows: written on change, re-seen otherwise, one
        # per (game, book, market) per run. They never touch Game.spread or
        # the full_game_total rows (whose own `spread` column the existing
        # readers keep using).
        seen_side: set = set()
        for r in side_rows:
            gid = _resolve_gid(r, games, ids)
            if gid is None or (gid, r["book"], r["market"]) in seen_side:
                continue
            seen_side.add((gid, r["book"], r["market"]))
            prev = _latest_snapshot(s, gid, r["book"], r["market"])
            home, away = r.get("home_price"), r.get("away_price")
            stamp = feed_stamp_for(r, now)
            if _changed(prev, r["line"], None, None, None, home=home, away=away):
                s.add(
                    OddsSnapshot(
                        game_id=gid,
                        book=r["book"],
                        market=r["market"],
                        line=r["line"],
                        home_price=home,
                        away_price=away,
                        captured_at=now,
                        event_id=r.get("event_id"),
                        feed_updated_at=stamp,
                    )
                )
                written_side[r["market"]] += 1
            else:
                prev.last_seen_at = now
                note_reseen(prev, stamp)

        seen_h1: set = set()
        for r in h1_rows:
            gid = _resolve_gid(r, games, ids)
            if gid is None or (gid, r["book"]) in seen_h1:
                continue
            seen_h1.add((gid, r["book"]))
            prev = _latest_snapshot(s, gid, r["book"], "1H_total")
            stamp = feed_stamp_for(r, now)
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
                        event_id=r.get("event_id"),
                        feed_updated_at=stamp,
                    )
                )
                written_h1 += 1
            else:
                prev.last_seen_at = now
                note_reseen(prev, stamp)

    print(
        f"source={source} dk_events={dk_events} "
        f"fg_rows={len(fg_rows)} h1_rows={len(h1_rows)} matched={matched} "
        f"unmatched={unmatched} new_fg={written_fg} new_h1={written_h1} "
        f"side_rows={len(side_rows)} new_spread={written_side['full_game_spread']} "
        f"new_ml={written_side['full_game_ml']} "
        f"unchanged={skipped} games_updated={games_updated}"
    )
    if unmatched_names:
        uniq = sorted(set(unmatched_names))
        print(f"unmatched events ({len(uniq)}): {uniq[:10]}" + (" ..." if len(uniq) > 10 else ""))

    # Fail LOUD when nothing was captured: a dead key, an empty feed, or every
    # event unmatched must not leave sunday.yml green with an empty board
    # (see post_derived_lines.py for the same rule). Off-season runs are
    # skipped by the workflow before this script runs.
    if not fg_rows:
        if args.allow_empty:
            print("no full-game rows in the window — nothing to capture (--allow-empty)")
            return
        print("::error::no full-game rows came back from the source — nothing captured")
        sys.exit(1)
    if matched == 0:
        if args.allow_empty:
            print("no event matched a CFBD game in the window (--allow-empty)")
            return
        print("::error::no events matched a CFBD game — nothing captured")
        sys.exit(1)


if __name__ == "__main__":
    main()
