"""H-WEPA-F, ARM R: the retrospective residual test of dated in-season WEPA
(docs/HYPOTHESES.md).

Candidates for `scripts/harness_report.py` (`--candidate
beatvegas.backtest.wepa_f:candidate_epa1`, `:candidate_k4`; `--criterion
beatvegas.backtest.wepa_f:criterion`). Each candidate is the champion's own
line (`model.bv_line.bv_line_for_slate`, trained on seasons < target exactly as
the harness's incumbent) plus a ridge correction learned WALK-FORWARD WITHIN
THE TARGET SEASON from the derived z-table `data/wepa_2025_weekly_z.csv`
(scripts/wepa_weekly_extract.py: the 48 opponent-adjusted columns of the
Patreon weekly files z-scored within each weekly file).

For target week k the correction is fitted only on target rows with week < k,
a WEPA row and a trusted actual: residual (actual - champion) on the
composites. So week 5 (no earlier in-season row), weeks 1-4 and games absent
from the files carry correction 0, i.e. the champion's line unchanged. A row
whose week-k prediction read an actual from week >= k would be a leak; the
tests pin that it cannot.

Composites, each oriented so + means more scoring: for a metric m,
    z(home m) + z(away m) + z(home m allowed) + z(away m allowed).
`wepa_epa1` uses the adjusted-EPA composite alone (one slope); `wepa_k4` uses
EPA, success, explosiveness and line yards (four slopes). Ridge alpha 1.0,
free intercept, sklearn's `Ridge`. Nothing here is a gate, a constant or a
rule: the harness grades the outputs, the registered criterion reads its
report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from beatvegas.model.bv_line import bv_line_for_slate

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "wepa_2025_weekly_z.csv"

COMPOSITE_METRICS: Sequence[str] = ("epa", "success", "explosiveness", "line_yards")
EPA1_COLS: Sequence[str] = ("epa",)
K4_COLS: Sequence[str] = tuple(COMPOSITE_METRICS)
ARM_NAMES: Sequence[str] = ("wepa_epa1", "wepa_k4")

RIDGE_ALPHA = 1.0
# A fit on fewer rows than this is not attempted (correction 0). Inert on the
# real files (every 2025 weekly file has 9-65 games, week 6 trains on 51); it
# only guards a malformed frame.
MIN_TRAIN_ROWS = 30
HOLM_ALPHA = 0.05

Champion = Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]


def load_wepa_z(path: Optional[Path] = None) -> pd.DataFrame:
    """The derived z-table, one row per game id."""
    df = pd.read_csv(path or DATA_PATH)
    if df["id"].duplicated().any():
        raise ValueError("wepa z-table: duplicate game id")
    df["id"] = df["id"].astype(int)
    return df


def composites(z: pd.DataFrame, metrics: Sequence[str] = COMPOSITE_METRICS) -> pd.DataFrame:
    """`id` plus one scoring-oriented composite per metric."""
    out = pd.DataFrame({"id": z["id"].astype(int).values})
    for m in metrics:
        cols = [
            f"z_home_adjusted_{m}",
            f"z_away_adjusted_{m}",
            f"z_home_adjusted_{m}_allowed",
            f"z_away_adjusted_{m}_allowed",
        ]
        missing = [c for c in cols if c not in z.columns]
        if missing:
            raise ValueError(f"wepa z-table lacks {missing}")
        out[m] = z[cols].astype(float).sum(axis=1).values
    return out


def walk_forward_correction(
    target: pd.DataFrame,
    champion_pred: np.ndarray,
    comp: pd.DataFrame,
    cols: Sequence[str],
    alpha: float = RIDGE_ALPHA,
    min_train: int = MIN_TRAIN_ROWS,
) -> np.ndarray:
    """Per target row, the ridge correction to add to the champion's line.

    Week k's correction is fitted on rows with week < k only (plus a WEPA row
    and a finite actual); rows without a WEPA row, or in a week with fewer than
    `min_train` eligible earlier rows, get 0.0. Returns floats in target order,
    always finite."""
    n = len(target)
    corr = np.zeros(n, dtype=float)
    if n == 0:
        return corr
    champ = np.asarray(champion_pred, dtype=float).reshape(-1)
    if len(champ) != n:
        raise ValueError(f"champion returned {len(champ)} predictions for {n} rows")
    ids = pd.to_numeric(target["id"], errors="coerce").astype("Int64").to_numpy()
    weeks = pd.to_numeric(target["week"], errors="coerce").to_numpy(dtype=float)
    actual = (
        pd.to_numeric(target["actual"], errors="coerce").to_numpy(dtype=float)
        if "actual" in target.columns
        else np.full(n, np.nan)
    )
    lookup = comp.set_index("id")[list(cols)]
    X = lookup.reindex(pd.Index(ids, dtype="Int64")).to_numpy(dtype=float)
    has = np.isfinite(X).all(axis=1) & np.isfinite(weeks)
    resid = actual - champ
    for k in sorted({float(w) for w in weeks[has]}):
        pred_mask = has & (weeks == k)
        train_mask = has & (weeks < k) & np.isfinite(resid)
        if int(train_mask.sum()) < min_train:
            continue
        model = Ridge(alpha=alpha, fit_intercept=True)
        model.fit(X[train_mask], resid[train_mask])
        corr[pred_mask] = model.predict(X[pred_mask])
    if not np.all(np.isfinite(corr)):
        raise ValueError("non-finite correction")
    return corr


def make_candidate(
    cols: Sequence[str],
    champion: Champion = bv_line_for_slate,
    wepa_path: Optional[Path] = None,
    name: Optional[str] = None,
) -> Champion:
    """A harness candidate: champion(train, target) + the walk-forward correction."""

    def candidate(train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
        champ = np.asarray(champion(train, target), dtype=float).reshape(-1)
        if len(target) == 0:
            return champ
        comp = composites(load_wepa_z(wepa_path), COMPOSITE_METRICS)
        return champ + walk_forward_correction(target, champ, comp, cols)

    candidate.__name__ = name or f"wepa_{'_'.join(cols)}"
    candidate.__qualname__ = candidate.__name__
    return candidate


def candidate_epa1(train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
    """Sub-arm `wepa_epa1`: one slope on the adjusted-EPA composite."""
    return make_candidate(EPA1_COLS, name="wepa_epa1")(train, target)


def candidate_k4(train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
    """Sub-arm `wepa_k4`: ridge on the EPA, success, explosiveness and line-yards composites."""
    return make_candidate(K4_COLS, name="wepa_k4")(train, target)


def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def arm_passes(pair: Dict[str, Any], holm_p: Any) -> Optional[bool]:
    """The registered ARM R test for one sub-arm, from the harness's
    `comparisons.pairs[arm]` block and its Holm-adjusted abs_err p: lower
    paired |error| (mean < 0, interval excluding zero, Holm p < 0.05) AND
    close-graded portfolio units not lower (interval not entirely below zero).
    None when a number the test needs is missing."""
    ae = pair.get("abs_err") or {}
    pu = pair.get("portfolio_units") or {}
    mean, excl, p, hi = (
        _num(ae.get("mean")),
        ae.get("excludes_zero"),
        _num(holm_p),
        _num(pu.get("hi")),
    )
    if mean is None or excl is None or p is None or hi is None:
        return None
    mae_better = mean < 0 and bool(excl) and p < HOLM_ALPHA
    units_not_worse = hi >= 0
    return bool(mae_better and units_not_worse)


def criterion(report: Dict[str, Any]) -> Optional[bool]:
    """H-WEPA-F ARM R: True when any declared sub-arm passes `arm_passes`,
    False when both are present and neither does, None when a sub-arm or a
    needed number is missing from the report."""
    comp = report.get("comparisons") or {}
    pairs = comp.get("pairs") or {}
    holm = (comp.get("holm") or {}).get("abs_err") or {}
    answers = []
    for arm in ARM_NAMES:
        if arm not in pairs:
            return None
        answers.append(arm_passes(pairs[arm], holm.get(arm)))
    if any(a is None for a in answers):
        return None
    return any(answers)
