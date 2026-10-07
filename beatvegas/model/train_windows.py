"""H-HIST arms (docs/HYPOTHESES.md, registered 2026-10-06 before any script):
the champion's regressor, unchanged, trained on played prior seasons from a
floor year instead of from `FRAME_MIN_SEASON`. Each scorer has the harness's
`Candidate` contract (`fn(train, target) -> np.ndarray`); the harness hands it
every played prior season the study frame holds (built with `min_season=None,
require_total=False`), and the scorer keeps only seasons >= its floor.

`champion_2023` is the incumbent as live trains it (`harness.incumbent_arm`
pins the same floor when the frame reaches below it). Nothing live imports
this module.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..etl.features import FRAME_MIN_SEASON
from .bv_line import bv_line_for_slate


def _from(floor: int, drop_all_nan: bool = True):
    def scorer(train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
        # drop_all_nan: a fold trained on early seasons has inputs CFBD never
        # carried for them (talent before 2015); see fit_bv_regressor.
        return bv_line_for_slate(
            train[train["season"] >= int(floor)], target, drop_all_nan=drop_all_nan
        )

    scorer.__name__ = f"bv_line_from_{floor}"
    scorer.floor = int(floor)  # type: ignore[attr-defined]
    return scorer


bv_line_from_2003 = _from(2003)
bv_line_from_2010 = _from(2010)
bv_line_from_2015 = _from(2015)
# The incumbent exactly as live fits it: no column drop (live never sees an
# all-NaN column on 2023+, or the Sunday refit would crash).
champion_2023 = _from(FRAME_MIN_SEASON, drop_all_nan=False)
