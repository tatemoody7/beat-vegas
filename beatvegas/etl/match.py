"""Match Odds API events to CFBD game ids.

Odds API team names carry mascots ("Ohio State Buckeyes") and at neutral sites
the home/away designation can be flipped vs CFBD. We score both orientations
against same-window CFBD games and require a confident name match on both teams.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

_PUNCT = re.compile(r"[^a-z0-9 ]+")


def _norm(name: Optional[str]) -> str:
    if not name:
        return ""
    s = name.lower().replace("&", "and").replace(".", "")
    s = _PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_score(cfbd_school: str, odds_name: str) -> float:
    """How well a CFBD school matches an Odds API name (which appends a mascot).
    Compares full strings and also the school against the name's leading chars."""
    a, b = _norm(cfbd_school), _norm(odds_name)
    if not a or not b:
        return 0.0
    full = SequenceMatcher(None, a, b).ratio()
    lead = SequenceMatcher(None, a, b[: len(a)]).ratio()  # mascot is appended
    contained = 1.0 if (a == b or b.startswith(a + " ")) else 0.0
    return max(full, lead, contained)


def _parse_dt(s: Any) -> Optional[datetime]:
    if isinstance(s, datetime):
        return s
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def match_event(
    ev_home: str,
    ev_away: str,
    commence: Any,
    games: List[Dict[str, Any]],
    date_window_days: int = 1,
    min_team_score: float = 0.80,
) -> Tuple[Optional[int], float]:
    """Return (game_id, score) of the best CFBD match, or (None, 0.0).

    `games`: list of dicts with id, home_team, away_team, start_date.
    Both teams must score >= min_team_score in the chosen orientation."""
    cdt = _parse_dt(commence)
    cday: Optional[date] = cdt.date() if cdt else None

    best_id, best_score = None, 0.0
    for g in games:
        gdt = _parse_dt(g.get("start_date"))
        if cday is not None and gdt is not None:
            if abs((gdt.date() - cday).days) > date_window_days:
                continue
        gh, ga = g.get("home_team", ""), g.get("away_team", "")
        # Orientation A: ev_home<->cfbd_home ; Orientation B: swapped (neutral).
        a = (name_score(gh, ev_home), name_score(ga, ev_away))
        b = (name_score(ga, ev_home), name_score(gh, ev_away))
        for h, w in (a, b):
            if h >= min_team_score and w >= min_team_score:
                score = h + w
                if score > best_score:
                    best_id, best_score = g.get("id"), score
    return best_id, best_score


def resolve_game(
    home: str,
    away: str,
    games: List[Dict[str, Any]],
    week: Optional[int] = None,
    min_team_score: float = 0.72,
) -> Tuple[Optional[int], float, int, List[Dict[str, Any]]]:
    """Resolve a game id from typed team names (no kickoff time needed).

    Returns (game_id, score, n_close, candidates). n_close > 1 means genuinely
    ambiguous — two games scored within a hair of each other (a true rematch) —
    and `candidates` lists those near-tie games so the caller can show them;
    pass `week` to disambiguate. Either orientation is accepted.

    The 0.72 floor keeps common nicknames working ("Bama" vs "Alabama" ≈ 0.727)
    while rejecting the loose partial matches 0.6 let through."""
    hits = []
    for g in games:
        if week is not None and g.get("week") not in (None, week):
            continue
        gh, ga = g.get("home_team", ""), g.get("away_team", "")
        a = (name_score(gh, home), name_score(ga, away))
        b = (name_score(ga, home), name_score(gh, away))
        best = max(a, b, key=lambda t: min(t))
        if min(best) >= min_team_score:
            hits.append((g, best[0] + best[1]))
    if not hits:
        return None, 0.0, 0, []
    hits.sort(key=lambda t: t[1], reverse=True)
    top = hits[0][1]
    # Only near-ties (within 0.15 of the best combined score) count as ambiguous;
    # weak partial matches above the nickname threshold don't.
    close = [g for g, sc in hits if top - sc <= 0.15]
    return hits[0][0].get("id"), top, len(close), close
