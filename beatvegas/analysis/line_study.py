"""Line Study — rank how often the 1H under cashed, bucketed by OPENING line.

Per game we use the real consensus opening 1H line when snapshots exist, and
fall back to the proxy line (0.52 x full-game total) for seasons with no captured
lines. So the same tool serves historical (proxy, labeled) and live (real) data,
auto-upgrading as real lines accrue.

Caveat: on proxy data the cross-line ranking partly reflects game-total level
rather than a standalone tradeable signal — surfaced wherever this is displayed.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from ..db.models import Game, OddsSnapshot
from ..db.store import session_scope
from ..etl.proxy_line import load_games_frame, proxy_total
from ..lines import consensus_open_close

BREAKEVEN_PCT = 52.4          # win% to beat standard -110 juice


def _round_half(x: float) -> float:
    return round(x * 2) / 2


def assign_opening_line(games_df: pd.DataFrame,
                        snapshots_df: pd.DataFrame) -> pd.DataFrame:
    """Add `line` (opening, rounded to 0.5) and `line_source` to each game.

    `snapshots_df`: columns game_id, book, line, captured_at (may be empty).
    Real consensus opening preferred per game; proxy(0.52*full) otherwise."""
    df = games_df.copy()
    open_by_game = {}
    if snapshots_df is not None and not snapshots_df.empty:
        for gid, grp in snapshots_df.groupby("game_id"):
            snaps = list(grp.itertuples(index=False))
            opening, _close = consensus_open_close(snaps)
            if opening is not None:
                open_by_game[gid] = opening

    def _line(row):
        real = open_by_game.get(row["id"])
        if real is not None:
            return pd.Series([_round_half(real), "real_open"])
        return pd.Series([_round_half(proxy_total(row["full_game_total"],
                                                  spread=row.get("spread"))),
                          "proxy"])

    df[["line", "line_source"]] = df.apply(_line, axis=1)
    return df


def bucket_under_rates(games_df: pd.DataFrame, min_games: int = 15) -> pd.DataFrame:
    """Group games by opening `line` and compute the under hit-rate per bucket.

    Expects columns: line, line_source, first_half_total. Pure / testable."""
    df = games_df.copy()
    df["under"] = df["first_half_total"] < df["line"]
    df["push"] = df["first_half_total"] == df["line"]

    def _agg(x: pd.DataFrame) -> pd.Series:
        decided = len(x) - int(x["push"].sum())
        under = int(x["under"].sum())
        src = x["line_source"].mode()
        return pd.Series({
            "games": len(x),
            "under": under,
            "push": int(x["push"].sum()),
            "under_pct": round(100 * under / decided, 1) if decided else 0.0,
            "line_source": src.iloc[0] if len(src) else "proxy",
        })

    out = (df.groupby("line").apply(_agg, include_groups=False).reset_index())
    out = out[out["games"] >= min_games]
    return out.sort_values("under_pct", ascending=False).reset_index(drop=True)


def line_study(season: int, min_games: int = 15) -> pd.DataFrame:
    """DB wrapper: load season games + snapshots, assign opening line, rank."""
    games = load_games_frame(seasons=range(season, season + 1))
    with session_scope() as s:
        rows = (s.query(OddsSnapshot.game_id, OddsSnapshot.book,
                        OddsSnapshot.line, OddsSnapshot.captured_at)
                .join(Game, Game.id == OddsSnapshot.game_id)
                .filter(Game.season == season,
                        OddsSnapshot.market == "1H_total").all())
    snaps = pd.DataFrame(rows, columns=["game_id", "book", "line", "captured_at"])
    return bucket_under_rates(assign_opening_line(games, snaps), min_games)
