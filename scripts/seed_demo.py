#!/usr/bin/env python
"""Build a DEMO database so the dashboard has something to show in the offseason.

Copies the real DB to data/demo.db, then for a real past week synthesizes:
  - first-half line snapshots across 3 books with realistic movement over a week
  - graded market results (under vs closing line + CLV)
  - a handful of sample manual picks (graded)

Your real beatvegas.db is never touched. Launch the dashboard against the demo
DB with:  BEATVEGAS_DB=data/demo.db streamlit run beatvegas/dashboard/app.py
"""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta

from beatvegas.config import REPO_ROOT
from beatvegas.db.models import Game, ManualPick, OddsSnapshot, Result
from beatvegas.db.store import get_engine, init_db, session_scope
from beatvegas.etl.features import build_feature_frame
from beatvegas.etl.proxy_line import proxy_total
from beatvegas.grading import clv_under, under_result, units_won
from beatvegas.lines import consensus_open_close
from beatvegas.model.score import score_slate, store_predictions

DEMO = REPO_ROOT / "data" / "demo.db"
REAL = REPO_ROOT / "data" / "beatvegas.db"
BOOKS = ["draftkings", "fanduel", "betmgm"]
DEMO_SEASON, DEMO_WEEK = 2025, 8


def _snapshot_lines(close_line: float, n_days: int = 5):
    """Deterministic, realistic-looking drift toward the closing line per book.
    Returns list of (book, captured_at, line) over the lead-up week."""
    base = datetime(2025, 10, 13, 12, 0)           # fixed demo timestamps
    rows = []
    for bi, book in enumerate(BOOKS):
        # each book opens a touch off the close, drifts in over the week
        open_off = [1.0, -0.5, 0.5][bi]
        for d in range(n_days):
            frac = d / (n_days - 1)
            line = round((close_line + open_off * (1 - frac)) * 2) / 2
            rows.append((book, base + timedelta(days=d, hours=bi), float(line)))
    return rows


def main() -> None:
    if not REAL.exists():
        raise SystemExit("Real DB not found — run scripts/backfill.py first.")
    DEMO.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REAL, DEMO)
    get_engine(DEMO)                                # point the process at demo.db
    init_db(DEMO)

    with session_scope() as s:
        games = (s.query(Game)
                 .filter(Game.season == DEMO_SEASON, Game.week == DEMO_WEEK,
                         Game.full_game_total.isnot(None),
                         Game.first_half_total.isnot(None))
                 .order_by(Game.full_game_total).limit(12).all())
        if not games:
            raise SystemExit(f"No suitable games in {DEMO_SEASON} wk{DEMO_WEEK}.")

        # clear any prior demo artifacts
        s.query(OddsSnapshot).delete()
        s.query(Result).filter(Result.model_version == "market").delete()
        s.query(ManualPick).delete()

        close_by_gid = {}
        for g in games:
            close = proxy_total(g.full_game_total, 0.52)
            snaps = []
            for book, ts, line in _snapshot_lines(close):
                snap = OddsSnapshot(game_id=g.id, book=book, market="1H_total",
                                    line=line, over_price=-110, under_price=-110,
                                    captured_at=ts)
                s.add(snap)
                snaps.append(snap)
            opening, closing = consensus_open_close(snaps)
            close_by_gid[g.id] = closing
            res = under_result(g.first_half_total, closing)
            s.add(Result(game_id=g.id, model_version="market",
                         actual_first_half_total=g.first_half_total,
                         line_used=closing, line_kind="real",
                         under_hit=(res == "under"), closing_line=closing,
                         clv=clv_under(opening, closing),
                         units=units_won(g.first_half_total, closing)))

        # Pace + weather are inherited from the copied real DB (historical
        # backfill populated TeamTempo for all weeks + Weather for many games),
        # so the demo board shows real pace without a slow live fetch here.

        # a few sample manual picks (bet at the opening number)
        for g in games[:5]:
            bet_line = proxy_total(g.full_game_total, 0.52) + 0.5
            _, closing = consensus_open_close(
                [x for x in s.query(OddsSnapshot).filter(
                    OddsSnapshot.game_id == g.id).all()])
            res = under_result(g.first_half_total, bet_line)
            s.add(ManualPick(
                game_id=g.id, season=DEMO_SEASON, week=DEMO_WEEK,
                home_team=g.home_team, away_team=g.away_team, side="under",
                line=bet_line, price=-110, stake=1.0, book="draftkings",
                placed_at=datetime(2025, 10, 14, 9, 0), note="demo",
                graded=True, actual_first_half_total=g.first_half_total,
                result=res, units=units_won(g.first_half_total, bet_line),
                closing_line=closing, clv=clv_under(bet_line, closing)))

        n_games = len(games)

    # Score the slate (0-100 under score + factor payload) -> predictions.
    game_ids = list(close_by_gid)
    df = build_feature_frame(min_games=2)
    scored = score_slate(DEMO_SEASON, game_ids=game_ids,
                         line_lookup=close_by_gid, df=df)
    n_pred = store_predictions(scored)
    print(f"seeded {n_games} games of synthetic 1H lines + results, 5 sample "
          f"picks, {n_pred} scored predictions into {DEMO.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
