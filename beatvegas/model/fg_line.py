"""The champion's regressor fitted to the FULL-GAME total (H-FG-U-R / H-FG-O-R,
docs/HYPOTHESES.md). Live since 2026-10-06 ONLY as the H-FG-P shadow
(`scripts/fg_shadow.py` -> predictions `bv_fg_v1`, read by nothing but the paper
collector `beatvegas/fg_paper.py`); never the champion, never real money.

`bv_fg_line_for_slate` has the `Candidate` contract of the harness
(`bv_line_for_slate(train, target) -> np.ndarray`) and is the incumbent arm of
a `--market fg` run (`harness.incumbent_arm(FULL_GAME)`). Same 58 market-blind
inputs, same HGB, same walk-forward intercept — only the target changes to
`home_points + away_points`. The frame's `full_game_total` column is the
market's number and stays out of the fit (`etl.features.MARKET_COLS`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..markets import FG_ACTUAL_COL, FULL_GAME, with_target
from .bv_line import bv_line_for_slate


def bv_fg_line_for_slate(
    train_df: pd.DataFrame, target_df: pd.DataFrame, drop_all_nan: bool = False
) -> np.ndarray:
    """Fit on `train_df` (rows with a final score), predict `target_df`, return
    calibrated full-game lines. `drop_all_nan`: see bv_line.fit_bv_regressor
    (the shadow trains like the champion, on 2003+, since 2026-10-07)."""
    train = with_target(train_df, FULL_GAME)
    target = with_target(target_df, FULL_GAME)
    return bv_line_for_slate(train, target, target=FG_ACTUAL_COL, drop_all_nan=drop_all_nan)
