"""Is `bv_line`'s global calibration intercept doing more harm than good?

H-INTERCEPT in docs/HYPOTHESES.md. One question, one shot, same shape as
backtest/level_anchor.py.

WHAT IS BEING TESTED. `bv_line_for_slate` adds `bias_corrections(train)["global"]`
to every prediction -- the mean walk-forward out-of-fold residual over the
training seasons. With `min_train = 500` and three training seasons only TWO
folds are scorable, so that number is an average of two season-level
observations, extrapolated to a third. docs/MODEL_LEVEL_2026.md measured what it
did in 2026: it applied -1.81 where the season needed +1.09, and that 2.90-point
gap IS the entire level deficit that took the fixed 1.75-point bar from selecting
~15% of the board to selecting ~half of it.

THE ARMS ARE A CONSTANT SHIFT. Arm lambda predicts `raw + lambda * c`, so lambda=1
reproduces `bv_line_for_slate` EXACTLY -- the incumbent is an arm of this
experiment, not a re-implementation that might differ for some other reason --
and lambda=0 drops the intercept. Because every arm shares one fit and one `c`
per season, the whole grid costs one model fit per test season.

THE GRID (0, 0.25, 0.5, 0.75, 1.0) is declared here rather than passed in, so
"which lambdas did we try?" has one answer that predates any result. H-INTERCEPT's
criterion cell says "a grid declared in advance"; this is that declaration.

ADOPTION RULE, quoted from the registry row and applied verbatim by `_verdict`:
  the MEAN |level bias| across the three held-out seasons, and the WORST single
  season. An arm is adopted only if it beats the incumbent on BOTH, in every
  season, with a paired bootstrap 95% CI on the per-season bias difference
  excluding zero.
MAE and the share of priced games clearing BET_GAP_PTS are SECONDARY: reported,
never optimised. The mean across seasons is EQUAL-WEIGHT -- the criterion says
"across the three held-out seasons", and the question is whether a correction
transfers BETWEEN seasons, which game-weighting would hand to 2025 (744 rows)
over 2026 (153).

ONE SEASON CANNOT DISCRIMINATE, AND THAT IS A FACT ABOUT THE TEST. For test
season 2024 the training window is 2023 alone, so `oof_residuals` (which needs a
prior season inside the window) has no scorable fold and `bias_corrections`
returns 0.0. Every arm then predicts the same number, every bootstrap draw of the
difference is exactly 0, and the CI is [0, 0] -- which cannot exclude zero. So
the criterion's "in every season" clause is UNSATISFIABLE on 2024 for a reason
that has nothing to do with the intercept. The report says so in those words
rather than printing a bare "no". The criterion is not edited to route around it:
a row is closed under the rule it was registered with.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..etl.features import training_frame
from ..model.bv_line import BV_FEATURE_COLS, TARGET, bias_corrections, fit_bv_regressor
from ..model.score import BET_GAP_PTS
from .residual_gate import GateNotEvaluable, _bias, _clean, _mae

# The pre-declared grid. lambda=1.0 is the incumbent; lambda=0.0 drops the
# intercept entirely.
LAMBDA_GRID: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0)
INCUMBENT_LAMBDA = 1.0

# Walk-forward: each season predicted by a model trained only on prior seasons.
TEST_SEASONS: Sequence[int] = (2024, 2025, 2026)

N_BOOT = 2000
BOOT_SEED = 7

STRUCTURAL_TIE = (
    "structurally tied -- the training window holds no scorable fold, so the intercept "
    "is 0 and every arm coincides"
)


@dataclass
class InterceptResult:
    per_game: pd.DataFrame
    report: Dict[str, Any]


def season_predictions(frame: pd.DataFrame, test_season: int) -> Dict[str, Any]:
    """One fit for one held-out season: raw predictions, actuals and the intercept.

    Mirrors the live path -- `score_slate` trains on `season < target_season`
    strictly (model/score.py), so the season's own games reach neither the fit nor
    the intercept, and its errors are genuinely out-of-sample.
    """
    played = training_frame(frame)
    train = played[played["season"] < int(test_season)]
    test = played[played["season"] == int(test_season)]
    if test.empty:
        raise GateNotEvaluable(f"no played rows for test season {test_season}")
    if train.empty:
        raise GateNotEvaluable(f"no training rows before season {test_season}")
    model = fit_bv_regressor(train)
    return {
        "ids": test["id"].to_numpy(),
        "week": test["week"].to_numpy(),
        "raw": np.asarray(model.predict(test[BV_FEATURE_COLS]), dtype=float),
        "actual": pd.to_numeric(test[TARGET], errors="coerce").to_numpy(dtype=float),
        "intercept": float(bias_corrections(train)["global"]),
        "n_train": int(len(train)),
    }


def _abs_bias_ci(
    raw: np.ndarray,
    actual: np.ndarray,
    shift_arm: float,
    shift_inc: float,
    n_boot: int = N_BOOT,
    seed: int = BOOT_SEED,
) -> Dict[str, Any]:
    """Bootstrap CI for |bias(arm)| - |bias(incumbent)|; negative favours the arm.

    `stats.paired_bootstrap_mean` computes mean(a - b) and cannot express this:
    the statistic is the difference of two ABSOLUTE MEANS, not the mean of a
    per-game difference, and |mean| does not distribute over a resample. Same
    conventions as that helper otherwise -- one index draw per bootstrap replicate
    (so both arms see the same resampled games), percentile interval, fixed seed.

    When both shifts are equal -- which is every arm on a season whose intercept
    is 0 -- every replicate is exactly 0 and the interval is [0, 0]. That is the
    structural tie, reported as such rather than as a failed comparison.

    The interval also COLLAPSES for an ordinary season, and that is a property of
    the question rather than a defect. Both arms differ by a constant, so as long
    as a resampled bias keeps its sign the difference of absolute means is exactly
    `shift_arm - shift_inc` -- the same number in every replicate. Width appears
    only where a resample can carry the bias across zero. So "the CI excludes
    zero" is close to vacuous here: it is satisfied by construction wherever the
    bias is comfortably away from zero, and the clause that actually decides an
    arm is whether its |bias| is lower at all. `deterministic` marks it.
    """
    n = int(len(actual))
    if n == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None, "excludes_zero": False}
    err = raw - actual
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, (n_boot, n))
    means = err[idx].mean(axis=1)
    boots = np.abs(means + shift_arm) - np.abs(means + shift_inc)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    point = abs(float(err.mean()) + shift_arm) - abs(float(err.mean()) + shift_inc)
    return {
        "n": n,
        "mean": point,
        "lo": float(lo),
        "hi": float(hi),
        "excludes_zero": bool(lo > 0 or hi < 0),
        # Zero width with the arms genuinely apart: no resample crossed zero
        # bias, so the statistic is constant. See the docstring.
        "deterministic": bool(float(hi) - float(lo) < 1e-9 and shift_arm != shift_inc),
        "n_boot": int(n_boot),
    }


def evaluate(
    frame: pd.DataFrame,
    test_seasons: Sequence[int] = TEST_SEASONS,
    grid: Sequence[float] = LAMBDA_GRID,
    closes: Optional[Dict[int, float]] = None,
    min_games: int = 0,
    fbs_only: bool = True,
) -> InterceptResult:
    lams = [float(x) for x in grid]
    if INCUMBENT_LAMBDA not in lams:
        raise ValueError("the grid must contain lambda=1.0 -- it is the incumbent arm")

    fits = {int(s): season_predictions(frame, int(s)) for s in test_seasons}

    rows = []
    for season, f in fits.items():
        block = pd.DataFrame(
            {
                "id": f["ids"],
                "season": season,
                "week": f["week"],
                "actual": f["actual"],
                "raw": f["raw"],
                "intercept": f["intercept"],
            }
        )
        for lam in lams:
            block[f"pred_l{lam}"] = block["raw"] + lam * f["intercept"]
        rows.append(block)
    per_game = pd.concat(rows, ignore_index=True).set_index("id")
    if closes:
        # Real captured 1H closes only -- the cut every other conclusion here is
        # drawn on. A game without one is absent from the gate count, never
        # defaulted to a proxy line.
        per_game["line"] = pd.Series(closes).reindex(per_game.index)

    seasons_meta = [
        {
            "season": s,
            "n": int(len(f["actual"])),
            "n_train": f["n_train"],
            "intercept": f["intercept"],
            "degenerate": abs(f["intercept"]) < 1e-12,
            "n_priced": (
                int(per_game.loc[per_game["season"] == s, "line"].notna().sum())
                if "line" in per_game
                else 0
            ),
        }
        for s, f in fits.items()
    ]

    arms: List[Dict[str, Any]] = []
    for lam in lams:
        by_season = {}
        for s, f in fits.items():
            sub = per_game[per_game["season"] == s]
            col = f"pred_l{lam}"
            stats: Dict[str, Any] = {
                "n": int(len(sub)),
                # Signed as (prediction - actual): NEGATIVE means bv_line reads
                # low, which inflates every gap and pushes games over the bar.
                "bias": _bias(sub[col], sub["actual"]),
                "abs_bias": abs(_bias(sub[col], sub["actual"])),
                "mae": _mae(sub["actual"], sub[col]),
                "vs_incumbent": _abs_bias_ci(
                    f["raw"], f["actual"], lam * f["intercept"], INCUMBENT_LAMBDA * f["intercept"]
                ),
                "degenerate": abs(f["intercept"]) < 1e-12,
            }
            if "line" in sub.columns:
                priced = sub[sub["line"].notna()]
                gap = priced["line"] - priced[col]
                stats["gate"] = {
                    "n_priced": int(len(priced)),
                    "mean_gap": float(gap.mean()) if len(priced) else None,
                    "n_clearing": int((gap >= BET_GAP_PTS).sum()),
                    "share_clearing": (float((gap >= BET_GAP_PTS).mean()) if len(priced) else None),
                }
            by_season[str(s)] = stats
        abs_biases = [v["abs_bias"] for v in by_season.values()]
        arm = {
            "lambda": lam,
            "is_incumbent": lam == INCUMBENT_LAMBDA,
            # EQUAL-WEIGHT across seasons: the question is transfer between
            # seasons, and game-weighting would hand it to the biggest one.
            "mean_abs_bias": float(np.mean(abs_biases)),
            "worst_abs_bias": float(np.max(abs_biases)),
            "seasons": by_season,
        }
        arms.append(arm)

    incumbent = next(a for a in arms if a["is_incumbent"])
    for arm in arms:
        arm["verdict"] = _verdict(arm, incumbent)

    report = {
        "kind": "intercept_gate",
        "hypothesis": "H-INTERCEPT",
        "grid": lams,
        "incumbent_lambda": INCUMBENT_LAMBDA,
        "min_games": int(min_games),
        "fbs_only": bool(fbs_only),
        "bet_gap_pts": BET_GAP_PTS,
        "n_boot": N_BOOT,
        "seasons": seasons_meta,
        "arms": arms,
        "caveats": _caveats(seasons_meta, arms),
    }
    return InterceptResult(per_game=per_game.reset_index(), report=_clean(report))


def _verdict(arm: Dict[str, Any], incumbent: Dict[str, Any]) -> Dict[str, Any]:
    """H-INTERCEPT's adoption rule, applied as registered and not edited."""
    if arm["is_incumbent"]:
        return {"adopt": False, "why": "incumbent (the baseline arm)"}

    why: List[str] = []
    beats_mean = arm["mean_abs_bias"] < incumbent["mean_abs_bias"]
    beats_worst = arm["worst_abs_bias"] < incumbent["worst_abs_bias"]
    if not beats_mean:
        why.append(
            f"mean |bias| {arm['mean_abs_bias']:.3f} does not beat {incumbent['mean_abs_bias']:.3f}"
        )
    if not beats_worst:
        why.append(
            f"worst season {arm['worst_abs_bias']:.3f} does not beat "
            f"{incumbent['worst_abs_bias']:.3f}"
        )

    every_season = True
    for season, s in sorted(arm["seasons"].items()):
        ci = s["vs_incumbent"]
        lower = s["abs_bias"] < incumbent["seasons"][season]["abs_bias"]
        if lower and ci["excludes_zero"]:
            continue
        every_season = False
        if s["degenerate"]:
            why.append(f"{season}: {STRUCTURAL_TIE}, so the every-season clause cannot be met")
        elif not lower:
            why.append(f"{season}: |bias| {s['abs_bias']:.3f} is not lower than the incumbent's")
        else:
            why.append(f"{season}: CI [{ci['lo']:+.3f}, {ci['hi']:+.3f}] does not exclude zero")

    return {
        "adopt": bool(beats_mean and beats_worst and every_season),
        "beats_mean": bool(beats_mean),
        "beats_worst": bool(beats_worst),
        "every_season": bool(every_season),
        "why": "; ".join(why) or "beats the incumbent on mean, worst and every season",
    }


def _caveats(seasons_meta: List[Dict[str, Any]], arms: List[Dict[str, Any]]) -> List[str]:
    out = [
        "lambda=1.0 IS the incumbent -- the same code path with the intercept scaled, "
        "not a re-implementation.",
        "Every arm is a CONSTANT shift, so the ORDER of a board is identical across the "
        "grid. What moves is the threshold, never the ranking.",
        "The mean across seasons is EQUAL-WEIGHT: the question is whether a correction "
        "transfers between seasons.",
        "Three seasons is THIN. A pass would be a finding and would license a registered "
        "parallel paper arm only; H-STOP is running on the frozen rule.",
    ]
    n_det = sum(
        1
        for a in arms
        if not a["is_incumbent"]
        for s in a["seasons"].values()
        if s["vs_incumbent"].get("deterministic")
    )
    n_cmp = sum(1 for a in arms if not a["is_incumbent"]) * len(seasons_meta)
    if n_det:
        out.append(
            f"{n_det} of {n_cmp} challenger-season intervals have ZERO WIDTH. Two arms "
            "differ by a constant, so while a resampled bias keeps its sign the "
            "difference of absolute means is that constant in every replicate; width "
            "appears only where a resample can cross zero bias. So the criterion's "
            "'CI excludes zero' clause is close to vacuous against a constant shift -- "
            "what decides an arm here is whether its |bias| is lower at all."
        )
    for s in seasons_meta:
        if s["degenerate"]:
            out.append(
                f"{s['season']}: {STRUCTURAL_TIE}. Its training window is the single season "
                f"before it, and oof_residuals needs a prior season inside the window. The "
                f"criterion's every-season clause is UNSATISFIABLE there, for a reason about "
                f"the test rather than about the intercept."
            )
    return out


def render_markdown(report: Dict[str, Any]) -> str:
    L = [
        "# Intercept gate — H-INTERCEPT",
        "",
        f"Grid {report['grid']} (lambda=1.0 is the incumbent). "
        f"Walk-forward, min_games={report['min_games']}, "
        f"fbs_only={report['fbs_only']}, {report['n_boot']} bootstrap draws.",
        "",
        "## Held-out seasons",
        "",
        "| season | test n | train n | intercept applied | priced |",
        "|---|---|---|---|---|",
    ]
    for s in report["seasons"]:
        note = " (no scorable fold)" if s["degenerate"] else ""
        L.append(
            f"| {s['season']} | {s['n']} | {s['n_train']} | {s['intercept']:+.4f}{note} "
            f"| {s['n_priced']} |"
        )

    season_ids = [str(s["season"]) for s in report["seasons"]]
    L += [
        "",
        "## Arms — signed bias (prediction − actual)",
        "",
        "| lambda | " + " | ".join(season_ids) + " | mean abs | worst |",
        "|---" * (len(season_ids) + 3) + "|",
    ]
    for arm in report["arms"]:
        cells = [f"{arm['seasons'][s]['bias']:+.2f}" for s in season_ids]
        tag = " (incumbent)" if arm["is_incumbent"] else ""
        L.append(
            f"| {arm['lambda']}{tag} | "
            + " | ".join(cells)
            + f" | {arm['mean_abs_bias']:.3f} | {arm['worst_abs_bias']:.3f} |"
        )

    L += [
        "",
        "## Per-season comparison against the incumbent",
        "",
        "Difference in |bias|, challenger − incumbent; negative favours the challenger.",
        "",
        "| lambda | season | diff | 95% CI | excludes 0 |",
        "|---|---|---|---|---|",
    ]
    for arm in report["arms"]:
        if arm["is_incumbent"]:
            continue
        for s in season_ids:
            ci = arm["seasons"][s]["vs_incumbent"]
            note = " — " + STRUCTURAL_TIE if arm["seasons"][s]["degenerate"] else ""
            L.append(
                f"| {arm['lambda']} | {s} | {ci['mean']:+.3f} | "
                f"[{ci['lo']:+.3f}, {ci['hi']:+.3f}] | "
                f"{'yes' if ci['excludes_zero'] else 'no'}{note} |"
            )

    if any("gate" in arm["seasons"][season_ids[0]] for arm in report["arms"]):
        L += [
            "",
            f"## Secondary — MAE, and the share clearing {report['bet_gap_pts']} pts",
            "",
            "Reported, never optimised.",
            "",
            "| lambda | season | MAE | priced | clearing | share |",
            "|---|---|---|---|---|---|",
        ]
        for arm in report["arms"]:
            for s in season_ids:
                st = arm["seasons"][s]
                g = st.get("gate")
                if not g:
                    continue
                share = "—" if g["share_clearing"] is None else f"{g['share_clearing']:.1%}"
                L.append(
                    f"| {arm['lambda']} | {s} | {st['mae']:.3f} | {g['n_priced']} "
                    f"| {g['n_clearing']} | {share} |"
                )

    L += ["", "## Verdict", "", "| lambda | adopt? | why |", "|---|---|---|"]
    for arm in report["arms"]:
        v = arm["verdict"]
        L.append(f"| {arm['lambda']} | {'**YES**' if v['adopt'] else 'no'} | {v['why']} |")

    L += ["", "## Caveats", ""] + [f"- {c}" for c in report["caveats"]]
    return "\n".join(L) + "\n"
