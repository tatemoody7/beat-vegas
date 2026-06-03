#!/usr/bin/env python
"""Build a DEMO database so the dashboard has something to show in the offseason.

Copies the real DB to data/demo.db, then for a real past week synthesizes:
  - first-half line snapshots across 3 books with realistic movement over a week
  - graded market results (under vs closing line + CLV)
  - a handful of sample manual picks (graded)

Your real beatvegas.db is never touched. Launch the dashboard against the demo
DB with:  BEATVEGAS_DB=data/demo.db streamlit run beatvegas/dashboard/app.py

The synthesize/grade/score steps are exposed as importable functions so the week
simulator (scripts/simulate_week.py -> beatvegas/pipeline.py) reuses them against
a local Postgres sim DB instead of duplicating the logic.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional

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
_DEFAULT_BASE = datetime(2025, 10, 13, 12, 0)


def _snapshot_lines(close_line: float, base: datetime, n_days: int = 5):
    """Deterministic, realistic-looking drift toward the closing line per book.
    Returns list of (book, captured_at, line) over the lead-up week."""
    rows = []
    for bi, book in enumerate(BOOKS):
        # each book opens a touch off the close, drifts in over the week
        open_off = [1.0, -0.5, 0.5][bi]
        for d in range(n_days):
            frac = d / (n_days - 1)
            line = round((close_line + open_off * (1 - frac)) * 2) / 2
            rows.append((book, base + timedelta(days=d, hours=bi), float(line)))
    return rows


def synthesize_1h_snapshots(s, games: List[Game],
                            base: Optional[datetime] = None
                            ) -> Dict[int, List[OddsSnapshot]]:
    """Add synthetic 1H line snapshots (3 books, week-long drift) for each game.
    Returns {game_id: [snapshots]}. Clears any prior OddsSnapshot rows first."""
    base = base or _DEFAULT_BASE
    s.query(OddsSnapshot).delete()
    snaps_by_gid: Dict[int, List[OddsSnapshot]] = {}
    for g in games:
        close = proxy_total(g.full_game_total, spread=getattr(g, "spread", None))
        snaps = []
        for book, ts, line in _snapshot_lines(close, base):
            snap = OddsSnapshot(game_id=g.id, book=book, market="1H_total",
                                line=line, over_price=-110, under_price=-110,
                                captured_at=ts)
            s.add(snap)
            snaps.append(snap)
        snaps_by_gid[g.id] = snaps
    return snaps_by_gid


def grade_market_results(s, games: List[Game],
                         snaps_by_gid: Dict[int, List[OddsSnapshot]]
                         ) -> Dict[int, float]:
    """Grade the market (under vs closing 1H line) for each completed game.
    Returns {game_id: closing_line}. Clears prior 'market' results first."""
    s.query(Result).filter(Result.model_version == "market").delete()
    close_by_gid: Dict[int, float] = {}
    for g in games:
        opening, closing = consensus_open_close(snaps_by_gid[g.id])
        close_by_gid[g.id] = closing
        res = under_result(g.first_half_total, closing)
        s.add(Result(game_id=g.id, model_version="market",
                     actual_first_half_total=g.first_half_total,
                     line_used=closing, line_kind="real",
                     under_hit=(res == "under"), closing_line=closing,
                     clv=clv_under(opening, closing),
                     units=units_won(g.first_half_total, closing)))
    return close_by_gid


def sample_manual_picks(s, games: List[Game], season: int, week: int,
                        base: Optional[datetime] = None, n: int = 5) -> None:
    """Add a few graded sample manual picks (bet at the opener + 0.5)."""
    base = base or _DEFAULT_BASE
    s.query(ManualPick).delete()
    for g in games[:n]:
        bet_line = proxy_total(g.full_game_total,
                               spread=getattr(g, "spread", None)) + 0.5
        _, closing = consensus_open_close(
            list(s.query(OddsSnapshot).filter(OddsSnapshot.game_id == g.id).all()))
        res = under_result(g.first_half_total, bet_line)
        s.add(ManualPick(
            game_id=g.id, season=season, week=week,
            home_team=g.home_team, away_team=g.away_team, side="under",
            line=bet_line, price=-110, stake=1.0, book="draftkings",
            placed_at=base + timedelta(days=1, hours=-3), note="demo",
            graded=True, actual_first_half_total=g.first_half_total,
            result=res, units=units_won(g.first_half_total, bet_line),
            closing_line=closing, clv=clv_under(bet_line, closing)))


def score_and_store(season: int, line_lookup: Dict[int, float],
                    min_games: int = 2) -> int:
    """Build features, score the listed games, persist predictions. Returns count."""
    df = build_feature_frame(min_games=min_games)
    scored = score_slate(season, game_ids=list(line_lookup),
                         line_lookup=line_lookup, df=df)
    return store_predictions(scored)


def pick_games(s, season: int, week: int, limit: Optional[int] = 12) -> List[Game]:
    """Completed games for a week that have both a full-game total and a final
    1H score (so they're derivable + gradeable). Cheapest unders first."""
    q = (s.query(Game)
         .filter(Game.season == season, Game.week == week,
                 Game.full_game_total.isnot(None),
                 Game.first_half_total.isnot(None))
         .order_by(Game.full_game_total))
    return q.limit(limit).all() if limit else q.all()


def main() -> None:
    if not REAL.exists():
        raise SystemExit("Real DB not found — run scripts/backfill.py first.")
    DEMO.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REAL, DEMO)
    get_engine(DEMO)                                # point the process at demo.db
    init_db(DEMO)

    with session_scope() as s:
        games = pick_games(s, DEMO_SEASON, DEMO_WEEK, limit=12)
        if not games:
            raise SystemExit(f"No suitable games in {DEMO_SEASON} wk{DEMO_WEEK}.")
        snaps_by_gid = synthesize_1h_snapshots(s, games)
        close_by_gid = grade_market_results(s, games, snaps_by_gid)
        sample_manual_picks(s, games, DEMO_SEASON, DEMO_WEEK)
        n_games = len(games)

    n_pred = score_and_store(DEMO_SEASON, close_by_gid)
    print(f"seeded {n_games} games of synthetic 1H lines + results, 5 sample "
          f"picks, {n_pred} scored predictions into {DEMO.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
