"""Derive ground-truth first-half points for each game.

Two paths, in order of preference:
  1. Per-quarter line scores from CFBD /games (light, reliable): 1H = Q1 + Q2.
  2. Play-by-play fallback: cumulative running score at the end of period 2,
     corroborated for a scoreless half by the feed reaching the stored final.

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


def _all_numbers(ls: Any) -> bool:
    return isinstance(ls, list) and len(ls) > 0 and all(isinstance(x, (int, float)) for x in ls)


def line_scores_trustworthy(game: Dict[str, Any], first_half: Tuple[int, int]) -> bool:
    """Guard against corrupt/placeholder line scores (e.g. all-zero quarters that
    yielded a real 27-point final). Reject when the quarter totals can't be
    reconciled with the final score. When the final score is unknown we can't
    check, so we trust the line scores.

    A 0-point first half in a game that scored is SUSPICIOUS, not invalid: a
    scoreless half is real football (Iowa-Northwestern 2023, Nebraska-Purdue 2024,
    SDSU-UCLA 2026 all finished with points after a 0-0 half). It is trusted only
    on evidence -- every quarter present as a number, at least four of them, and
    each side's quarters summing to its final. Anything short of that (a partial
    box, an in-progress placeholder) is rejected, and the PBP path gets its turn."""
    home_pts = _get(game, "homePoints", "home_points")
    away_pts = _get(game, "awayPoints", "away_points")
    home_1h, away_1h = first_half
    home_ls = _get(game, "homeLineScores", "home_line_scores")
    away_ls = _get(game, "awayLineScores", "away_line_scores")
    # Per-quarter totals must reconcile with the final score, when both are known.
    if home_pts is not None and _all_numbers(home_ls) and sum(home_ls) != home_pts:
        return False
    if away_pts is not None and _all_numbers(away_ls) and sum(away_ls) != away_pts:
        return False
    # A scoreless half once the game has points needs the full, reconciled box.
    final_total = (home_pts or 0) + (away_pts or 0)
    if (
        (home_pts is not None or away_pts is not None)
        and final_total > 0
        and (home_1h + away_1h) == 0
    ):
        return _full_box_reconciles(home_ls, home_pts) and _full_box_reconciles(away_ls, away_pts)
    return True


def _full_box_reconciles(ls: Any, pts: Any) -> bool:
    """Four or more numeric quarters whose sum is exactly the side's final."""
    return pts is not None and _all_numbers(ls) and len(ls) >= 4 and sum(ls) == pts


def _play_home_away_score(p: Dict[str, Any]) -> Tuple[Any, Any]:
    """Running (home, away) score for one play. CFBD /plays carries the score
    relative to the OFFENSE (offenseScore/defenseScore + offense/home team
    names); older shapes carried homeScore/awayScore directly — accept both."""
    hs = _get(p, "homeScore", "home_score")
    as_ = _get(p, "awayScore", "away_score")
    if hs is not None and as_ is not None:
        return hs, as_
    off_s = _get(p, "offenseScore", "offense_score")
    def_s = _get(p, "defenseScore", "defense_score")
    offense, home = _get(p, "offense"), _get(p, "home")
    if off_s is None or def_s is None or offense is None or home is None:
        return None, None
    return (off_s, def_s) if offense == home else (def_s, off_s)


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
        hs, as_ = _play_home_away_score(p)
        if gid is None or hs is None or as_ is None:
            continue
        cur = best.get(gid)
        # Keep the largest combined running score within the half.
        if cur is None or (hs + as_) > (cur[0] + cur[1]):
            best[gid] = (int(hs), int(as_))
    return best


def final_from_plays(plays: List[Dict[str, Any]]) -> Dict[int, Tuple[int, int]]:
    """Map game_id -> (home, away) running score on the LAST play of the game
    (every period, overtime included): the largest combined running score seen.
    Used to corroborate a play-by-play feed against the stored final -- a feed
    that never reaches the final is incomplete and cannot vouch for a 0-0 half."""
    best: Dict[int, Tuple[int, int]] = {}
    for p in plays:
        gid = _get(p, "gameId", "game_id")
        hs, as_ = _play_home_away_score(p)
        if gid is None or hs is None or as_ is None:
            continue
        cur = best.get(gid)
        if cur is None or (hs + as_) > (cur[0] + cur[1]):
            best[gid] = (int(hs), int(as_))
    return best


def attach_first_half(
    game: Dict[str, Any],
    pbp_lookup: Optional[Dict[int, Tuple[int, int]]] = None,
    pbp_final: Optional[Dict[int, Tuple[int, int]]] = None,
) -> Dict[str, Any]:
    """Return a dict of the first-half columns to persist for one game.
    Prefers line scores; falls back to play-by-play if provided.

    A play-by-play 0-0 half in a game that scored is persisted only when the same
    feed corroborates itself: `pbp_final[gid]` (see `final_from_plays`) must equal
    the stored final. A feed that stops short of the final is incomplete, and an
    incomplete feed's 0-0 is exactly the false zero this module exists to keep out
    of the ledger. With no `pbp_final` to check against, the zero is not trusted."""
    gid = _get(game, "id")
    res = first_half_from_line_scores(game)
    source = "linescores"
    # Reject line scores that disagree with the final score: fall through to PBP,
    # else leave NULL — never persist a false 0.
    if res is not None and not line_scores_trustworthy(game, res):
        res = None
    if res is None and pbp_lookup and gid in pbp_lookup:
        res = pbp_lookup[gid]
        source = "pbp"
        if res is not None and not _pbp_zero_corroborated(game, res, pbp_final):
            res = None
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


def _pbp_zero_corroborated(
    game: Dict[str, Any],
    first_half: Tuple[int, int],
    pbp_final: Optional[Dict[int, Tuple[int, int]]],
) -> bool:
    """True unless the PBP half is 0-0 in a game that scored AND the feed's own
    running score never reaches the stored final."""
    if (first_half[0] + first_half[1]) != 0:
        return True
    home_pts = _get(game, "homePoints", "home_points")
    away_pts = _get(game, "awayPoints", "away_points")
    if ((home_pts or 0) + (away_pts or 0)) == 0:
        return True  # 0-0 final (or unknown): nothing to contradict
    if not pbp_final:
        return False
    fin = pbp_final.get(_get(game, "id"))
    return fin is not None and fin == (int(home_pts or 0), int(away_pts or 0))
