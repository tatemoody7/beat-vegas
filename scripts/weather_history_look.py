#!/usr/bin/env python
"""H-WX-HIST (docs/HYPOTHESES.md; exploratory, one look): did windy forecasts
move, or beat, the totals market in 2024-25?

Strategic review topic 3 (Tate, 2026-10-09): weather is tested as its own edge.
Universe: 2024-25 FBS-vs-FBS games, outdoor, with the decision-safe forecast 72
hours out (`weather_obs`, lead 72, `decision_safe`, the newest fetch per game),
wind read at the kickoff hour. WINDY = sustained wind of 10+ mph (the threshold
frozen for the forward arms, beatvegas/wx_paper.py); CALM = the rest, the control.

Two readings per market, windy beside calm:
- LINE VALUE: the under at the early consensus line (24+ hours out; the history
  holds a ~48-hour snapshot), priced -110, read by the 2026 judge against the
  consensus close (beatvegas/backtest/early_close.py). A no-move bet reads
  about -4.5%; a market slow to price wind shows windy above calm.
- THE CLOSE: the under at the consensus closing line, pushes dropped -- the
  win rate with its Wilson interval and a one-sided exact binomial against the
  52.38% break-even at -110.
Plus both readings by wind band (a dose-response read, no criterion).

Exploratory: counts and intervals only; nothing is adopted from it, and the
forward arms H-ARM-WX1H / H-ARM-WXFG are judged on their own clocks. READ-ONLY;
writes reports/wx_history_<UTC>.{md,json}. Runs through study.yml.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beatvegas.backtest.early_close import (  # noqa: E402
    bootstrap_mean_ci,
    exclusion_counts,
    records,
    settle,
    units,
    week_key,
)
from beatvegas.backtest.literature import binomial_p  # noqa: E402
from beatvegas.backtest.stats import wilson  # noqa: E402
from beatvegas.db.models import WeatherObs  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402

SEASONS = (2024, 2025)
LEAD_HOURS = 72
WIND_MIN_MPH = 10.0  # frozen 2026-10-09; the same as wx_paper.WIND_MIN_MPH
BANDS = ((0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, None))
MARKETS = ("1H_total", "full_game_total")


def forecasts(session) -> Dict[int, dict]:
    """game_id -> the newest decision-safe 72-hour forecast row."""
    rows = (
        session.query(WeatherObs)
        .filter(WeatherObs.lead_hours == LEAD_HOURS, WeatherObs.decision_safe.is_(True))
        .order_by(WeatherObs.retrieved_at.asc(), WeatherObs.id.asc())
        .all()
    )
    out: Dict[int, dict] = {}
    for r in rows:  # ascending, so the newest wins
        out[int(r.game_id)] = {"wind": r.wind_mph, "dome": bool(r.dome)}
    return out


def band(w: float) -> str:
    for lo, hi in BANDS:
        if w >= lo and (hi is None or w < hi):
            return f"{lo:g}+" if hi is None else f"{lo:g}-{hi:g}"
    return "?"


def summarize(recs: List[dict]) -> dict:
    """Line value and the record against the close for one group of games."""
    by_week = defaultdict(list)
    for r in recs:
        ev = r["under"]["ev"]
        if ev is not None:
            by_week[week_key(r)].append(ev)
    evs = [x for g in by_week.values() for x in g]
    results = [settle(r["total"], r["close"], "under") for r in recs]
    wins = results.count("win")
    losses = results.count("loss")
    pushes = results.count("push")
    n = wins + losses
    lo, hi = wilson(wins, n) if n else (None, None)
    profit = [units(x) for x in results if x in ("win", "loss", "push")]
    return {
        "games": len(recs),
        "line_value_n": len(evs),
        "line_value_mean": sum(evs) / len(evs) if evs else None,
        "line_value_ci95": bootstrap_mean_ci(list(by_week.values())),
        "close_record": f"{wins}-{losses}-{pushes}",
        "close_win_rate": wins / n if n else None,
        "close_wilson95": (lo, hi),
        "close_p_vs_breakeven": binomial_p(wins, n) if n else None,
        "close_units": round(sum(profit), 2) if profit else None,
        "excluded_line_value": exclusion_counts(recs, sides=("under",)),
        "excluded_close": sum(1 for x in results if x is None),
    }


def split(recs: List[dict], fc: Dict[int, dict]) -> Dict[str, List[dict]]:
    """Outdoor games with a forecast, into windy / calm and the wind bands."""
    groups: Dict[str, List[dict]] = defaultdict(list)
    for r in recs:
        f = fc.get(r["game_id"])
        if f is None or f["dome"] or f["wind"] is None:
            continue
        groups["windy" if f["wind"] >= WIND_MIN_MPH else "calm"].append(r)
        groups[f"band {band(f['wind'])}"].append(r)
    return groups


def _fmt(x: Optional[float], pct: bool = True) -> str:
    if x is None:
        return "—"
    return f"{100 * x:+.2f}%" if pct else f"{x:.3f}"


def render(result: dict, stamp: str) -> str:
    L = [
        f"# H-WX-HIST, weather history look ({stamp})",
        "",
        f"2024-25 FBS-vs-FBS outdoor games; forecast {LEAD_HOURS} h out (decision-safe), wind at the "
        f"kickoff hour; WINDY = {WIND_MIN_MPH:g}+ mph. Line value = the under at the early consensus "
        "line (24+ h out), -110, against the consensus close (a no-move bet reads about -4.5%). "
        "Close = the under at the consensus closing line, pushes dropped; p is one-sided exact "
        "binomial vs 52.38%. Exploratory: nothing is adopted from it.",
        "",
        "| market | group | games | line value n | mean line value (95% CI, weeks) | record vs close | "
        "win rate (Wilson 95%) | p | units at -110 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for market, groups in result.items():
        for name, r in groups.items():
            ci = r["line_value_ci95"]
            ci_s = "—" if ci is None else f"{_fmt(ci[0])} to {_fmt(ci[1])}"
            lo, hi = r["close_wilson95"]
            wr = (
                "—"
                if r["close_win_rate"] is None
                else f"{100 * r['close_win_rate']:.1f}% ({100 * lo:.1f}–{100 * hi:.1f})"
            )
            p = "—" if r["close_p_vs_breakeven"] is None else f"{r['close_p_vs_breakeven']:.3f}"
            L.append(
                f"| {market} | {name} | {r['games']} | {r['line_value_n']} | "
                f"{_fmt(r['line_value_mean'])} ({ci_s}) | {r['close_record']} | {wr} | {p} | "
                f"{r['close_units']} |"
            )
    L.append("")
    for market, groups in result.items():
        for name in ("windy", "calm"):
            if name in groups:
                why = groups[name]["excluded_line_value"]
                why_s = ", ".join(f"{k} {v}" for k, v in sorted(why.items())) or "none"
                L.append(f"- {market} {name}: unders with no line-value reading: {why_s}")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports")
    args = ap.parse_args(argv)
    if not try_init_db():
        return 1
    result: Dict[str, dict] = {}
    with session_scope() as s:
        fc = forecasts(s)
        for market in MARKETS:
            groups = split(records(s, SEASONS, market), fc)
            order = ["windy", "calm"] + sorted(k for k in groups if k.startswith("band"))
            result[market] = {k: summarize(groups[k]) for k in order if k in groups}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md = render(result, stamp)
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"wx_history_{stamp}.md").write_text(md)
    (outdir / f"wx_history_{stamp}.json").write_text(json.dumps(result, indent=1, default=str))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
