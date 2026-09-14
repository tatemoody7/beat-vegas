"""Does censoring leave information the PRICE has not already absorbed?

The mechanism was never in doubt. An underdog's first-half scoring distribution
is censored at zero and the censoring grows with the spread -- measured here,
the dog is held scoreless in 8.6% of close games and 23.1% at 28+, while the
favourite's rate falls to zero. That is a real and strong property of football.

It is not, by itself, a reason to build anything. "The distribution is censored"
and "the market misprices the censoring" are different claims, and only the
second one is bettable. This module tests the second one.

THE TESTS, and what each can actually support:

  Test 1 (zero_mass_by_bucket) -- MECHANISM DIAGNOSTIC, NOT A MARKET TEST.
    Realized per-team zero mass and skew by spread bucket. A 1H total plus a
    full-game spread does NOT uniquely determine the probability the market
    assigns to a team scoring zero -- deriving that needs a distributional
    assumption, after which the answer tells you about your assumption as much
    as about the market. So this can show football is censored. It cannot show
    the market is wrong about it, in either direction. Its job is to say whether
    a zero-mass component would be structurally worth having, if we ever build.

  Test 2 (spread_residual) -- THE GATE.
    After controlling for the book's OWN de-vigged probability, does spread still
    predict whether the Under wins? Fitted as a logistic model with the market's
    probability entered as an OFFSET (coefficient fixed at 1), so the question is
    purely "does spread add anything the price has not said?" A free-coefficient
    variant is reported alongside to show whether the market is miscalibrated in
    level as well.

  Test 3 -- economic, and only reached if Test 2 is positive: does the residual
    survive real prices, including pushes, with monotone edge buckets?

PUSHES ARE HANDLED FIRST, and the reason is not pedantry. A two-way de-vig
returns fair_over + fair_under = 1, which implicitly assumes no push -- so it is
not comparable to a raw Under percentage that still has pushes in its
denominator. Measured on this set: 27% of closes land on an integer total and
those push 5.66% of the time, moving the headline Under rate 48.74% -> 49.49%.
That 0.75pp is the same order as the effect being hunted.

The resolution is clean: on an integer line a push VOIDS the bet, so the book's
two prices are effectively pricing {under | decided} against {over | decided}.
A two-way de-vig therefore already yields conditional-on-decided probabilities,
and comparing it to the realized decided Under rate is correct for integer and
half-point lines alike. Everything below conditions on non-push and reports the
push rate separately.

SCOPE. The real-close cut only (postmortem_games, scope hist_2023_25,
line_real not null). Never the 1,699 games no book priced: that split has
inverted conclusions in this repo before, and the unpriced games are not a
random sample -- they are the games nobody wanted to price.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..devig import devig_two_way, is_centred_quote

# Spread buckets. Coarse on purpose: the whole sample is 1,902 games and the
# tail is thin, so finer cuts buy resolution the n cannot support.
SPREAD_BUCKETS: Sequence[float] = (-0.1, 7.0, 14.0, 21.0, 28.0, 99.0)
BUCKET_LABELS: Sequence[str] = ("<7", "7-14", "14-21", "21-28", "28+")

# Break-even at -110 is 52.38%, i.e. 2.38 points of edge over a coin flip. Any
# residual smaller than this is not a bet however real it is.
VIG_HURDLE_PP = 2.38


# --------------------------------------------------------------- probabilities
#
# There is no Brier score, no log-loss and no calibration helper anywhere else
# in this repo (the only model probability, score.py's predict_proba, is
# uncalibrated and is squashed into a 0-100 display score without ever being
# scored). These are written three-outcome-aware from the start so the same
# functions serve a future engine that emits P(under)/P(push)/P(over) -- a
# binary version would have to be rewritten, and worse, its numbers would not be
# comparable to the ones this study reports.


def brier(p: np.ndarray, y: np.ndarray) -> float:
    """Mean squared error of a probability forecast. Lower is better."""
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray, eps: float = 1e-12) -> float:
    """Negative mean log-likelihood. Lower is better."""
    p = np.clip(np.asarray(p, float), eps, 1 - eps)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier_multi(p: np.ndarray, y_onehot: np.ndarray) -> float:
    """Three-outcome Brier over {under, push, over}. `p` and `y_onehot` are
    (n, 3); rows of `p` should sum to 1. Reduces to 2*binary Brier in the
    two-outcome case, which is why the binary helper above is kept separate
    rather than derived from this one."""
    p, y = np.asarray(p, float), np.asarray(y_onehot, float)
    return float(np.mean(np.sum((p - y) ** 2, axis=1)))


def wilson(hits: int, n: int, z: float = 1.959963985) -> Tuple[Optional[float], Optional[float]]:
    """Wilson score interval. Correct in the tails where normal approximation
    is not, which matters: the 28+ bucket holds 65 games."""
    if n <= 0:
        return None, None
    ph = hits / n
    denom = 1 + z * z / n
    centre = ph + z * z / (2 * n)
    half = z * np.sqrt((ph * (1 - ph) + z * z / (4 * n)) / n)
    return float((centre - half) / denom), float((centre + half) / denom)


def reliability(p: np.ndarray, y: np.ndarray, bins: int = 10) -> List[Dict[str, Any]]:
    """Calibration table: predicted vs realized within probability bins."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    edges = (
        np.linspace(p.min(), p.max(), bins + 1)
        if p.max() > p.min()
        else np.array([p.min(), p.min() + 1e-9])
    )
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, len(edges) - 2)
    out: List[Dict[str, Any]] = []
    for b in range(len(edges) - 1):
        m = idx == b
        if not m.any():
            continue
        lo, hi = wilson(int(y[m].sum()), int(m.sum()))
        out.append(
            {
                "bin": b,
                "n": int(m.sum()),
                "predicted": float(p[m].mean()),
                "realized": float(y[m].mean()),
                "lo": lo,
                "hi": hi,
            }
        )
    return out


# ------------------------------------------------------------------ market read


def closing_fair_under(quotes: Iterable[Dict[str, Any]]) -> Dict[int, float]:
    """{game_id: median de-vigged fair P(under) across books at the close}.

    `quotes` are one row per (game, book) carrying over_price / under_price --
    each book's LAST pre-kickoff quote inside the close window. Off-centre
    ladder rungs are dropped (devig.is_centred_quote): Hard Rock serves one on
    26 of 28 quotes inside 3h of kickoff, and de-vigging a rung produces a
    confident probability for a number nobody was offered."""
    by_game: Dict[int, List[float]] = {}
    for r in quotes:
        over, under = r.get("over_price"), r.get("under_price")
        if over is None or under is None:
            continue
        over, under = int(over), int(under)
        if not is_centred_quote(over, under):
            continue
        _fo, fu, _hold = devig_two_way(over, under, method="multiplicative")
        if fu is not None:
            by_game.setdefault(int(r["game_id"]), []).append(float(fu))
    return {g: statistics.median(v) for g, v in by_game.items()}


def push_audit(df: pd.DataFrame) -> Dict[str, Any]:
    """Push rate overall and split by integer vs half-point close.

    Run BEFORE any comparison. If this is ignored, a de-vigged probability
    (which carries no push mass) gets compared against an Under rate that does,
    and the bias is silent."""
    d = df[df["line_real"].notna()].copy()
    d["integer_line"] = d["line_real"] == np.floor(d["line_real"])
    out: Dict[str, Any] = {"n": int(len(d))}
    rows = []
    for is_int, g in d.groupby("integer_line"):
        pushes = int((g["outcome_real"] == "push").sum())
        rows.append(
            {
                "line_type": "integer" if is_int else "half-point",
                "n": int(len(g)),
                "pushes": pushes,
                "push_pct": 100.0 * pushes / len(g) if len(g) else None,
            }
        )
    out["by_line_type"] = rows
    pushes = int((d["outcome_real"] == "push").sum())
    decided = d[d["outcome_real"] != "push"]
    out["pushes"] = pushes
    out["push_pct"] = 100.0 * pushes / len(d) if len(d) else None
    out["under_pct_all"] = 100.0 * (d["outcome_real"] == "under").mean()
    out["under_pct_decided"] = 100.0 * (decided["outcome_real"] == "under").mean()
    out["bias_pp_if_ignored"] = out["under_pct_decided"] - out["under_pct_all"]
    return out


# ---------------------------------------------------------------------- Test 1


def zero_mass_by_bucket(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """MECHANISM ONLY. Realized per-team zero mass and means by spread bucket.

    `df` needs spread (home-relative, negative = home favoured), spread_abs and
    per-team first-half points. Read it as a statement about football, never as
    a statement about the market -- see the module docstring."""
    d = df.dropna(subset=["spread", "spread_abs", "home_fh", "away_fh"]).copy()
    fav = np.where(d["spread"] <= 0, d["home_fh"], d["away_fh"])
    dog = np.where(d["spread"] <= 0, d["away_fh"], d["home_fh"])
    d["fav_pts"], d["dog_pts"] = fav, dog
    d["bucket"] = pd.cut(d["spread_abs"], list(SPREAD_BUCKETS), labels=list(BUCKET_LABELS))
    out: List[Dict[str, Any]] = []
    for label, g in d.groupby("bucket", observed=True):
        lo, hi = wilson(int((g["dog_pts"] == 0).sum()), len(g))
        out.append(
            {
                "bucket": str(label),
                "n": int(len(g)),
                "dog_shutout_pct": 100.0 * float((g["dog_pts"] == 0).mean()),
                "dog_shutout_lo": None if lo is None else 100 * lo,
                "dog_shutout_hi": None if hi is None else 100 * hi,
                "fav_shutout_pct": 100.0 * float((g["fav_pts"] == 0).mean()),
                "dog_mean": float(g["dog_pts"].mean()),
                "fav_mean": float(g["fav_pts"].mean()),
                "dog_median": float(g["dog_pts"].median()),
            }
        )
    return out


def score_support(df: pd.DataFrame, top: int = 8) -> List[Dict[str, Any]]:
    """How lumpy is a team's first-half score? Decides whether a future model
    may use a continuous distribution (it may not)."""
    d = df.dropna(subset=["spread", "home_fh", "away_fh"]).copy()
    dog = np.where(d["spread"] <= 0, d["away_fh"], d["home_fh"])
    vc = pd.Series(dog).value_counts().sort_values(ascending=False).head(top)
    return [{"points": int(k), "pct": 100.0 * v / len(d)} for k, v in vc.items()]


# ---------------------------------------------------------------------- Test 2


def _fit_logit(offset: np.ndarray, X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Logistic MLE with a fixed offset. Newton-Raphson with a ridge nudge on
    the Hessian, which keeps it stable when a column is nearly constant --
    `fair_under` has a tiny spread and would otherwise be ill-conditioned."""
    b = np.zeros(X.shape[1])
    for _ in range(60):
        z = offset + X @ b
        p = 1.0 / (1.0 + np.exp(-z))
        grad = X.T @ (y - p)
        W = p * (1 - p)
        H = (X * W[:, None]).T @ X + 1e-8 * np.eye(X.shape[1])
        step = np.linalg.solve(H, grad)
        b = b + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return b


def spread_residual(df: pd.DataFrame, n_boot: int = 400, seed: int = 7) -> Dict[str, Any]:
    """THE GATE. After controlling for the book's own de-vigged probability,
    does spread still predict the Under?

    The market's probability enters as an OFFSET (coefficient fixed at 1), so a
    non-zero spread coefficient means spread carries information the price does
    not. The free-coefficient variant is reported too: a market-logit
    coefficient far from 1.0 would say the price is miscalibrated in level,
    which is a different and also interesting failure."""
    d = df[
        (df["outcome_real"] != "push") & df["fair_under"].notna() & df["spread_abs"].notna()
    ].copy()
    y = (d["outcome_real"] == "under").to_numpy(dtype=float)
    p = d["fair_under"].clip(1e-6, 1 - 1e-6).to_numpy()
    offset = np.log(p / (1 - p))
    x = d["spread_abs"].to_numpy(dtype=float)
    xbar = float(x.mean())
    X = np.column_stack([np.ones_like(x), x - xbar])

    b = _fit_logit(offset, X, y)
    rng = np.random.default_rng(seed)
    boots = np.empty((n_boot, 2))
    for i in range(n_boot):
        s = rng.integers(0, len(y), len(y))
        boots[i] = _fit_logit(offset[s], X[s], y[s])
    lo, hi = np.percentile(boots[:, 1], [2.5, 97.5])
    ilo, ihi = np.percentile(boots[:, 0], [2.5, 97.5])

    free = _fit_logit(
        np.zeros_like(offset), np.column_stack([np.ones_like(x), offset, x - xbar]), y
    )

    # What the point estimate would be worth if it were real, in percentage
    # points of P(under) across the whole spread range, against the vig hurdle.
    swing_pp = 100.0 * (
        1 / (1 + np.exp(-(b[1] * (28 - xbar)))) - 1 / (1 + np.exp(-(b[1] * (7 - xbar))))
    )
    return {
        "n": int(len(d)),
        "under_rate": float(y.mean()),
        "market_mean_p": float(p.mean()),
        "calibration_gap": float(y.mean() - p.mean()),
        "brier_market": brier(p, y),
        "brier_coinflip": brier(np.full_like(p, 0.5), y),
        "log_loss_market": log_loss(p, y),
        "spread_coef": float(b[1]),
        "spread_ci": [float(lo), float(hi)],
        "spread_excludes_zero": bool(not (lo <= 0 <= hi)),
        "intercept": float(b[0]),
        "intercept_ci": [float(ilo), float(ihi)],
        "market_level_unbiased": bool(ilo <= 0 <= ihi),
        "free_market_logit_coef": float(free[1]),
        "free_spread_coef": float(free[2]),
        "swing_pp_7_to_28": float(swing_pp),
        "vig_hurdle_pp": VIG_HURDLE_PP,
        "clears_vig": bool(abs(swing_pp) > VIG_HURDLE_PP),
        "n_boot": int(n_boot),
    }


def per_season(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """The spread coefficient season by season. A coefficient that changes sign
    is noise, whatever the pooled interval says."""
    out: List[Dict[str, Any]] = []
    d = df[(df["outcome_real"] != "push") & df["fair_under"].notna() & df["spread_abs"].notna()]
    xbar = float(d["spread_abs"].mean())
    for season, g in d.groupby("season"):
        y = (g["outcome_real"] == "under").to_numpy(dtype=float)
        p = g["fair_under"].clip(1e-6, 1 - 1e-6).to_numpy()
        x = g["spread_abs"].to_numpy(dtype=float)
        b = _fit_logit(np.log(p / (1 - p)), np.column_stack([np.ones_like(x), x - xbar]), y)
        out.append(
            {
                "season": int(season),
                "n": int(len(g)),
                "spread_coef": float(b[1]),
                "under_rate": float(y.mean()),
                "market_mean_p": float(p.mean()),
            }
        )
    return out


def walk_forward(df: pd.DataFrame, test_season: int) -> Dict[str, Any]:
    """Fit on every earlier season, score the held-out one. The only evidence
    that counts: an in-sample coefficient proves nothing about a season it has
    already seen."""
    d = df[(df["outcome_real"] != "push") & df["fair_under"].notna() & df["spread_abs"].notna()]
    tr, te = d[d["season"] < test_season], d[d["season"] == test_season]
    if tr.empty or te.empty:
        return {"test_season": int(test_season), "evaluable": False}
    xbar = float(tr["spread_abs"].mean())

    def parts(g):
        p = g["fair_under"].clip(1e-6, 1 - 1e-6).to_numpy()
        return (
            np.log(p / (1 - p)),
            g["spread_abs"].to_numpy(dtype=float),
            (g["outcome_real"] == "under").to_numpy(dtype=float),
        )

    off_tr, x_tr, y_tr = parts(tr)
    b = _fit_logit(off_tr, np.column_stack([np.ones_like(x_tr), x_tr - xbar]), y_tr)
    off_te, x_te, y_te = parts(te)
    p_mkt = 1 / (1 + np.exp(-off_te))
    p_mdl = 1 / (1 + np.exp(-(off_te + b[0] + b[1] * (x_te - xbar))))
    return {
        "test_season": int(test_season),
        "evaluable": True,
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
        "spread_coef": float(b[1]),
        "brier_market": brier(p_mkt, y_te),
        "brier_with_spread": brier(p_mdl, y_te),
        "log_loss_market": log_loss(p_mkt, y_te),
        "log_loss_with_spread": log_loss(p_mdl, y_te),
        "spread_helps_brier": bool(brier(p_mdl, y_te) < brier(p_mkt, y_te)),
        "brier_delta": float(brier(p_mkt, y_te) - brier(p_mdl, y_te)),
    }


def realized_vs_implied(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Realized minus market-implied Under rate, by spread bucket, with Wilson
    intervals. The same question as Test 2 in a form that can be eyeballed."""
    d = df[
        (df["outcome_real"] != "push") & df["fair_under"].notna() & df["spread_abs"].notna()
    ].copy()
    d["y"] = (d["outcome_real"] == "under").astype(int)
    d["bucket"] = pd.cut(d["spread_abs"], list(SPREAD_BUCKETS), labels=list(BUCKET_LABELS))
    out: List[Dict[str, Any]] = []
    for label, g in d.groupby("bucket", observed=True):
        lo, hi = wilson(int(g["y"].sum()), len(g))
        out.append(
            {
                "bucket": str(label),
                "n": int(len(g)),
                "realized_pct": 100.0 * float(g["y"].mean()),
                "implied_pct": 100.0 * float(g["fair_under"].mean()),
                "diff_pp": 100.0 * float(g["y"].mean() - g["fair_under"].mean()),
                "lo_pct": None if lo is None else 100 * lo,
                "hi_pct": None if hi is None else 100 * hi,
            }
        )
    return out


def verdict(
    gate: Dict[str, Any], seasons: List[Dict[str, Any]], wf: Dict[str, Any]
) -> Dict[str, Any]:
    """The decision rule, fixed before the run (the plan of 2026-09-13).

    Test 2 is the gate. Test 1 chooses an architecture; it never authorises a
    build, because it does not measure market pricing."""
    signs = {np.sign(s["spread_coef"]) for s in seasons if s["spread_coef"] != 0}
    stable = len(signs) <= 1
    reasons: List[str] = []
    if not gate["spread_excludes_zero"]:
        reasons.append(
            f"spread coef {gate['spread_coef']:+.5f} CI "
            f"[{gate['spread_ci'][0]:+.5f}, {gate['spread_ci'][1]:+.5f}] includes zero"
        )
    if not stable:
        reasons.append("the per-season coefficient changes sign")
    if not gate["clears_vig"]:
        reasons.append(
            f"the point estimate is worth {gate['swing_pp_7_to_28']:+.2f} pp across the whole "
            f"7-to-28 spread range, under the {gate['vig_hurdle_pp']} pp vig hurdle"
        )
    return {
        "build": bool(gate["spread_excludes_zero"] and stable and gate["clears_vig"]),
        "sign_stable_across_seasons": bool(stable),
        "reasons": reasons,
        "rule": "Test 2 is the gate; Test 1 informs the model family only.",
    }
