"""Recent first-half form + home/away 1H splits for the game card.

For each team in a game:
  form_<side>   the team's last three played games' 1H points for / against,
                oldest -> newest: {"pf": [..], "pa": [..], "n": k, "source": ..}
  split_<side>  the team's 1H PF/PA averages at home vs on the road:
                {"at_home": {"pf", "pa", "n"} | None, "on_road": {...} | None,
                 "source": ..}

Source rule (same as etl/context.py's 1H priors): season-to-date from week 3
when the team has a played game this season; otherwise the PRIOR season stands
in ("prior_season"). A team with nothing in either season gets None for the
whole block — never NaN, never an empty shell. Display only; not a model input.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from ..db.models import Game
from .context import SEASON_TO_DATE_FROM_WEEK, _games, json_safe

FORM_N = 3


def _ord(r: Dict) -> Tuple:
    """Chronological sort key: start_date, then week (start_date may be NULL)."""
    sd = r.get("start_date")
    return (0 if sd is not None else 1, sd if sd is not None else 0, r.get("week") or 0)


def last_n_form(rows: List[Dict], n: int = FORM_N) -> Optional[Dict]:
    """Last `n` played games, oldest -> newest. None when there are no rows."""
    if not rows:
        return None
    ordered = sorted(rows, key=_ord)[-n:]
    return {
        "pf": [r["pf"] for r in ordered],
        "pa": [r["pa"] for r in ordered],
        "n": len(ordered),
    }


def _avg_block(rows: List[Dict]) -> Optional[Dict]:
    if not rows:
        return None
    n = len(rows)
    return {
        "pf": sum(r["pf"] for r in rows) / n,
        "pa": sum(r["pa"] for r in rows) / n,
        "n": n,
    }


def home_away_split(rows: List[Dict]) -> Optional[Dict]:
    """1H PF/PA averages at home and on the road. None when there are no rows."""
    if not rows:
        return None
    return {
        "at_home": _avg_block([r for r in rows if r.get("is_home")]),
        "on_road": _avg_block([r for r in rows if not r.get("is_home")]),
    }


def _team_rows(session, seasons: List[int], teams: List[str]) -> Dict[Tuple[int, str], List[Dict]]:
    """{(season, team): [{week, start_date, is_home, pf, pa}, ...]} over PLAYED
    games (both sides' 1H points known)."""
    out: Dict[Tuple[int, str], List[Dict]] = {}
    if not seasons or not teams:
        return out
    q = (
        session.query(
            Game.season,
            Game.week,
            Game.start_date,
            Game.home_team,
            Game.away_team,
            Game.home_first_half_points,
            Game.away_first_half_points,
        )
        .filter(
            Game.season.in_(seasons),
            Game.home_first_half_points.isnot(None),
            Game.away_first_half_points.isnot(None),
            (Game.home_team.in_(teams)) | (Game.away_team.in_(teams)),
        )
        .all()
    )
    for season, week, sd, home, away, hfh, afh in q:
        if home in teams:
            out.setdefault((season, home), []).append(
                {"week": week, "start_date": sd, "is_home": True, "pf": hfh, "pa": afh}
            )
        if away in teams:
            out.setdefault((season, away), []).append(
                {"week": week, "start_date": sd, "is_home": False, "pf": afh, "pa": hfh}
            )
    return out


def _source_rows(
    rows: Dict[Tuple[int, str], List[Dict]], team: str, season: int, week: int
) -> Tuple[List[Dict], Optional[str]]:
    if week >= SEASON_TO_DATE_FROM_WEEK:
        std = [
            r for r in rows.get((season, team), []) if r["week"] is not None and r["week"] < week
        ]
        if std:
            return std, "season_to_date"
    prior = rows.get((season - 1, team), [])
    if prior:
        return prior, "prior_season"
    return [], None


def _team_block(rows, team, season, week, n) -> Tuple[Optional[Dict], Optional[Dict]]:
    src_rows, source = _source_rows(rows, team, season, week)
    form = last_n_form(src_rows, n=n)
    split = home_away_split(src_rows)
    if form is not None:
        form["source"] = source
    if split is not None:
        split["source"] = source
    return form, split


def form_for_games(
    session, season: int, week: int, game_ids: Iterable[int], n: int = FORM_N
) -> Dict[int, Dict]:
    """{game_id: {form_home, form_away, split_home, split_away}} for the given
    games of one (season, week). Unknown ids are skipped; JSON-clean."""
    games = _games(session, season, week, game_ids)
    if not games:
        return {}
    teams = sorted({t for pair in games.values() for t in pair})
    rows = _team_rows(session, [season, season - 1], teams)
    out: Dict[int, Dict] = {}
    for gid, (home, away) in games.items():
        fh, sh = _team_block(rows, home, season, week, n)
        fa, sa = _team_block(rows, away, season, week, n)
        out[gid] = json_safe({"form_home": fh, "form_away": fa, "split_home": sh, "split_away": sa})
    return out
