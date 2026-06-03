"""Best-effort college-football news + injuries from ESPN's undocumented API.

DISPLAY CONTEXT ONLY — never a model feature. The API is unofficial (can change
without notice) and CFB injury reporting is unreliable, so every call fails silent
(returns empty) rather than raising. Results are cached by the dashboard.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import requests

from ..config import REPO_ROOT
from ..etl.match import name_score

_UA = {"User-Agent": "Mozilla/5.0"}
_SITE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
_CORE = ("https://sports.core.api.espn.com/v2/sports/football/leagues/"
         "college-football")
_CACHE = REPO_ROOT / "data" / "cache"


def _get(url: str, params: Optional[dict] = None, timeout: int = 12):
    try:
        r = requests.get(url, params=params or {}, headers=_UA, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def _teams() -> List[dict]:
    """Cached ESPN team list (id, location, displayName)."""
    fp = _CACHE / "espn_teams.json"
    if fp.exists():
        return json.loads(fp.read_text())
    data = _get(f"{_SITE}/teams", {"limit": 1000})
    out = []
    if data:
        try:
            for t in data["sports"][0]["leagues"][0]["teams"]:
                tm = t["team"]
                out.append({"id": tm["id"], "location": tm.get("location", ""),
                            "displayName": tm.get("displayName", "")})
        except (KeyError, IndexError, TypeError):
            out = []
    if out:
        _CACHE.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps(out))
    return out


def espn_team_id(school: str, min_score: float = 0.8) -> Optional[str]:
    best, best_s = None, 0.0
    for t in _teams():
        s = max(name_score(school, t["location"]), name_score(school, t["displayName"]))
        if s > best_s:
            best, best_s = t["id"], s
    return best if best_s >= min_score else None


def team_news(espn_id: str, limit: int = 4) -> List[str]:
    data = _get(f"{_SITE}/news", {"team": espn_id, "limit": limit})
    if not data:
        return []
    return [a.get("headline", "") for a in data.get("articles", []) if a.get("headline")]


def team_injuries(espn_id: str, limit: int = 6) -> List[str]:
    data = _get(f"{_CORE}/teams/{espn_id}/injuries", {"limit": limit})
    if not data or not data.get("items"):
        return []
    out = []
    for item in data["items"][:limit]:
        try:
            if "$ref" in item:
                item = _get(item["$ref"]) or {}
            status = (item.get("status")
                      or (item.get("type") or {}).get("description") or "")
            ath = item.get("athlete") or {}
            if "$ref" in ath:
                ath = _get(ath["$ref"]) or {}
            name = ath.get("displayName") or ath.get("shortName") or "Player"
            pos = ((ath.get("position") or {}).get("abbreviation") or "")
            label = f"{pos + ' ' if pos else ''}{name}"
            out.append(f"{label} — {status}" if status else label)
        except (KeyError, TypeError, AttributeError):
            continue
    return out


_OUT_STATUSES = ("out", "doubtful", "injured reserve", "season")


def _qb_out_from_injuries(injuries: List[str]) -> Optional[str]:
    """Given team_injuries() strings ('QB Name — Out'), return the detail string
    if a QB is listed Out/Doubtful, else None. Heuristic + unofficial."""
    for inj in injuries:
        low = inj.lower()
        is_qb = low.startswith("qb ") or " qb " in low.split("—")[0].lower()
        if is_qb and any(st in low for st in _OUT_STATUSES):
            return inj
    return None


def qb_out_flags(home_school: str, away_school: str) -> Dict[str, object]:
    """Forward-only 'starting QB out' flag per side from live ESPN injuries.

    DISPLAY ONLY, unofficial, fail-silent. Returns
    {"home": bool, "away": bool, "detail": str}. Never used as a model feature
    and never backfilled (no historical injury data exists)."""
    out = {"home": False, "away": False, "detail": ""}
    details = []
    try:
        for side, school in (("home", home_school), ("away", away_school)):
            eid = espn_team_id(school)
            if not eid:
                continue
            d = _qb_out_from_injuries(team_injuries(eid))
            if d:
                out[side] = True
                details.append(f"{school}: {d}")
    except Exception:  # noqa: BLE001 — unofficial source, never break scoring
        return {"home": False, "away": False, "detail": ""}
    out["detail"] = " · ".join(details)
    return out


def game_context(home_school: str, away_school: str) -> Dict[str, Dict[str, List[str]]]:
    """News + injuries for both teams (each may be empty)."""
    ctx = {}
    for side, school in (("home", home_school), ("away", away_school)):
        eid = espn_team_id(school)
        ctx[side] = {
            "school": school,
            "news": team_news(eid) if eid else [],
            "injuries": team_injuries(eid) if eid else [],
        }
    return ctx
