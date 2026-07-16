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

from beatvegas.db.models import Game, OddsSnapshot, Prediction, Result
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.grading import (
    clv_under,
    price_clv_under,
    trusted_first_half_total,
    under_result,
    units_won,
)
from beatvegas.lines import closing_before_kickoff, fair_under_before_kickoff
from beatvegas.model.score import MODEL_VERSION, is_model_bet

MODEL_MARKET = "market"  # tag for the pure market-vs-result grade (1H)
MODEL_MARKET_FG = "market_fg"  # full-game market-vs-result grade


def _closings(session, season: int):
    """game -> (g, (opening, closing), closing_at) for finished games.

    The closing line uses only snapshots captured BEFORE kickoff (so a late poll
    that ran after the game started can't pollute it), and closing_at is the
    freshest such snapshot — the CLV-trust signal (how close to kickoff we got).
    """
    games = (
        session.query(Game).filter(Game.season == season, Game.first_half_total.isnot(None)).all()
    )
    out = {}
    for g in games:
        snaps = (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.game_id == g.id, OddsSnapshot.market == "1H_total")
            .all()
        )
        opening, closing, closing_at = closing_before_kickoff(snaps, g.start_date)
        fair = fair_under_before_kickoff(snaps, g.start_date)
        out[g.id] = (g, (opening, closing), closing_at, fair)
    return out


def _closings_fg(session, season: int):
    """game -> (g, (opening, closing), closing_at) for the FULL-GAME market.

    Mirrors _closings but uses full_game_total snapshots and games with a final
    score (home_points + away_points = the realized full-game total)."""
    games = (
        session.query(Game)
        .filter(
            Game.season == season,
            Game.home_points.isnot(None),
            Game.away_points.isnot(None),
        )
        .all()
    )
    out = {}
    for g in games:
        snaps = (
            session.query(OddsSnapshot)
            .filter(OddsSnapshot.game_id == g.id, OddsSnapshot.market == "full_game_total")
            .all()
        )
        opening, closing, closing_at = closing_before_kickoff(snaps, g.start_date)
        fair = fair_under_before_kickoff(snaps, g.start_date)
        out[g.id] = (g, (opening, closing), closing_at, fair)
    return out


def grade_market_fg(session, closings_fg) -> int:
    """Full-game market ledger: consensus open/close vs the realized total."""
    n = 0
    for gid, (g, (opening, closing), closing_at, (fair_open, fair_close)) in closings_fg.items():
        if closing is None:
            continue
        actual = g.home_points + g.away_points
        (
            session.query(Result)
            .filter(Result.game_id == gid, Result.model_version == MODEL_MARKET_FG)
            .delete()
        )
        session.add(
            Result(
                game_id=gid,
                model_version=MODEL_MARKET_FG,
                market="full",
                actual_first_half_total=actual,  # full-game total (see model note)
                line_used=closing,
                line_kind="real",
                under_hit=under_result(actual, closing) == "under",
                closing_line=closing,
                closing_captured_at=closing_at,
                clv=clv_under(opening, closing),
                clv_prob=price_clv_under(fair_open, fair_close),
                units=units_won(actual, closing),
            )
        )
        n += 1
    return n


def grade_market(session, closings) -> int:
    n = 0
    for gid, (g, (opening, closing), closing_at, (fair_open, fair_close)) in closings.items():
        if closing is None:
            continue
        # Delete BEFORE the trust check so a previously-graded false zero is
        # cleaned up (not just skipped) when grading is re-run.
        (
            session.query(Result)
            .filter(Result.game_id == gid, Result.model_version == MODEL_MARKET)
            .delete()
        )
        actual = trusted_first_half_total(
            g.first_half_total, g.home_points, g.away_points, g.first_half_source
        )
        if actual is None:
            continue
        session.add(
            Result(
                game_id=gid,
                model_version=MODEL_MARKET,
                market="1H",
                actual_first_half_total=actual,
                line_used=closing,
                line_kind="real",
                under_hit=under_result(actual, closing) == "under",
                closing_line=closing,
                closing_captured_at=closing_at,
                clv=clv_under(opening, closing),
                clv_prob=price_clv_under(fair_open, fair_close),
                units=units_won(actual, closing),
            )
        )
        n += 1
    return n


def grade_model(session, season: int, closings) -> int:
    """Grade the model's bets (under_score >= threshold) at the line it picked."""
    preds = session.query(Prediction).filter(Prediction.model_version == MODEL_VERSION).all()
    n = 0
    for p in preds:
        if not is_model_bet(p.under_score) or p.line_used is None:
            continue
        entry = closings.get(p.game_id)
        if entry is None:
            continue
        g, (_open, closing), closing_at, (fair_open, fair_close) = entry
        bet_line = p.line_used
        (
            session.query(Result)
            .filter(Result.game_id == p.game_id, Result.model_version == MODEL_VERSION)
            .delete()
        )
        actual = trusted_first_half_total(
            g.first_half_total, g.home_points, g.away_points, g.first_half_source
        )
        if actual is None:
            continue
        session.add(
            Result(
                game_id=p.game_id,
                model_version=MODEL_VERSION,
                market="1H",
                actual_first_half_total=actual,
                line_used=bet_line,
                line_kind="real" if closing is not None else "proxy",
                under_hit=under_result(actual, bet_line) == "under",
                closing_line=closing,
                closing_captured_at=closing_at,
                clv=clv_under(bet_line, closing),
                clv_prob=price_clv_under(fair_open, fair_close),
                units=units_won(actual, bet_line),
            )
        )
        n += 1
    return n


def _summary(session, model_version: str, label: str) -> None:
    rows = session.query(Result).filter(Result.model_version == model_version).all()
    if not rows:
        print(f"{label}: no graded bets")
        return
    n = len(rows)
    unders = sum(1 for r in rows if r.under_hit)
    # A push is neither a win nor a loss — leaving it in the denominator
    # understates the under% every time a total lands exactly on the line.
    pushes = sum(1 for r in rows if r.actual_first_half_total == r.line_used)
    decided = n - pushes
    units = sum(r.units for r in rows)
    clvs = [r.clv for r in rows if r.clv is not None]
    clv_txt = f"  avg CLV={statistics.mean(clvs):+.2f}" if clvs else ""
    pclvs = [r.clv_prob for r in rows if r.clv_prob is not None]
    pclv_txt = f"  price-CLV={100 * statistics.mean(pclvs):+.2f}pp" if pclvs else ""
    pct = f"{100 * unders / decided:.1f}%" if decided else "n/a"
    push_txt = f" ({pushes}P)" if pushes else ""
    print(
        f"{label}: UNDER {unders}/{decided} ({pct}){push_txt}  "
        f"units={units:+.2f}{clv_txt}{pclv_txt}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    args = ap.parse_args()
    if not try_init_db():
        return

    with session_scope() as s:
        closings = _closings(s, args.season)
        closings_fg = _closings_fg(s, args.season)
        m = grade_market(s, closings)
        mdl = grade_model(s, args.season, closings)
        mfg = grade_market_fg(s, closings_fg)
    print(f"graded {m} market(1H) + {mdl} model(1H) + {mfg} market(FG) bets for {args.season}")
    with session_scope() as s:
        _summary(s, MODEL_MARKET, "MARKET 1H")
        _summary(s, MODEL_VERSION, "MODEL  1H")
        _summary(s, MODEL_MARKET_FG, "MARKET FG")


if __name__ == "__main__":
    main()
