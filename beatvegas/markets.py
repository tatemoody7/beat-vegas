"""The two totals markets the research harness can grade, as one frozen
descriptor each (2026-10-06, Track A of the deep program).

The champion is first-half only and every live path (`score_slate`, the card,
`verdict.ts`) stays first-half only this season: a `Market` threads through the
RESEARCH harness and the regressor's target keyword, nothing else. The default
everywhere is `FIRST_HALF`, so every existing caller is byte-identical.

A `Market` says four things: which frame column the regressor fits (`target`),
which `odds_snapshots.market` row carries the book line (`snapshot_market`),
how close to kickoff a snapshot must be to count as a REAL close
(`close_window_h`, `lines.REAL_*_CLOSE_WINDOW_H`), and the ledger label
(`results.market` / `challenger_picks.market`). `actuals()` is the one place a
market's realized total is read from a frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from .grading import trusted_first_half_total
from .lines import REAL_1H_CLOSE_WINDOW_H, REAL_FG_CLOSE_WINDOW_H

FG_ACTUAL_COL = "full_game_actual"


@dataclass(frozen=True)
class Market:
    key: str  # "1h" | "fg"
    target: str  # frame column the regressor fits
    snapshot_market: str  # odds_snapshots.market
    close_window_h: float  # a snapshot counts as the close only inside this many hours
    window_name: str  # the lines.py constant's name, for refusal messages and docs
    ledger_market: str  # results.market / challenger_picks.market
    label: str  # prose
    short: str  # the tag messages and tests use ("1H", "full-game")

    def describe(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "target": self.target,
            "snapshot_market": self.snapshot_market,
            "close_window_h": self.close_window_h,
            "ledger_market": self.ledger_market,
        }


FIRST_HALF = Market(
    key="1h",
    target="first_half_total",
    snapshot_market="1H_total",
    close_window_h=REAL_1H_CLOSE_WINDOW_H,
    window_name="REAL_1H_CLOSE_WINDOW_H",
    ledger_market="1H",
    label="first-half total",
    short="1H",
)
FULL_GAME = Market(
    key="fg",
    target=FG_ACTUAL_COL,
    snapshot_market="full_game_total",
    close_window_h=REAL_FG_CLOSE_WINDOW_H,
    window_name="REAL_FG_CLOSE_WINDOW_H",
    ledger_market="full",
    label="full-game total",
    short="full-game",
)
MARKETS: Tuple[Market, ...] = (FIRST_HALF, FULL_GAME)
SIDES: Tuple[str, ...] = ("under", "over")


def by_key(key: str) -> Market:
    for m in MARKETS:
        if m.key == key:
            return m
    raise ValueError(f"unknown market {key!r}; one of {[m.key for m in MARKETS]}")


def with_target(df: pd.DataFrame, market: Market) -> pd.DataFrame:
    """The frame with the market's target column present. First half: the frame
    already carries `first_half_total`. Full game: adds `full_game_actual` =
    `home_points + away_points` (NaN when either is missing). Never touches the
    market's LINE columns (`full_game_total` is a market/proxy column and stays
    out of every fit)."""
    if market.key == "fg" and FG_ACTUAL_COL not in df.columns:
        out = df.copy()
        hp = pd.to_numeric(out.get("home_points"), errors="coerce")
        ap = pd.to_numeric(out.get("away_points"), errors="coerce")
        out[FG_ACTUAL_COL] = (hp + ap).astype(float)
        return out
    return df


def actuals(df: pd.DataFrame, market: Market) -> pd.Series:
    """The realized total per row for `market`, NaN when the row cannot be
    graded. First half: `grading.trusted_first_half_total` (a 0-0 half is
    trusted only on evidence). Full game: `home_points + away_points`."""
    if market.key == "1h":
        src = (
            df["first_half_source"]
            if "first_half_source" in df
            else pd.Series(None, index=df.index)
        )
        hp = df["home_points"] if "home_points" in df else pd.Series(np.nan, index=df.index)
        ap = df["away_points"] if "away_points" in df else pd.Series(np.nan, index=df.index)
        out = []
        for fh, h, a, s in zip(df["first_half_total"], hp, ap, src):
            fh_v = None if pd.isna(fh) else float(fh)
            v = trusted_first_half_total(
                fh_v,
                None if pd.isna(h) else float(h),
                None if pd.isna(a) else float(a),
                None if (s is None or (isinstance(s, float) and math.isnan(s))) else s,
            )
            out.append(np.nan if v is None else float(v))
        return pd.Series(out, index=df.index, dtype=float)
    if market.key == "fg":
        hp = pd.to_numeric(df["home_points"], errors="coerce") if "home_points" in df else None
        ap = pd.to_numeric(df["away_points"], errors="coerce") if "away_points" in df else None
        if hp is None or ap is None:
            return pd.Series(np.nan, index=df.index, dtype=float)
        return (hp + ap).astype(float)
    raise ValueError(f"unknown market {market.key!r}")
