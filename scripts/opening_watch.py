#!/usr/bin/env python3
"""The market-opening watch (temporary research, Tate's approval 2026-10-15).

When does each book first post NEXT week's college-football first-half totals, team totals
and first-half team totals, and its full-game totals? Run every 20 minutes (10 on Monday
morning) by `.github/workflows/opening_watch.yml` from Friday 2026-10-16 18:00 ET to
Tuesday 2026-10-20 18:00 ET, then removed.

Read-only: standard library only, never imports `beatvegas`, never touches the database
(a row in `odds_snapshots` would silently enlarge the frozen pricing study's sample). Each
tick writes JSONL to --out and carries its state in --state (the workflow caches it).

Cost discipline (The Odds API v4): an event-odds call costs (markets RETURNED) x (book
groups of 10), and an empty answer is free. Detection therefore asks for each market ONLY
from the books that have not yet posted it -- a credit is spent at the moment a book opens,
never while we wait for a slow one. Full-game totals come from one bulk call (markets x
regions = 4 credits) every other tick; a first-half snapshot of every opened game every 6
hours tracks movement. A hard stop ends all paid calls at BUDGET credits.

Three times are kept apart in the output: the book's true open (not observable), the
provider's market `last_update` (when the provider last SAW the price; it refreshes about
every 60 s), and our capture second. A first sighting carries the window it opened in:
from the previous tick that asked and did not see it, to this tick.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_ncaaf"
UTC = timezone.utc

WATCH_START = datetime(2026, 10, 16, 22, 0, tzinfo=UTC)  # Fri 18:00 ET
WATCH_END = datetime(2026, 10, 20, 22, 0, tzinfo=UTC)  # Tue 18:00 ET
# Next week's games: after this weekend's last game, before the following Monday.
TARGET_FROM = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
TARGET_TO = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

BUDGET = 5500
MAX_BOOKS_PER_CALL = 10  # one region-equivalent per call
BOOKS = [
    "hardrockbet", "draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers",
    "espnbet", "fanatics", "bovada", "betonlineag", "fliff", "ballybet", "betparx",
    "pinnacle", "kalshi", "novig", "prophetx", "polymarket",
]  # fmt: skip
MARKETS = ["totals_h1", "team_totals", "team_totals_h1"]
FG_REGIONS = "us,us2,eu,us_ex"
FG_EVERY_TICKS = 2  # full-game bulk every other tick
MOVEMENT_HOURS = 6
WORKERS = 6  # parallel requests per tick (429s back off and retry)
LOCK = threading.Lock()  # the credit counter and the log are shared by the workers


# --- pure logic (tested) -----------------------------------------------------------


def in_window(now: datetime) -> bool:
    return WATCH_START <= now <= WATCH_END


def is_target(commence_iso: str) -> bool:
    t = datetime.fromisoformat(commence_iso.replace("Z", "+00:00"))
    return TARGET_FROM < t <= TARGET_TO


def groups(books: Iterable[str], size: int = MAX_BOOKS_PER_CALL) -> List[List[str]]:
    b = list(books)
    return [b[i : i + size] for i in range(0, len(b), size)]


def new_state() -> Dict[str, Any]:
    return {"spent": 0, "ticks": [], "listed": {}, "seen": {}, "last_asked": {}, "fg_seen": {}}


def plan_detection(
    state: Dict[str, Any], event_ids: Iterable[str]
) -> List[Tuple[str, str, List[str]]]:
    """(event, market, books) requests: each market asked only of books that have not
    posted it for that event, at most MAX_BOOKS_PER_CALL books per request."""
    out = []
    for eid in event_ids:
        seen = state["seen"].get(eid, {})
        for m in MARKETS:
            unseen = [b for b in BOOKS if b not in seen.get(m, {})]
            for g in groups(unseen):
                out.append((eid, m, g))
    return out


def market_rows(event: Dict[str, Any], market: str) -> List[Dict[str, Any]]:
    """One row per (book, outcome) for `market` in an event-odds response, as fed."""
    rows = []
    for bm in event.get("bookmakers", []) or []:
        for mk in bm.get("markets", []) or []:
            if mk.get("key") != market:
                continue
            for o in mk.get("outcomes", []) or []:
                rows.append(
                    {
                        "book": bm.get("key"),
                        "market": market,
                        "name": o.get("name"),
                        "description": o.get("description"),  # the team, for team totals
                        "point": o.get("point"),
                        "price": o.get("price"),
                        "last_update": mk.get("last_update"),
                    }
                )
    return rows


def record_hits(
    state: Dict[str, Any],
    eid: str,
    market: str,
    asked: List[str],
    rows: List[Dict[str, Any]],
    now: str,
) -> List[Dict[str, Any]]:
    """Mark the books in `asked` that now show `market` as opened. The window opens at the
    last tick that asked this event and market and did not see the book; on the first ask
    there is no earlier miss, so the window reads 'already-open-at-first-ask'."""
    seen = state["seen"].setdefault(eid, {}).setdefault(market, {})
    prev = state["last_asked"].get(eid, {}).get(market)
    hits = []
    for book in sorted({r["book"] for r in rows if r["book"] in asked}):
        if book in seen:
            continue
        seen[book] = now
        hits.append(
            {
                "type": "open",
                "event": eid,
                "market": market,
                "book": book,
                "captured_at": now,
                "window_from": prev or "already-open-at-first-ask",
                "rows": [r for r in rows if r["book"] == book],
            }
        )
    state["last_asked"].setdefault(eid, {})[market] = now
    return hits


def budget_left(state: Dict[str, Any]) -> int:
    return BUDGET - int(state.get("spent", 0))


# --- network -----------------------------------------------------------------------


def _get(path: str, params: Dict[str, str], state: Dict[str, Any], log) -> Optional[Any]:
    q = dict(params, apiKey=os.environ["ODDS_API_KEY"])
    url = f"{BASE}{path}?{urllib.parse.urlencode(q)}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                body = json.loads(r.read().decode())
                cost = int(r.headers.get("x-requests-last") or 0)
                with LOCK:
                    state["spent"] = int(state.get("spent", 0)) + cost
                    log({"type": "call", "path": path, "cost": cost,
                         "remaining": r.headers.get("x-requests-remaining")})  # fmt: skip
                return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            with LOCK:
                log({"type": "error", "path": path, "status": e.code})
            return None
        except urllib.error.URLError as e:
            with LOCK:
                log({"type": "error", "path": path, "error": str(e.reason)})
            time.sleep(2 ** (attempt + 1))
    return None


def tick(state: Dict[str, Any], now: datetime, log) -> None:
    stamp = now.isoformat().replace("+00:00", "Z")
    state["ticks"].append(stamp)
    log({"type": "tick", "at": stamp, "spent": state["spent"], "n": len(state["ticks"])})
    events = _get(f"/sports/{SPORT}/events", {"dateFormat": "iso"}, state, log) or []
    targets = [e for e in events if is_target(e["commence_time"])]
    for e in targets:
        if e["id"] not in state["listed"]:
            state["listed"][e["id"]] = stamp
            log({"type": "listed", "event": e["id"], "game": f"{e['away_team']} @ {e['home_team']}",
                 "kick": e["commence_time"], "first_seen": stamp})  # fmt: skip
    # 1. opening detection, paid only on a hit (requests in parallel, recorded in order)
    plan = plan_detection(state, [e["id"] for e in targets])
    if budget_left(state) <= 0:
        log({"type": "budget_stop", "at": stamp, "spent": state["spent"]})
        return

    def ask(req):
        eid, market, books = req
        return _get(f"/sports/{SPORT}/events/{eid}/odds",
                    {"markets": market, "bookmakers": ",".join(books), "oddsFormat": "american",
                     "dateFormat": "iso"}, state, log)  # fmt: skip

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        bodies = list(pool.map(ask, plan))
    for (eid, market, books), body in zip(plan, bodies):
        for h in record_hits(state, eid, market, books, market_rows(body or {}, market), stamp):
            log(h)
    # 2. full-game totals for every game, every other tick
    if len(state["ticks"]) % FG_EVERY_TICKS == 1 and budget_left(state) > 0:
        bulk = _get(f"/sports/{SPORT}/odds",
                    {"markets": "totals", "regions": FG_REGIONS, "oddsFormat": "american",
                     "dateFormat": "iso"}, state, log) or []  # fmt: skip
        for e in bulk:
            if not is_target(e["commence_time"]):
                continue
            rows = market_rows(e, "totals")
            log({"type": "fg", "event": e["id"], "at": stamp, "rows": rows})
            fs = state["fg_seen"].setdefault(e["id"], {})
            for b in {r["book"] for r in rows}:
                fs.setdefault(b, stamp)
    # 3. movement: every opened game's first-half totals, every MOVEMENT_HOURS
    if now.hour % MOVEMENT_HOURS == 0 and now.minute < 20:
        for eid, mk in state["seen"].items():
            if not mk.get("totals_h1") or budget_left(state) <= 0:
                continue
            for g in groups(BOOKS):
                body = _get(f"/sports/{SPORT}/events/{eid}/odds",
                            {"markets": "totals_h1", "bookmakers": ",".join(g),
                             "oddsFormat": "american", "dateFormat": "iso"}, state, log)  # fmt: skip
                log({"type": "move", "event": eid, "at": stamp,
                     "rows": market_rows(body or {}, "totals_h1")})  # fmt: skip


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--force", action="store_true", help="run outside the watch window (a test tick)"
    )
    args = ap.parse_args(argv)
    now = datetime.now(UTC)
    state = json.loads(args.state.read_text()) if args.state.exists() else new_state()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as f:

        def log(rec: Dict[str, Any]) -> None:
            f.write(json.dumps(rec) + "\n")
            f.flush()

        if not (in_window(now) or args.force):
            log({"type": "outside_window", "at": now.isoformat()})
        elif budget_left(state) <= 0:
            log({"type": "budget_spent", "spent": state["spent"]})
        else:
            tick(state, now, log)
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps(state))
    print(f"opening-watch: ticks {len(state['ticks'])}, spent {state['spent']} of {BUDGET}, "
          f"events {len(state['listed'])}, opened pairs "
          f"{sum(len(b) for m in state['seen'].values() for b in m.values())}")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
