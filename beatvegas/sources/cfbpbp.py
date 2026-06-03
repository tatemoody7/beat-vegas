"""Play-by-play loader, normalized across two free sources.

- 2002-2021: bulk parquet from the sportsdataverse/cfbfastR-data repo (free, no
  API rate limit). Cached under data/pbp_cache/.
- 2022+: CFBD /plays (the parquet repo stops at 2021). ~15 calls/season.

Both are normalized to ONE per-play schema so the 1H aggregation in
etl/fh_factors.py is source-agnostic. We deliberately recompute success
(EPA>0) and explosiveness (yards>=15) ourselves rather than trust each source's
precomputed flags, so the definitions are identical across eras.

We never match team *names* across sources: each play carries `is_home_off`
(was the offense the home team), and the backfill attaches our own canonical
team names from the games table by game_id. Game ids are the shared ESPN id.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config import REPO_ROOT
from .cfbd import CFBDClient

PBP_CACHE = REPO_ROOT / "data" / "pbp_cache"
_PARQUET_URL = ("https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/"
                "main/pbp/parquet/play_by_play_{year}.parquet")
PARQUET_MAX_YEAR = 2021         # repo coverage ceiling; >this uses CFBD

# Normalized columns every loader returns.
NORM_COLS = ["game_id", "period", "is_home_off", "epa", "yards", "down",
             "distance", "is_pass", "scoring", "is_to", "is_havoc",
             "yte", "is_td", "is_special", "drive_key", "play_order"]

EXPLOSIVE_YDS = 15              # yards threshold for an explosive play


def _col(df: pd.DataFrame, name: str):
    return df[name] if name in df.columns else pd.Series(np.nan, index=df.index)


def load_parquet_season(season: int, download: bool = True) -> pd.DataFrame:
    """Raw cfbfastR parquet for a season (cached locally)."""
    PBP_CACHE.mkdir(parents=True, exist_ok=True)
    fp = PBP_CACHE / f"play_by_play_{season}.parquet"
    if not fp.exists():
        if not download:
            raise FileNotFoundError(fp)
        url = _PARQUET_URL.format(year=season)
        pd.read_parquet(url).to_parquet(fp)
    return pd.read_parquet(fp)


def _boolnum(df: pd.DataFrame, name: str) -> pd.Series:
    """A cfbfastR boolean column -> 0/1 float (missing -> 0)."""
    return _col(df, name).astype("boolean").astype("float64").fillna(0.0)


def normalize_cfbfastr(df: pd.DataFrame) -> pd.DataFrame:
    # pos_team is a team *id* here; use the ready `is_home` / `scrimmage_play`
    # / `havoc` booleans cfbfastR already provides.
    yards = pd.to_numeric(_col(df, "statYardage"), errors="coerce")
    turnover = _boolnum(df, "turnover_vec")
    sack = _boolnum(df, "sack")
    tfl = _boolnum(df, "TFL")
    out = pd.DataFrame({
        "game_id": pd.to_numeric(_col(df, "game_id"), errors="coerce"),
        "period": pd.to_numeric(_col(df, "period"), errors="coerce"),
        "is_home_off": _boolnum(df, "is_home"),
        "epa": pd.to_numeric(_col(df, "EPA"), errors="coerce"),
        "yards": yards,
        "down": pd.to_numeric(_col(df, "start.down"), errors="coerce"),
        "distance": pd.to_numeric(_col(df, "start.distance"), errors="coerce"),
        "is_pass": _boolnum(df, "pass"),
        "scoring": _boolnum(df, "scoringPlay"),
        "is_to": turnover,
        "yte": pd.to_numeric(_col(df, "start.yardsToEndzone"), errors="coerce"),
        "is_td": ((_boolnum(df, "rush_td") > 0) | (_boolnum(df, "pass_td") > 0)).astype(float),
        "is_special": ((_boolnum(df, "punt") > 0) | (_boolnum(df, "fg_attempt") > 0)).astype(float),
        "drive_key": _col(df, "drive.id").astype("string"),
        "play_order": pd.to_numeric(_col(df, "game_play_number"), errors="coerce"),
    })
    out["is_havoc"] = (((turnover > 0) | (sack > 0) | (tfl > 0)).astype(float))
    out["_is_scrim"] = _boolnum(df, "scrimmage_play")
    return out


_CFBD_TO = ("Interception", "Fumble Recovery (Opponent)", "Fumble Return")
_CFBD_PASS = ("Pass", "Sack", "Interception")
_CFBD_RUSH = ("Rush",)


def normalize_cfbd(plays: List[dict]) -> pd.DataFrame:
    df = pd.DataFrame(plays)
    if df.empty:
        return pd.DataFrame(columns=NORM_COLS + ["_is_scrim"])
    pt = _col(df, "playType").astype("string").fillna("")
    yards = pd.to_numeric(_col(df, "yardsGained"), errors="coerce")
    is_pass = pt.str.contains("|".join(_CFBD_PASS), case=False, regex=True)
    is_rush = pt.str.startswith("Rush") | pt.str.contains("Rushing", case=False)
    turnover = pt.apply(lambda s: any(k in s for k in _CFBD_TO))
    sack = pt.str.contains("Sack", case=False)
    is_td = pt.isin(["Rushing Touchdown", "Passing Touchdown"])
    is_special = pt.str.contains("Punt", case=False) | pt.str.contains("Field Goal", case=False)
    out = pd.DataFrame({
        "game_id": pd.to_numeric(_col(df, "gameId"), errors="coerce"),
        "period": pd.to_numeric(_col(df, "period"), errors="coerce"),
        "is_home_off": (_col(df, "offense").astype("string")
                        == _col(df, "home").astype("string")).astype(float),
        "epa": pd.to_numeric(_col(df, "ppa"), errors="coerce"),
        "yards": yards,
        "down": pd.to_numeric(_col(df, "down"), errors="coerce"),
        "distance": pd.to_numeric(_col(df, "distance"), errors="coerce"),
        "is_pass": is_pass.astype(float),
        "scoring": pd.to_numeric(_col(df, "scoring"), errors="coerce").fillna(0),
        "is_to": turnover.astype(float),
        "yte": pd.to_numeric(_col(df, "yardsToGoal"), errors="coerce"),
        "is_td": is_td.astype(float),
        "is_special": is_special.astype(float),
        "drive_key": _col(df, "driveId").astype("string"),
        "play_order": pd.to_numeric(_col(df, "playNumber"), errors="coerce"),
    })
    is_scrim = is_pass | is_rush
    out["is_havoc"] = ((turnover | sack | (is_rush & (yards < 0))).astype(float))
    out["_is_scrim"] = is_scrim.astype(float)
    return out


def load_plays(season: int, client: Optional[CFBDClient] = None,
               weeks: int = 20) -> pd.DataFrame:
    """Normalized plays for a season from whichever free source covers it."""
    if season <= PARQUET_MAX_YEAR:
        return normalize_cfbfastr(load_parquet_season(season))
    client = client or CFBDClient()
    frames = []
    for wk in range(1, weeks + 1):
        try:
            plays = client.plays(year=season, week=wk)
        except Exception:
            continue
        if plays:
            frames.append(normalize_cfbd(plays))
    if not frames:
        return pd.DataFrame(columns=NORM_COLS + ["_is_scrim"])
    return pd.concat(frames, ignore_index=True)
