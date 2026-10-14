"""The alternate-line probe (programme 4.4, Tate's approval 2026-10-14): one by-hand
run, writes nothing.

Near kickoff Hard Rock's first-half feed row drifts from its MAIN line to an alternate
rung (main-line share 97% beyond 48 h, 31% inside 2 h; 142 main->rung flips vs 5 back,
measured 2026-10-01), so late candidates read `no_hr_line`. This asks the feed, for the
next games kicking off, for Hard Rock's `totals_h1` AND `alternate_totals_h1`, and prints
whether the main line (the rung priced near even money, both sides better than -140) is
still there in the alternate ladder. Compare the printout with Florida-app screenshots
taken at the same minute (`data/fl_app_checks.csv`). The answer decides between capturing
the alternate market (a design note, then a PR), accepting the drift, or reporting it to
The Odds API.

    python scripts/probe_alt_totals_h1.py --within-min 120 --max-events 10 --out <file>

Cost: 2 credits per event (two markets, one bookmaker = one region). Hard cap 12 events
(24 credits). Prints the credits it spent. Never writes the database.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from beatvegas.devig import is_hr_rung  # noqa: E402
from beatvegas.sources.odds import OddsAPIClient  # noqa: E402

HR = "hardrockbet"
MARKETS = "totals_h1,alternate_totals_h1"
CREDITS_PER_EVENT = 2
MAX_EVENTS = 12


def _pairs(market: Dict[str, Any]) -> List[Tuple[float, Optional[int], Optional[int]]]:
    """(line, over, under) per point of one market."""
    by: Dict[float, Dict[str, int]] = {}
    for o in market.get("outcomes", []):
        pt = o.get("point")
        if pt is None:
            continue
        by.setdefault(float(pt), {})[str(o.get("name", "")).lower()] = o.get("price")
    return sorted((pt, d.get("over"), d.get("under")) for pt, d in by.items())


def centred(pairs: List[Tuple[float, Optional[int], Optional[int]]]) -> List[float]:
    """The ladder points priced like a MAIN line: both sides present and neither
    at -140 or worse (the price half of `devig.is_hr_rung`)."""
    out = []
    for pt, over, under in pairs:
        if over is None or under is None:
            continue
        if not is_hr_rung(over, under, pt, []):
            out.append(pt)
    return out


def summarize(event: Dict[str, Any]) -> Dict[str, Any]:
    """Pure: Hard Rock's fed totals_h1 row and its alternate ladder, for one event."""
    main: List[Tuple[float, Optional[int], Optional[int]]] = []
    alt: List[Tuple[float, Optional[int], Optional[int]]] = []
    for bm in event.get("bookmakers", []):
        if bm.get("key") != HR:
            continue
        for m in bm.get("markets", []):
            if m.get("key") == "totals_h1":
                main = _pairs(m)
            elif m.get("key") == "alternate_totals_h1":
                alt = _pairs(m)
    fed = main[0] if main else None
    fed_is_rung = (
        fed is not None
        and fed[1] is not None
        and fed[2] is not None
        and is_hr_rung(fed[1], fed[2], fed[0], [])
    )
    main_in_ladder = centred(alt)
    return {
        "event": f"{event.get('away_team')} @ {event.get('home_team')}",
        "kick": event.get("commence_time"),
        "fed": fed,
        "fed_is_rung": fed_is_rung,
        "ladder_points": len(alt),
        "main_in_ladder": main_in_ladder,
    }


def verdict(rows: List[Dict[str, Any]]) -> str:
    rung = [r for r in rows if r["fed_is_rung"]]
    recovered = [r for r in rung if r["main_in_ladder"]]
    return (
        f"{len(rows)} events read; Hard Rock's fed 1H row was an alternate rung on {len(rung)}; "
        f"the alternate ladder still carried a main-priced line on {len(recovered)} of those."
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--within-min", type=int, default=120, help="games kicking off within N minutes"
    )
    ap.add_argument("--max-events", type=int, default=10)
    ap.add_argument("--out", type=Path, help="also write the markdown here")
    args = ap.parse_args(argv)
    if not 1 <= args.max_events <= MAX_EVENTS:
        ap.error(f"--max-events must be 1..{MAX_EVENTS} ({CREDITS_PER_EVENT} credits each)")

    client = OddsAPIClient()
    now = datetime.now(timezone.utc)
    events = client.list_events()  # free
    c = client.last_credits
    used_before = c.used if c and c.used is not None else None
    horizon = now + timedelta(minutes=args.within_min)
    soon = [
        e
        for e in events
        if e.get("commence_time")
        and now < datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) <= horizon
    ]
    picked = sorted(soon, key=lambda e: e["commence_time"])[: args.max_events]
    rows = []
    for e in picked:
        data = client.event_odds_raw(e["id"], MARKETS, [HR])
        if data:
            rows.append(summarize(data))
    c = client.last_credits
    spent = (c.used - used_before) if c and c.used is not None and used_before is not None else None
    out = [
        f"# Alternate-line probe ({now:%Y-%m-%dT%H:%M:%SZ})",
        "",
        verdict(rows),
        "",
        "| game | kick (UTC) | Hard Rock 1H row as fed | fed row is a rung | ladder points | main-priced lines in the ladder |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        fed = "—" if r["fed"] is None else f"{r['fed'][0]} ({r['fed'][1]}/{r['fed'][2]})"
        out.append(
            f"| {r['event']} | {r['kick']} | {fed} | {'yes' if r['fed_is_rung'] else 'no'} | "
            f"{r['ladder_points']} | {', '.join(str(x) for x in r['main_in_ladder']) or 'none'} |"
        )
    out += [
        "",
        f"Credits: this run {spent if spent is not None else 'unknown'} "
        f"(cap {CREDITS_PER_EVENT * MAX_EVENTS}); remaining {c.remaining if c else '?'}.",
    ]
    text = "\n".join(out) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
