"""The H-INSEASON challenger family, live.

Registry row **H-INSEASON-P**; spec in docs/INSEASON_PAPER.md. The developmental
row (H-INSEASON) passed on a metric that is PARTLY MECHANICAL for this estimator,
so nothing here is an improvement claim -- it is prospective collection, judged
later on paper profit and line value, which are not mechanically tied to the
correction.

WHAT AN ARM IS. The champion adds `c_prior = bias_corrections(train)["global"]`
to every prediction: one number per season, learned from PRIOR seasons only. An
arm blends it with the season's own realized bias,

    c_t = (1 - w) * c_prior + w * c_season,   w = n / (n + k)

where `c_season = mean(actual - RAW pred)` over the season's games completed
STRICTLY BEFORE this build. The raw prediction is `bv_line - bv_intercept`,
which is why `Prediction.bv_intercept` is stored: deriving `c_season` from a
calibrated prediction would re-apply `c_prior` scaled by `w`, and no number in
any report would reveal it.

At n=0 the weight is 0 and the arm IS the champion, so an early-season build
cannot be harmed by this.

WHAT THIS MODULE DOES NOT DO. It never decides anything. It rewrites `bv_line`
on a copy of the prediction rows and hands them back to the SAME `build_card`
the champion runs through, so every gate, every blocker and `qualifies` itself
are the champion's code, not a parallel implementation that could drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

# Frozen at registration. tests/test_challenger.py pins these against
# backtest.inseason.K_GRID so the live family and the studied family cannot
# diverge; changing either without the other fails.
PAPER_ARMS: Sequence[float] = (25.0, 50.0, 100.0, 200.0)


def arm_label(k: float) -> str:
    return f"k{int(k)}"


def blend(c_prior: float, c_season: Optional[float], n: int, k: float) -> float:
    """`c_t`, the intercept one arm applies. n=0 (or no c_season) is the champion."""
    if k <= 0:
        raise ValueError("k must be positive -- w = n/(n+k) is undefined otherwise")
    if not n or c_season is None:
        return float(c_prior)
    w = n / (n + float(k))
    return (1.0 - w) * float(c_prior) + w * float(c_season)


def weight(n: int, k: float) -> float:
    return 0.0 if not n else n / (n + float(k))


@dataclass
class SeasonRead:
    """What the season's completed games say about the model's level, as of a build."""

    n: int
    c_season: Optional[float]

    @classmethod
    def from_completed(cls, raws: Sequence[float], actuals: Sequence[float]) -> "SeasonRead":
        if len(raws) != len(actuals):
            raise ValueError("raws and actuals must be the same length")
        if not raws:
            return cls(n=0, c_season=None)
        # The sign bias_corrections uses and apply_bias adds: actual - prediction.
        errs = [float(a) - float(r) for r, a in zip(raws, actuals)]
        return cls(n=len(errs), c_season=sum(errs) / len(errs))


def season_read(rows: Iterable[Dict[str, Any]]) -> SeasonRead:
    """`rows` are completed games with `bv_line`, `bv_intercept` and the realized
    1H total. The raw prediction is reconstructed, never re-derived from a
    calibrated one."""
    raws: List[float] = []
    actuals: List[float] = []
    for r in rows:
        bv, ic, actual = r.get("bv_line"), r.get("bv_intercept"), r.get("first_half_total")
        if bv is None or ic is None or actual is None:
            continue
        raws.append(float(bv) - float(ic))
        actuals.append(float(actual))
    return SeasonRead.from_completed(raws, actuals)


def arm_predictions(
    predictions: Sequence[Dict[str, Any]],
    read: SeasonRead,
    k: float,
    *,
    model_version: str,
) -> List[Dict[str, Any]]:
    """The champion's prediction rows with `bv_line` moved to the arm's intercept.

    Only rows of `model_version` carrying both `bv_line` and `bv_intercept` are
    shifted; reference rows (the derived-lines fallback the card uses when no
    book has posted) pass through untouched, because they are not model output
    and an intercept has no meaning for them.
    """
    out: List[Dict[str, Any]] = []
    for p in predictions:
        q = dict(p)
        if (
            p.get("model_version") == model_version
            and p.get("bv_line") is not None
            and p.get("bv_intercept") is not None
        ):
            raw = float(p["bv_line"]) - float(p["bv_intercept"])
            q["bv_line"] = round(raw + blend(float(p["bv_intercept"]), read.c_season, read.n, k), 2)
            q["champion_bv_line"] = float(p["bv_line"])
        out.append(q)
    return out


def arm_context(c_prior: Optional[float], read: SeasonRead, k: float) -> Dict[str, Any]:
    """What gets frozen onto every pick this arm makes at this build."""
    return {
        "arm": arm_label(k),
        "c_prior": None if c_prior is None else float(c_prior),
        "c_season": read.c_season,
        "in_season_n": int(read.n),
        "in_season_weight": round(weight(read.n, k), 6),
    }
