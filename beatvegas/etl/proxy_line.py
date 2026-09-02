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
from ..db.models import Game
from ..db.store import session_scope
from .fbs import filter_fbs_games, load_fbs_teams

# Central estimate when we have no spread / no fitted curve. The research band for
# the CFB 1H share is ~0.50-0.53 (clamp wider to absorb extreme favorites).
DEFAULT_SHARE = 0.52
SHARE_CLAMP = (0.48, 0.56)
# Fitted spread->share coefficients live in a derived artifact written ONLY when
# scripts/derive_multiplier.py proves it beats the flat 0.52 by a meaningful
# walk-forward-MAE margin. Absent file => flat 0.52 (no behavior change). Unlike
# the rest of data/, multiplier.json IS git-tracked — committing it is how the
# fitted curve reaches the cloud jobs.
_COEFFS_PATH = REPO_ROOT / "data" / "multiplier.json"


def load_games_frame(seasons: Optional[range] = None, fbs_only: bool = True) -> pd.DataFrame:
    """Games that have BOTH a realized 1H total and a full-game total. `fbs_only`
    (default) keeps FBS-vs-FBS games only — lower-division games run a higher 1H
    share and would bias the fitted proxy (see etl/fbs.py)."""
    df = _query_games_frame(seasons)
    if fbs_only:
        df = filter_fbs_games(df, load_fbs_teams())
    return df


def _query_games_frame(seasons: Optional[range] = None) -> pd.DataFrame:
    with session_scope() as s:
        q = s.query(
            Game.id,
            Game.season,
            Game.week,
            Game.home_team,
            Game.away_team,
            Game.first_half_total,
            Game.full_game_total,
            Game.home_points,
            Game.away_points,
            Game.neutral_site,
            Game.spread,
        ).filter(
            Game.first_half_total.isnot(None),
            Game.full_game_total.isnot(None),
            Game.full_game_total > 0,
        )
        if seasons is not None:
            q = q.filter(Game.season.in_(list(seasons)))
        df = pd.DataFrame(
            q.all(),
            columns=[
                "id",
                "season",
                "week",
                "home_team",
                "away_team",
                "first_half_total",
                "full_game_total",
                "home_points",
                "away_points",
                "neutral_site",
                "spread",
            ],
        )
    df["full_game_actual"] = df["home_points"] + df["away_points"]
    df["fh_ratio"] = df["first_half_total"] / df["full_game_total"]
    return df


@lru_cache(maxsize=1)
def _load_share_coeffs() -> Optional[Dict[str, float]]:
    """Fitted {'a','b'} for share = a + b*|spread|, or None if unfit (-> flat)."""
    try:
        d = json.loads(_COEFFS_PATH.read_text())
        if d.get("kind") == "step":
            return {
                "kind": "step",
                "base": float(d["base"]),
                "blowout": float(d["blowout"]),
                "cut": float(d["cut"]),
            }
        if "a" in d and "b" in d:
            return {"a": float(d["a"]), "b": float(d["b"])}
    except (OSError, ValueError, TypeError):
        pass
    return None


def fh_share(spread: Optional[float] = None, coeffs: Optional[Dict[str, float]] = None) -> float:
    """Fraction of the full-game total expected in the 1H, as a function of the
    spread magnitude (favorites score relatively more early). Falls back to the
    flat DEFAULT_SHARE when no spread or no fitted curve is available."""
    if coeffs is None:
        coeffs = _load_share_coeffs()
    if coeffs is None:
        return DEFAULT_SHARE
    no_spread = spread is None or pd.isna(spread)
    if coeffs.get("kind") == "step":
        # Piecewise share: a flat base below the blowout cut, a higher share at or
        # above it (FBS-only 2023-25: ~0.51 below 21, ~0.54 at 21+). With no
        # spread the fitted base is the best guess, not the legacy flat.
        share = coeffs["base"]
        if not no_spread and abs(float(spread)) >= coeffs["cut"]:
            share = coeffs["blowout"]
        return min(max(share, SHARE_CLAMP[0]), SHARE_CLAMP[1])
    if no_spread:
        return DEFAULT_SHARE
    share = coeffs["a"] + coeffs["b"] * abs(float(spread))
    return min(max(share, SHARE_CLAMP[0]), SHARE_CLAMP[1])


def proxy_total(
    full_game_total: float,
    spread: Optional[float] = None,
    ratio: Optional[float] = None,
    coeffs: Optional[Dict[str, float]] = None,
) -> float:
    """The synthetic 1H line we grade against (rounded to the nearest half-point,
    matching how books post totals).

    `ratio` forces a fixed fraction (back-compat / tests). Otherwise the fraction
    is the spread-aware `fh_share(spread)` — flat 0.52 when spread/curve absent."""
    r = ratio if ratio is not None else fh_share(spread, coeffs)
    return round(full_game_total * r * 2) / 2


def fit_share(
    full_total: np.ndarray, spread: np.ndarray, first_half_total: np.ndarray
) -> Dict[str, float]:
    """Least-squares fit of realized 1H share ~ a + b*|spread|. Pure / testable."""
    share = np.asarray(first_half_total, float) / np.asarray(full_total, float)
    x = np.abs(np.asarray(spread, float))
    b, a = np.polyfit(x, share, 1)
    return {"a": float(a), "b": float(b)}


SHARE_GRID = np.round(np.arange(SHARE_CLAMP[0], SHARE_CLAMP[1] + 1e-9, 0.0025), 4)


def _mae_optimal_share(full_total: np.ndarray, first_half_total: np.ndarray) -> float:
    """The constant share whose proxy line (share x total, unrounded) minimises
    MAE vs realized 1H points — i.e. the median-type fair line a book would post,
    not the mean ratio, which right-skew (blowouts) pulls upward. Rounding to the
    half-point happens at prediction time; optimising the rounded line would tie
    across neighbouring shares."""
    best, best_mae = DEFAULT_SHARE, np.inf
    for sh in SHARE_GRID:
        line = full_total * sh
        mae = float(np.mean(np.abs(line - first_half_total)))
        if mae < best_mae - 1e-12:
            best, best_mae = float(sh), mae
    return best


def fit_share_step(
    full_total: np.ndarray,
    spread: np.ndarray,
    first_half_total: np.ndarray,
    cut: float = 21.0,
) -> Dict[str, float]:
    """Piecewise share: MAE-optimal constant below `cut` (|spread|) and at/above it."""
    full = np.asarray(full_total, float)
    fh = np.asarray(first_half_total, float)
    big = np.abs(np.asarray(spread, float)) >= cut
    base = _mae_optimal_share(full[~big], fh[~big]) if (~big).any() else DEFAULT_SHARE
    blow = _mae_optimal_share(full[big], fh[big]) if big.any() else base
    return {"kind": "step", "base": base, "blowout": blow, "cut": float(cut)}
