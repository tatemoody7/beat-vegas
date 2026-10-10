"""H-MODEL-FIX (docs/HYPOTHESES.md, Tate 2026-10-10): the frozen criterion and
the two arms' frame builds, read by scripts/model_fix_study.py.

The incumbent is the live champion as the 2026-10-11 refit trains it: 2003+,
bowls in, week-ordered season-to-date means, no seed, and sklearn's
`early_stopping='auto'`. The candidate is the same model with the four fixes:
bowls out and date-ordered means, a 2015 floor (the frame read from 2014 for
the seed), `PRIOR_SEASON_WEIGHT` = 3, early stopping off.

NOT MET on 2026-10-10 (`study.yml` run 38070611660, docs/MODEL_FIX.md): the
candidate was less accurate, and the live model stayed. Both arms pin every
setting here rather than reading the live defaults, so the study reproduces
whatever the live model later becomes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union
from unittest import mock

import pandas as pd

from ..etl.features import CFBD_TOTALS_FROM, build_feature_frame, training_frame
from ..model import bv_line

ROW_ID = "H-MODEL-FIX"
CANDIDATE_NAME = "model_fix"
# Frozen with the row: the candidate passes when the pooled paired change in
# absolute error (candidate minus incumbent) has a 95% upper bound at or under
# this many points -- "not worse".
NON_INFERIORITY_MARGIN = 0.10

INCUMBENT_FLOOR = 2003
INCUMBENT_PRIOR_WEIGHT = 0.0
INCUMBENT_EARLY_STOPPING: Union[str, bool] = "auto"
CANDIDATE_FLOOR = 2015
CANDIDATE_PRIOR_WEIGHT = 3.0
CANDIDATE_EARLY_STOPPING: Union[str, bool] = False


def incumbent_frame() -> pd.DataFrame:
    """The live champion's frame (bowls in, week-ordered, no seed)."""
    return build_feature_frame(
        min_games=0,
        min_season=INCUMBENT_FLOOR,
        total_required_from=CFBD_TOTALS_FROM,
        prior_weight=INCUMBENT_PRIOR_WEIGHT,
        model_fix_candidate=False,
    )


def candidate_frame() -> pd.DataFrame:
    """The candidate's frame (bowls out, date-ordered, seeded from 2014)."""
    return build_feature_frame(
        min_games=0,
        min_season=CANDIDATE_FLOOR,
        total_required_from=CFBD_TOTALS_FROM,
        prior_weight=CANDIDATE_PRIOR_WEIGHT,
        model_fix_candidate=True,
    )


def incumbent_scorer(legacy: pd.DataFrame):
    """A harness scorer for the live champion. The harness hands it the
    CANDIDATE frame's rows; it scores the same game ids from the incumbent's
    frame, trained on that frame's seasons before the target's, as live does
    (`score_slate`: training_frame of the earlier seasons, drop_all_nan)."""
    played = training_frame(legacy)
    by_id = legacy.drop_duplicates("id").set_index("id")

    def score(train: pd.DataFrame, target: pd.DataFrame):
        season = int(target["season"].iloc[0])
        ids = target["id"].astype(int).tolist()
        missing = [g for g in ids if g not in by_id.index]
        if missing:
            raise ValueError(f"{len(missing)} target game(s) missing from the incumbent's frame")
        tr = played[played["season"] < season]
        tg = by_id.loc[ids].reset_index()
        with mock.patch.object(bv_line, "EARLY_STOPPING", INCUMBENT_EARLY_STOPPING):
            return bv_line.bv_line_for_slate(tr, tg, drop_all_nan=True)

    return score


def candidate_scorer(train: pd.DataFrame, target: pd.DataFrame):
    """The candidate: the candidate frame's own rows, early stopping off."""
    with mock.patch.object(bv_line, "EARLY_STOPPING", CANDIDATE_EARLY_STOPPING):
        return bv_line.bv_line_for_slate(train, target, drop_all_nan=True)


def criterion(report: Dict[str, Any]) -> Optional[bool]:
    """PASS (True) when the pooled paired |error| change's 95% upper bound is at
    or under NON_INFERIORITY_MARGIN; None when the comparison was not computed."""
    pair = (report.get("comparisons") or {}).get("pairs", {}).get(CANDIDATE_NAME) or {}
    hi = (pair.get("abs_err") or {}).get("hi")
    if hi is None:
        return None
    return bool(float(hi) <= NON_INFERIORITY_MARGIN)
