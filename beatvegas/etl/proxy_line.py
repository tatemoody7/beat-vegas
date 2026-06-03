"""Calibrate the proxy first-half total from the full-game total.

We have real first-half points (CFBD) and real full-game totals, but NO historical
1H betting line. The realized ratio (actual 1H total / full-game total) tells us
where a *fair* 1H line sits. Books typically price 1H totals around 0.50-0.52 of
the full game; if the realized ratio is meaningfully below that, 1H unders carry
systematic value. This module quantifies that ratio and fits a simple model.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..config import REPO_ROOT
from ..db.store import session_scope
from ..db.models import Game

# Central estimate when we have no spread / no fitted curve. The research band for
# the CFB 1H share is ~0.50-0.53 (clamp wider to absorb extreme favorites).
DEFAULT_SHARE = 0.52
SHARE_CLAMP = (0.48, 0.56)
# Fitted spread->share coefficients live in a derived artifact written ONLY when
# scripts/derive_multiplier.py proves it beats the flat 0.52 (walk-forward MAE).
# Absent file => flat 0.52 (no behavior change). data/ is gitignored, like the DB.
_COEFFS_PATH = REPO_ROOT / "data" / "multiplier.json"


def load_games_frame(seasons: Optional[range] = None) -> pd.DataFrame:
    """Games that have BOTH a realized 1H total and a full-game total."""
    with session_scope() as s:
        q = s.query(
            Game.id, Game.season, Game.week, Game.home_team, Game.away_team,
            Game.first_half_total, Game.full_game_total, Game.home_points,
            Game.away_points, Game.neutral_site, Game.spread,
        ).filter(
            Game.first_half_total.isnot(None),
            Game.full_game_total.isnot(None),
            Game.full_game_total > 0,
        )
        if seasons is not None:
            q = q.filter(Game.season.in_(list(seasons)))
        df = pd.DataFrame(q.all(), columns=[
            "id", "season", "week", "home_team", "away_team", "first_half_total",
            "full_game_total", "home_points", "away_points", "neutral_site", "spread",
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


@lru_cache(maxsize=1)
def _load_share_coeffs() -> Optional[Dict[str, float]]:
    """Fitted {'a','b'} for share = a + b*|spread|, or None if unfit (-> flat)."""
    try:
        d = json.loads(_COEFFS_PATH.read_text())
        if "a" in d and "b" in d:
            return {"a": float(d["a"]), "b": float(d["b"])}
    except (OSError, ValueError, TypeError):
        pass
    return None


def fh_share(spread: Optional[float] = None,
             coeffs: Optional[Dict[str, float]] = None) -> float:
    """Fraction of the full-game total expected in the 1H, as a function of the
    spread magnitude (favorites score relatively more early). Falls back to the
    flat DEFAULT_SHARE when no spread or no fitted curve is available."""
    if coeffs is None:
        coeffs = _load_share_coeffs()
    if spread is None or pd.isna(spread) or coeffs is None:
        return DEFAULT_SHARE
    share = coeffs["a"] + coeffs["b"] * abs(float(spread))
    return min(max(share, SHARE_CLAMP[0]), SHARE_CLAMP[1])


def proxy_total(full_game_total: float, spread: Optional[float] = None,
                ratio: Optional[float] = None,
                coeffs: Optional[Dict[str, float]] = None) -> float:
    """The synthetic 1H line we grade against (rounded to the nearest half-point,
    matching how books post totals).

    `ratio` forces a fixed fraction (back-compat / tests). Otherwise the fraction
    is the spread-aware `fh_share(spread)` — flat 0.52 when spread/curve absent."""
    r = ratio if ratio is not None else fh_share(spread, coeffs)
    return round(full_game_total * r * 2) / 2


def fit_share(full_total: np.ndarray, spread: np.ndarray,
              first_half_total: np.ndarray) -> Dict[str, float]:
    """Least-squares fit of realized 1H share ~ a + b*|spread|. Pure / testable."""
    share = np.asarray(first_half_total, float) / np.asarray(full_total, float)
    x = np.abs(np.asarray(spread, float))
    b, a = np.polyfit(x, share, 1)
    return {"a": float(a), "b": float(b)}
