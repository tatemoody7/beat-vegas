"""Deep-dive a single factor or combination before trusting it.

A high pooled ROI can hide a fragile signal: all the edge in one era, decayed to
nothing recently, or an artifact of the exact proxy line. inspect_combo runs the
same walk-forward selection as the ranking, then breaks the top-fraction picks
down by season, era, and game segment, stress-tests the proxy line, and reports
which direction each factor leans — so a human can judge whether it's real.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from ..backtest.engine import _roi
from .evaluate import _screen_model

_SEG_COLS = ["era_post2023", "wx_dome", "conference_game", "neutral_site"]


def _oof_preds(
    df: pd.DataFrame, cols: List[str], first_test_season: int = 2018, min_train: int = 500
) -> Optional[pd.DataFrame]:
    keep = (
        ["id", "season", "week", "under", "proxy_line", "first_half_total", "full_game_total"]
        + _SEG_COLS
        + cols
    )
    sub = df.dropna(subset=cols + ["under"])  # played games only
    preds = []
    for ts in sorted(s for s in sub["season"].unique() if s >= first_test_season):
        train = sub[sub["season"] < ts]
        test = sub[sub["season"] == ts]
        if len(train) < min_train or test.empty or train["under"].nunique() < 2:
            continue
        m = _screen_model()
        m.fit(train[cols], train["under"])
        t = test[[c for c in keep if c in test.columns]].copy()
        t["prob"] = m.predict_proba(test[cols])[:, 1]
        preds.append(t)
    return pd.concat(preds, ignore_index=True) if preds else None


def _top(pg: pd.DataFrame, top_frac: float) -> pd.DataFrame:
    """Top-fraction picks per season, keeping all columns (incl. season)."""
    parts = []
    for _, g in pg.groupby("season"):
        g = g.sort_values("prob", ascending=False)
        parts.append(g.head(max(1, int(len(g) * top_frac))))
    return pd.concat(parts, ignore_index=True)


def _summ(g: pd.DataFrame) -> Dict:
    return {
        "n": int(len(g)),
        "under_pct": round(100 * g["under"].mean(), 1),
        "roi": round(_roi(int(g["under"].sum()), len(g)), 4),
    }


def inspect_combo(
    df: pd.DataFrame, cols: List[str], top_frac: float = 0.20, first_test_season: int = 2018
) -> Dict:
    pg = _oof_preds(df, cols, first_test_season)
    if pg is None or pg.empty:
        return {"error": "no out-of-sample rows", "factors": cols}
    sel = _top(pg, top_frac)

    by_season = [{"season": int(s), **_summ(g)} for s, g in sel.groupby("season")]
    era = {
        "pre2023 (<=2022)": _summ(sel[sel["season"] <= 2022]),
        "post2023 (>=2023)": _summ(sel[sel["season"] >= 2023]),
    }
    recent = {"2023-2025": _summ(sel[sel["season"] >= 2023])}

    segs = {}
    for c in _SEG_COLS:
        if c in sel.columns and sel[c].notna().any():
            segs[c] = {str(int(v)) if pd.notna(v) else "na": _summ(g) for v, g in sel.groupby(c)}

    # proxy-line stress: re-grade the SAME selected games at proxy +/- delta.
    stress = []
    for d in (-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0):
        s = sel.copy()
        s["_line"] = s["proxy_line"] + d
        s = s[s["first_half_total"] != s["_line"]]
        hit = (s["first_half_total"] < s["_line"]).astype(int)
        stress.append(
            {
                "delta": d,
                "n": int(len(s)),
                "under_pct": round(100 * hit.mean(), 1),
                "roi": round(_roi(int(hit.sum()), len(s)), 4),
            }
        )

    # direction: mean factor value in the selected picks vs the whole OOS pool.
    direction = {}
    for c in cols:
        if c in pg.columns:
            direction[c] = {
                "selected_mean": round(float(sel[c].mean()), 3),
                "pool_mean": round(float(pg[c].mean()), 3),
            }

    return {
        "factors": cols,
        "top_frac": top_frac,
        "overall": _summ(sel),
        "by_season": by_season,
        "by_era": era,
        "recent": recent,
        "by_segment": segs,
        "proxy_stress": stress,
        "direction": direction,
    }
