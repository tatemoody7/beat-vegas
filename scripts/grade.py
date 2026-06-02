#!/usr/bin/env python
"""Grade completed games: consensus opening/closing 1H lines vs actual 1H points.

Produces the real-line ledger that finally answers "are first-half unders
cashing against the true market number?" — with CLV (open->close) per game.

Prereqs: poll_lines.py captured snapshots through the week, and the season's
actual results are loaded (re-run backfill --season <yr> after games finish).

    python scripts/grade.py --season 2025
"""
from __future__ import annotations

import argparse
import statistics
from typing import Dict, List, Optional, Tuple

from beatvegas.db.models import Game, OddsSnapshot, Prediction, Result
from beatvegas.db.store import init_db, session_scope
from beatvegas.grading import clv_under, under_result, units_won
from beatvegas.lines import consensus_open_close
from beatvegas.model.score import MODEL_VERSION, is_model_bet

MODEL_MARKET = "market"   # tag for the pure market-vs-result grade


def _closings(session, season: int):
    """game -> (opening, closing) consensus for finished games with snapshots."""
    games = (session.query(Game)
             .filter(Game.season == season,
                     Game.first_half_total.isnot(None)).all())
    out = {}
    for g in games:
        snaps = (session.query(OddsSnapshot)
                 .filter(OddsSnapshot.game_id == g.id,
                         OddsSnapshot.market == "1H_total").all())
        out[g.id] = (g, consensus_open_close(snaps) if snaps else (None, None))
    return out


def grade_market(session, closings) -> int:
    n = 0
    for gid, (g, (opening, closing)) in closings.items():
        if closing is None:
            continue
        actual = g.first_half_total
        (session.query(Result).filter(Result.game_id == gid,
         Result.model_version == MODEL_MARKET).delete())
        session.add(Result(
            game_id=gid, model_version=MODEL_MARKET, actual_first_half_total=actual,
            line_used=closing, line_kind="real",
            under_hit=under_result(actual, closing) == "under",
            closing_line=closing, clv=clv_under(opening, closing),
            units=units_won(actual, closing)))
        n += 1
    return n


def grade_model(session, season: int, closings) -> int:
    """Grade the model's bets (under_score >= threshold) at the line it picked."""
    preds = (session.query(Prediction)
             .filter(Prediction.model_version == MODEL_VERSION).all())
    n = 0
    for p in preds:
        if not is_model_bet(p.under_score) or p.line_used is None:
            continue
        entry = closings.get(p.game_id)
        if entry is None:
            continue
        g, (_open, closing) = entry
        actual = g.first_half_total
        bet_line = p.line_used
        (session.query(Result).filter(Result.game_id == p.game_id,
         Result.model_version == MODEL_VERSION).delete())
        session.add(Result(
            game_id=p.game_id, model_version=MODEL_VERSION,
            actual_first_half_total=actual, line_used=bet_line,
            line_kind="real" if closing is not None else "proxy",
            under_hit=under_result(actual, bet_line) == "under",
            closing_line=closing, clv=clv_under(bet_line, closing),
            units=units_won(actual, bet_line)))
        n += 1
    return n


def _summary(session, model_version: str, label: str) -> None:
    rows = (session.query(Result)
            .filter(Result.model_version == model_version).all())
    if not rows:
        print(f"{label}: no graded bets")
        return
    n = len(rows)
    unders = sum(1 for r in rows if r.under_hit)
    units = sum(r.units for r in rows)
    clvs = [r.clv for r in rows if r.clv is not None]
    clv_txt = f"  avg CLV={statistics.mean(clvs):+.2f}" if clvs else ""
    print(f"{label}: UNDER {unders}/{n} ({100*unders/n:.1f}%)  "
          f"units={units:+.2f}{clv_txt}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    args = ap.parse_args()
    init_db()

    with session_scope() as s:
        closings = _closings(s, args.season)
        m = grade_market(s, closings)
        mdl = grade_model(s, args.season, closings)
    print(f"graded {m} market + {mdl} model bets for {args.season}")
    with session_scope() as s:
        _summary(s, MODEL_MARKET, "MARKET")
        _summary(s, MODEL_VERSION, "MODEL ")


if __name__ == "__main__":
    main()
