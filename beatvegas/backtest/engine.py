"""Walk-forward backtest of the 1H-under selection model.

For each test season we train only on prior seasons (no look-ahead), score the
test season, and ask the real question: do the games the model is most confident
are unders actually beat the -110 breakeven (52.4%)? If yes, predictive selection
signal exists. (Still graded vs the 0.52*full proxy line — directional until real
1H lines validate it.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from ..etl.features import FEATURE_COLS, build_feature_frame

BREAKEVEN = 0.524  # win% needed to beat standard -110 juice
WIN_PROFIT = 100 / 110  # units won on a winning -110 bet


def _roi(hits: int, n: int) -> float:
    if n == 0:
        return 0.0
    losses = n - hits
    return (hits * WIN_PROFIT - losses) / n


def _new_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_depth=3,
        max_iter=300,
        l2_regularization=1.0,
        min_samples_leaf=40,
        random_state=7,
    )


@dataclass
class BacktestResult:
    per_game: pd.DataFrame  # test-season predictions across all seasons
    by_season: pd.DataFrame
    summary: Dict[str, float]


def run_backtest(
    df: Optional[pd.DataFrame] = None, first_test_season: int = 2023, top_frac: float = 0.20
) -> BacktestResult:
    if df is None:
        df = build_feature_frame(min_games=2)
    seasons = sorted(df["season"].unique())
    test_seasons = [s for s in seasons if s >= first_test_season]

    preds = []
    for ts in test_seasons:
        train = df[df["season"] < ts]
        test = df[df["season"] == ts]
        if len(train) < 500 or test.empty:
            continue
        model = _new_model()
        model.fit(train[FEATURE_COLS], train["under"])
        p = model.predict_proba(test[FEATURE_COLS])[:, 1]
        t = test[
            [
                "id",
                "season",
                "week",
                "home_team",
                "away_team",
                "full_game_total",
                "proxy_line",
                "first_half_total",
                "under",
            ]
        ].copy()
        t["under_prob"] = p
        preds.append(t)

    per_game = pd.concat(preds, ignore_index=True)

    rows = []
    for ts, g in per_game.groupby("season"):
        g = g.sort_values("under_prob", ascending=False)
        k = max(1, int(len(g) * top_frac))
        top = g.head(k)
        rows.append(
            {
                "season": int(ts),
                "games": len(g),
                "all_under_pct": 100 * g["under"].mean(),
                f"top{int(top_frac * 100)}_under_pct": 100 * top["under"].mean(),
                f"top{int(top_frac * 100)}_roi": _roi(int(top["under"].sum()), len(top)),
                f"top{int(top_frac * 100)}_n": len(top),
            }
        )
    by_season = pd.DataFrame(rows)

    # Pooled top-fraction performance (rank within each season, then pool).
    pooled_top = per_game.groupby("season", group_keys=False).apply(
        lambda g: g.sort_values("under_prob", ascending=False).head(max(1, int(len(g) * top_frac))),
        include_groups=False,
    )
    summary = {
        "test_seasons": f"{test_seasons[0]}-{test_seasons[-1]}",
        "n_games": int(len(per_game)),
        "baseline_under_pct": round(100 * per_game["under"].mean(), 2),
        "top_n": int(len(pooled_top)),
        "top_under_pct": round(100 * pooled_top["under"].mean(), 2),
        "top_roi": round(_roi(int(pooled_top["under"].sum()), len(pooled_top)), 4),
        "breakeven_pct": round(100 * BREAKEVEN, 1),
    }
    return BacktestResult(per_game=per_game, by_season=by_season, summary=summary)


def stress_test_lines(
    per_game: pd.DataFrame, deltas: List[float], top_frac: float = 0.20
) -> pd.DataFrame:
    """Re-grade the top-fraction selections at proxy line +/- delta points to
    check the conclusion isn't an artifact of the exact proxy ratio."""
    rows = []
    for d in deltas:
        g = per_game.copy()
        g["line"] = g["proxy_line"] + d
        g = g[g["first_half_total"] != g["line"]]
        g["under_shifted"] = (g["first_half_total"] < g["line"]).astype(int)
        top = g.groupby("season", group_keys=False).apply(
            lambda x: x.sort_values("under_prob", ascending=False).head(
                max(1, int(len(x) * top_frac))
            ),
            include_groups=False,
        )
        rows.append(
            {
                "line_delta": d,
                "n": len(top),
                "top_under_pct": round(100 * top["under_shifted"].mean(), 2),
                "roi": round(_roi(int(top["under_shifted"].sum()), len(top)), 4),
            }
        )
    return pd.DataFrame(rows)
