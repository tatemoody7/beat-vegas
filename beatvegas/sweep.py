"""1H sweep window, universe filters and (legacy) prioritisation.

On the paid Odds API tier (2026-09) the sweep captures EVERY Hard Rock first-half
line, so the window helpers matter more than the ranking: `select_window` picks
the events a slot should touch (a days-ahead opener sweep, or the games kicking
off within N minutes for a per-game close), `filter_hr_universe` keeps the games
Hard Rock has priced a full-game total on (the only bettable universe from
Florida), and `filter_missing_hr` lets the opener sweep stop paying for a game
once Hard Rock's 1H line is captured. `rank_events` still orders the window by
bettability so a capped or credit-limited run spends on the right games first.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .etl.match import _parse_dt, match_event

CLOSE_SPREAD = 14.0  # |spread| <= 14: the card's "not a blowout" band


def build_context(
    events: List[Dict[str, Any]],
    games: List[Dict[str, Any]],
    dome_by_game: Dict[int, Optional[bool]],
    pace_by_team: Dict[str, float],
) -> Dict[str, Dict[str, Any]]:
    """event id -> {game_id, spread, dome, pace} for events that match a game.

    `games` rows need id/home_team/away_team/start_date/spread; pace is the mean
    of both teams' seconds-per-play, None unless both are known."""
    by_id = {g["id"]: g for g in games}
    ctx: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        gid, _ = match_event(ev["home_team"], ev["away_team"], ev.get("commence_time"), games)
        if gid is None:
            continue
        g = by_id[gid]
        ph, pa = pace_by_team.get(g["home_team"]), pace_by_team.get(g["away_team"])
        pace = round((ph + pa) / 2, 2) if ph is not None and pa is not None else None
        ctx[ev["id"]] = {
            "game_id": gid,
            "spread": g.get("spread"),
            "dome": dome_by_game.get(gid),
            "pace": pace,
        }
    return ctx


def _spread_band(spread: Optional[float]) -> int:
    if spread is None:
        return 2
    return 0 if abs(spread) <= CLOSE_SPREAD else 1


def rank_events(
    events: List[Dict[str, Any]],
    ctx: Dict[str, Dict[str, Any]],
    max_events: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Close spread > wide > no spread; outdoor > dome; slower pace first;
    kickoff order breaks ties. Events with no matched game go last."""

    def key(ev: Dict[str, Any]) -> Tuple[int, int, float, str]:
        c = ctx.get(ev["id"])
        when = ev.get("commence_time") or ""
        if c is None:
            return (3, 1, float("inf"), when)
        pace = c.get("pace")
        return (
            _spread_band(c.get("spread")),
            1 if c.get("dome") else 0,
            -pace if pace is not None else float("inf"),
            when,
        )

    ranked = sorted(events, key=key)
    return ranked[:max_events] if max_events else ranked


def latest_pace_by_team(rows: Iterable[Tuple[int, int, str, Optional[float]]]) -> Dict[str, float]:
    """team -> most recent non-null seconds_per_play from (season, week, team,
    seconds_per_play) rows, any order. Week-1 rows are null (season not started),
    so this falls back to last season's final number."""
    best: Dict[str, Tuple[Tuple[int, int], float]] = {}
    for season, week, team, spp in rows:
        if spp is None:
            continue
        stamp = (season, week or 0)
        cur = best.get(team)
        if cur is None or stamp > cur[0]:
            best[team] = (stamp, float(spp))
    return {t: v for t, (_, v) in best.items()}


def select_window(
    events: List[Dict[str, Any]],
    now: datetime,
    *,
    days_ahead: int,
    hours_back: float,
    kickoff_within_min: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Events with now - hours_back <= kickoff <= horizon, where horizon is
    now + kickoff_within_min (per-game CLOSE mode) or now + days_ahead (sweep).
    Events whose kickoff cannot be parsed are kept (the matcher decides later)."""
    lo = now - timedelta(hours=hours_back)
    if kickoff_within_min is not None:
        hi = now + timedelta(minutes=kickoff_within_min)
    else:
        hi = now + timedelta(days=days_ahead)
    out = []
    for ev in events:
        dt = _parse_dt(ev.get("commence_time"))
        if dt is None or lo <= dt <= hi:
            out.append(ev)
    return out


def filter_missing_hr(
    events: List[Dict[str, Any]],
    ctx: Dict[str, Dict[str, Any]],
    games_with_hr_1h: Set[int],
) -> List[Dict[str, Any]]:
    """Opener mode: drop events whose matched game already has a Hard Rock 1H
    snapshot, so a game is paid for once until the close slots take over."""
    out = []
    for ev in events:
        c = ctx.get(ev["id"])
        if c is not None and c["game_id"] in games_with_hr_1h:
            continue
        out.append(ev)
    return out


def filter_hr_universe(
    events: List[Dict[str, Any]],
    ctx: Dict[str, Dict[str, Any]],
    hr_universe: Set[int],
) -> Tuple[List[Dict[str, Any]], bool]:
    """Keep events matched to a game Hard Rock has priced a full-game total on.
    Returns (events, used_fallback): when the universe is EMPTY (the Sunday
    capture was dropped) every event is returned and used_fallback is True so
    the caller warns loudly instead of sweeping nothing."""
    if not hr_universe:
        return list(events), True
    kept = []
    for ev in events:
        c = ctx.get(ev["id"])
        if c is not None and c["game_id"] in hr_universe:
            kept.append(ev)
    return kept, False
