"""Fetch + cache season-level team quality/efficiency stats (SP+ and advanced).

These are full-season aggregates, so to stay leak-free we only ever join a
season's stats to the *following* season's games (a stable preseason prior).
Raw responses are cached under data/cache/ to avoid refetching.
"""

from __future__ import annotations

import json
from typing import Dict, List

import pandas as pd

from ..config import REPO_ROOT
from .cfbd import CFBDClient

CACHE = REPO_ROOT / "data" / "cache"


def _cached_soft(name: str, fetch, what: str):
    """_cached, but a season whose stats cannot be fetched WARNS instead of
    killing the build.

    These are prior-season quality priors, and build_feature_frame asks for one
    per season in the games table -- which includes the CURRENT season, whose
    full-year aggregate does not exist yet and never will until it ends. Before
    the empty-payload guard above, that hole was papered over by a cached `[]`.
    With the guard, an unfetchable season would take down every feature build
    instead, which trades a silent wrong answer for a loud useless one.

    So: the rows for that season are simply absent, the merge leaves NaN, and the
    reason is printed once. Same trade backfill.py makes for venues (a reference
    failure warns; a season failure is fatal). An auth or quota problem shows up
    here as a warning per season rather than a stack trace, which is the honest
    shape -- the features are degraded, not broken."""
    try:
        return _cached(name, fetch)
    except Exception as e:  # noqa: BLE001 - reference data is best-effort
        print(f"::warning::{what}: {type(e).__name__}: {e} (features degraded for this season)")
        return []


def _cached(name: str, fetch):
    """Read-through cache with NO expiry -- these are finished-season aggregates,
    so a hit is permanently correct.

    Except when it is empty. A cache written for a season CFBD has not finished
    (or had not started) publishing stores `[]`, and `[]` is a hit forever: the
    file is 2 bytes, the fetch never runs again, and every column it feeds goes
    silently NaN. Measured 2026-09-13: data/cache/{sp,adv,talent,roster,
    returning}_2026.json were all 2 bytes, written 2026-06-03 before 2026 data
    existed, so a LOCAL 2026 feature build NaN'd out eight columns with no error
    and no log line. (GHA runners start cold and refetch, so this never reached
    production -- which is exactly why it went unnoticed for three months.)

    An empty payload is therefore treated as a MISS and refetched. If the fetch
    returns empty again nothing is written, so the next caller retries rather
    than inheriting the hole. The cost of being wrong in this direction is one
    repeated API call; in the other it is a season of quietly missing features."""
    CACHE.mkdir(parents=True, exist_ok=True)
    fp = CACHE / name
    if fp.exists():
        cached = json.loads(fp.read_text())
        if cached:
            return cached
    data = fetch()
    if data:
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
        data = _cached_soft(f"sp_{yr}.json", lambda yr=yr: client.sp_ratings(year=yr), f"SP+ {yr}")
        for r in data:
            team = _g(r, "team")
            if not team:
                continue
            off = _g(r, "offense") or {}
            de = _g(r, "defense") or {}
            rows.append(
                {
                    "season": _g(r, "year", "season"),
                    "team": team,
                    "sp_overall": _g(r, "rating"),
                    "sp_offense": _g(off, "rating"),
                    "sp_defense": _g(de, "rating"),
                }
            )
    # Keep the column schema when empty so prefixed merges in build_feature_frame
    # don't KeyError on missing join keys (thin/sandbox data).
    return pd.DataFrame(rows, columns=["season", "team", "sp_overall", "sp_offense", "sp_defense"])


def returning_frame(client: CFBDClient, seasons: List[int]) -> pd.DataFrame:
    """Returning production per (season, team) — the aggregate of roster churn
    (transfers in/out + departures). Known preseason, so joined on SAME season."""
    rows = []
    for yr in seasons:
        data = _cached_soft(
            f"returning_{yr}.json",
            lambda yr=yr: client._get("/player/returning", {"year": yr}),
            f"returning production {yr}",
        )
        for r in data:
            team = _g(r, "team")
            if not team:
                continue
            rows.append(
                {
                    "season": _g(r, "season", "year"),
                    "team": team,
                    "returning_ppa": _g(r, "percentPPA", "percent_ppa"),
                    "returning_pass_ppa": _g(r, "percentPassingPPA", "percent_passing_ppa"),
                    "returning_usage": _g(r, "returningUsage", "returning_usage"),
                }
            )
    return pd.DataFrame(
        rows,
        columns=["season", "team", "returning_ppa", "returning_pass_ppa", "returning_usage"],
    )


def talent_frame(client: CFBDClient, seasons: List[int]) -> pd.DataFrame:
    """Team talent composite per (season, team). Preseason-known -> SAME season."""
    rows = []
    for yr in seasons:
        data = _cached_soft(
            f"talent_{yr}.json", lambda yr=yr: client.talent(year=yr), f"talent {yr}"
        )
        for r in data:
            team = _g(r, "team")
            if not team:
                continue
            rows.append(
                {"season": _g(r, "year", "season"), "team": team, "talent": _g(r, "talent")}
            )
    return pd.DataFrame(rows, columns=["season", "team", "talent"])


def roster_experience_frame(client: CFBDClient, seasons: List[int]) -> pd.DataFrame:
    """Roster experience per (season, team): mean class year + upperclass share.

    Class `year` is 1 (FR) .. 4+ (SR), known preseason -> joined on SAME season.
    """
    rows = []
    for yr in seasons:
        data = _cached_soft(
            f"roster_{yr}.json", lambda yr=yr: client.roster(year=yr), f"roster {yr}"
        )
        df = pd.DataFrame(
            [
                {"team": _g(r, "team"), "yr": pd.to_numeric(_g(r, "year"), errors="coerce")}
                for r in data
            ]
        )
        if df.empty:
            continue
        # CFBD roster `year` is class 1(FR)..5; some rows carry a bad value (the
        # season, e.g. 2023) — keep only valid class years.
        df.loc[(df["yr"] < 1) | (df["yr"] > 5), "yr"] = pd.NA
        for team, g in df.dropna(subset=["team"]).groupby("team"):
            yrs = g["yr"].dropna()
            if yrs.empty:
                continue
            rows.append(
                {
                    "season": yr,
                    "team": team,
                    "roster_exp": round(float(yrs.mean()), 3),
                    "roster_upperclass": round(float((yrs >= 3).mean()), 3),
                }
            )
    return pd.DataFrame(rows, columns=["season", "team", "roster_exp", "roster_upperclass"])


def advanced_frame(client: CFBDClient, seasons: List[int]) -> pd.DataFrame:
    rows = []
    for yr in seasons:
        data = _cached_soft(
            f"adv_{yr}.json",
            lambda yr=yr: client.advanced_season_stats(year=yr),
            f"advanced stats {yr}",
        )
        for r in data:
            team = _g(r, "team")
            if not team:
                continue
            off = _g(r, "offense") or {}
            de = _g(r, "defense") or {}
            rows.append(
                {
                    "season": _g(r, "season", "year"),
                    "team": team,
                    "off_ppa": _g(off, "ppa"),
                    "def_ppa": _g(de, "ppa"),
                    "off_success": _g(off, "successRate", "success_rate"),
                    "def_success": _g(de, "successRate", "success_rate"),
                    "off_explosive": _g(off, "explosiveness"),
                    "def_explosive": _g(de, "explosiveness"),
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "season",
            "team",
            "off_ppa",
            "def_ppa",
            "off_success",
            "def_success",
            "off_explosive",
            "def_explosive",
        ],
    )
