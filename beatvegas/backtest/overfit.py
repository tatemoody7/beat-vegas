"""Overfitting controls for the walk-forward backtest (research doc Stage 3).

Two Bailey & Lopez de Prado tools, pure and dependency-light:

- Deflated Sharpe Ratio (DSR): the probability the strategy's true Sharpe is
  positive AFTER deflating for (a) the number of configurations tried and (b)
  non-normal returns (skew/fat tails). A high in-sample Sharpe found among many
  trials is "easily achievable" by chance — DSR discounts exactly that.
- Probability of Backtest Overfitting (PBO) via Combinatorially Symmetric
  Cross-Validation (CSCV): across every balanced in/out split of the data, how
  often does the in-sample-best configuration land below the median out-of-sample?
  PBO -> 0.5 means the selection carries no real skill.

These never feed the market-blind regressor; they only judge the backtest.
"""

from __future__ import annotations

import math
from itertools import combinations
from statistics import NormalDist
from typing import List, Sequence

_PHI = NormalDist()
_EULER = 0.5772156649015329  # Euler-Mascheroni constant


def _moments(returns: Sequence[float]):
    """(mean, std, skew, kurtosis) — population moments; kurtosis is raw (3=normal)."""
    n = len(returns)
    mu = sum(returns) / n
    var = sum((r - mu) ** 2 for r in returns) / n
    sd = math.sqrt(var)
    if sd == 0:
        return mu, 0.0, 0.0, 3.0
    skew = (sum((r - mu) ** 3 for r in returns) / n) / sd**3
    kurt = (sum((r - mu) ** 4 for r in returns) / n) / sd**4
    return mu, sd, skew, kurt


def sharpe_ratio(returns: Sequence[float]) -> float:
    """Per-observation Sharpe (mean / std) — no annualization; bets are the unit."""
    mu, sd, _, _ = _moments(returns)
    return mu / sd if sd > 0 else 0.0


def probabilistic_sharpe_ratio(
    sr: float, n: int, skew: float, kurtosis: float, sr_benchmark: float = 0.0
) -> float:
    """P(true SR > sr_benchmark) given the observed SR over n returns, adjusted
    for skew and kurtosis (Bailey & Lopez de Prado 2012)."""
    if n < 2:
        return float("nan")
    denom = math.sqrt(max(1e-12, 1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr**2))
    z = (sr - sr_benchmark) * math.sqrt(n - 1) / denom
    return _PHI.cdf(z)


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Expected maximum Sharpe from `n_trials` independent strategies whose SRs
    have variance `sr_variance` — the benchmark a real edge must clear."""
    if n_trials < 2 or sr_variance <= 0:
        return 0.0
    z1 = _PHI.inv_cdf(1.0 - 1.0 / n_trials)
    z2 = _PHI.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(sr_variance) * ((1.0 - _EULER) * z1 + _EULER * z2)


def deflated_sharpe_ratio(returns: Sequence[float], n_trials: int, sr_variance: float) -> float:
    """DSR: PSR benchmarked against the expected-max Sharpe of `n_trials` configs.
    Near 1.0 = the edge survives the multiple-testing + non-normality discount;
    below ~0.95 = not significant."""
    mu, sd, skew, kurt = _moments(returns)
    if sd == 0:
        return float("nan")
    sr = mu / sd
    sr_star = expected_max_sharpe(n_trials, sr_variance)
    return probabilistic_sharpe_ratio(sr, len(returns), skew, kurt, sr_benchmark=sr_star)


def pbo(perf_matrix: List[Sequence[float]], n_splits: int = 16) -> float:
    """Probability of Backtest Overfitting via CSCV.

    `perf_matrix`: T observations (rows) x N configurations (cols) of per-obs
    performance (e.g. per-game bet returns). Splits the rows into S equal groups,
    and over every balanced in/out combination picks the in-sample-best config and
    records its out-of-sample relative rank. PBO = share of combinations where the
    IS-best config ranks at/below the OOS median. Returns nan when there is too
    little data (need >= 4 even groups and >= 2 configs)."""
    t = len(perf_matrix)
    if t == 0:
        return float("nan")
    n = len(perf_matrix[0])
    s = min(n_splits, t)
    if s % 2:
        s -= 1
    if s < 4 or n < 2:
        return float("nan")

    # Contiguous, (near-)equal row groups; precompute per-group column sums so each
    # combination is cheap.
    bounds = [round(i * t / s) for i in range(s + 1)]
    group_sums: List[List[float]] = []
    for g in range(s):
        cols = [0.0] * n
        for r in range(bounds[g], bounds[g + 1]):
            row = perf_matrix[r]
            for c in range(n):
                cols[c] += row[c]
        group_sums.append(cols)

    logits: List[float] = []
    all_groups = range(s)
    for is_groups in combinations(all_groups, s // 2):
        is_set = set(is_groups)
        is_perf = [sum(group_sums[g][c] for g in is_set) for c in range(n)]
        oos_perf = [sum(group_sums[g][c] for g in all_groups if g not in is_set) for c in range(n)]
        best = max(range(n), key=lambda c: is_perf[c])
        # OOS relative rank of the IS-best config (1 = best), as omega in (0,1).
        worse = sum(1 for c in range(n) if oos_perf[c] < oos_perf[best])
        omega = (worse + 1) / (n + 1)
        omega = min(max(omega, 1e-9), 1.0 - 1e-9)
        logits.append(math.log(omega / (1.0 - omega)))

    return sum(1 for v in logits if v <= 0.0) / len(logits)


def sr_variance_across_configs(config_returns: List[Sequence[float]]) -> float:
    """Variance of the per-config Sharpe ratios — the `sr_variance` input to
    expected_max_sharpe / DSR when configs share the same observation count."""
    srs = [sharpe_ratio(r) for r in config_returns if len(r) > 1]
    if len(srs) < 2:
        return 0.0
    m = sum(srs) / len(srs)
    return sum((x - m) ** 2 for x in srs) / (len(srs) - 1)
