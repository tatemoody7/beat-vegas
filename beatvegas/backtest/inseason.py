"""Does re-estimating the calibration intercept from the season's OWN games help?

H-INSEASON in docs/HYPOTHESES.md. The criterion was frozen before this file
existed; everything below implements it and nothing here may reinterpret it.

WHAT IS BEING TESTED. `score_slate` trains on `season < target_season` strictly
(model/score.py), so the current season's completed games reach NEITHER the fit
NOR the calibration intercept. H-INTERCEPT showed that shrinking the
prior-season intercept cannot work: 2025 reads +2.46 HIGH before calibration and
2026 reads low, so no constant multiplier serves both (docs/MODEL_LEVEL_2026.md).
The number is estimated from the wrong seasons, not scaled wrongly. This asks
whether the right seasons are available -- the current one, as it accumulates.

THE ESTIMATOR, quoted from the row:

    c_t = (1 - w) * c_prior + w * c_season,   w = n / (n + k)

`c_prior` is `bias_corrections(train)["global"]`, exactly what the incumbent
applies. `c_season` is `mean(actual - RAW pred)` over the season's games already
completed -- the raw, PRE-intercept prediction. Deriving it from a calibrated
prediction would re-apply `c_prior` scaled by `w`, which is the one arithmetic
mistake this design can make. `k` is how many games of in-season evidence it
takes to half-trust the season's own bias; at n=0 the weight is 0 and the arm IS
the incumbent, which is why week 1 can never be hurt by this.

THE AS-OF RULE. Live, a build may use only games whose final was available
STRICTLY BEFORE that build's timestamp. In this study the expanding window closes
at the week boundary: a game in week w is scored with the games of weeks < w
only. The two coincide for Friday and Saturday builds and diverge only for a
midweek build after a Thursday game of the same week. THE WEEK RULE IS WHAT
PRODUCED THESE NUMBERS, and the report says so.

THE RULE, applied by `_verdict`:
  * PRIMARY, both required -- the EQUAL-WEIGHT mean of the held-out seasons'
    absolute bias, and the WORST single season's absolute bias. An arm must beat
    the incumbent on both, each with a bootstrap 95% CI entirely BELOW zero.
  * PER-SEASON non-inferiority -- a season fails only if its CI is entirely ABOVE
    zero. Crossing zero is a tie and is allowed. (This is the clause H-INTERCEPT
    died on, deliberately relaxed here BEFORE any number was read.)
  * HOLM across the four challenger arms.

ONE THING THE CRITERION LEFT OPEN, resolved here and flagged rather than buried:
Holm needs ONE p-value per arm and the primary has TWO required tests. An arm is
taken to be as strong as its WEAKER required component, so its Holm input is the
LARGER of the two p-values. That is an intersection-union test, which needs no
correction across the two components themselves; the correction is across arms,
as the row says.

THE DECLARED LIMITATION, restated because it is easy to forget once a number
looks good: resampling games within a season is blind to BETWEEN-season
variation, which is the dominant uncertainty here -- 2025 and 2026 disagree by
about four points. The interval is narrower than the transfer claim it is read
against. That is the same failure that produced the intercept problem.
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
from .stats import holm_adjust, holm_reject

# The pre-declared grid, from the registry row. k is the number of in-season
# games at which the season's own bias earns half the weight.
K_GRID: Sequence[float] = (25.0, 50.0, 100.0, 200.0)

# The incumbent is k -> infinity: the in-season weight is 0 at every n, so the
# arm reduces to `raw + c_prior`, which IS bv_line_for_slate.
INCUMBENT = float("inf")
INCUMBENT_LABEL = "incumbent"

TEST_SEASONS: Sequence[int] = (2024, 2025, 2026)

N_BOOT = 2000
BOOT_SEED = 7
ALPHA = 0.05

# Secondary only. Matches the bands docs/MODEL_LEVEL_2026.md reports OOF
# residuals in, so the two tables can be read side by side.
WEEK_BANDS = ((1, 3), (4, 6), (7, 10), (11, 99))

AS_OF_RULE = "week boundary: a game in week w is scored using the completed games of weeks < w only"


@dataclass
class InSeasonResult:
    per_game: pd.DataFrame
    report: Dict[str, Any]


def _arm_label(k: float) -> str:
    return INCUMBENT_LABEL if k == INCUMBENT else f"k{int(k)}"


def in_season_shift(
    week: np.ndarray, raw: np.ndarray, actual: np.ndarray, c_prior: float, k: float
) -> Dict[str, np.ndarray]:
    """The per-game intercept `c_t` under the week-boundary as-of rule.

    Returns the shift applied to each game and the `n` and `w` behind it, so the
    report can show how much of the season's own evidence each arm actually used.
    A game in week w sees the games of weeks < w and nothing else; at n=0 the
    weight is 0 and the shift is `c_prior` exactly.
    """
    n_games = len(actual)
    shift = np.full(n_games, float(c_prior), dtype=float)
    n_seen = np.zeros(n_games, dtype=float)
    weight = np.zeros(n_games, dtype=float)
    if k == INCUMBENT:
        return {"shift": shift, "n_seen": n_seen, "weight": weight}

    raw_err = actual - raw  # the sign bias_corrections uses and apply_bias adds
    for w in np.unique(week):
        earlier = week < w
        n = int(earlier.sum())
        here = week == w
        n_seen[here] = n
        if n == 0:
            continue
        c_season = float(raw_err[earlier].mean())
        wt = n / (n + k)
        weight[here] = wt
        shift[here] = (1.0 - wt) * float(c_prior) + wt * c_season
    return {"shift": shift, "n_seen": n_seen, "weight": weight}


def season_fit(frame: pd.DataFrame, test_season: int) -> Dict[str, Any]:
    """One fit for one held-out season: raw predictions, actuals and `c_prior`.

    Identical to the intercept gate's split, and to the live path: the season's
    own games reach neither the fit nor `c_prior`, so its errors are genuinely
    out-of-sample and may be read back in by the arms without leakage.
    """
    played = training_frame(frame)
    train = played[played["season"] < int(test_season)]
    test = played[played["season"] == int(test_season)].sort_values(["week", "id"])
    if test.empty:
        raise GateNotEvaluable(f"no played rows for test season {test_season}")
    if train.empty:
        raise GateNotEvaluable(f"no training rows before season {test_season}")
    model = fit_bv_regressor(train)
    return {
        "ids": test["id"].to_numpy(),
        "week": pd.to_numeric(test["week"], errors="coerce").to_numpy(dtype=float),
        "raw": np.asarray(model.predict(test[BV_FEATURE_COLS]), dtype=float),
        "actual": pd.to_numeric(test[TARGET], errors="coerce").to_numpy(dtype=float),
        "c_prior": float(bias_corrections(train)["global"]),
        "n_train": int(len(train)),
    }


def _boot_biases(errs: Dict[int, np.ndarray], idx: Dict[int, np.ndarray]) -> Dict[int, np.ndarray]:
    """Per-season bootstrap bias, one row per replicate, on shared indices."""
    return {s: errs[s][idx[s]].mean(axis=1) for s in errs}


def _p_two_sided(boots: np.ndarray, point: float, n_boot: int) -> float:
    """The convention stats.paired_bootstrap_mean uses, kept identical."""
    other = float(np.mean(boots >= 0) if point < 0 else np.mean(boots <= 0))
    return float(min(1.0, max(2 * other, 1.0 / n_boot)))


def evaluate(
    frame: pd.DataFrame,
    test_seasons: Sequence[int] = TEST_SEASONS,
    grid: Sequence[float] = K_GRID,
    closes: Optional[Dict[int, float]] = None,
    min_games: int = 0,
    fbs_only: bool = True,
    n_boot: int = N_BOOT,
    seed: int = BOOT_SEED,
) -> InSeasonResult:
    ks = [float(x) for x in grid]
    if any(k <= 0 for k in ks):
        raise ValueError("every k must be positive -- w = n/(n+k) is undefined otherwise")
    arms_k = ks + [INCUMBENT]

    fits = {int(s): season_fit(frame, int(s)) for s in test_seasons}

    blocks = []
    shifts: Dict[float, Dict[int, np.ndarray]] = {k: {} for k in arms_k}
    for season, f in fits.items():
        block = pd.DataFrame(
            {
                "id": f["ids"],
                "season": season,
                "week": f["week"],
                "actual": f["actual"],
                "raw": f["raw"],
                "c_prior": f["c_prior"],
            }
        )
        for k in arms_k:
            out = in_season_shift(f["week"], f["raw"], f["actual"], f["c_prior"], k)
            shifts[k][season] = out["shift"]
            label = _arm_label(k)
            block[f"pred_{label}"] = f["raw"] + out["shift"]
            if k != INCUMBENT:
                block[f"w_{label}"] = out["weight"]
                block[f"n_seen_{label}"] = out["n_seen"]
        blocks.append(block)
    per_game = pd.concat(blocks, ignore_index=True).set_index("id")
    if closes:
        # Real captured 1H closes only -- the cut every other conclusion here is
        # drawn on. A game without one is absent, never given a proxy line.
        per_game["line"] = pd.Series(closes).reindex(per_game.index)

    seasons = sorted(fits)
    # One index draw per season, SHARED by every arm: the comparison is paired on
    # the resampled games, which is what makes the difference interpretable.
    rng = np.random.default_rng(seed)
    idx = {
        s: rng.integers(0, len(fits[s]["actual"]), (n_boot, len(fits[s]["actual"])))
        for s in seasons
    }
    errs = {
        k: {s: (fits[s]["raw"] + shifts[k][s]) - fits[s]["actual"] for s in seasons} for k in arms_k
    }
    boots = {k: _boot_biases(errs[k], idx) for k in arms_k}

    inc_abs = np.abs(np.column_stack([boots[INCUMBENT][s] for s in seasons]))
    inc_mean_boot, inc_worst_boot = inc_abs.mean(axis=1), inc_abs.max(axis=1)
    inc_point = {s: float(errs[INCUMBENT][s].mean()) for s in seasons}
    inc_mean = float(np.mean([abs(v) for v in inc_point.values()]))
    inc_worst = float(np.max([abs(v) for v in inc_point.values()]))

    arms: List[Dict[str, Any]] = []
    for k in arms_k:
        label = _arm_label(k)
        point = {s: float(errs[k][s].mean()) for s in seasons}
        abs_pt = {s: abs(point[s]) for s in seasons}
        arm_abs = np.abs(np.column_stack([boots[k][s] for s in seasons]))

        by_season = {}
        for j, s in enumerate(seasons):
            d = arm_abs[:, j] - inc_abs[:, j]
            lo, hi = np.percentile(d, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
            sub = per_game[per_game["season"] == s]
            stats: Dict[str, Any] = {
                "n": int(len(sub)),
                "c_prior": float(fits[s]["c_prior"]),
                # Signed as (prediction - actual): NEGATIVE means bv_line reads
                # low, which inflates every gap and pushes games over the bar.
                "bias": point[s],
                "abs_bias": abs_pt[s],
                "mae": _mae(sub["actual"], sub[f"pred_{label}"]),
                "vs_incumbent": {
                    "mean": abs_pt[s] - abs(inc_point[s]),
                    "lo": float(lo),
                    "hi": float(hi),
                    # The clause as registered: a season FAILS only if the whole
                    # interval sits above zero. Crossing zero is a tie.
                    "worse": bool(lo > 0),
                },
                "mean_weight": (
                    float(sub[f"w_{label}"].mean()) if f"w_{label}" in sub.columns else 0.0
                ),
            }
            stats["by_week_band"] = _week_bands(sub, label)
            if "line" in sub.columns:
                priced = sub[sub["line"].notna()]
                gap = priced["line"] - priced[f"pred_{label}"]
                stats["gate"] = {
                    "n_priced": int(len(priced)),
                    "mean_gap": float(gap.mean()) if len(priced) else None,
                    "n_clearing": int((gap >= BET_GAP_PTS).sum()),
                    "share_clearing": float((gap >= BET_GAP_PTS).mean()) if len(priced) else None,
                }
            by_season[str(s)] = stats

        arm_mean = float(np.mean([abs_pt[s] for s in seasons]))
        arm_worst = float(np.max([abs_pt[s] for s in seasons]))
        agg = {}
        for name, arm_boot, inc_boot, pt, inc_pt_v in (
            ("mean_abs_bias", arm_abs.mean(axis=1), inc_mean_boot, arm_mean, inc_mean),
            ("worst_abs_bias", arm_abs.max(axis=1), inc_worst_boot, arm_worst, inc_worst),
        ):
            d = arm_boot - inc_boot
            lo, hi = np.percentile(d, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
            agg[name] = {
                "arm": pt,
                "incumbent": inc_pt_v,
                "diff": pt - inc_pt_v,
                "lo": float(lo),
                "hi": float(hi),
                # An aggregate pass needs the interval ENTIRELY BELOW zero.
                "below_zero": bool(hi < 0),
                "p": _p_two_sided(d, pt - inc_pt_v, n_boot),
            }

        arms.append(
            {
                "k": None if k == INCUMBENT else k,
                "label": label,
                "is_incumbent": k == INCUMBENT,
                "mean_abs_bias": arm_mean,
                "worst_abs_bias": arm_worst,
                "aggregate": agg,
                "seasons": by_season,
            }
        )

    _apply_holm(arms)
    for arm in arms:
        arm["verdict"] = _verdict(arm)

    report = {
        "kind": "inseason_gate",
        "hypothesis": "H-INSEASON",
        "grid": ks,
        "as_of_rule": AS_OF_RULE,
        "min_games": int(min_games),
        "fbs_only": bool(fbs_only),
        "bet_gap_pts": BET_GAP_PTS,
        "n_boot": int(n_boot),
        "alpha": ALPHA,
        "seasons": [
            {
                "season": s,
                "n": int(len(fits[s]["actual"])),
                "n_train": fits[s]["n_train"],
                "c_prior": float(fits[s]["c_prior"]),
                "n_priced": (
                    int(per_game.loc[per_game["season"] == s, "line"].notna().sum())
                    if "line" in per_game
                    else 0
                ),
            }
            for s in seasons
        ],
        "arms": arms,
        "caveats": _caveats(fits, arms),
    }
    return InSeasonResult(per_game=per_game.reset_index(), report=_clean(report))


def _week_bands(sub: pd.DataFrame, label: str) -> List[Dict[str, Any]]:
    """Secondary: bias by week band. Early weeks have n near 0, so w is near 0
    and the arm is near the incumbent BY CONSTRUCTION -- which is exactly why
    this is reported rather than optimised."""
    out = []
    for lo, hi in WEEK_BANDS:
        band = sub[(sub["week"] >= lo) & (sub["week"] <= hi)]
        if band.empty:
            continue
        out.append(
            {
                "band": f"{lo}-{hi}" if hi < 99 else f"{lo}+",
                "n": int(len(band)),
                "bias": _bias(band[f"pred_{label}"], band["actual"]),
                "mean_weight": (
                    float(band[f"w_{label}"].mean()) if f"w_{label}" in band.columns else 0.0
                ),
            }
        )
    return out


def _apply_holm(arms: List[Dict[str, Any]]) -> None:
    """Holm across the four challenger arms, as the row says.

    The row asks for ONE correction across arms while the primary has TWO
    required tests. An arm is only as strong as its WEAKER required component,
    so its input is the LARGER of the two p-values -- an intersection-union test,
    which needs no correction across the components themselves.
    """
    challengers = [a for a in arms if not a["is_incumbent"]]
    pvals = [
        max(a["aggregate"][n]["p"] for n in ("mean_abs_bias", "worst_abs_bias"))
        for a in challengers
    ]
    adj = holm_adjust(pvals)
    rej = holm_reject(pvals, alpha=ALPHA)
    for arm, p, a, r in zip(challengers, pvals, adj, rej):
        arm["holm"] = {"p_raw": float(p), "p_adjusted": a, "rejects": bool(r)}
    for arm in arms:
        if arm["is_incumbent"]:
            arm["holm"] = None


def _verdict(arm: Dict[str, Any]) -> Dict[str, Any]:
    """H-INSEASON's rule, applied as registered."""
    if arm["is_incumbent"]:
        return {"adopt": False, "why": "incumbent (the baseline arm)"}

    why: List[str] = []
    agg = arm["aggregate"]
    beats_mean = agg["mean_abs_bias"]["diff"] < 0 and agg["mean_abs_bias"]["below_zero"]
    beats_worst = agg["worst_abs_bias"]["diff"] < 0 and agg["worst_abs_bias"]["below_zero"]
    for name, ok, human in (
        ("mean_abs_bias", beats_mean, "mean"),
        ("worst_abs_bias", beats_worst, "worst season"),
    ):
        a = agg[name]
        if not ok:
            why.append(
                f"{human} {a['arm']:.3f} vs {a['incumbent']:.3f}, CI "
                f"[{a['lo']:+.3f}, {a['hi']:+.3f}] not entirely below zero"
            )

    worse_seasons = [s for s, v in sorted(arm["seasons"].items()) if v["vs_incumbent"]["worse"]]
    non_inferior = not worse_seasons
    for s in worse_seasons:
        ci = arm["seasons"][s]["vs_incumbent"]
        why.append(f"{s}: CI [{ci['lo']:+.3f}, {ci['hi']:+.3f}] is entirely above zero -- worse")

    holm_ok = bool(arm["holm"] and arm["holm"]["rejects"])
    if not holm_ok and arm["holm"]:
        why.append(f"Holm-adjusted p {arm['holm']['p_adjusted']:.4f} does not clear {ALPHA}")

    return {
        "adopt": bool(beats_mean and beats_worst and non_inferior and holm_ok),
        "beats_mean": bool(beats_mean),
        "beats_worst": bool(beats_worst),
        "non_inferior_every_season": bool(non_inferior),
        "holm_rejects": holm_ok,
        "why": "; ".join(why)
        or "beats the incumbent on mean and worst, harms no season, and survives Holm",
    }


def _caveats(fits: Dict[int, Dict[str, Any]], arms: List[Dict[str, Any]]) -> List[str]:
    out = [
        f"AS-OF RULE USED: {AS_OF_RULE}. Live, the window closes strictly before the "
        "build's timestamp; the two coincide except for a midweek build after a "
        "Thursday game of the same week.",
        "The incumbent is an ARM (k -> infinity, so w = 0 at every n): the same code "
        "path with the season's own evidence given no weight, not a re-implementation.",
        "At n=0 the weight is 0, so week 1 is the incumbent exactly and cannot be harmed.",
        "The mean across seasons is EQUAL-WEIGHT: the question is whether the estimator "
        "transfers between seasons.",
        "DEVELOPMENT EVIDENCE. 2026 motivated this hypothesis, so a pass here is NOT "
        "prospective validation; prospective evidence begins with decisions logged after "
        "the row was registered.",
        "DECLARED LIMITATION: the bootstrap resamples games WITHIN a season and is blind "
        "to BETWEEN-season variation, the dominant uncertainty here. The interval is "
        "narrower than the transfer claim it is read against.",
        "A pass would license a prospective paper arm only -- and that arm needs its own "
        "registry row and its own clock before it logs a pick. H-STOP is untouched.",
    ]
    for s, f in sorted(fits.items()):
        if abs(f["c_prior"]) < 1e-12:
            out.append(
                f"{s}: c_prior is 0 (its training window holds no scorable fold), so every "
                f"arm there is IN-SEASON ONLY rather than a blend. Informative, not "
                f"degenerate -- unlike H-INTERCEPT, no season collapses to an all-arms tie."
            )
    return out


def render_markdown(report: Dict[str, Any]) -> str:
    season_ids = [str(s["season"]) for s in report["seasons"]]
    L = [
        "# In-season intercept gate — H-INSEASON",
        "",
        f"Blend `c_t = (1-w)*c_prior + w*c_season`, `w = n/(n+k)`, grid k={report['grid']}. "
        f"Walk-forward, min_games={report['min_games']}, fbs_only={report['fbs_only']}, "
        f"{report['n_boot']} bootstrap draws, alpha {report['alpha']}.",
        "",
        f"**As-of rule: {report['as_of_rule']}.**",
        "",
        "## Held-out seasons",
        "",
        "| season | test n | train n | c_prior | priced |",
        "|---|---|---|---|---|",
    ]
    for s in report["seasons"]:
        note = " (no scorable fold)" if abs(s["c_prior"]) < 1e-12 else ""
        L.append(
            f"| {s['season']} | {s['n']} | {s['n_train']} | {s['c_prior']:+.4f}{note} "
            f"| {s['n_priced']} |"
        )

    L += [
        "",
        "## Arms — signed bias (prediction − actual)",
        "",
        "| arm | " + " | ".join(season_ids) + " | mean abs | worst | mean w |",
        "|---" * (len(season_ids) + 4) + "|",
    ]
    for arm in report["arms"]:
        cells = [f"{arm['seasons'][s]['bias']:+.2f}" for s in season_ids]
        mw = np.mean([arm["seasons"][s]["mean_weight"] for s in season_ids])
        tag = " (incumbent)" if arm["is_incumbent"] else ""
        L.append(
            f"| {arm['label']}{tag} | "
            + " | ".join(cells)
            + f" | {arm['mean_abs_bias']:.3f} | {arm['worst_abs_bias']:.3f} | {mw:.2f} |"
        )

    L += [
        "",
        "## Primary — the two required aggregate tests",
        "",
        "Difference in |bias|, challenger − incumbent. A pass needs the interval "
        "ENTIRELY BELOW zero on both.",
        "",
        "| arm | statistic | arm | incumbent | diff | 95% CI | below 0 | Holm p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for arm in report["arms"]:
        if arm["is_incumbent"]:
            continue
        for name, human in (("mean_abs_bias", "mean"), ("worst_abs_bias", "worst")):
            a = arm["aggregate"][name]
            hp = arm["holm"]["p_adjusted"] if arm["holm"] else None
            L.append(
                f"| {arm['label']} | {human} | {a['arm']:.3f} | {a['incumbent']:.3f} "
                f"| {a['diff']:+.3f} | [{a['lo']:+.3f}, {a['hi']:+.3f}] "
                f"| {'yes' if a['below_zero'] else 'no'} "
                f"| {'—' if hp is None else format(hp, '.4f')} |"
            )

    L += [
        "",
        "## Per-season non-inferiority",
        "",
        "A season fails only if its interval is ENTIRELY ABOVE zero. Crossing zero is a tie.",
        "",
        "| arm | season | diff | 95% CI | worse? |",
        "|---|---|---|---|---|",
    ]
    for arm in report["arms"]:
        if arm["is_incumbent"]:
            continue
        for s in season_ids:
            ci = arm["seasons"][s]["vs_incumbent"]
            L.append(
                f"| {arm['label']} | {s} | {ci['mean']:+.3f} | "
                f"[{ci['lo']:+.3f}, {ci['hi']:+.3f}] | {'YES' if ci['worse'] else 'no'} |"
            )

    L += ["", "## Secondary — reported, never optimised", "", "### Bias by week band", ""]
    L += [
        "| arm | season | "
        + " | ".join(f"{lo}-{hi}" if hi < 99 else f"{lo}+" for lo, hi in WEEK_BANDS)
        + " |"
    ]
    L += ["|---" * (len(WEEK_BANDS) + 2) + "|"]
    for arm in report["arms"]:
        for s in season_ids:
            bands = {b["band"]: b for b in arm["seasons"][s]["by_week_band"]}
            cells = []
            for lo, hi in WEEK_BANDS:
                key = f"{lo}-{hi}" if hi < 99 else f"{lo}+"
                b = bands.get(key)
                cells.append("—" if b is None else f"{b['bias']:+.2f} (n{b['n']})")
            L.append(f"| {arm['label']} | {s} | " + " | ".join(cells) + " |")

    if any("gate" in arm["seasons"][season_ids[0]] for arm in report["arms"]):
        L += [
            "",
            f"### MAE, and the share clearing {report['bet_gap_pts']} pts",
            "",
            "| arm | season | MAE | priced | clearing | share |",
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
                    f"| {arm['label']} | {s} | {st['mae']:.3f} | {g['n_priced']} "
                    f"| {g['n_clearing']} | {share} |"
                )

    L += ["", "## Verdict", "", "| arm | adopt? | why |", "|---|---|---|"]
    for arm in report["arms"]:
        v = arm["verdict"]
        L.append(f"| {arm['label']} | {'**YES**' if v['adopt'] else 'no'} | {v['why']} |")

    L += ["", "## Caveats", ""] + [f"- {c}" for c in report["caveats"]]
    return "\n".join(L) + "\n"
