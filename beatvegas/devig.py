"""No-vig (devigged) fair-probability math for two-way totals.

Kept dependency-free and unit-tested, mirrored verbatim by web/lib/devig.ts.
Convention: we reason about the UNDER side, but the math is symmetric.

The book's two posted prices imply probabilities that sum to >1 (the overround
/ hold). Devigging removes that margin to recover the market's fair probability.
Three standard methods:
  - multiplicative: divide each implied prob by their sum (fine for near-
    symmetric -110/-110 lines).
  - power: raise each implied prob to a common exponent k so they sum to 1
    (handles favorite-longshot skew better than multiplicative).
  - shin: Shin (1992/1993) insider-trading model; solves for the proportion of
    informed money z, then backs out fair probs.

Devig outputs are MARKET signal — they must never feed the market-blind BV
regressor. Used only for CLV, line-check EV, staking, and backtest grading.
"""

from __future__ import annotations

from typing import Tuple

from .grading import american_to_decimal


def american_to_prob(price: int) -> float:
    """Implied (vig-included) probability from American odds.

    -110 -> 0.5238, +120 -> 0.4545.
    """
    return 1.0 / american_to_decimal(price)


def _multiplicative(p_over: float, p_under: float) -> Tuple[float, float]:
    total = p_over + p_under
    return p_over / total, p_under / total


def _power(p_over: float, p_under: float) -> Tuple[float, float]:
    """Find k such that p_over**k + p_under**k == 1, via bisection."""
    lo, hi = 0.0, 10.0
    for _ in range(60):
        k = (lo + hi) / 2.0
        s = p_over**k + p_under**k
        if s > 1.0:
            lo = k  # larger k shrinks the sum (probs < 1)
        else:
            hi = k
    k = (lo + hi) / 2.0
    return p_over**k, p_under**k


def _shin(p_over: float, p_under: float) -> Tuple[float, float]:
    """Shin's two-outcome devig. The recovered fair probs are
        fair_i = (sqrt(z^2 + 4(1-z) * o_i^2 / booksum) - z) / (2(1-z))
    where o_i are the raw implied probs and z is the insider proportion. The
    sum-to-one constraint reduces (for two outcomes) to
        sqrt(z^2 + 4(1-z)a) + sqrt(z^2 + 4(1-z)b) = 2,   a=o_over^2/booksum, etc.
    which we solve for the interior root z in (0, 0.5) by bisection. Falls back
    to multiplicative when the overround is non-positive."""
    booksum = p_over + p_under
    if booksum <= 1.0:
        return _multiplicative(p_over, p_under)
    a = p_over**2 / booksum
    b = p_under**2 / booksum

    def s(z: float) -> float:
        return (z**2 + 4.0 * (1.0 - z) * a) ** 0.5 + (z**2 + 4.0 * (1.0 - z) * b) ** 0.5

    # s(0) = 2*sqrt(booksum) > 2; s dips below 2 before returning to 2 at z=1.
    # The wanted root is the first crossing, bracketed by [0, 0.5].
    lo, hi = 0.0, 0.5
    for _ in range(60):
        z = (lo + hi) / 2.0
        if s(z) > 2.0:
            lo = z
        else:
            hi = z
    z = (lo + hi) / 2.0

    def fair(p: float) -> float:
        return (((z**2 + 4.0 * (1.0 - z) * p**2 / booksum) ** 0.5) - z) / (2.0 * (1.0 - z))

    return fair(p_over), fair(p_under)


def devig_two_way(
    over_price: int, under_price: int, method: str = "multiplicative"
) -> Tuple[float, float, float]:
    """Return (fair_over, fair_under, hold) from a two-way total's prices.

    `hold` is the book's overround (raw implied-prob sum - 1). The two fair
    probabilities sum to 1.
    """
    p_over = american_to_prob(over_price)
    p_under = american_to_prob(under_price)
    hold = p_over + p_under - 1.0
    if method == "multiplicative":
        fo, fu = _multiplicative(p_over, p_under)
    elif method == "power":
        fo, fu = _power(p_over, p_under)
    elif method == "shin":
        fo, fu = _shin(p_over, p_under)
    else:
        raise ValueError(f"unknown devig method: {method}")
    return fo, fu, hold


def ev_under(fair_under_prob: float, offered_under_price: int) -> float:
    """Per-$1 EV of taking the UNDER at `offered_under_price`, given a reference
    no-vig fair under probability. Positive = +EV.

    EV = p*(decimal-1) - (1-p).
    """
    payout = american_to_decimal(offered_under_price) - 1.0
    return fair_under_prob * payout - (1.0 - fair_under_prob)
