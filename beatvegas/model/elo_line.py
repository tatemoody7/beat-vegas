"""H-ELO-F arm (docs/HYPOTHESES.md, registered 2026-10-06 before any script):
the champion as pinned (training seasons >= FRAME_MIN_SEASON) plus CFBD's
pregame Elo for each side as two extra inputs. Same HGB, same walk-forward
global intercept (`bv_line_for_slate(feature_cols=...)`). Pregame Elo is set
before kickoff, so it is leak-free as of the game. `FEATURE_COLS` is
unchanged; nothing live imports this module.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..etl.features import FRAME_MIN_SEASON
from .bv_line import BV_FEATURE_COLS, bv_line_for_slate

ELO_COLS = ("home_pregame_elo", "away_pregame_elo")
ELO_FEATURE_COLS = tuple(BV_FEATURE_COLS) + ELO_COLS


def _with_elo(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ELO_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(float) if c in out else np.nan
    return out


def bv_line_with_elo(train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
    train = _with_elo(train[train["season"] >= FRAME_MIN_SEASON])
    return bv_line_for_slate(train, _with_elo(target), feature_cols=list(ELO_FEATURE_COLS))
