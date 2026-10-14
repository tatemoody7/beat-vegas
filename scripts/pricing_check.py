#!/usr/bin/env python
"""H-PRICE-HR (docs/HYPOTHESES.md, exploratory; docs/PRICING_RESEARCH.md): Hard
Rock's prices against the vig-free market reference at the same moment, on the
odds_snapshots already captured. The frozen rule is `pv1` (beatvegas/pricing.py).

    pricing_monday.yml -> pricing_check            (Monday, Vercel-dispatched)
    study.yml          -> pricing_check [--season N] [--markets ...] [--fl-checks FILE]

READ-ONLY: writes reports/pricing_check_<UTC>.{md,json,csv}, no table. Refuses
(exit 2) when the registry row is not runnable (beatvegas/registry.py). The
report separates DEVELOPMENT states (captured before pricing.FORWARD_CUTOFF,
2026-10-13: the rule was chosen after looking at them) from FORWARD states, and
the cumulative verdict reads the forward opportunities only. Every flag carries
an evidence tier; a tier rises to 2 only when a row of data/fl_app_checks.csv
(Tate's Florida screenshots) matches the same game, market, line, prices and a
capture within ten minutes. Nothing below tier 2 is ever called available in
Florida. Independent of every arm, the judge and the card.
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
from beatvegas.season import current_season  # noqa: E402

FL_CHECKS_PATH = ROOT / "data" / "fl_app_checks.csv"


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
            first_half_source=g.first_half_source,
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
    return s


def _share(lo, hi) -> str:
    return "—" if lo is None else f"{100 * lo:.0f}% to {100 * hi:.0f}%"


def _market_rows(label: str, by_market: Dict[str, Dict[str, Any]]) -> List[str]:
    out = [
        f"### {label}",
        "",
        "| market | HR states (games) | mean EV vs ref | ≥+2% (point) | flags (lower bound) | opportunities | EV vs ref (lower) | EV vs close | market moved | Florida | record | units |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m, s in by_market.items():
        fl = s.get("fl_checks", {})
        fl_txt = f"{fl.get('match', 0)} match / {fl.get('mismatch', 0)} mismatch / {s['opportunities'] - fl.get('match', 0) - fl.get('mismatch', 0) - fl.get('ambiguous', 0)} unverified"
        out.append(
            f"| {m} | {s['states_compared']} ({s['games']}) | {_pct(s['mean_ev_ref'])} | {s['ev_ge2_point']} | "
            f"{s['flagged_lower_bound']} | {s['opportunities']} | {_ci(s['opps_ev_ref_lower'])} | {_ci(s['opps_ev_close'])} | "
            f"{s['opps_market_moved'] or '—'} | {fl_txt} | {s['opps_record'] or '—'} | {s['opps_units']:+.2f} |"
        )
    return out + [""]


def _opp_rows(opps: List[Dict[str, Any]]) -> List[str]:
    out = [
        "| market | week | game | captured (UTC) | h to kick | Hard Rock | ref | side @ price | EV ref | EV lower | EV close | moved | tier | Florida | result |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for o in sorted(opps, key=lambda r: (r["captured_at"], r["market"])):
        hr = (
            f"{o['hr_line']} ({o['hr_over']}/{o['hr_under']})"
            if o["market"] in P.TOTALS_MARKETS
            else f"ML {o['hr_home']}/{o['hr_away']}"
        )
        out.append(
            f"| {o['market']} | {o['week']} | {o['game']} | {o['captured_at'].strftime('%m-%d %H:%M')} | {o['hrs_to_kick']:.1f} | {hr} | "
            f"{o['ref_line'] if o['ref_line'] is not None else '—'} | {o['side']} @ {o['price']} | {_pct(o['ev_ref'])} | {_pct(o['ev_ref_lower'])} | "
            f"{_pct(o['ev_close'])} | {o['market_moved']} | {o['tier']} | {o.get('fl_check', 'none')} | {o['result'] or '—'} |"
        )
    return out


def _drops_and_shares(by_market: Dict[str, Dict[str, Any]]) -> List[str]:
    """The two tables the criterion names and the report did not print until
    2026-10-14: every drop reason per market, and the flag share by hours to
    kickoff and by weekday (ET)."""
    out = ["", "| market | drops (reason: states) |", "|---|---|"]
    for m, sm in by_market.items():
        d = sm.get("drops") or {}
        txt = ", ".join(f"{k} {v}" for k, v in sorted(d.items())) or "none"
        out.append(f"| {m} | {txt} |")
    out += [
        "",
        "| market | hours to kickoff | states | flag share | mean EV vs ref |",
        "|---|---|---|---|---|",
    ]
    for m, sm in by_market.items():
        for band, r in (sm.get("by_hours_to_kick") or {}).items():
            out.append(
                f"| {m} | {band} | {r['n']} | {r['flag_share']:.1%} | {_pct(r['mean_ev_ref'])} |"
            )
    out += ["", "| market | weekday (ET) | states | flags |", "|---|---|---|---|"]
    for m, sm in by_market.items():
        for day, r in (sm.get("by_weekday") or {}).items():
            out.append(f"| {m} | {day} | {r['n']} | {r['flags']} |")
    return out + [""]


def render(
    row: Any,
    season: int,
    dev: Dict[str, Dict[str, Any]],
    fwd: Dict[str, Dict[str, Any]],
    v: Dict[str, Any],
    opps_fwd: List[Dict[str, Any]],
    opps_dev: List[Dict[str, Any]],
    fl_counts: Mapping[str, int],
    stamp: str,
) -> str:
    lo, hi = v["toward_hr_share_90"]
    out = [
        f"# Pricing research, week ending {stamp[:8]} — {P.ROW_ID}, rule `{P.RULE_VERSION}`",
        "",
        f"## Verdict (forward observations since {P.FORWARD_CUTOFF:%Y-%m-%d} only): **{v['verdict'].upper()}**",
        "",
        f"- {v['why']}.",
        f"- Forward opportunities: **{v['opportunities']}** of the {v['min_required']} needed before a direction is read; "
        f"{v['fl_verified']} verified in the Florida app (tier 2+).",
        f"- Market moved toward Hard Rock in {v['toward_hr']} of {v['resolved']} resolved ({_share(lo, hi)} at 90%); "
        f"reads as Hard Rock off-market when the upper bound is below 50%, as Hard Rock right when the lower bound is above 40%.",
        f"- EV against the close on forward opportunities: {_ci(v['ev_close'])} (n {v['ev_close']['n']}). Not independent when the close equals the reference.",
        "",
        "**Every flag below tier 2 is UNVERIFIED for Florida.** Tiers: 0 one feed observation; 1 provider stamp within "
        f"{P.FRESH_MIN} min and re-seen (quoted and persisting, not available between polls); 2 Florida-app screenshot matching the "
        "game, market, line, prices and a capture within 10 minutes (data/fl_app_checks.csv); 3 ticket. The feed has no "
        "Florida key (probe 2026-10-11).",
        "",
        "## Forward (the evidence)",
        "",
    ]
    out += _market_rows(f"Since {P.FORWARD_CUTOFF:%Y-%m-%d}", fwd)
    out += _drops_and_shares(fwd)
    out += ["#### Forward opportunities", ""]
    out += _opp_rows(opps_fwd) if opps_fwd else ["(none yet)"]
    out += [
        "",
        "## Development (weeks before the cutoff; the rule was chosen after seeing these, so they are context, not evidence)",
        "",
    ]
    out += _market_rows(f"Before {P.FORWARD_CUTOFF:%Y-%m-%d}", dev)
    out += _drops_and_shares(dev)
    out += ["<details><summary>Development opportunities</summary>", ""]
    out += _opp_rows(opps_dev) if opps_dev else ["(none)"]
    out += ["", "</details>", "", "## Florida checks on file", ""]
    out.append(
        f"- Screenshot rows: {sum(fl_counts.get(k, 0) for k in ('match', 'mismatch', 'ambiguous'))} matched to a compared state "
        f"({fl_counts.get('match', 0)} match, {fl_counts.get('mismatch', 0)} mismatch, {fl_counts.get('ambiguous', 0)} ambiguous); "
        f"{fl_counts.get('invalid_rows', 0)} rows unreadable (skipped, never guessed)."
    )
    out += [
        "",
        "## Rule and reading",
        "",
        f"Reference = median of every other centred book confirmed present at the capture minute (≥ {P.MIN_BOOKS}; Fliff and the "
        f"consensus row excluded), de-vigged {P.DEVIG}; totals converted to Hard Rock's exact line through the frozen table within "
        f"{P.MAX_CONVERT_PTS} pts; a FLAG is EV ≥ {P.EV_FLAG:+.0%} at the LOWER bound of the table's integer masses; moneylines only "
        f"within ±{P.ML_MAX_ABS_PRICE}; spreads not compared; one opportunity per game-side (the first). Season {season}. "
        "Exploratory: nothing is adopted from this report; a changed rule is `pv2`, read beside this one.",
        "",
        "> " + row.criterion,
    ]
    return "\n".join(out) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=None, help="default: the current season")
    ap.add_argument("--markets", default=",".join(P.MARKETS))
    ap.add_argument("--out", default="reports")
    ap.add_argument(
        "--fl-checks", type=Path, default=FL_CHECKS_PATH, help="Tate's Florida screenshot CSV"
    )
    ap.add_argument("--no-init", action="store_true", help="skip init_db (a local read-only run)")
    args = ap.parse_args(argv)
    season = args.season or current_season()
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
    checks = P.load_fl_checks(args.fl_checks)
    with session_scope() as s:
        games, snaps = load(s, season, markets)
    dev_by: Dict[str, Dict[str, Any]] = {}
    fwd_by: Dict[str, Dict[str, Any]] = {}
    opps_dev: List[Dict[str, Any]] = []
    opps_fwd: List[Dict[str, Any]] = []
    states_all: List[Dict[str, Any]] = []
    fl_counts: Dict[str, int] = defaultdict(int)
    for m in markets:
        states, drops = P.price_states(games, snaps, m, table)
        for k, n in P.apply_fl_checks(states, checks).items():
            fl_counts[k] += n
        dev, fwd = P.split_dev_forward(states)
        # Each era's own drops (2026-10-14): one shared counter used to put the
        # development drops into the forward summary as well.
        dev_by[m] = P.summarize_market(dev, P.drops_for(drops, "dev"))
        fwd_by[m] = P.summarize_market(fwd, P.drops_for(drops, "forward"))
        for block, summary in ((dev, dev_by[m]), (fwd, fwd_by[m])):
            o = P.first_per_game_side(block)
            summary["fl_checks"] = dict(
                (k, sum(1 for x in o if x.get("fl_check") == k))
                for k in ("match", "mismatch", "ambiguous")
            )
        opps_dev += P.first_per_game_side(dev)
        opps_fwd += P.first_per_game_side(fwd)
        states_all += states
        print(
            f"[pricing] {m}: dev {dev_by[m]['states_compared']} states / {dev_by[m]['opportunities']} opps; "
            f"forward {fwd_by[m]['states_compared']} states / {fwd_by[m]['opportunities']} opps; drops {dict(drops)}"
        )
    fl_counts["invalid_rows"] = sum(1 for c in checks if c.get("invalid"))
    v = P.verdict(opps_fwd)
    print(f"[pricing] verdict: {v['verdict']} ({v['why']})")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md = render(row, season, dev_by, fwd_by, v, opps_fwd, opps_dev, fl_counts, stamp)
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    stem = outdir / f"pricing_check_{stamp}"
    stem.with_suffix(".md").write_text(md)
    stem.with_suffix(".json").write_text(
        json.dumps(
            {
                "rule": P.RULE_VERSION,
                "season": season,
                "run_at": stamp,
                "forward_cutoff": P.FORWARD_CUTOFF.isoformat(),
                "verdict": v,
                "development": dev_by,
                "forward": fwd_by,
                "opportunities_forward": opps_fwd,
                "opportunities_development": opps_dev,
                "fl_checks": dict(fl_counts),
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
