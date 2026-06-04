"""Derive ground-truth first-half points for each game.

Two paths, in order of preference:
  1. Per-quarter line scores from CFBD /games (light, reliable): 1H = Q1 + Q2.
  2. Play-by-play fallback: cumulative running score at the end of period 2.

CFBD JSON key casing has varied across API versions, so every lookup tolerates
both camelCase and snake_case. Functions here are pure and unit-tested.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _get(d: Dict[str, Any], *names: str) -> Any:
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return None


def first_half_from_line_scores(game: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    """Return (home_1h, away_1h) from per-quarter line scores, or None if absent.

    Line scores are a list of per-quarter point totals, e.g. [7, 10, 3, 14].
    First half = first two entries. Returns None if either side is missing or
    has fewer than 2 quarters recorded (e.g. unplayed game)."""
    home = _get(game, "homeLineScores", "home_line_scores")
    away = _get(game, "awayLineScores", "away_line_scores")
    if not _valid_line_score(home) or not _valid_line_score(away):
        return None
    return sum(home[:2]), sum(away[:2])


def _valid_line_score(ls: Any) -> bool:
    return (
        isinstance(ls, list) and len(ls) >= 2 and all(isinstance(x, (int, float)) for x in ls[:2])
    )


def first_half_from_plays(plays: List[Dict[str, Any]]) -> Dict[int, Tuple[int, int]]:
    """Map game_id -> (home_1h, away_1h) using the cumulative running score on
    the last play of period 2. Requires per-play running scores to be present."""
    # Track, per game, the running score seen on the highest-ordered play in
    # period <= 2. Plays arrive roughly ordered, but we don't rely on order:
    # within the first half, the running score is monotonic, so the max wins.
    best: Dict[int, Tuple[int, int]] = {}
    for p in plays:
        period = _get(p, "period")
        if period is None or period > 2:
            continue
        gid = _get(p, "gameId", "game_id")
        hs = _get(p, "homeScore", "home_score")
        as_ = _get(p, "awayScore", "away_score")
        if gid is None or hs is None or as_ is None:
            continue
        cur = best.get(gid)
        # Keep the largest combined running score within the half.
        if cur is None or (hs + as_) > (cur[0] + cur[1]):
            best[gid] = (int(hs), int(as_))
    return best


def attach_first_half(
    game: Dict[str, Any], pbp_lookup: Optional[Dict[int, Tuple[int, int]]] = None
) -> Dict[str, Any]:
    """Return a dict of the first-half columns to persist for one game.
    Prefers line scores; falls back to play-by-play if provided."""
    gid = _get(game, "id")
    res = first_half_from_line_scores(game)
    source = "linescores"
    if res is None and pbp_lookup and gid in pbp_lookup:
        res = pbp_lookup[gid]
        source = "pbp"
    if res is None:
        return {
            "home_first_half_points": None,
            "away_first_half_points": None,
            "first_half_total": None,
            "first_half_source": None,
        }
    home_1h, away_1h = res
    return {
        "home_first_half_points": home_1h,
        "away_first_half_points": away_1h,
        "first_half_total": home_1h + away_1h,
        "first_half_source": source,
    }
