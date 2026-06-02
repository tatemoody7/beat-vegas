"""Calibrate the proxy first-half total from the full-game total.

We have real first-half points (CFBD) and real full-game totals, but NO historical
1H betting line. The realized ratio (actual 1H total / full-game total) tells us
where a *fair* 1H line sits. Books typically price 1H totals around 0.50-0.52 of
the full game; if the realized ratio is meaningfully below that, 1H unders carry
systematic value. This module quantifies that ratio and fits a simple model.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..db.store import session_scope
from ..db.models import Game


def load_games_frame(seasons: Optional[range] = None) -> pd.DataFrame:
    """Games that have BOTH a realized 1H total and a full-game total."""
    with session_scope() as s:
        q = s.query(
            Game.id, Game.season, Game.week, Game.home_team, Game.away_team,
            Game.first_half_total, Game.full_game_total, Game.home_points,
            Game.away_points, Game.neutral_site,
        ).filter(
            Game.first_half_total.isnot(None),
            Game.full_game_total.isnot(None),
            Game.full_game_total > 0,
        )
        if seasons is not None:
            q = q.filter(Game.season.in_(list(seasons)))
        df = pd.DataFrame(q.all(), columns=[
            "id", "season", "week", "home_team", "away_team", "first_half_total",
            "full_game_total", "home_points", "away_points", "neutral_site",
        ])
    df["full_game_actual"] = df["home_points"] + df["away_points"]
    df["fh_ratio"] = df["first_half_total"] / df["full_game_total"]
    return df


def calibrate(df: pd.DataFrame) -> Dict[str, float]:
    """Summary stats for the realized 1H/full ratio + a fitted ratio."""
    r = df["fh_ratio"].to_numpy()
    return {
        "n": int(len(df)),
        "ratio_mean": float(np.mean(r)),
        "ratio_median": float(np.median(r)),
        "ratio_std": float(np.std(r)),
        # OLS through fit: 1H_total ~ a + b * full_total
        **_ols(df["full_game_total"].to_numpy(), df["first_half_total"].to_numpy()),
    }


def _ols(x: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    b, a = np.polyfit(x, y, 1)
    return {"ols_intercept": float(a), "ols_slope": float(b)}


def proxy_total(full_game_total: float, ratio: float = 0.52) -> float:
    """The synthetic 1H line we grade against (rounded to the nearest half-point,
    matching how books post totals)."""
    return round(full_game_total * ratio * 2) / 2
