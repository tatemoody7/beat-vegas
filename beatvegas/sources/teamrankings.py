"""Scrape pace/tempo from TeamRankings and map team names to CFBD schools.

TeamRankings exposes per-stat HTML tables (parseable with pandas.read_html) and
supports an `?date=YYYY-MM-DD` param that returns season-to-date values *as of*
that date — which keeps historical features leak-free.

Team names use abbreviations ("S Florida", "Ohio St", "Miami (FL)"), so we expand
common patterns, then take an EXACT match against the CFBD school list, and only
fall back to fuzzy matching when there is none. Fuzzy-first was the 2025 bug:
`name_score` treats a school that is a prefix of the source name as a perfect
match (built for "Kansas Jayhawks"), so "Kansas St" scored 1.0 for BOTH Kansas
and Kansas State and the first one scanned won — 136 TeamRankings rows became
110 stored teams, and Mississippi State carried Ole Miss's numbers.
"""

from __future__ import annotations

import io
import re
from typing import Dict, List, Optional

import pandas as pd
import requests

from ..etl.match import _norm, name_score

_UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}
_BASE = "https://www.teamrankings.com/college-football/stat"

# Directional / common abbreviations TeamRankings uses.
_PREFIX = {
    "N ": "North ",
    "S ": "South ",
    "E ": "East ",
    "W ": "West ",
    "C ": "Central ",
    "St ": "State ",
}

# Exact aliases (TeamRankings name -> CFBD school) for names that expansion
# alone can't resolve. Values must be the CFBD spelling in the `teams` table.
_ALIASES = {
    "UMass": "Massachusetts",
    "Southern Miss": "Southern Miss",
    "App State": "App State",
    "Hawaii": "Hawai'i",
    "Miami (FL)": "Miami",
    "Miami FL": "Miami",
    "Miami (OH)": "Miami (OH)",
    "Miami OH": "Miami (OH)",
    "Mississippi": "Ole Miss",  # TeamRankings' name for Ole Miss
    "Florida Intl": "Florida International",
    "Middle Tenn": "Middle Tennessee",
    "Middle Tennessee": "Middle Tennessee",
    "Georgia So": "Georgia Southern",
    "Coastal Car": "Coastal Carolina",
    "J Madison": "James Madison",
    "N Illinois": "Northern Illinois",
    "San Jose St": "San José State",
}


def _fetch_stat(stat: str, date: Optional[str], timeout: int = 30) -> pd.DataFrame:
    url = f"{_BASE}/{stat}"
    params = {"date": date} if date else {}
    r = requests.get(url, params=params, headers=_UA, timeout=timeout)
    r.raise_for_status()
    return pd.read_html(io.StringIO(r.text))[0]


def _season_col(df: pd.DataFrame) -> str:
    """The 4-digit-year column = season-to-date average."""
    yrs = [c for c in df.columns if re.fullmatch(r"\d{4}", str(c))]
    return yrs[0] if yrs else df.columns[2]  # leftmost year, else 3rd col


def fetch_tempo(date: Optional[str] = None) -> pd.DataFrame:
    """Return DataFrame: tr_team, seconds_per_play, plays_per_game."""
    spp = _fetch_stat("seconds-per-play", date)
    ppg = _fetch_stat("plays-per-game", date)
    spp = spp.rename(columns={"Team": "tr_team", _season_col(spp): "seconds_per_play"})
    ppg = ppg.rename(columns={"Team": "tr_team", _season_col(ppg): "plays_per_game"})
    out = spp[["tr_team", "seconds_per_play"]].merge(
        ppg[["tr_team", "plays_per_game"]], on="tr_team", how="outer"
    )
    for c in ("seconds_per_play", "plays_per_game"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _expand(name: str) -> str:
    s = str(name).strip()
    if s in _ALIASES:
        return _ALIASES[s]
    for ab, full in _PREFIX.items():
        if s.startswith(ab):
            s = full + s[len(ab) :]
    s = re.sub(r"\bSt\b", "State", s)  # "Ohio St" -> "Ohio State"
    s = re.sub(r"\s*\((FL|OH|PA|CA|TX)\)", lambda m: " " + m.group(1), s)  # Miami (FL)
    return s


def map_to_cfbd(
    tr_names: List[str], cfbd_teams: List[str], min_score: float = 0.78
) -> Dict[str, Optional[str]]:
    """Best CFBD school for each TeamRankings name (None if no confident match).

    Exact match on the expanded name first (normalised: case/punctuation-blind),
    then fuzzy. Fuzzy ties go to the LONGER school name, so a prefix school
    ("Kansas") never beats the full one ("Kansas State")."""
    by_key: Dict[str, str] = {}
    for school in cfbd_teams:
        by_key.setdefault(_norm(school), school)

    mapping: Dict[str, Optional[str]] = {}
    for tr in tr_names:
        expanded = _expand(tr)
        exact = by_key.get(_norm(expanded)) or by_key.get(_norm(tr))
        if exact:
            mapping[tr] = exact
            continue
        best, best_s = None, 0.0
        for school in cfbd_teams:
            s = max(name_score(school, expanded), name_score(school, tr))
            if s > best_s or (s == best_s and best is not None and len(school) > len(best)):
                best, best_s = school, s
        mapping[tr] = best if best_s >= min_score else None
    return mapping
