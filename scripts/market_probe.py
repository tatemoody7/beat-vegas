#!/usr/bin/env python
"""H-MKT-PROBE -- which per-event markets does the Odds API serve for CFB, and
does Hard Rock post them?

PROBE ONLY (docs/HYPOTHESES.md row H-MKT-PROBE): no capture, config or roadmap
change. The full-game capture (scripts/poll_full_game.py) reads the bulk /odds
endpoint, which serves only the featured markets; team totals and first-half
sides are ADDITIONAL markets, served one event at a time. This script asks for
them on a handful of chosen events and reports what came back:

  1. dry run (default, FREE): list_events, the credit balance, and the slate for
     one ET date (default: the coming Saturday) with each event's id and kickoff,
     so the five events can be chosen by the registered rule.
  2. --live --event-ids a,b,c,d,e: one per-event call each on REGIONS us,us2 (every
     book in the feed, Hard Rock included) for the five markets below. Billed
     (markets x regions), so at most 10 credits an event; the run stops before a
     call that could pass --max-credits. A 422 on the combined call (a market key
     the sport does not take) is retried one market at a time on that event, and
     the rejected key is dropped for the rest of the run.

    PYTHONPATH=. python scripts/market_probe.py                       # dry run: the slate
    PYTHONPATH=. python scripts/market_probe.py --live --event-ids ... # spends <= --max-credits

Writes reports/market_probe_<UTC>.{md,json}; touches no database; exits 0.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from beatvegas.backtest.reporting import append_step_summary, report_paths  # noqa: E402
from beatvegas.ci import ET  # noqa: E402
from beatvegas.hardrock import HR_BOOK_KEY, normalize_book  # noqa: E402
from beatvegas.sources.odds import OddsAPIClient, _raise_for_status, redact_key  # noqa: E402

PROBE_MARKETS = (
    "team_totals",
    "team_totals_h1",
    "spreads_h1",
    "h2h_h1",
    "alternate_team_totals",
)
PROBE_REGIONS = "us,us2"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--live", action="store_true", help="spend credits (default: dry run)")
    ap.add_argument("--event-ids", default="", help="comma-separated Odds API event ids")
    ap.add_argument("--max-credits", type=int, default=50)
    ap.add_argument("--regions", default=PROBE_REGIONS)
    ap.add_argument("--markets", default=",".join(PROBE_MARKETS))
    ap.add_argument(
        "--slate-date",
        default=None,
        help="ET date (YYYY-MM-DD) the dry run lists; default the coming Saturday",
    )
    ap.add_argument("--out", default="reports/market_probe")
    return ap.parse_args(argv)


# ---------------------------------------------------------------- pure


def coming_saturday(today: date) -> date:
    """Today when it is Saturday, else the next Saturday."""
    return today + timedelta(days=(5 - today.weekday()) % 7)


def kickoff_et(commence: Optional[str]) -> Optional[datetime]:
    if not commence:
        return None
    dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET)


def slate_for_date(events: Iterable[Dict[str, Any]], day: date) -> List[Dict[str, Any]]:
    """The events kicking off on one ET date, in kickoff order (then home team)."""
    rows = []
    for ev in events:
        k = kickoff_et(ev.get("commence_time"))
        if k is not None and k.date() == day:
            rows.append({**ev, "kickoff_et": k})
    return sorted(rows, key=lambda r: (r["kickoff_et"], r.get("home_team") or ""))


def market_quotes(event: Dict[str, Any], market_key: str) -> List[Dict[str, Any]]:
    """One row per bookmaker posting `market_key` in an event response: its
    outcomes as (name, description, point, price), and its update time."""
    rows: List[Dict[str, Any]] = []
    for bk in event.get("bookmakers") or []:
        for m in bk.get("markets") or []:
            if m.get("key") != market_key:
                continue
            rows.append(
                {
                    "book": normalize_book(bk.get("key")),
                    "outcomes": [
                        {
                            "name": oc.get("name"),
                            "description": oc.get("description"),
                            "point": oc.get("point"),
                            "price": oc.get("price"),
                        }
                        for oc in m.get("outcomes") or []
                    ],
                    "last_update": m.get("last_update") or bk.get("last_update"),
                }
            )
    return rows


def summarize(responses: Sequence[Dict[str, Any]], markets: Sequence[str]) -> Dict[str, Any]:
    """Per market: how many of the probed events carry it, which books post it
    (and on how many events), how many events Hard Rock posted it on, and the
    per-event detail for the report."""
    n = len(responses)
    out: Dict[str, Any] = {"events": n, "markets": {}}
    for mk in markets:
        books: Dict[str, int] = {}
        events_posted = hr_posted = 0
        detail = []
        for ev in responses:
            quotes = market_quotes(ev, mk)
            if quotes:
                events_posted += 1
            hr = next((q for q in quotes if q["book"] == HR_BOOK_KEY), None)
            if hr is not None:
                hr_posted += 1
            # A book counts once per event, even if it is listed twice
            # (hardrockbet and hardrockbet_fl fold into one key).
            posting = {q["book"] for q in quotes}
            for b in posting:
                books[b] = books.get(b, 0) + 1
            detail.append(
                {
                    "event_id": ev.get("id"),
                    "game": f"{ev.get('away_team')} @ {ev.get('home_team')}",
                    "n_books": len(posting),
                    "hard_rock": hr,
                }
            )
        out["markets"][mk] = {
            "events_posted": events_posted,
            "hr_posted": hr_posted,
            "books": dict(sorted(books.items(), key=lambda kv: (-kv[1], kv[0]))),
            "per_event": detail,
        }
    return out


def _fmt_outcomes(outcomes: Sequence[Dict[str, Any]]) -> str:
    parts = []
    for oc in outcomes:
        label = " ".join(str(x) for x in (oc.get("description"), oc.get("name")) if x)
        pt = "" if oc.get("point") is None else f" {oc['point']}"
        parts.append(f"{label}{pt} ({oc.get('price')})")
    return "; ".join(parts)


def render_markdown(r: Dict[str, Any]) -> str:
    c = r["credits"]
    L = [
        "# Market-availability probe (H-MKT-PROBE)",
        "",
        f"Run {r['generated_at']} ({r['weekday']}). Regions {r['regions']}; markets "
        f"{', '.join(r['markets'])}. Credits used {c['start_used']} → {c['end_used']} "
        f"(spent {c['spent']}, remaining {c['remaining']}, cap {r['max_credits']}). "
        "Probe only — no capture or config change.",
        "",
    ]
    if not r["live"]:
        L += [f"## Slate for {r['slate_date']} (ET), dry run", ""]
        L += ["| event id | kickoff (ET) | game |", "|---|---|---|"]
        for ev in r["slate"]:
            L.append(
                f"| `{ev['id']}` | {ev['kickoff_et']} | {ev['away_team']} @ {ev['home_team']} |"
            )
        return "\n".join(L) + "\n"
    L += ["## Events probed", ""]
    for ev in r["probed"]:
        L.append(f"- `{ev['id']}` {ev['kickoff_et']} ET — {ev['away_team']} @ {ev['home_team']}")
    if r["invalid_markets"]:
        L += ["", f"Market keys the API rejected (422): {', '.join(r['invalid_markets'])}."]
    if r["errors"]:
        L += ["", "Call errors: " + "; ".join(r["errors"])]
    s = r["summary"]
    L += [
        "",
        f"## By market ({s['events']} events)",
        "",
        "| market | events posted | Hard Rock posted | books posting (events) |",
        "|---|---|---|---|",
    ]
    for mk, m in s["markets"].items():
        books = ", ".join(f"{k} ({v})" for k, v in m["books"].items()) or "none"
        L.append(f"| `{mk}` | {m['events_posted']} | {m['hr_posted']} | {books} |")
    L += ["", "## Hard Rock's quotes", ""]
    for mk, m in s["markets"].items():
        for e in m["per_event"]:
            if e["hard_rock"] is not None:
                L.append(f"- `{mk}` {e['game']}: {_fmt_outcomes(e['hard_rock']['outcomes'])}")
    if not any(m["hr_posted"] for m in s["markets"].values()):
        L.append("Hard Rock posted none of the probed markets on these events.")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- main


def _event_call(client: OddsAPIClient, event_id: str, markets: str, regions: str):
    """(status, json-or-None, error text). Regions on purpose: the probe wants
    every book in the feed, so it never inherits the ten-key bookmakers scope."""
    url = f"{client.base_url}/sports/{client.sport}/events/{event_id}/odds"
    params = {
        "apiKey": client.api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": client.odds_format,
        "dateFormat": "iso",
    }
    resp = client._get(url, params)
    if resp.status_code == 404:
        return 404, None, ""
    if resp.status_code == 422:
        return 422, None, redact_key(resp.text[:200])
    _raise_for_status(resp)
    return resp.status_code, resp.json(), ""


def _merge(base: Optional[Dict[str, Any]], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Fold one single-market response into an event response, book by book.
    Works on copies: a response object is never extended in place."""
    extra = copy.deepcopy(extra)
    if base is None:
        return extra
    by_key = {bk.get("key"): bk for bk in base.get("bookmakers") or []}
    for bk in extra.get("bookmakers") or []:
        if bk.get("key") in by_key:
            by_key[bk["key"]].setdefault("markets", []).extend(bk.get("markets") or [])
        else:
            base.setdefault("bookmakers", []).append(bk)
    return base


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    markets = [m for m in args.markets.split(",") if m]
    n_regions = len([r for r in args.regions.split(",") if r])
    client = OddsAPIClient()
    events = client.list_events()  # free; carries the credit headers
    start_used = client.last_credits.used if client.last_credits else None
    day = (
        date.fromisoformat(args.slate_date)
        if args.slate_date
        else coming_saturday(datetime.now(ET).date())
    )
    slate = slate_for_date(events, day)
    r: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weekday": datetime.now(ET).strftime("%A"),
        "live": args.live,
        "regions": args.regions,
        "markets": markets,
        "max_credits": args.max_credits,
        "slate_date": day.isoformat(),
        "slate": [
            {
                "id": ev["id"],
                "kickoff_et": ev["kickoff_et"].strftime("%a %H:%M"),
                "away_team": ev.get("away_team"),
                "home_team": ev.get("home_team"),
            }
            for ev in slate
        ],
        "probed": [],
        "invalid_markets": [],
        "errors": [],
        "summary": None,
    }

    def spent() -> int:
        u = client.last_credits.used if client.last_credits else None
        return (u - start_used) if (u is not None and start_used is not None) else 0

    def credits() -> Dict[str, Any]:
        return {
            "start_used": start_used,
            "end_used": client.last_credits.used if client.last_credits else None,
            "spent": spent(),
            "remaining": client.last_credits.remaining if client.last_credits else None,
        }

    print(
        f"[probe] {len(events)} upcoming events, {len(slate)} on {day} (ET); credits "
        f"remaining {client.last_credits.remaining if client.last_credits else '?'}"
    )
    if not args.live:
        print("[probe] dry run — nothing spent. Choose 5 ids, then pass --live --event-ids.")
        r["credits"] = credits()
        _write(r, args.out)
        return 0

    ids = [e for e in args.event_ids.split(",") if e]
    if not ids:
        print("::error::--live needs --event-ids")
        return 2
    by_id = {ev["id"]: ev for ev in events}
    responses: List[Dict[str, Any]] = []
    for eid in ids:
        ev = by_id.get(eid, {"id": eid})
        live = [m for m in markets if m not in r["invalid_markets"]]
        worst = len(live) * n_regions
        if not live or spent() + worst > args.max_credits:
            print(f"[probe] stopping before {eid}: spent {spent()}, next call up to {worst}")
            break
        status, payload, err = _event_call(client, eid, ",".join(live), args.regions)
        if status == 422:
            # One key the sport does not take rejects the whole call: learn which.
            payload = None
            for m in live:
                if spent() + n_regions > args.max_credits:
                    break
                s1, p1, e1 = _event_call(client, eid, m, args.regions)
                if s1 == 422:
                    r["invalid_markets"].append(m)
                    print(f"[probe] {m}: rejected ({e1})")
                elif p1:
                    payload = _merge(payload, p1)
        elif status == 404:
            r["errors"].append(f"{eid}: 404 (no odds posted)")
        k = kickoff_et(ev.get("commence_time"))
        r["probed"].append(
            {
                "id": eid,
                "kickoff_et": k.strftime("%a %H:%M") if k else "?",
                "away_team": ev.get("away_team"),
                "home_team": ev.get("home_team"),
            }
        )
        responses.append(
            payload
            or {
                "id": eid,
                "home_team": ev.get("home_team"),
                "away_team": ev.get("away_team"),
                "bookmakers": [],
            }
        )
        print(f"[probe] {eid}: status {status}, spent so far {spent()}")
    r["summary"] = summarize(responses, markets)
    r["credits"] = credits()
    _write(r, args.out)
    return 0


def _write(r: Dict[str, Any], out: str) -> None:
    md = render_markdown(r)
    md_path, json_path, _csv = report_paths(out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)
    json_path.write_text(json.dumps(r, indent=1, default=str))
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path}")


if __name__ == "__main__":
    raise SystemExit(main())
