"""Does seeding the season-to-date window with prior-season form help?

One question, one shot, same shape as backtest/residual_gate.py.

WHAT IS BEING TESTED. `etl/features._season_to_date` computes a team's form as
an expanding mean over its PRIOR games this season, so game 1 of every season is
NaN and game 2 is a one-game mean. 68 of the regressor's 115 features are NaN at
zero games played. The change seeds that window with `k` synthetic games of the
team's prior-season mean (see the docstring there); k=0 reproduces the unseeded
frame exactly, so THE INCUMBENT IS THE k=0 ARM -- not a separate code path that
might differ for some other reason.

WHY IT NEEDS A GATE AT ALL. The seed changes FEATURE_COLS values on EVERY
historical row, not just the early-season ones it targets, so bv_line moves in
weeks 3+ where nothing is currently broken. "Weeks 1-2 improved" is not
sufficient evidence to ship that.

THE STATISTIC IS PAIRED. Both arms score the SAME games, so the useful quantity
is the per-game difference in absolute error, not two independent MAEs. A paired
interval is far tighter than comparing two MAEs with their own noise, and it is
the only way to see a real effect in ~90 test rows per season.

ADOPTION RULE, fixed before the run (docs: the plan of 2026-09-13):
  * weeks 1-2 must IMPROVE -- mean paired gain > 0 with a 95% CI excluding 0;
  * weeks 3+ must be NON-INFERIOR -- the upper bound of the 95% CI on the MAE
    difference stays under NON_INFERIORITY_MARGIN.
Both are reported for every k; `verdict` applies the rule. Tuning happens on the
earlier seasons and the newest season is the untouched confirmation set, so a k
chosen because it flattered the test set is not a k this can produce.

WHAT THE FIRST RUN FOUND (2026-09-13, and why BIAS is also reported).
The rule returned NO ADOPTION and the reason was instructive. Weeks 1-2 -- the
bucket the change was built for -- showed nothing: pooled over both tuning splits
(n=180) the gains ran -0.019 to +0.131 with every interval spanning zero and no
monotonicity in k. Weeks 3+, which nobody was testing, improved monotonically
(+0.038 to +0.117, interval excluding zero at k>=1). The seed helps where a team
already has SOME data -- ordinary shrinkage -- not where it has none.

The reason it has no purchase on weeks 1-2 is that the NaNs were never the
problem. HistGradientBoostingRegressor handles missing values natively by
learning a routing direction for them, so "no games played yet" is a usable
signal to the tree rather than an absence. Replacing it with a noisy
prior-season estimate trades one imperfect input for another.

But MAE is close to BLIND to what this change does. The seed measurably lifts
bv_line's LEVEL -- on 2026 weeks 1-2, 24.26 at k=0 against a realized 26.90,
rising to 25.20 at k=3 -- while MAE moves by less than the noise floor, because
a ~1-point bias correction is nothing against ~11 points of per-game spread.
And bias is what this system actually spends: the product is
`gap = line - bv_line` compared to BET_GAP_PTS, so a level shift changes
SELECTION even when accuracy is flat. On the 23 of those games carrying a real
captured close, the count clearing the gate fell 14 -> 11 across the grid.

So every bucket now also reports `bias`, and `gate` (mean gap + how many games
clear BET_GAP_PTS) whenever closes are supplied. Decision 2026-09-13: those two
are what a future bias-focused gate must be judged on, with MAE demoted to
context. Fixed HERE, before that question is asked of the untouched 2025 set.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..etl.features import build_feature_frame, training_frame
from ..model.bv_line import bv_line_for_slate
from ..model.score import BET_GAP_PTS
from .residual_gate import GateNotEvaluable, _bias, _clean, _mae, walk_forward_split

# The pre-declared grid. Stated here rather than passed in, so "which k did we
# try?" has one answer that predates any result.
PRIOR_WEIGHT_GRID: Sequence[float] = (0.0, 0.5, 1.0, 2.0, 3.0)

# Weeks 3+ may get worse by at most this much (points of MAE, upper 95% bound).
# ~1% of the incumbent's ~9.2 MAE: inside the noise the eyeball comparison this
# replaces was reacting to, and well under the ~1 pt/game effect being chased.
NON_INFERIORITY_MARGIN = 0.10

EARLY_WEEKS = (1, 2)


@dataclass
class AnchorResult:
    per_game: pd.DataFrame
    report: Dict[str, Any]


def _paired_ci(diff: pd.Series, conf: float = 0.95) -> Dict[str, Optional[float]]:
    """Mean of a paired difference with a normal 95% interval.

    `diff` is (incumbent |error|) - (seeded |error|), so POSITIVE = the seed is
    better. n-1 denominator; a single observation has no interval."""
    d = pd.to_numeric(diff, errors="coerce").dropna()
    n = len(d)
    if n == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None, "se": None}
    mean = float(d.mean())
    if n < 2:
        return {"n": n, "mean": mean, "lo": None, "hi": None, "se": None}
    se = float(d.std(ddof=1) / math.sqrt(n))
    z = 1.959963985 if conf == 0.95 else 1.959963985
    return {"n": n, "mean": mean, "lo": mean - z * se, "hi": mean + z * se, "se": se}


def _frames(
    prior_weights: Sequence[float], min_games: int, fbs_only: bool
) -> Dict[float, pd.DataFrame]:
    """One feature frame per k. Built once and reused for every split -- the
    build is the expensive step and it does not depend on the season split."""
    out: Dict[float, pd.DataFrame] = {}
    for k in prior_weights:
        out[float(k)] = build_feature_frame(
            min_games=min_games, fbs_only=fbs_only, prior_weight=float(k)
        )
    return out


def _predict(frame: pd.DataFrame, train_seasons: Sequence[int], test_season: int) -> pd.DataFrame:
    """bv_line for one arm's test season, fitted on that arm's own train rows."""
    played = training_frame(frame)
    train, test = walk_forward_split(played, train_seasons, test_season)
    pred = bv_line_for_slate(train, test)
    return pd.DataFrame(
        {
            "id": test["id"].to_numpy(),
            "season": test["season"].to_numpy(),
            "week": test["week"].to_numpy(),
            "actual": pd.to_numeric(test["first_half_total"], errors="coerce").to_numpy(),
            "pred": np.asarray(pred, dtype=float),
        }
    ).set_index("id")


def evaluate(
    train_seasons: Sequence[int],
    test_season: int,
    prior_weights: Sequence[float] = PRIOR_WEIGHT_GRID,
    min_games: int = 0,
    fbs_only: bool = True,
    frames: Optional[Dict[float, pd.DataFrame]] = None,
    closes: Optional[Dict[int, float]] = None,
) -> AnchorResult:
    ks = [float(k) for k in prior_weights]
    if 0.0 not in ks:
        raise ValueError("the grid must contain k=0.0 -- it is the incumbent arm")
    frames = frames or _frames(ks, min_games, fbs_only)

    preds = {k: _predict(frames[k], train_seasons, test_season) for k in ks}
    base = preds[0.0]
    if base.empty:
        raise GateNotEvaluable(f"no test rows for season {test_season}")

    per_game = base[["season", "week", "actual"]].copy()
    for k in ks:
        p = preds[k].reindex(base.index)
        per_game[f"pred_k{k}"] = p["pred"]
        per_game[f"abserr_k{k}"] = (per_game["actual"] - p["pred"]).abs()

    if closes:
        # Real captured 1H closes only -- the same cut every other conclusion in
        # this repo is drawn on. Games without one are simply absent from the
        # gate-crossing count, never defaulted to a proxy line.
        per_game["line"] = pd.Series(closes).reindex(per_game.index)

    early = per_game["week"].isin(EARLY_WEEKS)
    buckets = {"weeks_1_2": early, "weeks_3plus": ~early}

    arms: List[Dict[str, Any]] = []
    for k in ks:
        row: Dict[str, Any] = {"prior_weight": k, "is_incumbent": k == 0.0}
        for name, mask in buckets.items():
            sub = per_game[mask]
            # gain > 0 means the seed beat the incumbent on that game.
            gain = sub["abserr_k0.0"] - sub[f"abserr_k{k}"]
            stats = {
                "n": int(len(sub)),
                "mae": _mae(sub["actual"], sub[f"pred_k{k}"]),
                "mae_incumbent": _mae(sub["actual"], sub["pred_k0.0"]),
                # Signed, as (prediction - actual): NEGATIVE means bv_line reads
                # low, which inflates every gap and pushes games over the bet
                # threshold. This is the quantity the change actually moves.
                "bias": _bias(sub[f"pred_k{k}"], sub["actual"]),
                "bias_incumbent": _bias(sub["pred_k0.0"], sub["actual"]),
                "paired_gain": _paired_ci(gain),
                "n_changed": int((gain.abs() > 1e-9).sum()),
            }
            if "line" in sub.columns:
                priced = sub[sub["line"].notna()]
                gap = priced["line"] - priced[f"pred_k{k}"]
                stats["gate"] = {
                    "n_priced": int(len(priced)),
                    "mean_gap": float(gap.mean()) if len(priced) else None,
                    "n_clearing": int((gap >= BET_GAP_PTS).sum()),
                }
            row[name] = stats
        row["verdict"] = _verdict(row)
        arms.append(row)

    report = {
        "kind": "level_anchor_gate",
        "train_seasons": [int(s) for s in train_seasons],
        "test_season": int(test_season),
        "min_games": int(min_games),
        "fbs_only": bool(fbs_only),
        "grid": ks,
        "non_inferiority_margin": NON_INFERIORITY_MARGIN,
        "n_test": int(len(per_game)),
        "n_with_close": int(per_game["line"].notna().sum()) if "line" in per_game else 0,
        "bet_gap_pts": BET_GAP_PTS,
        "arms": arms,
        "caveats": _caveats(per_game, ks),
    }
    return AnchorResult(per_game=per_game.reset_index(), report=_clean(report))


def _verdict(arm: Dict[str, Any]) -> Dict[str, Any]:
    """The adoption rule, applied. Stated in the module docstring and fixed
    before any number was computed."""
    if arm["prior_weight"] == 0.0:
        return {"adopt": False, "why": "incumbent (the baseline arm)"}
    early, late = arm["weeks_1_2"], arm["weeks_3plus"]
    eg, lg = early["paired_gain"], late["paired_gain"]
    if eg["lo"] is None or lg["lo"] is None:
        # A split with an empty bucket (2026 has no weeks 3+ played yet) is
        # EVIDENCE ABOUT ONE BUCKET, not a failed adoption test. Saying "no"
        # would read as "we tested it and it lost".
        missing = [n for n, b in (("weeks 1-2", eg), ("weeks 3+", lg)) if b["lo"] is None]
        return {
            "adopt": False,
            "why": f"not evaluable here: {', '.join(missing)} has too few rows for an interval",
        }
    improves = eg["lo"] > 0
    # lg is a GAIN, so "worse by at most the margin" is gain > -margin.
    non_inferior = lg["lo"] > -NON_INFERIORITY_MARGIN
    why = []
    if not improves:
        why.append(
            f"weeks 1-2 gain {eg['mean']:+.3f} [{eg['lo']:+.3f}, {eg['hi']:+.3f}] does not exclude 0"
        )
    if not non_inferior:
        why.append(
            f"weeks 3+ gain {lg['mean']:+.3f} [{lg['lo']:+.3f}, {lg['hi']:+.3f}] breaches the "
            f"-{NON_INFERIORITY_MARGIN} margin"
        )
    return {
        "adopt": bool(improves and non_inferior),
        "improves_early": bool(improves),
        "non_inferior_late": bool(non_inferior),
        "why": "; ".join(why) or "improves weeks 1-2 and is non-inferior on weeks 3+",
    }


def _caveats(per_game: pd.DataFrame, ks: Sequence[float]) -> List[str]:
    out = [
        "Paired on the same games: the statistic is per-game |error| difference, not two MAEs.",
        "k=0.0 IS the incumbent -- the same code path with the seed weight zeroed, "
        "not a re-implementation.",
        f"Adoption needs weeks 1-2 to improve (95% CI excludes 0) AND weeks 3+ to stay within "
        f"{NON_INFERIORITY_MARGIN} pts of MAE. Both were fixed before the run.",
    ]
    early_n = int(per_game["week"].isin(EARLY_WEEKS).sum())
    if early_n < 150:
        out.append(
            f"Only {early_n} weeks 1-2 test rows -- the bucket this change targets is the thin one."
        )
    return out


def render_markdown(report: Dict[str, Any]) -> str:
    ts, tr = report["test_season"], report["train_seasons"]
    L = [
        f"# Level-anchor gate — test {ts}, trained on {tr}",
        "",
        "Does seeding the season-to-date window with prior-season form beat leaving",
        "game 1 of every season as NaN? `k` = synthetic games of prior-season mean;",
        "**k=0 is the incumbent**, the same code path with the seed switched off.",
        "",
        f"- test rows: **{report['n_test']}**   min_games: {report['min_games']}   "
        f"fbs_only: {report['fbs_only']}",
        f"- non-inferiority margin (weeks 3+): **{report['non_inferiority_margin']} pts of MAE**",
        "",
        "## Weeks 1-2 — the bucket this change is for",
        "",
        "| k | n | MAE | incumbent MAE | paired gain | 95% CI | rows changed |",
        "|---|---|---|---|---|---|---|",
    ]

    def fmt(v, nd=3):
        return "—" if v is None else f"{v:+.{nd}f}"

    def mae(v):
        return "—" if v is None else f"{v:.3f}"

    def row(arm, bucket):
        b = arm[bucket]
        g = b["paired_gain"]
        ci = "—" if g["lo"] is None else f"[{g['lo']:+.3f}, {g['hi']:+.3f}]"
        return (
            f"| {arm['prior_weight']} | {b['n']} | {mae(b['mae'])} | {mae(b['mae_incumbent'])} | "
            f"{fmt(g['mean'])} | {ci} | {b['n_changed']} |"
        )

    for arm in report["arms"]:
        L.append(row(arm, "weeks_1_2"))
    L += [
        "",
        "## Weeks 3+ — where nothing is currently broken",
        "",
        "| k | n | MAE | incumbent MAE | paired gain | 95% CI | rows changed |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm in report["arms"]:
        L.append(row(arm, "weeks_3plus"))
    if report.get("n_with_close"):
        L += [
            "",
            f"## What it does to SELECTION — {report['n_with_close']} games with a real 1H close",
            "",
            "MAE is close to blind to a level shift (a ~1-pt bias against ~11 pts of",
            f"per-game spread), but `gap = line − bv_line` against {report['bet_gap_pts']} pts is",
            "what the system spends. Bias is signed as (prediction − actual): **negative**",
            "means bv_line reads low, which inflates every gap.",
            "",
            "| k | bucket | n priced | bias | mean gap | clears the bar |",
            "|---|---|---|---|---|---|",
        ]
        for arm in report["arms"]:
            for bucket in ("weeks_1_2", "weeks_3plus"):
                g = arm[bucket].get("gate")
                if not g or not g["n_priced"]:
                    continue
                L.append(
                    f"| {arm['prior_weight']} | {bucket.replace('_', ' ')} | {g['n_priced']} | "
                    f"{fmt(arm[bucket]['bias'], 2)} | {fmt(g['mean_gap'], 2)} | {g['n_clearing']} |"
                )

    L += ["", "## Verdict", "", "| k | adopt? | why |", "|---|---|---|"]
    for arm in report["arms"]:
        v = arm["verdict"]
        L.append(f"| {arm['prior_weight']} | {'**YES**' if v['adopt'] else 'no'} | {v['why']} |")
    L += ["", "## Caveats", ""] + [f"- {c}" for c in report["caveats"]]
    L += ["", "_positive gain = the seeded arm was closer to the realized 1H total._"]
    return "\n".join(L) + "\n"
