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

    python scripts/archive/probe_alt_totals_h1.py --within-min 120 --max-events 10 --out <file>

Since 2026-10-15 (Tate's approval) the same call also names up to nine other books -- the
configured `odds_api.bookmakers_1h` list, Hard Rock plus nine -- so Hard Rock's alternate
prices can be compared with the market's at the EXACT same line and side. Ten or fewer
named books bill as one region, so the cost is unchanged: 2 credits per event (two
markets x one region). The probe stops after the first event if the feed bills more.
It reports, per event: every book's rows as fed (nothing substituted), Hard Rock against
the other books at each identical line, each two-sided quote's hold and de-vigged fair
probability, Hard Rock's quotes by price range, and the data-quality gaps. `--csv`
writes the raw rows for the Florida-app comparison.

Cost: 2 credits per event. Hard cap 12 events (24 credits). Prints the credits it spent.
Never writes the database.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from beatvegas.devig import devig_two_way, is_hr_rung  # noqa: E402
from beatvegas.sources.odds import OddsAPIClient  # noqa: E402

HR = "hardrockbet"
MARKETS = "totals_h1,alternate_totals_h1"
CREDITS_PER_EVENT = 2
MAX_EVENTS = 12
MAX_BOOKS = 10  # one region (sources/odds.py MAX_BOOKMAKERS_ONE_REGION)
# Hard Rock's price for a side is "noticeably" different from the market's when its
# implied probability is 2+ points away from the other books' median at the same line.
NOTICEABLE_PTS = 0.02
PRICE_RANGES = (
    (100, 10_000, "plus money"),
    (-120, -100, "-100 to -120"),
    (-150, -121, "-121 to -150"),
    (-200, -151, "-151 to -200"),
    (-250, -201, "-201 to -250"),
    (-100_000, -251, "-251 and shorter"),
)


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


def implied(price: int) -> float:
    """The probability an American price charges (vig included)."""
    return 100.0 / (price + 100.0) if price > 0 else -price / (-price + 100.0)


def price_range(price: Optional[int]) -> Optional[str]:
    if price is None:
        return None
    for lo, hi, label in PRICE_RANGES:
        if lo <= price <= hi:
            return label
    return None


def book_rows(event: Dict[str, Any], captured_at: str) -> List[Dict[str, Any]]:
    """Every (book, market, line) the feed returned for one event, exactly as fed: a
    missing side stays None and nothing is substituted. `last_update` is the feed's
    market stamp, else the bookmaker's."""
    out: List[Dict[str, Any]] = []
    for bm in event.get("bookmakers", []):
        for m in bm.get("markets", []):
            for pt, over, under in _pairs(m):
                out.append(
                    {
                        "event_id": event.get("id"),
                        "game": f"{event.get('away_team')} @ {event.get('home_team')}",
                        "kick": event.get("commence_time"),
                        "book": bm.get("key"),
                        "market": m.get("key"),
                        "line": pt,
                        "over": over,
                        "under": under,
                        "last_update": m.get("last_update") or bm.get("last_update"),
                        "captured_at": captured_at,
                    }
                )
    return out


def quote_stats(over: Optional[int], under: Optional[int]) -> Dict[str, Optional[float]]:
    """Hold and the multiplicative de-vigged under share, two-sided quotes only."""
    if over is None or under is None:
        return {"hold": None, "fair_under": None}
    _, fair_under, _ = devig_two_way(over, under, "multiplicative")
    return {"hold": implied(over) + implied(under) - 1.0, "fair_under": fair_under}


def compare_hr(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Hard Rock against the other books at the IDENTICAL line, per event and side.

    Main and alternate markets are pooled per book (a book's line is its line, whichever
    market carried it). A Hard Rock line no other book quotes is reported with no
    comparison, never matched to a nearby total. The market's fair under share at the
    line is the median of the other books' two-sided de-vigged shares (2+ books)."""
    by_key: Dict[Tuple[Any, float], Dict[str, Tuple[Optional[int], Optional[int]]]] = {}
    for r in rows:
        by_key.setdefault((r["event_id"], r["line"]), {}).setdefault(
            r["book"], (r["over"], r["under"])
        )
    games = {r["event_id"]: r["game"] for r in rows}
    out: List[Dict[str, Any]] = []
    for (eid, line), books in sorted(by_key.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        if HR not in books:
            continue
        hr_over, hr_under = books[HR]
        others = {b: q for b, q in books.items() if b != HR}
        fairs = [
            quote_stats(o, u)["fair_under"]
            for o, u in others.values()
            if o is not None and u is not None
        ]
        fair_under = statistics.median(fairs) if len(fairs) >= 2 else None
        for side, hr_price, idx in (("under", hr_under, 1), ("over", hr_over, 0)):
            if hr_price is None:
                continue
            prices = [q[idx] for q in others.values() if q[idx] is not None]
            med = statistics.median(implied(p) for p in prices) if prices else None
            fair = (
                None
                if fair_under is None
                else (fair_under if side == "under" else 1.0 - fair_under)
            )
            out.append(
                {
                    "event_id": eid,
                    "game": games.get(eid),
                    "line": line,
                    "side": side,
                    "hr_price": hr_price,
                    "range": price_range(hr_price),
                    "others": len(prices),
                    "best_other": max(prices, key=lambda p: -implied(p)) if prices else None,
                    "hr_minus_market_pts": None if med is None else implied(hr_price) - med,
                    "hr_hold": quote_stats(hr_over, hr_under)["hold"],
                    "fair": fair,
                    "fair_books": len(fairs),
                    # EV at Hard Rock's price against the other books' fair share, no
                    # push mass (a whole-number line is flagged in the report).
                    "ev": None
                    if fair is None
                    else fair * (100.0 / -hr_price if hr_price < 0 else hr_price / 100.0)
                    - (1.0 - fair),
                    "whole_line": abs(line - round(line)) < 1e-9,
                }
            )
    return out


def quality(rows: List[Dict[str, Any]], books_asked: List[str], events: int) -> List[str]:
    """Plain lines about what the feed did NOT give: books absent per event, events with
    no alternate ladder per book, one-sided quotes, and stamp ages at capture."""
    lines: List[str] = []
    for b in books_asked:
        evs = {r["event_id"] for r in rows if r["book"] == b}
        alt = {
            r["event_id"] for r in rows if r["book"] == b and r["market"] == "alternate_totals_h1"
        }
        one_sided = sum(
            1 for r in rows if r["book"] == b and (r["over"] is None or r["under"] is None)
        )
        ages = []
        for r in rows:
            if r["book"] != b or not r["last_update"]:
                continue
            try:
                lu = datetime.fromisoformat(str(r["last_update"]).replace("Z", "+00:00"))
                cap = datetime.fromisoformat(str(r["captured_at"]).replace("Z", "+00:00"))
                ages.append((cap - lu).total_seconds())
            except ValueError:
                continue
        age = (
            f"stamp age at capture median {statistics.median(ages):.0f}s, max {max(ages):.0f}s"
            if ages
            else "no stamps"
        )
        seen: Dict[Tuple[Any, float], set] = {}
        for r in rows:
            if r["book"] == b:
                seen.setdefault((r["event_id"], r["line"]), set()).add((r["over"], r["under"]))
        conflicts = sum(1 for v in seen.values() if len(v) > 1)
        lines.append(
            f"- {b}: quoted {len(evs)} of {events} events; alternate ladder on {len(alt)}; "
            f"one-sided quotes {one_sided}; same line priced two ways {conflicts}; {age}"
        )
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--within-min", type=int, default=120, help="games kicking off within N minutes"
    )
    ap.add_argument("--max-events", type=int, default=10)
    ap.add_argument("--out", type=Path, help="also write the markdown here")
    ap.add_argument("--csv", type=Path, help="also write every book's raw rows here")
    args = ap.parse_args(argv)
    if not 1 <= args.max_events <= MAX_EVENTS:
        ap.error(f"--max-events must be 1..{MAX_EVENTS} ({CREDITS_PER_EVENT} credits each)")

    client = OddsAPIClient()
    books = [HR] + [b for b in client.bookmakers if b != HR][: MAX_BOOKS - 1]
    if len(books) > MAX_BOOKS:
        ap.error("more than one region's worth of books")
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
    rows: List[Dict[str, Any]] = []
    raw: List[Dict[str, Any]] = []
    stopped = None
    for e in picked:
        stamp = datetime.now(timezone.utc).isoformat()
        data = client.event_odds_raw(e["id"], MARKETS, books)
        last = client.last_credits.last_cost if client.last_credits else None
        if data:
            rows.append(summarize(data))
            raw += book_rows(data, stamp)
        if last is not None and last > CREDITS_PER_EVENT:
            stopped = f"STOPPED: the feed billed {last} credits for one event (budget {CREDITS_PER_EVENT})."
            break
    c = client.last_credits
    spent = (c.used - used_before) if c and c.used is not None and used_before is not None else None
    out = [
        f"# Alternate-line probe ({now:%Y-%m-%dT%H:%M:%SZ})",
        "",
        f"Books asked ({len(books)}, one region): {', '.join(books)}.",
        "",
    ]
    if stopped:
        out += [stopped, ""]
    out += [
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
    cmp_rows = compare_hr(raw)
    pct = lambda v: "—" if v is None else f"{100 * v:+.1f}"  # noqa: E731
    out += [
        "",
        "## Hard Rock against the other books at the identical line",
        "",
        "`vs market` = Hard Rock's implied probability minus the other books' median at the same "
        "line and side (negative = Hard Rock is cheaper). `fair` = the other books' median "
        "de-vigged share (2+ two-sided books). `EV` = Hard Rock's price against that fair share, "
        "no push mass (whole-number lines marked *). Nothing is matched to a different total.",
        "",
        "| game | line | side | Hard Rock | range | other books | best other | vs market (pts) | HR hold | fair | EV |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in cmp_rows:
        fair_txt = "—" if r["fair"] is None else f"{100 * r['fair']:.1f}%"
        best = "—" if r["best_other"] is None else str(r["best_other"])
        star = "*" if r["whole_line"] else ""
        out.append(
            f"| {r['game']} | {r['line']}{star} | {r['side']} | {r['hr_price']} | {r['range']} | "
            f"{r['others']} | {best} | {pct(r['hr_minus_market_pts'])} | {pct(r['hr_hold'])} | "
            f"{fair_txt} | {pct(r['ev'])} |"
        )
    out += ["", "## Hard Rock's unders by price range", ""]
    for _, _, label in PRICE_RANGES:
        rs = [r for r in cmp_rows if r["side"] == "under" and r["range"] == label]
        if not rs:
            out.append(f"- {label}: none")
            continue
        compared = [r for r in rs if r["hr_minus_market_pts"] is not None]
        better = [r for r in compared if r["hr_minus_market_pts"] <= -NOTICEABLE_PTS]
        worse = [r for r in compared if r["hr_minus_market_pts"] >= NOTICEABLE_PTS]
        evs = [r["ev"] for r in rs if r["ev"] is not None]
        out.append(
            f"- {label}: {len(rs)} Hard Rock quotes; {len(compared)} with the same line at another "
            f"book; Hard Rock noticeably cheaper on {len(better)}, dearer on {len(worse)}; "
            f"EV against the market's fair share: "
            + (
                f"median {100 * statistics.median(evs):+.1f}%, best {100 * max(evs):+.1f}% (n {len(evs)})"
                if evs
                else "none computable"
            )
        )
    out += ["", "## Data quality", ""] + quality(raw, books, len(rows))
    no_cmp = sum(1 for r in cmp_rows if r["others"] == 0)
    out += [
        f"- Hard Rock side-quotes with no other book at the identical line: {no_cmp} of {len(cmp_rows)} (left uncompared).",
        "",
        f"Credits: this run {spent if spent is not None else 'unknown'} "
        f"(cap {CREDITS_PER_EVENT * MAX_EVENTS}); remaining {c.remaining if c else '?'}.",
    ]
    text = "\n".join(out) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)
    if args.csv:
        with args.csv.open("w", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "event_id",
                    "game",
                    "kick",
                    "book",
                    "market",
                    "line",
                    "over",
                    "under",
                    "last_update",
                    "captured_at",
                ],
            )
            w.writeheader()
            w.writerows(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
