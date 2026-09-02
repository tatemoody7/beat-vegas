"""Full-game total + spread from CFBD /lines — a cloud-reliable opener source.

DraftKings' hidden API may 403 datacenter IPs (GitHub Actions), but CFBD is a
key-based API reachable from anywhere. This module turns CFBD /lines into the
SAME row shape `scripts/poll_full_game.py` consumes, so it's a drop-in fallback
for the DK capture path. Rows carry the CFBD game id directly (== Game.id), so
the poller can match by id without fuzzy name matching.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..hardrock import normalize_book

# Provider priority for picking a single full-game line per game.
PROVIDER_PRIORITY = ["consensus", "DraftKings", "Bovada", "ESPN Bet", "William Hill (US)"]

# "both" = regular season + bowls/playoff. Iterated as two explicit fetches
# (rather than CFBD's own `seasonType=both`) because postseason week numbers
# restart at 1 — callers that key anything by week must never see mixed types
# in one response without the season_type tag CFBD includes per game.
DEFAULT_SEASON_TYPE = "both"


def _season_types(season_type: str) -> Tuple[str, ...]:
    return ("regular", "postseason") if season_type == "both" else (season_type,)


def _get(d: Dict[str, Any], *names: str) -> Any:
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return None


def pick_total_spread(
    lines: List[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """(over_under, spread, provider) by provider priority, else first non-null.

    `spread` is CFBD's home-relative line (negative = home favored)."""
    by_provider: Dict[str, Tuple[float, Optional[float]]] = {}
    for ln in lines or []:
        ou = _get(ln, "overUnder", "over_under")
        prov = _get(ln, "provider")
        sp = _get(ln, "spread")
        if ou is not None and prov is not None and prov not in by_provider:
            by_provider[prov] = (float(ou), float(sp) if sp is not None else None)
    for prov in PROVIDER_PRIORITY:
        if prov in by_provider:
            ou, sp = by_provider[prov]
            return ou, sp, prov
    if by_provider:
        prov = next(iter(by_provider))
        ou, sp = by_provider[prov]
        return ou, sp, prov
    return None, None, None


def pick_open_close(
    lines: List[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """(opening_total, closing_total, provider) by provider priority.

    Opener = CFBD `overUnderOpen`; close = `overUnder`. Either may be missing for
    a given provider, in which case the present value backfills the other so a
    game with only one number is still usable. Used by the full-game backtest to
    simulate betting the Sunday opener and to measure opener->close CLV."""
    by_provider: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
    for ln in lines or []:
        prov = _get(ln, "provider")
        opn = _get(ln, "overUnderOpen", "over_under_open")
        close = _get(ln, "overUnder", "over_under")
        if prov is None or prov in by_provider or (opn is None and close is None):
            continue
        o = float(opn) if opn is not None else float(close)
        c = float(close) if close is not None else float(opn)
        by_provider[prov] = (o, c)
    for prov in PROVIDER_PRIORITY:
        if prov in by_provider:
            o, c = by_provider[prov]
            return o, c, prov
    if by_provider:
        prov = next(iter(by_provider))
        o, c = by_provider[prov]
        return o, c, prov
    return None, None, None


def open_close_lookup(
    client, season: int, season_type: str = DEFAULT_SEASON_TYPE
) -> Dict[int, Tuple[float, float, str]]:
    """{game_id: (open_total, close_total, provider)} for a season from CFBD /lines.

    game_id is the CFBD id (== Game.id), so callers can join by id without fuzzy
    name matching. Games with no usable total are omitted."""
    out: Dict[int, Tuple[float, float, str]] = {}
    for st in _season_types(season_type):
        for g in client.lines(year=season, season_type=st):
            gid = _get(g, "id")
            if gid is None:
                continue
            o, c, prov = pick_open_close(_get(g, "lines") or [])
            if o is None:
                continue
            out[int(gid)] = (o, c, prov or "cfbd")
    return out


def full_game_rows(
    client, season: int, season_type: str = DEFAULT_SEASON_TYPE
) -> List[Dict[str, Any]]:
    """Full-game total+spread rows from CFBD /lines, shaped like the DK rows
    `poll_full_game` consumes. Each row carries `game_id` (CFBD id == Game.id).

    `line` is CFBD's CURRENT number (drifts toward the close as the week goes
    on); `line_open` is the same provider's `overUnderOpen` when present. The
    poller uses `line_open` for a game's FIRST snapshot so the CFBD fallback
    doesn't mislabel a closing number as the opener (that corrupts open->close
    CLV, the core edge measurement)."""
    rows: List[Dict[str, Any]] = []
    for st in _season_types(season_type):
        rows.extend(_full_game_rows_one_type(client, season, st))
    return rows


def _full_game_rows_one_type(client, season: int, season_type: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for g in client.lines(year=season, season_type=season_type):
        gid = _get(g, "id")
        lines = _get(g, "lines") or []
        ou, sp, prov = pick_total_spread(lines)
        if gid is None or ou is None:
            continue
        opn = None
        for ln in lines:
            if _get(ln, "provider") == prov:
                raw_open = _get(ln, "overUnderOpen", "over_under_open")
                opn = float(raw_open) if raw_open is not None else None
                break
        rows.append(
            {
                "game_id": gid,
                "event_id": str(gid),
                "commence_time": _get(g, "startDate", "start_date"),
                "home_team": _get(g, "homeTeam", "home_team"),
                "away_team": _get(g, "awayTeam", "away_team"),
                "book": normalize_book(prov or "cfbd"),  # "DraftKings" -> "draftkings"
                "line": float(ou),
                "line_open": opn,
                "spread": sp,
                "over_price": None,
                "under_price": None,
                "last_update": None,
            }
        )
    return rows
