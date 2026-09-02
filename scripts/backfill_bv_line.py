#!/usr/bin/env python
"""Backfill the calibrated BV line onto historical predictions.

Re-runs walk-forward scoring per past season (train on prior seasons, score the
whole season) and re-stores predictions so `bv_line` / `bv_gap` are populated for
already-played games. This is the prerequisite for the gap-vs-CLV tracker, which
joins historical `bv_line` to graded `results`. Uses cached DB features only —
no extra API calls. Real opening-consensus lines are used as `line_used` where
1H snapshots exist, proxy (0.52*full) otherwise — matching weekly_update.py.

    python scripts/backfill_bv_line.py                 # 2018..latest
    python scripts/backfill_bv_line.py --start-season 2021
"""

from __future__ import annotations

import argparse
from typing import Dict

from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import init_db, session_scope
from beatvegas.etl.features import build_feature_frame, training_frame
from beatvegas.lines import consensus_open_close
from beatvegas.model.score import score_slate, store_predictions


def season_opening_lines(season: int) -> Dict[int, float]:
    """Opening-consensus 1H line per game for a whole season (where snapshots
    exist). Mirrors weekly_update.opening_line_lookup but season-wide."""
    with session_scope() as s:
        rows = (
            s.query(
                OddsSnapshot.game_id, OddsSnapshot.book, OddsSnapshot.line, OddsSnapshot.captured_at
            )
            .join(Game, Game.id == OddsSnapshot.game_id)
            .filter(Game.season == season, OddsSnapshot.market == "1H_total")
            .all()
        )
    by_game: Dict[int, list] = {}
    for gid, book, line, captured_at in rows:
        by_game.setdefault(gid, []).append(
            type("S", (), {"book": book, "line": line, "captured_at": captured_at})
        )
    out: Dict[int, float] = {}
    for gid, snaps in by_game.items():
        opening = consensus_open_close(snaps)[0]
        if opening is not None:
            out[gid] = opening
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-season", type=int, default=2018)
    ap.add_argument("--min-games", type=int, default=2)
    args = ap.parse_args()
    init_db()

    # Historical backfill: played games only (the frame also carries the
    # unplayed upcoming slate, which weekly_update scores — not this script).
    df = training_frame(build_feature_frame(min_games=args.min_games))
    seasons = sorted(int(s) for s in df["season"].unique() if s >= args.start_season)
    print(f"backfilling BV line for seasons {seasons[0]}..{seasons[-1]}")

    total = 0
    for ts in seasons:
        lines = season_opening_lines(ts)
        scored = score_slate(ts, line_lookup=lines, df=df)
        if scored.empty:
            print(f"  {ts}: no scorable games (need prior-season training data)")
            continue
        n = store_predictions(scored)
        real = sum(1 for g in scored["id"] if g in lines)
        total += n
        print(f"  {ts}: stored {n} predictions ({real} real opening lines)")
    print(f"done — {total} predictions backfilled with bv_line/bv_gap")


if __name__ == "__main__":
    main()
