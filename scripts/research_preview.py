#!/usr/bin/env python
"""Build the week's research preview: slate + news (ESPN) + injuries/QB-out
(Rotowire) per game.

The start of the weekly loop — look at the week's games before lines drop and
pull any updated news. DISPLAY ONLY: both sources are unofficial + fail-silent,
never a model input. Upserts one game_previews row per game; the web /preview
view reads them. Run early in the week (locally or via a scheduled job).

Injuries come from ONE Rotowire report call for the whole slate (ESPN publishes
no college injuries — see sources/rotowire.py). If that call comes back empty
the run says so loudly instead of writing 455 quiet blanks, and --status-file
records it for scripts/build_card.py: an empty injury feed makes the card's
QB-out gate pass EVERY game, so a card built on one is marked degraded.

    python scripts/research_preview.py                 # current season, upcoming week
    python scripts/research_preview.py --season 2026 --week 1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Optional

from beatvegas import ci
from beatvegas.db.models import Game, GamePreview, Team
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.season import current_season, detect_week
from beatvegas.sources import rotowire
from beatvegas.sources.espn import espn_team_id, team_news, teams_available


def write_status(
    path: Optional[str],
    *,
    ok: bool,
    reason: Optional[str],
    rotowire_rows: int,
    espn_ok: bool,
    games: int,
    qb_outs: int,
) -> None:
    """This run's health, for scripts/build_card.py. `ok` False means the QB-out
    gate on the card is about to read a stale (or blank) injury file, which
    passes EVERY game — the card marks those games degraded rather than
    publishing a clean-looking final."""
    if not path:
        return
    payload = {
        "ok": bool(ok),
        "reason": reason,
        "rotowire_rows": int(rotowire_rows),
        "espn_ok": bool(espn_ok),
        "games": int(games),
        "qb_outs": int(qb_outs),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    print(f"[status] {path}: {json.dumps(payload)}")


def _upcoming_week(s, season: int) -> int:
    """The week the board is about to bet -- beatvegas.season.detect_week, the
    same rule card.yml and sunday.yml resolve with. The old rule ("smallest
    week with a game not yet final") sat on week 1 all season, because week 1
    keeps never-final rows, and the retired Tue/Fri workflow previewed it 456
    games at a time. The scan below is only the off-season fallback."""
    wk = detect_week(season)
    if wk is not None:
        return int(wk)
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
    ap.add_argument(
        "--status-file",
        default=None,
        dest="status_file",
        help="write this run's health as JSON here (ok, reason, rotowire_rows, "
        "espn_ok, games, qb_outs) so scripts/build_card.py can mark a card built "
        "on a stale QB read degraded",
    )
    args = ap.parse_args()

    # Sources first, DB second: if BOTH are empty every row would be a blank
    # preview and the QB-out gate would read "clear" for the whole slate — go red
    # instead of writing it. One empty source is a loud warning, not a stop.
    report = rotowire.fetch_injury_report()  # one call for the whole slate
    espn_ok = teams_available()
    if not report:
        ci.warn("[rotowire] injury report empty/unreachable — injuries will be blank")
    if not espn_ok:
        ci.warn("[espn] team list empty (blocked or down) — news will be blank")
    # ok is about the INJURY feed only: it is what the card's QB-out gate reads,
    # and an empty one passes every game. An empty ESPN news feed is recorded and
    # warned about but is display-only, so it does not flip ok.
    reason = None
    if not report:
        reason = "both_empty" if not espn_ok else "rotowire_empty"

    def status(games: int, outs: int, why: Optional[str] = reason) -> None:
        write_status(
            args.status_file,
            ok=why is None,
            reason=why,
            rotowire_rows=len(report),
            espn_ok=bool(espn_ok),
            games=games,
            qb_outs=outs,
        )

    if not report and not espn_ok:
        print("[espn] FATAL: both sources empty — refusing to write a blank slate. Fix, re-run.")
        status(0, 0)
        sys.exit(3)

    if not try_init_db():
        # Nothing was written, so the QB read on file is whatever it was: say
        # so (symmetric with poll_lines) rather than reporting a healthy run.
        status(0, 0, why=reason or "db_unreachable")
        return

    now = datetime.utcnow()
    n = with_news = with_inj = qb_outs = 0

    with session_scope() as s:
        schools = [t[0] for t in s.query(Team.school).distinct().all()]
    inj_by_school = rotowire.by_school(report, schools)

    news_cache: dict = {}

    def news_for(school: str) -> list:
        if school not in news_cache:
            eid = espn_team_id(school)
            news_cache[school] = team_news(eid) if eid else []
        return news_cache[school]

    with session_scope() as s:
        week = args.week or _upcoming_week(s, args.season)
        games = (
            s.query(Game)
            .filter(Game.season == args.season, Game.week == week)
            .order_by(Game.start_date)
            .all()
        )
        for g in games:
            news = {"home": news_for(g.home_team), "away": news_for(g.away_team)}
            home_rows = inj_by_school.get(g.home_team, [])
            away_rows = inj_by_school.get(g.away_team, [])
            injuries = {
                "home": [rotowire.format_entry(r) for r in home_rows],
                "away": [rotowire.format_entry(r) for r in away_rows],
            }
            details = []
            for side, rows in (("home", home_rows), ("away", away_rows)):
                d = rotowire.qb_out_detail(rows)
                if d:
                    details.append(f"{g.home_team if side == 'home' else g.away_team}: {d}")
            if news["home"] or news["away"]:
                with_news += 1
            if injuries["home"] or injuries["away"]:
                with_inj += 1
            if details:
                qb_outs += 1

            row = s.query(GamePreview).filter(GamePreview.game_id == g.id).one_or_none()
            if row is None:
                row = GamePreview(game_id=g.id)
                s.add(row)
            row.season = g.season
            row.week = g.week
            row.qb_out = bool(details)
            row.qb_out_detail = " · ".join(details)
            row.news_json = json.dumps(news)
            row.injuries_json = json.dumps(injuries)
            row.updated_at = now
            n += 1

    print(
        f"preview {args.season} wk{week}: {n} games, {with_news} with news, "
        f"{with_inj} with injuries ({len(report)} report rows, "
        f"{len(inj_by_school)} teams matched), {qb_outs} with a QB out"
    )
    status(n, qb_outs)
    if n and not with_news:
        ci.warn("[espn] no news for any game — team list or news endpoint is failing")


if __name__ == "__main__":
    main()
