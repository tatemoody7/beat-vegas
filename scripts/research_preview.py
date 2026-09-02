#!/usr/bin/env python
"""Build the week's research preview: slate + ESPN news/injuries/QB-out per game.

The start of the weekly loop — look at the week's games before lines drop and
pull any updated news. DISPLAY ONLY: ESPN is unofficial + fail-silent, never a
model input. Upserts one game_previews row per game; the web /preview view reads
them. Run early in the week (locally or via a scheduled job).

    python scripts/research_preview.py                 # current season, upcoming week
    python scripts/research_preview.py --season 2026 --week 1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from beatvegas.db.models import Game, GamePreview
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.season import current_season
from beatvegas.sources.espn import game_context, qb_out_flags, teams_available


def _upcoming_week(s, season: int) -> int:
    """Smallest week with games not yet final; falls back to the min week."""
    rows = s.query(Game.week).filter(Game.season == season, Game.home_points.is_(None)).all()
    weeks = sorted({r[0] for r in rows if r[0] is not None})
    if weeks:
        return weeks[0]
    allw = sorted({r[0] for r in s.query(Game.week).filter(Game.season == season) if r[0]})
    return allw[0] if allw else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int, default=None, help="default: the upcoming week")
    args = ap.parse_args()

    # ESPN blocked or down => every game would be written as a blank preview
    # and the QB-out gate would read 'clear' for the whole slate. Go red instead.
    if not teams_available():
        print(
            "[espn] FATAL: ESPN team list is empty (HTTP block or outage) — refusing "
            "to write blank previews. Fix the source, then re-run."
        )
        sys.exit(3)

    if not try_init_db():
        return

    now = datetime.utcnow()
    n = with_news = qb_outs = 0
    with session_scope() as s:
        week = args.week or _upcoming_week(s, args.season)
        games = (
            s.query(Game)
            .filter(Game.season == args.season, Game.week == week)
            .order_by(Game.start_date)
            .all()
        )
        for g in games:
            ctx = game_context(g.home_team, g.away_team)
            qb = qb_out_flags(g.home_team, g.away_team)
            news = {"home": ctx["home"]["news"], "away": ctx["away"]["news"]}
            injuries = {"home": ctx["home"]["injuries"], "away": ctx["away"]["injuries"]}
            if news["home"] or news["away"]:
                with_news += 1
            if qb["home"] or qb["away"]:
                qb_outs += 1

            row = s.query(GamePreview).filter(GamePreview.game_id == g.id).one_or_none()
            if row is None:
                row = GamePreview(game_id=g.id)
                s.add(row)
            row.season = g.season
            row.week = g.week
            row.qb_out = bool(qb["home"] or qb["away"])
            row.qb_out_detail = qb.get("detail") or ""
            row.news_json = json.dumps(news)
            row.injuries_json = json.dumps(injuries)
            row.updated_at = now
            n += 1

    print(
        f"preview {args.season} wk{week}: {n} games, {with_news} with news, {qb_outs} with a QB out"
    )


if __name__ == "__main__":
    main()
