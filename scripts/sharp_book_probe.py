#!/usr/bin/env python
"""H5 -- does any sharp book post CFB first-half totals through the Odds API?

PROBE ONLY (docs/HYPOTHESES.md row H5): no config change, no swap. Every "market"
number the system compares Hard Rock to is a retail median; if Pinnacle, Circa,
BookMaker or BetOnline post totals_h1, a sharper reference exists. This script finds
out, with a credit budget, in three steps:

  1. list_events (FREE) -- the upcoming slate and the current credit balance.
  2. discovery: for the first N events, one per-event call with REGIONS us,us2,eu
     (billed markets x regions = 3 credits each) to list EVERY bookmaker key that
     posts a 1H total, retail or sharp.
  3. coverage: the sharp keys found (any key not in our ten) plus hardrockbet, as a
     bookmakers= list (1 credit per event), across the slate: posted or not, line,
     prices, last_update, and Hard Rock's line in the same response.

    PYTHONPATH=. python scripts/sharp_book_probe.py                 # dry run: step 1 only, prints the plan
    PYTHONPATH=. python scripts/sharp_book_probe.py --live          # spends credits, capped by --max-credits

Writes reports/sharp_books_<UTC>.{md,json}; exits 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from residual_gate import append_step_summary, report_paths  # noqa: E402

from beatvegas.config import load_config  # noqa: E402
from beatvegas.hardrock import HR_BOOK_KEY  # noqa: E402
from beatvegas.sources.odds import OddsAPIClient  # noqa: E402

DISCOVERY_REGIONS = "us,us2,eu"
# Keys the Odds API has used for books the industry calls sharp. Discovery does
# not depend on this list -- it is only for labelling what comes back.
SHARP_HINTS = {
    "pinnacle": "Pinnacle",
    "betonlineag": "BetOnline",
    "lowvig": "LowVig",
    "bookmaker": "BookMaker",
    "circasports": "Circa",
    "circa": "Circa",
    "betcris": "Betcris",
}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--live", action="store_true", help="spend credits (default: dry run)")
    ap.add_argument("--max-credits", type=int, default=120)
    ap.add_argument("--discovery-events", type=int, default=3)
    ap.add_argument("--out", default="reports/sharp_books")
    return ap.parse_args(argv)


# ---------------------------------------------------------------- pure


def h1_quotes(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One row per bookmaker that posts a totals_h1 market in an event response."""
    rows: List[Dict[str, Any]] = []
    for bk in event.get("bookmakers") or []:
        for m in bk.get("markets") or []:
            if m.get("key") != "totals_h1":
                continue
            over = under = point = None
            for oc in m.get("outcomes") or []:
                if oc.get("name") == "Over":
                    over, point = oc.get("price"), oc.get("point")
                elif oc.get("name") == "Under":
                    under = oc.get("price")
                    point = oc.get("point") if point is None else point
            rows.append(
                {
                    "event_id": event.get("id"),
                    "book": bk.get("key"),
                    "title": bk.get("title"),
                    "line": point,
                    "over": over,
                    "under": under,
                    "last_update": bk.get("last_update"),
                }
            )
    return rows


def discovered_keys(responses: Iterable[Dict[str, Any]], ours: Sequence[str]) -> Dict[str, Any]:
    """Every key posting a 1H total across the discovery responses, split into
    the ten we already request and the rest."""
    seen: Dict[str, int] = {}
    for ev in responses:
        for q in h1_quotes(ev):
            seen[q["book"]] = seen.get(q["book"], 0) + 1
    others = {k: v for k, v in seen.items() if k not in ours}
    return {
        "all": dict(sorted(seen.items())),
        "ours_seen": {k: v for k, v in seen.items() if k in ours},
        "others": dict(sorted(others.items())),
        "sharp_labelled": {k: SHARP_HINTS[k] for k in others if k in SHARP_HINTS},
    }


def coverage(responses: Iterable[Dict[str, Any]], sharp_keys: Sequence[str]) -> Dict[str, Any]:
    """Per sharp key: events posted, events where Hard Rock also posted, mean
    |sharp - HR| and the sign, and how the update times compare."""
    per_event: List[Dict[str, Any]] = []
    for ev in responses:
        quotes = {q["book"]: q for q in h1_quotes(ev)}
        hr = quotes.get(HR_BOOK_KEY)
        row = {
            "event_id": ev.get("id"),
            "commence": ev.get("commence_time"),
            "away": ev.get("away_team"),
            "home": ev.get("home_team"),
            "hr_line": hr["line"] if hr else None,
            "hr_update": hr["last_update"] if hr else None,
        }
        for k in sharp_keys:
            q = quotes.get(k)
            row[f"{k}_line"] = q["line"] if q else None
            row[f"{k}_over"] = q["over"] if q else None
            row[f"{k}_under"] = q["under"] if q else None
            row[f"{k}_update"] = q["last_update"] if q else None
        per_event.append(row)
    n = len(per_event)
    n_hr = sum(1 for r in per_event if r["hr_line"] is not None)
    summary: Dict[str, Any] = {"events": n, "hr_posted": n_hr, "books": {}}
    for k in sharp_keys:
        posted = [r for r in per_event if r[f"{k}_line"] is not None]
        both = [r for r in posted if r["hr_line"] is not None]
        diffs = [float(r[f"{k}_line"]) - float(r["hr_line"]) for r in both]
        later = sum(1 for r in both if (r[f"{k}_update"] or "") > (r["hr_update"] or ""))
        summary["books"][k] = {
            "label": SHARP_HINTS.get(k, k),
            "posted": len(posted),
            "posted_where_hr_posted": len(both),
            "hr_posted_where_sharp_absent": n_hr - len(both),
            "mean_abs_diff_vs_hr": (sum(abs(d) for d in diffs) / len(diffs)) if diffs else None,
            "mean_signed_diff_vs_hr": (sum(diffs) / len(diffs)) if diffs else None,
            "updated_after_hr": later,
            "under_prices": [r[f"{k}_under"] for r in posted if r[f"{k}_under"] is not None],
        }
    return {"summary": summary, "per_event": per_event}


def render_markdown(r: Dict[str, Any]) -> str:
    L = [
        "# Sharp books and first-half totals — a probe",
        "",
        f"Run {r['generated_at']} ({r['weekday']}), {r['n_events']} upcoming events, credits used "
        f"{r['credits']['start_used']} → {r['credits']['end_used']} (spent {r['credits']['spent']}, "
        f"remaining {r['credits']['remaining']}). Probe only — no config change.",
        "",
        "## Discovery (regions us, us2, eu; every key posting a 1H total)",
        "",
    ]
    d = r["discovery"]
    L.append(f"- Events probed: {r['discovery_events']}.")
    L.append(
        "- Keys we already request, seen: "
        + (", ".join(f"{k} ({v})" for k, v in d["ours_seen"].items()) or "none")
    )
    L.append(
        "- Other keys posting a 1H total: "
        + (", ".join(f"{k} ({v})" for k, v in d["others"].items()) or "**none**")
    )
    L.append(
        "- Of those, sharp by reputation: "
        + (", ".join(f"{k} = {v}" for k, v in d["sharp_labelled"].items()) or "**none**")
    )
    L += ["", "## Coverage of the sharp keys across the slate", ""]
    cov = r.get("coverage")
    if not cov:
        L.append("Not run (no sharp key was discovered, or dry run).")
    else:
        s = cov["summary"]
        L.append(f"{s['events']} events called; Hard Rock posted a 1H total on {s['hr_posted']}.")
        L += [
            "",
            "| key | posted | where HR posted too | HR posted, sharp absent | mean abs diff vs HR | mean signed (sharp − HR) | updated after HR |",
            "|---|---|---|---|---|---|---|",
        ]
        for k, b in s["books"].items():
            mad = "—" if b["mean_abs_diff_vs_hr"] is None else f"{b['mean_abs_diff_vs_hr']:.2f}"
            msd = (
                "—"
                if b["mean_signed_diff_vs_hr"] is None
                else f"{b['mean_signed_diff_vs_hr']:+.2f}"
            )
            L.append(
                f"| {k} ({b['label']}) | {b['posted']} | {b['posted_where_hr_posted']} | {b['hr_posted_where_sharp_absent']} | {mad} | {msd} | {b['updated_after_hr']} |"
            )
    L += ["", "## What a swap would cost", "", r["swap_note"], ""]
    return "\n".join(L)


# ---------------------------------------------------------------- main


def _used(client: OddsAPIClient) -> Optional[int]:
    return client.last_credits.used if client.last_credits else None


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    cfg = load_config().get("odds_api", {}) or {}
    ours = list(cfg.get("bookmakers_1h") or [])
    client = OddsAPIClient()
    events = client.list_events()  # free
    start_used = _used(client)
    print(
        f"[probe] {len(events)} upcoming events; credits used so far this cycle: {start_used}, "
        f"remaining {client.last_credits.remaining if client.last_credits else '?'}"
    )
    plan = (
        f"[probe] plan: discovery on {min(args.discovery_events, len(events))} events at 3 credits each, "
        f"then coverage on up to {len(events)} events at 1 credit each; budget {args.max_credits}."
    )
    print(plan)
    r: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weekday": datetime.now(timezone.utc).strftime("%A"),
        "n_events": len(events),
        "discovery_events": 0,
        "discovery": {"all": {}, "ours_seen": {}, "others": {}, "sharp_labelled": {}},
        "coverage": None,
        "credits": {
            "start_used": start_used,
            "end_used": start_used,
            "spent": 0,
            "remaining": client.last_credits.remaining if client.last_credits else None,
        },
        "swap_note": "",
        "live": args.live,
    }
    if not args.live:
        print("[probe] dry run — nothing spent. Pass --live to run steps 2 and 3.")
        r["swap_note"] = "Dry run."
        _write(r, args.out)
        return 0

    def spent() -> int:
        u = _used(client)
        return (u - start_used) if (u is not None and start_used is not None) else 0

    # step 2: discovery by regions
    client.bookmakers = []
    client.regions = DISCOVERY_REGIONS
    disc_resps: List[Dict[str, Any]] = []
    for ev in events[: args.discovery_events]:
        if spent() + 3 > args.max_credits:
            break
        resp = client.event_first_half_totals(ev["id"])
        if resp:
            disc_resps.append(resp)
    r["discovery_events"] = len(disc_resps)
    r["discovery"] = discovered_keys(disc_resps, ours)
    sharp_keys = [k for k in r["discovery"]["others"]]
    print(f"[probe] discovery: {r['discovery']['all']}")
    # step 3: coverage with the sharp keys + Hard Rock as a bookmakers list
    if sharp_keys:
        keys = ([HR_BOOK_KEY] + sharp_keys)[:10]
        client.bookmakers = keys
        cov_resps: List[Dict[str, Any]] = []
        for ev in events:
            if spent() + 1 > args.max_credits:
                print(f"[probe] budget reached after {len(cov_resps)} events")
                break
            resp = client.event_first_half_totals(ev["id"])
            cov_resps.append(
                resp
                if resp
                else {
                    "id": ev["id"],
                    "commence_time": ev.get("commence_time"),
                    "home_team": ev.get("home_team"),
                    "away_team": ev.get("away_team"),
                    "bookmakers": [],
                }
            )
        r["coverage"] = coverage(cov_resps, [k for k in keys if k != HR_BOOK_KEY])
        r["swap_note"] = (
            "A sharp key can only enter the ten-key call by displacing a retail key; the fair price "
            "(card.py FAIR_PRICE_EXCLUDED) and the consensus median would then rest on nine retail "
            "books plus the sharp one. Nothing here changes config.example.yaml; Tate decides from "
            "the coverage above (docs/HYPOTHESES.md H5)."
        )
    else:
        r["swap_note"] = (
            "No key outside our ten posted a first-half total on the probed events, so there is "
            "nothing to swap in through this API today."
        )
    r["credits"] = {
        "start_used": start_used,
        "end_used": _used(client),
        "spent": spent(),
        "remaining": client.last_credits.remaining if client.last_credits else None,
    }
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
