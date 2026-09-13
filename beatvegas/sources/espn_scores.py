"""Final scores + first-half line scores from ESPN's public scoreboard.

Why this exists: on 2026-09-12 CFBD hit its monthly call quota and started
429ing every endpoint. scripts/backfill.py is the first step of grade.yml, so
grading stopped dead -- week 2 finished with finals for 14 of 303 games and
0 of 31 picks graded, and nothing was going to change until the month rolled
over. Scores are the one input we can get somewhere else for free.

Scope is deliberately narrow. This fetches SCORES ONLY and never invents a
game: ESPN's event ids are the same ids CFBD uses (and that `games.id` already
stores), so a row here updates points on a game the schedule load already
created. It does not touch team names (ESPN spells several of them
differently), lines, venues or anything else.

ESPN is unofficial, so this lives in sources/ and fails loudly to its caller
rather than silently returning half a slate.

**Send NO custom headers.** Akamai 403s a bare spoofed UA; requests' own
default is served. Host is site.web.api.espn.com -- site.api.espn.com is
403 from every network we run on. Both rules the hard way, see CLAUDE.md.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

_BASE = "https://site.web.api.espn.com/apis/site/v2/sports/football/college-football"
_FBS_GROUP = "80"  # ESPN's group id for FBS; the model only ever reads FBS games.


def _scoreboard(date: str, groups: str = _FBS_GROUP, timeout: int = 30) -> List[Dict[str, Any]]:
    """One day's events. `date` is YYYYMMDD in US Eastern, as ESPN reckons it."""
    r = requests.get(
        f"{_BASE}/scoreboard",
        params={"groups": groups, "dates": date, "limit": 400},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json().get("events") or []


def _linescores(competitor: Dict[str, Any]) -> Optional[List[int]]:
    raw = competitor.get("linescores")
    if not isinstance(raw, list) or len(raw) < 2:
        return None
    out = []
    for period in raw:
        v = period.get("value") if isinstance(period, dict) else None
        if v is None:
            return None
        out.append(int(v))
    return out


def _as_cfbd_game(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reshape one ESPN event into the dict shape etl/first_half.py expects.

    Returning CFBD's key names is the point: attach_first_half and
    line_scores_trustworthy then apply unchanged, so the false-zero guard that
    caught the corrupt 1H rows in the past protects this path too.
    """
    comps = event.get("competitions") or []
    if not comps:
        return None
    c = comps[0]
    if ((c.get("status") or {}).get("type") or {}).get("name") != "STATUS_FINAL":
        return None
    home = away = None
    for t in c.get("competitors") or []:
        if t.get("homeAway") == "home":
            home = t
        elif t.get("homeAway") == "away":
            away = t
    if not home or not away:
        return None
    try:
        gid = int(event["id"])
        home_pts = int(home["score"])
        away_pts = int(away["score"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "id": gid,
        "completed": True,
        "homePoints": home_pts,
        "awayPoints": away_pts,
        "homeLineScores": _linescores(home),
        "awayLineScores": _linescores(away),
    }


def final_scores(dates: List[str], groups: str = _FBS_GROUP) -> List[Dict[str, Any]]:
    """CFBD-shaped dicts for every FINAL game across `dates` (YYYYMMDD).

    Games still in progress are omitted entirely rather than returned with a
    partial score -- a live score written into home_points is how write-once
    pick grading freezes a half-played game (see tests/test_backfill_finality).
    """
    out: List[Dict[str, Any]] = []
    for d in dates:
        for ev in _scoreboard(d, groups=groups):
            g = _as_cfbd_game(ev)
            if g is not None:
                out.append(g)
    return out
