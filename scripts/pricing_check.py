#!/usr/bin/env python
"""H-PRICE-HR (docs/HYPOTHESES.md, exploratory; docs/PRICING_RESEARCH.md): Hard
Rock's prices against the vig-free market reference at the same moment, on the
odds_snapshots already captured. The frozen rule is `pv1` (beatvegas/pricing.py).

    study.yml -> pricing_check [--season 2026] [--markets 1H_total,full_game_total,full_game_ml]

READ-ONLY: writes reports/pricing_check_<UTC>.{md,json,csv}, no table. Refuses
(exit 2) when the registry row is not runnable (beatvegas/registry.py). Every
flag is labelled with its evidence tier; nothing below tier 2 is ever called
available in Florida. Independent of every arm, the judge and the card: it
reads the same snapshot table and writes nothing they read.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beatvegas import pricing as P  # noqa: E402
from beatvegas.db.models import Game, OddsSnapshot  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402
from beatvegas.registry import HarnessRefusal, require_runnable_row  # noqa: E402


def load(session, season: int, markets: List[str]):
    games: Dict[int, P.GameRow] = {}
    for g in session.query(Game).filter(Game.season == season, Game.start_date.isnot(None)).all():
        games[int(g.id)] = P.GameRow(
            id=int(g.id),
            week=g.week,
            home=g.home_team,
            away=g.away_team,
            kickoff=g.start_date,
            home_points=g.home_points,
            away_points=g.away_points,
            first_half_total=g.first_half_total,
        )
    snaps: Dict[int, List[P.Snap]] = defaultdict(list)
    q = (
        session.query(OddsSnapshot)
        .filter(OddsSnapshot.game_id.in_(list(games)), OddsSnapshot.market.in_(markets))
        .order_by(OddsSnapshot.game_id, OddsSnapshot.captured_at, OddsSnapshot.id)
    )
    for o in q.all():
        snaps[int(o.game_id)].append(
            P.Snap(
                game_id=int(o.game_id),
                book=(o.book or "").lower(),
                market=o.market,
                line=o.line,
                over_price=o.over_price,
                under_price=o.under_price,
                home_price=o.home_price,
                away_price=o.away_price,
                captured_at=o.captured_at,
                last_seen_at=o.last_seen_at,
                feed_updated_at=getattr(o, "feed_updated_at", None),
                feed_reseen_at=getattr(o, "feed_reseen_at", None),
            )
        )
    return games, snaps


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{100 * x:+.2f}%"


def _ci(d: Mapping[str, Any]) -> str:
    if d.get("mean") is None:
        return "—"
    s = _pct(d["mean"])
    if d.get("ci"):
        s += f" ({_pct(d['ci'][0])} to {_pct(d['ci'][1])})"
    return s + f", n {d['n']}"


def render(
    row: Any,
    season: int,
    per_market: Dict[str, Dict[str, Any]],
    opps: List[Dict[str, Any]],
    stamp: str,
) -> str:
    out = [
        f"# {P.ROW_ID} — Hard Rock against the market reference, rule `{P.RULE_VERSION}` ({stamp})",
        "",
        f"Season {season}; markets {', '.join(per_market)}. Reference = the median of every other centred book "
        f"confirmed present at the capture minute (at least {P.MIN_BOOKS}; Fliff and the feed's consensus row excluded), "
        f"de-vigged {P.DEVIG}, converted to Hard Rock's exact line through the frozen table (within {P.MAX_CONVERT_PTS} pts). "
        f"A FLAG needs EV >= {P.EV_FLAG:+.0%} at the LOWER bound of the table's integer masses; one opportunity per game-side "
        "(the first qualifying state). Spreads are not compared (no frozen spread table).",
        "",
        "**Every flag below tier 2 is UNVERIFIED for Florida.** Tiers: 0 = one feed observation; 1 = provider stamp within "
        f"{P.FRESH_MIN} min of our capture and the price re-seen at a later poll (quoted and persisting, NOT available between polls); "
        "2 = Florida-app screenshot; 3 = ticket. Tiers 2-3 come from Tate's records, never from this script. The feed offers no "
        "Florida-specific Hard Rock key (probe 2026-10-11).",
        "",
        "## The registry row's criterion (verbatim)",
        "",
        f"> {row.criterion}",
        "",
        "## Per market",
        "",
        "| market | HR states compared (games) | mean EV vs ref | EV>0 | >=+1% | >=+2% (point) | flagged (lower bound) | opportunities | tiers |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m, s in per_market.items():
        out.append(
            f"| {m} | {s['states_compared']} ({s['games']}) | {_pct(s['mean_ev_ref'])} | {s['ev_pos']} | {s['ev_ge1_point']} | "
            f"{s['ev_ge2_point']} | {s['flagged_lower_bound']} | {s['opportunities']} | {s['opps_tiers']} |"
        )
    out += [
        "",
        "## The opportunities, per market (first qualifying state per game-side)",
        "",
        "| market | n | EV vs ref (point) | EV vs ref (lower bound) | EV vs close | line value | market moved | record | units |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m, s in per_market.items():
        lv = s["opps_line_clv"]["mean"]
        lv_txt = "—" if lv is None else f"{lv:+.2f} pts"
        out.append(
            f"| {m} | {s['opportunities']} | {_ci(s['opps_ev_ref'])} | {_ci(s['opps_ev_ref_lower'])} | "
            f"{_ci(s['opps_ev_close'])} | {lv_txt} | {s['opps_market_moved']} | {s['opps_record']} | "
            f"{s['opps_units']:+.2f} |"
        )
    out += [
        "",
        "Reading the columns: *EV vs close* is NOT independent evidence when the close is the same number as the reference "
        "(the market did not move); *market moved* is the honest reading of that: `toward_hr` means the close agreed with Hard "
        "Rock more than the reference did. *record* and *units* are realized outcomes with the variance that implies.",
        "",
        "## Where the states sit (hours to kickoff; flag share)",
        "",
    ]
    for m, s in per_market.items():
        out.append(
            f"- **{m}**: "
            + "; ".join(
                f"{k}: n {v['n']}, flags {v['flag_share']:.1%}, mean EV {_pct(v['mean_ev_ref'])}"
                for k, v in s["by_hours_to_kick"].items()
            )
        )
        out.append(
            "  - by weekday (ET): "
            + ", ".join(f"{k} {v['n']}/{v['flags']}" for k, v in s["by_weekday"].items())
            + " (states/flags)"
        )
    out += ["", "## Drops", ""]
    for m, s in per_market.items():
        out.append(f"- {m}: {json.dumps(s['drops'])}")
    out += [
        "",
        "## Every opportunity",
        "",
        "| market | week | game | captured (UTC) | h to kick | HR | ref line | side @ price | EV ref | EV lower | EV close | moved | tier | result |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for o in sorted(opps, key=lambda r: (r["market"], r["captured_at"])):
        hr = (
            f"{o['hr_line']} ({o['hr_over']}/{o['hr_under']})"
            if o["market"] in P.TOTALS_MARKETS
            else f"ML {o['hr_home']}/{o['hr_away']}"
        )
        out.append(
            f"| {o['market']} | {o['week']} | {o['game']} | {o['captured_at'].strftime('%m-%d %H:%M')} | {o['hrs_to_kick']:.1f} | {hr} | "
            f"{o['ref_line'] if o['ref_line'] is not None else '—'} | {o['side']} @ {o['price']} | {_pct(o['ev_ref'])} | {_pct(o['ev_ref_lower'])} | "
            f"{_pct(o['ev_close'])} | {o['market_moved']} | {o['tier']} | {o['result'] or '—'} |"
        )
    out += [
        "",
        "Exploratory: counts and intervals only. Nothing is adopted from this report; a rule that looks better here is `pv2`, "
        "a second row read beside this one, never a replacement.",
    ]
    return "\n".join(out) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--markets", default=",".join(P.MARKETS))
    ap.add_argument("--out", default="reports")
    ap.add_argument("--no-init", action="store_true", help="skip init_db (a local read-only run)")
    args = ap.parse_args(argv)
    markets = [m.strip() for m in args.markets.split(",") if m.strip()]
    for m in markets:
        if m in P.REFUSED_MARKETS:
            print(f"[pricing] REFUSED market {m}: {P.REFUSED_MARKETS[m]}", file=sys.stderr)
            return 2
        if m not in P.MARKETS:
            print(f"[pricing] unknown market {m}", file=sys.stderr)
            return 2
    try:
        row = require_runnable_row(P.ROW_ID)
    except HarnessRefusal as e:
        print(f"[pricing] REFUSED: {e}", file=sys.stderr)
        return 2
    if not args.no_init and not try_init_db():
        return 1
    table = P.MassTable.load()
    with session_scope() as s:
        games, snaps = load(s, args.season, markets)
    per_market: Dict[str, Dict[str, Any]] = {}
    opps: List[Dict[str, Any]] = []
    states_all: List[Dict[str, Any]] = []
    for m in markets:
        states, drops = P.price_states(games, snaps, m, table)
        per_market[m] = P.summarize_market(states, drops)
        opps += P.first_per_game_side(states)
        states_all += states
        print(
            f"[pricing] {m}: {per_market[m]['states_compared']} states, {per_market[m]['flagged_lower_bound']} flagged, {per_market[m]['opportunities']} opportunities, drops {dict(drops)}"
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md = render(row, args.season, per_market, opps, stamp)
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    stem = outdir / f"pricing_check_{stamp}"
    stem.with_suffix(".md").write_text(md)
    stem.with_suffix(".json").write_text(
        json.dumps(
            {
                "rule": P.RULE_VERSION,
                "season": args.season,
                "run_at": stamp,
                "per_market": per_market,
                "opportunities": opps,
                "criterion": row.criterion,
            },
            indent=1,
            default=str,
        )
    )
    if states_all:
        with stem.with_suffix(".csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(states_all[0]))
            w.writeheader()
            w.writerows(states_all)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
