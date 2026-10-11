#!/usr/bin/env python
"""Probe: is The Odds API's `hardrockbet` the same price as `hardrockbet_fl`?

The capture folds every Hard Rock state key into `hardrockbet` (hardrock.normalize_book),
and the bookmaker docs call that key the Indiana book, "currently same odds as several other
states". Nothing we hold proves the Florida app shows those numbers. This probe asks the feed
for BOTH keys, keeps them as spelled, and prints them side by side with the provider's
`last_update` stamp, plus the credits the run cost (x-requests-last / x-requests-used).

    python scripts/probe_hr_keys.py --bulk                 # 1 credit: us2 full-game totals, every key seen
    python scripts/probe_hr_keys.py --per-event 20         # 1 credit per event: totals_h1 for both keys
    python scripts/probe_hr_keys.py --per-event 20 --markets totals_h1,totals   # 2 credits per event

READ-ONLY: no table is written; the output is a markdown table on stdout (and --out FILE).
One matching slate proves nothing about other weeks; the registry row that cites this
probe says so (Tate 2026-10-11).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beatvegas.sources.odds import OddsAPIClient, _raise_for_status  # noqa: E402

KEYS = ["hardrockbet", "hardrockbet_fl"]
MARKET_LABEL = {"totals": "full-game total", "totals_h1": "first-half total", "spreads": "spread"}


def _main_pair(outcomes: List[Dict[str, Any]]):
    """(point, over_price, under_price) for the most balanced point pair, as odds.py does."""
    by_pt: Dict[float, Dict[str, int]] = {}
    for o in outcomes:
        pt, name, price = o.get("point"), (o.get("name") or "").lower(), o.get("price")
        if pt is None or price is None:
            continue
        by_pt.setdefault(float(pt), {})[name] = int(price)
    full = {pt: d for pt, d in by_pt.items() if "over" in d and "under" in d}
    if not full:
        return None
    pt = min(full, key=lambda p: abs(full[p]["over"] - full[p]["under"]))
    return pt, full[pt]["over"], full[pt]["under"]


def _rows(event: Dict[str, Any], keys: List[str]) -> List[Dict[str, Any]]:
    out = []
    for bm in event.get("bookmakers", []):
        if bm.get("key") not in keys:
            continue
        for mkt in bm.get("markets", []):
            picked = _main_pair(mkt.get("outcomes", []))
            if picked is None:
                continue
            pt, over, under = picked
            out.append(
                {
                    "event": f"{event.get('away_team')} @ {event.get('home_team')}",
                    "kick": event.get("commence_time"),
                    "key": bm["key"],
                    "market": mkt.get("key"),
                    "line": pt,
                    "over": over,
                    "under": under,
                    "last_update": mkt.get("last_update") or bm.get("last_update"),
                }
            )
    return out


def _compare(rows: List[Dict[str, Any]]) -> Dict[str, Counter]:
    """Per market: identical / different / only_hardrockbet / only_fl, per event."""
    by: Dict[tuple, Dict[str, Dict[str, Any]]] = {}
    for r in rows:
        by.setdefault((r["event"], r["market"]), {})[r["key"]] = r
    verdicts: Dict[str, Counter] = {}
    for (_ev, mkt), d in by.items():
        c = verdicts.setdefault(mkt, Counter())
        a, b = d.get("hardrockbet"), d.get("hardrockbet_fl")
        if a and b:
            same = (a["line"], a["over"], a["under"]) == (b["line"], b["over"], b["under"])
            c["identical" if same else "different"] += 1
            if a["last_update"] != b["last_update"]:
                c["stamp_differs"] += 1
        elif a:
            c["only_hardrockbet"] += 1
        elif b:
            c["only_hardrockbet_fl"] += 1
    return verdicts


def _table(rows: List[Dict[str, Any]], captured: str) -> str:
    lines = [
        "| event | kick (UTC) | key | market | line | over | under | feed last_update | captured |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (r["kick"] or "", r["event"], r["market"], r["key"])):
        lines.append(
            f"| {r['event']} | {r['kick']} | {r['key']} | {MARKET_LABEL.get(r['market'], r['market'])} | "
            f"{r['line']} | {r['over']} | {r['under']} | {r['last_update']} | {captured} |"
        )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--bulk", action="store_true", help="one us2 bulk call for full-game totals (1 credit)"
    )
    ap.add_argument(
        "--per-event",
        type=int,
        default=0,
        metavar="N",
        help="per-event calls for the next N events",
    )
    ap.add_argument(
        "--markets", default="totals_h1", help="per-event markets (credits = markets x 1)"
    )
    ap.add_argument("--out", type=Path, help="also write the markdown here")
    args = ap.parse_args(argv)
    if not args.bulk and not args.per_event:
        ap.error("give --bulk and/or --per-event N")

    client = OddsAPIClient()
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: List[Dict[str, Any]] = []
    out: List[str] = [f"# Hard Rock key probe ({captured})", ""]
    used_before: Optional[int] = None

    if args.bulk:
        url = f"{client.base_url}/sports/{client.sport}/odds"
        resp = client._get(
            url,
            {
                "apiKey": client.api_key,
                "regions": "us2",
                "markets": "totals",
                "oddsFormat": client.odds_format,
                "dateFormat": "iso",
            },
        )
        _raise_for_status(resp)
        events = resp.json()
        c = client.last_credits
        used_before = (
            (c.used - c.last_cost) if c and c.used is not None and c.last_cost is not None else None
        )
        keys_seen = Counter(bm.get("key") for ev in events for bm in ev.get("bookmakers", []))
        out += [
            f"## Bulk `regions=us2`, `markets=totals`: {len(events)} events, cost {c.last_cost if c else '?'} credit(s)",
            "",
            "Bookmaker keys in the response: "
            + ", ".join(f"`{k}` ({n})" for k, n in keys_seen.most_common()),
            "",
        ]
        rows += [r for ev in events for r in _rows(ev, KEYS)]

    if args.per_event:
        events = client.list_events()
        if used_before is None:
            c = client.last_credits
            used_before = c.used if c and c.used is not None else None
        picked = sorted(events, key=lambda e: e.get("commence_time") or "")[: args.per_event]
        out += [
            f"## Per-event `bookmakers={','.join(KEYS)}`, `markets={args.markets}`: {len(picked)} events",
            "",
        ]
        n_404 = 0
        for ev in picked:
            data = client.event_odds_raw(ev["id"], args.markets, KEYS)
            if not data:
                n_404 += 1
                continue
            rows += _rows(data, KEYS)
        out.append(f"events without odds yet: {n_404}")
        out.append("")

    # The bulk and per-event passes list the same event twice; one row per distinct quote.
    uniq = {}
    for r in rows:
        uniq.setdefault(
            (r["event"], r["key"], r["market"], r["line"], r["over"], r["under"], r["last_update"]),
            r,
        )
    rows = list(uniq.values())
    verdicts = _compare(rows)
    out += ["## Verdict per market (events with the key present)", ""]
    for mkt, c in sorted(verdicts.items()):
        out.append(
            f"- **{MARKET_LABEL.get(mkt, mkt)}**: "
            + ", ".join(f"{k} {v}" for k, v in sorted(c.items()))
        )
    if not verdicts:
        out.append("- no Hard Rock rows in the response")
    out += ["", "## Rows", "", _table(rows, captured), ""]
    c = client.last_credits
    spent = (c.used - used_before) if c and c.used is not None and used_before is not None else None
    out.append(
        f"Credits: this run {spent if spent is not None else 'unknown'}; "
        f"used this month {c.used if c else '?'}; remaining {c.remaining if c else '?'}."
    )
    text = "\n".join(out) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
