"""Fetch + cache season-level team quality/efficiency stats (SP+ and advanced).

These are full-season aggregates, so to stay leak-free we only ever join a
season's stats to the *following* season's games (a stable preseason prior).
Raw responses are cached under data/cache/ to avoid refetching.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

from ..config import REPO_ROOT
from .cfbd import CFBDClient

CACHE = REPO_ROOT / "data" / "cache"


def _cached(name: str, fetch):
    CACHE.mkdir(parents=True, exist_ok=True)
    fp = CACHE / name
    if fp.exists():
        return json.loads(fp.read_text())
    data = fetch()
    fp.write_text(json.dumps(data))
    return data


def _g(d: Dict, *names):
    for n in names:
        if isinstance(d, dict) and d.get(n) is not None:
            return d[n]
    return None


def sp_frame(client: CFBDClient, seasons: List[int]) -> pd.DataFrame:
    rows = []
    for yr in seasons:
        data = _cached(f"sp_{yr}.json", lambda yr=yr: client.sp_ratings(year=yr))
        for r in data:
            team = _g(r, "team")
            if not team:
                continue
            off = _g(r, "offense") or {}
            de = _g(r, "defense") or {}
            rows.append({
                "season": _g(r, "year", "season"), "team": team,
                "sp_overall": _g(r, "rating"),
                "sp_offense": _g(off, "rating"),
                "sp_defense": _g(de, "rating"),
            })
    return pd.DataFrame(rows)


def returning_frame(client: CFBDClient, seasons: List[int]) -> pd.DataFrame:
    """Returning production per (season, team) — the aggregate of roster churn
    (transfers in/out + departures). Known preseason, so joined on SAME season."""
    rows = []
    for yr in seasons:
        data = _cached(
            f"returning_{yr}.json",
            lambda yr=yr: client._get("/player/returning", {"year": yr}))
        for r in data:
            team = _g(r, "team")
            if not team:
                continue
            rows.append({
                "season": _g(r, "season", "year"), "team": team,
                "returning_ppa": _g(r, "percentPPA", "percent_ppa"),
                "returning_pass_ppa": _g(r, "percentPassingPPA", "percent_passing_ppa"),
                "returning_usage": _g(r, "returningUsage", "returning_usage"),
            })
    return pd.DataFrame(rows)


def advanced_frame(client: CFBDClient, seasons: List[int]) -> pd.DataFrame:
    rows = []
    for yr in seasons:
        data = _cached(f"adv_{yr}.json",
                       lambda yr=yr: client.advanced_season_stats(year=yr))
        for r in data:
            team = _g(r, "team")
            if not team:
                continue
            off = _g(r, "offense") or {}
            de = _g(r, "defense") or {}
            rows.append({
                "season": _g(r, "season", "year"), "team": team,
                "off_ppa": _g(off, "ppa"),
                "def_ppa": _g(de, "ppa"),
                "off_success": _g(off, "successRate", "success_rate"),
                "def_success": _g(de, "successRate", "success_rate"),
                "off_explosive": _g(off, "explosiveness"),
                "def_explosive": _g(de, "explosiveness"),
            })
    return pd.DataFrame(rows)
