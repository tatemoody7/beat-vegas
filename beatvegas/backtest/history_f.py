"""Criteria for H-HIST and H-ELO-F (docs/HYPOTHESES.md, registered 2026-10-06
before any script; H-HIST amended the same day before any look).

Both reuse the H-WEPA-F per-arm test (`wepa_f.arm_passes`): paired per-game
absolute error against the incumbent lower (mean < 0, bootstrap interval
excluding zero, Holm-adjusted p < 0.05 across the row's arms) AND close-graded
portfolio units not lower (interval not entirely below zero). A row passes when
any of its declared arms passes; the per-arm answers are in the report.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from .wepa_f import arm_passes

HIST_ARMS = ("hist_2003", "hist_2010", "hist_2015")
ELO_ARMS = ("elo_2023",)


def _row(report: Dict[str, Any], arms: Sequence[str]) -> Optional[bool]:
    comp = report.get("comparisons") or {}
    pairs = comp.get("pairs") or {}
    holm = (comp.get("holm") or {}).get("abs_err") or {}
    answers = []
    for arm in arms:
        if arm not in pairs:
            return None
        answers.append(arm_passes(pairs[arm], holm.get(arm)))
    if any(a is None for a in answers):
        return None
    return any(answers)


def criterion_hist(report: Dict[str, Any]) -> Optional[bool]:
    """H-HIST: True when any training-floor arm passes, False when all three are
    present and none does, None when an arm or a needed number is missing."""
    return _row(report, HIST_ARMS)


def criterion_elo(report: Dict[str, Any]) -> Optional[bool]:
    """H-ELO-F: the single Elo arm."""
    return _row(report, ELO_ARMS)
