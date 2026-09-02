"""Friday 1H sweep prioritisation.

The Odds API lists events chronologically and the free-tier sweep can afford
~18 per-event calls, so a plain `[:18]` captured Friday night + the Saturday
noon wave and never reached the evening games the card actually wants. Rank
the window by what makes a first-half under bettable — a Sunday-captured
spread inside the close band, outdoors, slow pace — then cap.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from .etl.match import match_event

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
