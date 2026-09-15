"""Small, shared inference helpers for the study scripts.

Before 2026-09-15 every study carried its own inline bootstrap (censoring,
two_sided, weather_style) and none shared a multiple-comparisons step. These are
the two pieces the pre-registered rules in docs/HYPOTHESES.md keep asking for:
a paired bootstrap on a mean (a difference paired on the game, or a single
series against zero) and Holm's step-down correction across a family.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np


def paired_bootstrap_mean(
    a: Sequence[float],
    b: Optional[Sequence[float]] = None,
    n_boot: int = 2000,
    seed: int = 7,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Percentile bootstrap CI for mean(a - b), paired on the index; with `b`
    None, for mean(a) against zero. Returns n, mean, lo, hi, excludes_zero and a
    two-sided bootstrap p-value for mean == 0 (the share of resamples on the
    other side of zero, doubled, floored at 1/n_boot)."""
    x = np.asarray(a, float)
    if b is not None:
        y = np.asarray(b, float)
        if len(y) != len(x):
            raise ValueError("paired series must have equal length")
        x = x - y
    x = x[~np.isnan(x)]
    n = int(len(x))
    if n == 0:
        return {
            "n": 0,
            "mean": None,
            "lo": None,
            "hi": None,
            "p": None,
            "n_boot": int(n_boot),
            "excludes_zero": False,
        }
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, (n_boot, n))
    boots = x[idx].mean(axis=1)
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    mean = float(x.mean())
    other = float(np.mean(boots <= 0) if mean > 0 else np.mean(boots >= 0))
    p = min(1.0, max(2 * other, 1.0 / n_boot))
    return {
        "n": n,
        "mean": mean,
        "lo": float(lo),
        "hi": float(hi),
        "p": float(p),
        "n_boot": int(n_boot),
        "excludes_zero": bool(lo > 0 or hi < 0),
    }


def holm_adjust(pvalues: Sequence[Optional[float]]) -> List[Optional[float]]:
    """Holm step-down adjusted p-values (monotone, capped at 1). None stays None
    and does not count toward the family size."""
    idx = [i for i, p in enumerate(pvalues) if p is not None]
    out: List[Optional[float]] = [None] * len(pvalues)
    if not idx:
        return out
    m = len(idx)
    order = sorted(idx, key=lambda i: pvalues[i])
    running = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * float(pvalues[i]))
        running = max(running, adj)
        out[i] = running
    return out


def holm_reject(pvalues: Sequence[Optional[float]], alpha: float = 0.05) -> List[bool]:
    """Which members of the family are rejected at family-wise level alpha."""
    return [p is not None and p <= alpha for p in holm_adjust(pvalues)]
