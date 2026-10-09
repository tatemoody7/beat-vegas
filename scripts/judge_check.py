#!/usr/bin/env python
"""H-JUDGE (docs/HYPOTHESES.md; exploratory, one look): does the 2026 judge's
line value predict what bets actually return?

Strategic review topic 3 (Tate, 2026-10-09). Every arm is judged by `ev_cons`,
the EV of its wager against the vig-free consensus close (beatvegas/consensus.py).
That only measures an edge if the close itself is unbiased. This reads the
2023-25 first-half history (and the full game where an early line exists): for
every FBS-vs-FBS game, the UNDER and the OVER at the early consensus line (24+
hours out), priced -110 (beatvegas/backtest/early_close.py). PREDICTED = the
judge's EV of that bet; REALIZED = units won at -110 on the game's trusted result.

Readings, each with a 95% interval from resampling whole weeks:
1. mean predicted vs mean realized, all bets;
2. by quintile of predicted EV: mean predicted vs mean realized;
3. the slope and intercept of realized on predicted (least squares). A judge
   that tracks reality reads a slope near 1 and an intercept near 0.

Exploratory: it reports; nothing is adopted from it. READ-ONLY; writes
reports/judge_check_<UTC>.{md,json}. Runs through study.yml.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beatvegas.backtest.early_close import (  # noqa: E402
    bootstrap_mean_ci,
    records,
    settle,
    units,
    week_key,
)
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402

SEASONS = {"1H_total": (2023, 2024, 2025), "full_game_total": (2024, 2025)}
QUINTILES = 5
REPS = 2000


def pairs(recs: Sequence[dict]) -> Dict[tuple, List[Tuple[float, float]]]:
    """week -> [(predicted EV, realized units)], both sides of every game."""
    out: Dict[tuple, List[Tuple[float, float]]] = defaultdict(list)
    for r in recs:
        for side in ("under", "over"):
            ev = r[side]["ev"]
            u = units(settle(r["total"], r["early"], side))
            if ev is None or u is None:
                continue
            out[week_key(r)].append((float(ev), float(u)))
    return out


def ols(xy: Sequence[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """(slope, intercept) of y on x; None when x has no spread."""
    n = len(xy)
    if n < 3:
        return None
    mx = sum(x for x, _ in xy) / n
    my = sum(y for _, y in xy) / n
    sxx = sum((x - mx) ** 2 for x, _ in xy)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in xy) / sxx
    return slope, my - slope * mx


def ols_ci(groups: Sequence[Sequence[Tuple[float, float]]], seed: int = 13):
    """95% intervals for slope and intercept, resampling whole weeks."""
    gs = [list(g) for g in groups if g]
    if len(gs) < 2:
        return None
    rnd = random.Random(seed)
    slopes, ints = [], []
    for _ in range(REPS):
        flat = [p for _ in gs for p in gs[rnd.randrange(len(gs))]]
        fit = ols(flat)
        if fit is not None:
            slopes.append(fit[0])
            ints.append(fit[1])
    if not slopes:
        return None
    slopes.sort()
    ints.sort()
    k = len(slopes)
    return (
        (slopes[int(0.025 * k)], slopes[int(0.975 * k) - 1]),
        (ints[int(0.025 * k)], ints[int(0.975 * k) - 1]),
    )


def quintiles(groups: Dict[tuple, List[Tuple[float, float]]]) -> List[dict]:
    """Mean predicted vs mean realized by quintile of predicted EV."""
    flat = sorted(((ev, u, wk) for wk, g in groups.items() for ev, u in g), key=lambda t: t[0])
    if not flat:
        return []
    out = []
    size = len(flat) / QUINTILES
    for q in range(QUINTILES):
        chunk = flat[int(round(q * size)) : int(round((q + 1) * size))]
        if not chunk:
            continue
        by_wk_pred, by_wk_real = defaultdict(list), defaultdict(list)
        for ev, u, wk in chunk:
            by_wk_pred[wk].append(ev)
            by_wk_real[wk].append(u)
        out.append(
            {
                "quintile": q + 1,
                "n": len(chunk),
                "pred_range": (chunk[0][0], chunk[-1][0]),
                "pred_mean": sum(ev for ev, _, _ in chunk) / len(chunk),
                "real_mean": sum(u for _, u, _ in chunk) / len(chunk),
                "real_ci95": bootstrap_mean_ci(list(by_wk_real.values())),
            }
        )
    return out


def read(recs: Sequence[dict]) -> dict:
    groups = pairs(recs)
    flat = [p for g in groups.values() for p in g]
    fit = ols(flat)
    ci = ols_ci(list(groups.values()))
    return {
        "games": len(recs),
        "bets": len(flat),
        "weeks": len(groups),
        "pred_mean": sum(ev for ev, _ in flat) / len(flat) if flat else None,
        "pred_ci95": bootstrap_mean_ci([[ev for ev, _ in g] for g in groups.values()]),
        "real_mean": sum(u for _, u in flat) / len(flat) if flat else None,
        "real_ci95": bootstrap_mean_ci([[u for _, u in g] for g in groups.values()]),
        "slope": None if fit is None else fit[0],
        "intercept": None if fit is None else fit[1],
        "slope_ci95": None if ci is None else ci[0],
        "intercept_ci95": None if ci is None else ci[1],
        "quintiles": quintiles(groups),
        "excluded_no_reading": sum(
            1 for r in recs for side in ("under", "over") if r[side]["ev"] is None
        ),
    }


def _pct(x) -> str:
    return "—" if x is None else f"{100 * x:+.2f}%"


def _ci(c, pct=True) -> str:
    if c is None:
        return "—"
    return f"{_pct(c[0])} to {_pct(c[1])}" if pct else f"{c[0]:.2f} to {c[1]:.2f}"


def render(result: dict, stamp: str) -> str:
    L = [
        f"# H-JUDGE, does line value predict returns? ({stamp})",
        "",
        "Both sides of every FBS-vs-FBS game at the early consensus line (24+ h out), -110. "
        "Predicted = the judge's EV against the consensus close; realized = units on the trusted "
        "result. Intervals resample whole weeks. Exploratory: nothing is adopted from it.",
        "",
        "| market | seasons | games | bets | mean predicted (95%) | mean realized (95%) | slope (95%) | "
        "intercept (95%) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for market, r in result.items():
        slope = "—" if r["slope"] is None else f"{r['slope']:.2f}"
        icpt = _pct(r["intercept"])
        L.append(
            f"| {market} | {'-'.join(map(str, SEASONS[market]))} | {r['games']} | {r['bets']} | "
            f"{_pct(r['pred_mean'])} ({_ci(r['pred_ci95'])}) | {_pct(r['real_mean'])} "
            f"({_ci(r['real_ci95'])}) | {slope} ({_ci(r['slope_ci95'], pct=False)}) | "
            f"{icpt} ({_ci(r['intercept_ci95'])}) |"
        )
    for market, r in result.items():
        if not r["quintiles"]:
            continue
        L += [
            "",
            f"**{market}, by quintile of predicted EV**",
            "",
            "| quintile | bets | predicted range | mean predicted | mean realized (95%) |",
            "|---|---|---|---|---|",
        ]
        for q in r["quintiles"]:
            lo, hi = q["pred_range"]
            L.append(
                f"| {q['quintile']} | {q['n']} | {_pct(lo)} to {_pct(hi)} | {_pct(q['pred_mean'])} | "
                f"{_pct(q['real_mean'])} ({_ci(q['real_ci95'])}) |"
            )
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports")
    args = ap.parse_args(argv)
    if not try_init_db():
        return 1
    result = {}
    with session_scope() as s:
        for market, seasons in SEASONS.items():
            result[market] = read(records(s, seasons, market))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md = render(result, stamp)
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"judge_check_{stamp}.md").write_text(md)
    (outdir / f"judge_check_{stamp}.json").write_text(json.dumps(result, indent=1, default=str))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
