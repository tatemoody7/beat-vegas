"""Full-game total + spread from CFBD /lines — a cloud-reliable opener source.

DraftKings' hidden API may 403 datacenter IPs (GitHub Actions), but CFBD is a
key-based API reachable from anywhere. This module turns CFBD /lines into the
SAME row shape `scripts/poll_full_game.py` consumes, so it's a drop-in fallback
for the DK capture path. Rows carry the CFBD game id directly (== Game.id), so
the poller can match by id without fuzzy name matching.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Provider priority for picking a single full-game line per game.
PROVIDER_PRIORITY = ["consensus", "DraftKings", "Bovada", "ESPN Bet", "William Hill (US)"]


def _get(d: Dict[str, Any], *names: str) -> Any:
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return None


def pick_total_spread(lines: List[Dict[str, Any]]
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


def full_game_rows(client, season: int, season_type: str = "regular"
                   ) -> List[Dict[str, Any]]:
    """Full-game total+spread rows from CFBD /lines, shaped like the DK rows
    `poll_full_game` consumes. Each row carries `game_id` (CFBD id == Game.id)."""
    rows: List[Dict[str, Any]] = []
    for g in client.lines(year=season, season_type=season_type):
        gid = _get(g, "id")
        ou, sp, prov = pick_total_spread(_get(g, "lines") or [])
        if gid is None or ou is None:
            continue
        rows.append({
            "game_id": gid,
            "event_id": str(gid),
            "commence_time": _get(g, "startDate", "start_date"),
            "home_team": _get(g, "homeTeam", "home_team"),
            "away_team": _get(g, "awayTeam", "away_team"),
            "book": prov or "cfbd",
            "line": float(ou),
            "spread": sp,
            "over_price": None,
            "under_price": None,
            "last_update": None,
        })
    return rows
