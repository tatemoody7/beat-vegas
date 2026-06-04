"""Factor-testing & ranking harness.

The centerpiece of the mispricing pivot: test every candidate signal (factor)
for its relationship to the 1H-under outcome, individually and in combination,
walk-forward and out-of-sample, then rank them. Overfitting guards (per-season
stability, sample size) are reported as diagnostics, not used as filters.
"""

from .evaluate import (  # noqa: F401
    evaluate_combos,
    evaluate_factor,
    permutation_importances,
    rank_factors,
)
from .registry import Factor, default_registry, evaluable_factors  # noqa: F401
