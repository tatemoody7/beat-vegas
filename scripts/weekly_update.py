#!/usr/bin/env python
"""Score the upcoming slate and log the model's picks (predictions).

Builds features, scores each game's 1H-under probability + 0-100 score, and
stores predictions with the current **opening consensus** line as `line_used`
(proxy fallback when no line is posted yet). Auto-detects the current week.

    python scripts/weekly_update.py                 # current season, auto week
    python scripts/weekly_update.py --season 2025 --week 8
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from typing import Dict, Optional

from beatvegas.db.models import Game, OddsSnapshot
from beatvegas.db.store import init_db, session_scope
from beatvegas.etl.features import build_feature_frame
from beatvegas.lines import consensus_open_close
from beatvegas.model.score import score_slate, store_predictions
from beatvegas.season import current_season, detect_week


def opening_line_lookup(season: int, week: int) -> Dict[int, float]:
    with session_scope() as s:
        rows = (s.query(OddsSnapshot.game_id, OddsSnapshot.book,
                        OddsSnapshot.line, OddsSnapshot.captured_at)
                .join(Game, Game.id == OddsSnapshot.game_id)
                .filter(Game.season == season, Game.week == week,
                        OddsSnapshot.market == "1H_total").all())
    by_game: Dict[int, list] = {}
    for r in rows:
        by_game.setdefault(r[0], []).append(
            type("S", (), {"book": r[1], "line": r[2], "captured_at": r[3]}))
    return {gid: consensus_open_close(snaps)[0]
            for gid, snaps in by_game.items()
            if consensus_open_close(snaps)[0] is not None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int)
    ap.add_argument("--min-games", type=int, default=2)
    args = ap.parse_args()
    init_db()

    week = args.week or detect_week(args.season)
    if week is None:
        print(f"Could not detect an active week for {args.season}. "
              "Pass --week explicitly (offseason has no upcoming games).")
        return

    df = build_feature_frame(min_games=args.min_games)
    lines = opening_line_lookup(args.season, week)
    scored = score_slate(args.season, target_week=week, line_lookup=lines, df=df)
    if scored.empty:
        print(f"No scorable games for {args.season} wk{week} "
              f"(need >= {args.min_games} games played by both teams).")
        return
    n = store_predictions(scored)
    real = sum(1 for g in scored["id"] if g in lines)
    print(f"scored {n} games for {args.season} wk{week} "
          f"({real} with real opening lines, rest proxy)")
    top = scored.head(5)
    for _, r in top.iterrows():
        print(f"  #{int(r['rank'])} score {int(r['under_score'])}  "
              f"{r['away_team']} @ {r['home_team']}  line {r['line']:g}")


if __name__ == "__main__":
    main()
