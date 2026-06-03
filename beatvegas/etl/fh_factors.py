"""First-half (period<=2) factor computation from normalized play-by-play.

Two stages:
  1. aggregate_fh(plays) -> per (game, offense-side) 1H offensive aggregates
     (what the backfill stores in fh_team_game).
  2. fh_factor_frame() -> reads fh_team_game and builds leak-free season-to-date
     offense + defense-allowed factors per game, exactly like the existing
     fh_pf/fh_pa season-to-date pattern in features.py (shift(1) expanding mean).
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from ..db.models import FhTeamGame, Game
from ..db.store import session_scope

# Offensive-perspective metrics stored per (game, off_team).
FH_METRICS: List[str] = [
    "epa", "success", "explosive", "pass_rate", "early_success", "third_conv",
    "havoc_suffered", "turnovers", "n_plays", "opening_score", "opening_3out",
    "redzone_td", "fourth_go",
]


def _redzone_td(group: pd.DataFrame) -> float:
    """Fraction of 1H red-zone drives (reached yte<=20) that scored a TD."""
    d = group.dropna(subset=["drive_key"])
    if d.empty:
        return np.nan
    rz = rz_td = 0
    for _, dr in d.groupby("drive_key"):
        if dr["yte"].min() <= 20:
            rz += 1
            if dr["is_td"].max() > 0:
                rz_td += 1
    return (rz_td / rz) if rz else np.nan


def _fourth_go(group: pd.DataFrame) -> float:
    """4th-down go-for-it rate = scrimmage 4th downs / (scrimmage + punt/FG)."""
    f = group[group["down"] == 4]
    att = f[(f["_is_scrim"] == 1) | (f["is_special"] == 1)]
    if len(att) == 0:
        return np.nan
    return float((f["_is_scrim"] == 1).sum()) / len(att)


def _opening(group: pd.DataFrame) -> tuple:
    """(opening_score, opening_3out) for one team's first 1H drive."""
    g = group.dropna(subset=["drive_key"])
    if g.empty:
        return (np.nan, np.nan)
    first_drive = g.sort_values("play_order").iloc[0]["drive_key"]
    d = g[g["drive_key"] == first_drive]
    scored = int(d["scoring"].max() > 0)
    n_scrim = int(d["_is_scrim"].sum())
    three_out = int((n_scrim <= 3) and not scored)
    return (scored, three_out)


def aggregate_fh(plays: pd.DataFrame) -> pd.DataFrame:
    """Per (game_id, is_home_off) first-half offensive aggregates."""
    fh = plays[plays["period"] <= 2].copy()
    rows = []
    for (gid, ishome), g in fh.groupby(["game_id", "is_home_off"]):
        scrim = g[g["_is_scrim"] == 1]
        n = len(scrim)
        early = scrim[scrim["down"].isin([1, 2])]
        third = scrim[scrim["down"] == 3]
        opening_score, opening_3out = _opening(g)
        rows.append({
            "game_id": int(gid), "is_home_off": int(ishome),
            "n_plays": n,
            "epa": scrim["epa"].mean() if n else np.nan,
            "success": (scrim["epa"] > 0).mean() if n else np.nan,
            "explosive": (scrim["yards"] >= 15).mean() if n else np.nan,
            "pass_rate": scrim["is_pass"].mean() if n else np.nan,
            "early_success": (early["epa"] > 0).mean() if len(early) else np.nan,
            "third_conv": (third["yards"] >= third["distance"]).mean() if len(third) else np.nan,
            "havoc_suffered": scrim["is_havoc"].mean() if n else np.nan,
            "turnovers": float(g["is_to"].sum()),
            "opening_score": opening_score,
            "opening_3out": opening_3out,
            "redzone_td": _redzone_td(g),
            "fourth_go": _fourth_go(g),
        })
    return pd.DataFrame(rows)


def _std(long: pd.DataFrame, metrics: List[str], prefix: str) -> pd.DataFrame:
    """Season-to-date expanding mean (shift(1), prior games only) per team."""
    long = long.sort_values(["season", "team", "week", "start_date"],
                            na_position="last")
    grp = long.groupby(["season", "team"], sort=False)
    out = long[["game_id", "team"]].copy()
    for m in metrics:
        out[f"{prefix}{m}"] = grp[m].transform(
            lambda s: s.shift(1).expanding().mean())
    return out


def fh_factor_frame() -> pd.DataFrame:
    """One row per game id with leak-free season-to-date 1H factors.

    Columns: home_fh_off_<m>, away_fh_off_<m> (the team's own offense) and
    home_fh_def_<m>, away_fh_def_<m> (what the team's defense ALLOWED), for each
    metric in FH_METRICS. Empty frame (just `id`) if fh_team_game is unpopulated.
    """
    with session_scope() as s:
        fh = pd.DataFrame(
            s.query(FhTeamGame.game_id, FhTeamGame.season, FhTeamGame.week,
                    FhTeamGame.off_team, FhTeamGame.def_team,
                    *[getattr(FhTeamGame, m) for m in FH_METRICS]).all(),
            columns=["game_id", "season", "week", "off_team", "def_team"] + FH_METRICS)
        games = pd.DataFrame(
            s.query(Game.id, Game.start_date, Game.home_team, Game.away_team).all(),
            columns=["game_id", "start_date", "home_team", "away_team"])
    if fh.empty:
        return pd.DataFrame({"id": []})

    fh = fh.merge(games[["game_id", "start_date"]], on="game_id", how="left")
    for m in FH_METRICS:
        fh[m] = pd.to_numeric(fh[m], errors="coerce")

    # Offense long: the offense team's own metrics. Defense long: attribute the
    # same offensive metrics to the DEFENDING team (what it allowed).
    off_long = fh.rename(columns={"off_team": "team"})
    def_long = fh.rename(columns={"def_team": "team"})
    off_std = _std(off_long, FH_METRICS, "off_")
    def_std = _std(def_long, FH_METRICS, "def_")

    out = games[["game_id", "home_team", "away_team"]].rename(columns={"game_id": "id"})
    for side, tcol in (("home", "home_team"), ("away", "away_team")):
        o = off_std.rename(columns={"game_id": "id", "team": tcol})
        o = o.rename(columns={c: f"{side}_fh_{c}" for c in o.columns
                              if c.startswith("off_")})
        out = out.merge(o, on=["id", tcol], how="left")
        d = def_std.rename(columns={"game_id": "id", "team": tcol})
        d = d.rename(columns={c: f"{side}_fh_{c}" for c in d.columns
                              if c.startswith("def_")})
        out = out.merge(d, on=["id", tcol], how="left")
    return out.drop(columns=["home_team", "away_team"])
