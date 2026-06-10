#!/usr/bin/env python
"""Run the walk-forward 1H-under backtest and print the verdict."""

from __future__ import annotations

import warnings
from typing import Dict

from beatvegas.backtest.engine import run_backtest, stress_test_lines
from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.features import build_feature_frame
from beatvegas.lines import closing_before_kickoff

warnings.filterwarnings("ignore")


def real_1h_closing_lines() -> Dict[int, float]:
    """game_id -> real pre-kickoff 1H closing line from captured snapshots.

    Empty when the DB is unreachable or no 1H_total snapshots exist (most
    historical games) — the backtest then grades everything on the proxy."""
    if not try_init_db():
        return {}
    out: Dict[int, float] = {}
    with session_scope() as s:
        game_ids = [
            gid
            for (gid,) in s.query(OddsSnapshot.game_id)
            .filter(OddsSnapshot.market == "1H_total")
            .distinct()
        ]
        for gid in game_ids:
            g = s.query(Game.start_date).filter(Game.id == gid).one_or_none()
            snaps = (
                s.query(OddsSnapshot)
                .filter(OddsSnapshot.game_id == gid, OddsSnapshot.market == "1H_total")
                .all()
            )
            _open, closing, _at = closing_before_kickoff(snaps, g[0] if g else None)
            if closing is not None:
                out[gid] = closing
    return out


def main() -> None:
    df = build_feature_frame(min_games=2)
    real_lines = real_1h_closing_lines()
    for top_frac in (0.10, 0.20):
        res = run_backtest(df, top_frac=top_frac, real_lines=real_lines)
        print(f"\n===== TOP {int(top_frac * 100)}% MOST-CONFIDENT UNDERS =====")
        print("summary:", res.summary)
        print(res.by_season.round(2).to_string(index=False))
        if top_frac == 0.20:
            print("\nline stress test (top 20%):")
            print(
                stress_test_lines(res.per_game, [-1.5, -1.0, 0.0, 1.0, 1.5]).to_string(index=False)
            )


if __name__ == "__main__":
    main()
