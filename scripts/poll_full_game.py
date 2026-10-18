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

`--research-regions eu` (oddsapi only) adds a second bulk call after the live one:
the sharp reference, written to `research_snapshots` (purpose `sharp_eu`) and never
to `odds_snapshots`, so the judge and every frozen reader see no new book or region.

    python scripts/poll_full_game.py                      # auto, local
    python scripts/poll_full_game.py --source cfbd        # cloud-safe, one book
    python scripts/poll_full_game.py --source oddsapi     # multi-book incl. Hard Rock

Pair with scripts/poll_lines.py (The Odds API) for cross-book 1H consensus + close.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from beatvegas import credit_plan, research_capture
from beatvegas.ci import warn
from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import _parse_dt, match_event
from beatvegas.hardrock import hr_universe_game_ids, normalize_book
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

# Why the last _fetch returned nothing it was asked for (None = it did not skip).
# _fetch's tuple is read by tests and callers, so the one skip that exits 0 with
# no rows (the credit-floor guard) leaves its reason here for the status file.
_FETCH_STATE: Dict[str, Optional[str]] = {"skip": None}
# The Odds API client the live pull used, kept for the research call that follows
# it (same key, same credit headers). None when the pull never made one.
_LIVE_CLIENT: Dict[str, object] = {"client": None}


def write_status(
    path: Optional[str],
    *,
    complete: bool,
    reason: Optional[str],
    events_in_window: int,
    events_polled: int,
    rows_written: int,
    rows_reseen: int,
    events_unmatched: int = 0,
) -> None:
    """The run's coverage, for scripts/health_check.py (lines_watch's
    `fg_close_polled`). Written on every exit that gets past the fetch: this
    step is continue-on-error and exits 0 on an empty or skipped pull, so a
    missing file means the run died before it could say what it did.

    `complete` is true when the run was not skipped (credit floor, database
    unreachable) and either found no event inside the window or priced at
    least one that resolves to a CFBD game. An event the matcher cannot tie to
    a game (an FCS pairing) is counted in `events_unmatched`, never a failure."""
    if not path:
        return
    payload: Dict[str, object] = {
        "complete": bool(complete),
        "reason": reason,
        "events_in_window": int(events_in_window),
        "events_polled": int(events_polled),
        "events_unmatched": int(events_unmatched),
        "rows_written": int(rows_written),
        "rows_reseen": int(rows_reseen),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    print(f"[status] {path}: {json.dumps(payload)}")


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
    gate: Optional[Callable[[List[Dict]], bool]] = None,
) -> Tuple[List[Dict], List[Dict], str, int]:
    """Return (full_game_rows, first_half_rows, source_used, event_count).

    The Odds API's full-game rows also carry the side-market rows (spread,
    moneyline), told apart by their `market` key; main() splits them."""
    fg, h1, used, n = _fetch_raw(source, season, regions, credit_floor, markets, gate)
    return _normalize_books(fg), _normalize_books(h1), used, n


def _fetch_raw(
    source: str,
    season: int,
    regions: str,
    credit_floor: int,
    markets: str = DEFAULT_MARKETS,
    gate: Optional[Callable[[List[Dict]], bool]] = None,
) -> Tuple[List[Dict], List[Dict], str, int]:
    dk_events = 0
    if source == "oddsapi":
        # Bulk /odds: multi-book full-game totals incl. Hard Rock (us2). The
        # rows carry team names + commence_time, so they match by name+time like
        # the DK path (no CFBD game id). 1H is captured separately (poll_lines).
        client = OddsAPIClient()
        _LIVE_CLIENT["client"] = client
        # list_events is FREE but returns the credit headers: learn the balance
        # before the paid bulk call so a reserve floor can stop it.
        events_free = client.list_events()
        # --hr-only-gate: the free event list decides whether the paid pull is
        # worth making at all (nothing due that Hard Rock prices -> 0 credits).
        if gate is not None and not gate(events_free):
            _FETCH_STATE["skip"] = "no_hr_game"
            return [], [], "oddsapi", 0
        if client.credits_low(credit_floor):
            warn(
                f"Odds API credits at reserve floor "
                f"({client.last_credits.remaining} <= {credit_floor}) — skipping the "
                "full-game pull. Pass --credit-floor 0 to override."
            )
            _FETCH_STATE["skip"] = "credit_floor"
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


def _research_pull(
    client,
    *,
    regions: str,
    markets: str,
    purpose: str,
    now: datetime,
    season: int,
    keep: Callable[[Dict], bool],
) -> None:
    """The sharp reference (final-2026 plan PR-C4a): a SECOND bulk call beside the
    live one, on regions the judge never reads (`eu`: Pinnacle and others), written
    to `research_snapshots` only. Billed markets x regions, like any bulk call.

    The live pull is already done and written; nothing here can change its rows or
    the exit code. The credit controller decides first: the allowance (balance from
    the live response's own credit header, floor and recurring need from
    `app_settings`) must cover the call, else it is skipped with a printed reason.
    Any failure is a warning."""
    label = f"research {regions}"
    cost = len([m for m in markets.split(",") if m]) * len([r for r in regions.split(",") if r])
    try:
        balance = getattr(getattr(client, "last_credits", None), "remaining", None)
        if balance is None:
            print(f"{label}: skipped (balance unknown)")
            return
        with session_scope() as s:
            st = credit_plan.load_settings(s)
            measured = credit_plan.measured_recurring(s, now)
        per_week = st.recurring_fallback if measured is None else measured
        room = credit_plan.allowance(balance, now, st.reset_at, st.floor, per_week)
        if room < cost:
            print(
                f"{label}: skipped (allowance {room:,} < {cost} credits; balance {balance:,}, "
                f"floor {st.floor:,}, recurring {per_week:,}/wk)"
            )
            return
        # Never names a book: the call is regions x markets, nothing else.
        saved = getattr(client, "purpose", None)
        client.purpose = purpose
        try:
            events = client.list_full_game_odds(regions=regions, markets=markets)
            request_id = getattr(client, "last_spend_id", None)
        finally:
            client.purpose = saved
        credits = getattr(getattr(client, "last_credits", None), "last_cost", None)
        rows = oa_normalize_full_game(events) + normalize_full_game_sides(events)
        rows = [r for r in rows if keep(r)]
        for r in rows:
            r["market"] = r.get("market") or "full_game_total"
        with session_scope() as s:
            games = _candidate_games(s, season)
            ids = {g["id"] for g in games}
            for r in rows:
                r["game_id"] = _resolve_gid(r, games, ids)
            n = research_capture.write_rows(
                s,
                rows,
                purpose=purpose,
                region=regions if "," not in regions else None,
                request_id=request_id,
                source="live",
                dedupe=True,
                now=now,
            )
        print(
            f"{label}: {n['written']} written, {n['reseen']} reseen, "
            f"{credits if credits is not None else 'unknown'} credits"
        )
    except Exception as e:  # noqa: BLE001 - a research failure never touches the live pull
        print(f"::warning::{label}: not captured ({type(e).__name__}: {e})")


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
        "--hr-only-gate",
        action="store_true",
        dest="hr_only_gate",
        help="--source oddsapi only: after the free event list, make the paid pull only "
        "when a Hard Rock-universe game (one Hard Rock has priced a full-game total on) "
        "kicks off inside the window; otherwise exit 0 having spent nothing (the "
        "close ticks, final-2026 PR-C2)",
    )
    ap.add_argument(
        "--allow-empty",
        action="store_true",
        help="exit 0 when no row was captured (a close tick with no full-game event "
        "due is a normal state inside the 1H close job, not a dead feed)",
    )
    ap.add_argument(
        "--status-file",
        dest="status_file",
        metavar="PATH",
        default=None,
        help="write the run's coverage as JSON (events_in_window, events_polled, rows_written, "
        "rows_reseen, complete) for the lines_watch health contract",
    )
    ap.add_argument(
        "--research-regions",
        default=None,
        metavar="REGIONS",
        help="--source oddsapi only: after the live pull, one more bulk call on these "
        "regions (e.g. `eu`, Pinnacle) written to research_snapshots only, never "
        "odds_snapshots; skipped when the credit allowance is short, or when the "
        "live pull was gated or skipped (final-2026 PR-C4a)",
    )
    ap.add_argument(
        "--research-markets",
        default="totals",
        help="markets for the --research-regions call, billed (markets x regions)",
    )
    ap.add_argument(
        "--research-purpose",
        default="sharp_eu",
        help="research_snapshots.purpose (and odds_spend.purpose) for that call",
    )
    args = ap.parse_args(argv)

    _FETCH_STATE["skip"] = None
    _LIVE_CLIENT["client"] = None
    if not try_init_db():
        write_status(
            args.status_file,
            complete=False,
            reason="db_unreachable",
            events_in_window=0,
            events_polled=0,
            rows_written=0,
            rows_reseen=0,
        )
        return

    def _window(at: datetime) -> Tuple[datetime, datetime]:
        horizon = at + timedelta(days=args.days_ahead)
        if args.kickoff_within_min is not None:
            horizon = min(horizon, at + timedelta(minutes=args.kickoff_within_min))
        lo = at if args.kickoff_within_min is not None else at - timedelta(days=1)
        return lo, horizon

    def _hr_game_due(events: List[Dict]) -> bool:
        """True when an event inside the window is a Hard Rock-universe game."""
        lo, hi = _window(datetime.utcnow())
        due = [
            ev
            for ev in events
            if (dt := _parse_dt(ev.get("commence_time"))) is not None and lo <= dt <= hi
        ]
        if not due:
            return False
        with session_scope() as s:
            games = _candidate_games(s, args.season)
            universe = hr_universe_game_ids(s, args.season)
        for ev in due:
            gid, _ = match_event(ev["home_team"], ev["away_team"], ev.get("commence_time"), games)
            if gid in universe:
                return True
        return False

    fetch_kwargs = {"gate": _hr_game_due} if args.hr_only_gate else {}
    fg_rows, h1_rows, source, dk_events = _fetch(
        args.source,
        args.season,
        args.regions,
        credit_floor=args.credit_floor,
        markets=args.markets,
        **fetch_kwargs,
    )
    if _FETCH_STATE["skip"] == "no_hr_game":
        print("no Hard Rock game inside the window: the paid pull was not made (0 credits)")
        write_status(
            args.status_file,
            complete=True,
            reason="no_hr_game",
            events_in_window=0,
            events_polled=0,
            rows_written=0,
            rows_reseen=0,
        )
        return

    now = datetime.utcnow()
    lo, horizon = _window(now)

    def _in_window(r) -> bool:
        dt = _parse_dt(r.get("commence_time"))
        if dt is None:
            return True
        return lo <= dt <= horizon

    fg_rows = [r for r in fg_rows if _in_window(r)]
    h1_rows = [r for r in h1_rows if _in_window(r)]
    # The side markets ride in the same list from the Odds API (tagged with
    # `market`); the totals rows below never carry one.
    side_rows = [r for r in fg_rows if r.get("market") in SIDE_MARKETS.values()]
    fg_rows = [r for r in fg_rows if r.get("market") is None]

    written_fg = written_h1 = matched = unmatched = skipped = games_updated = 0
    reseen = 0
    # Distinct feed events in the window (the side markets ride the same events),
    # for the status file; polled = the games they resolved to.
    in_window_events = {
        r.get("event_id")
        or (r.get("game_id"), r.get("home_team"), r.get("away_team"), r.get("commence_time"))
        for r in fg_rows + side_rows
    }
    polled_gids: set = set()
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
            polled_gids.add(gid)
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
                reseen += 1
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
            polled_gids.add(gid)
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
                reseen += 1

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

    # The sharp reference rides behind the live pull: only when the live pull ran,
    # priced something inside the window, and the source is the Odds API.
    live_client = _LIVE_CLIENT["client"]
    if (
        args.research_regions
        and source == "oddsapi"
        and live_client is not None
        and _FETCH_STATE["skip"] is None
        and (fg_rows or side_rows)
    ):
        _research_pull(
            live_client,
            regions=args.research_regions,
            markets=args.research_markets,
            purpose=args.research_purpose,
            now=now,
            season=args.season,
            keep=_in_window,
        )

    skip_reason = _FETCH_STATE["skip"]
    write_status(
        args.status_file,
        complete=skip_reason is None and (not in_window_events or bool(polled_gids)),
        reason=skip_reason or (None if polled_gids or not in_window_events else "no_match"),
        events_in_window=len(in_window_events),
        events_polled=len(polled_gids),
        events_unmatched=len(set(unmatched_names)),
        rows_written=written_fg + sum(written_side.values()),
        rows_reseen=reseen,
    )
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
