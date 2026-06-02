"""Schedule-derived situational features — rest, travel, time zone, kickoff hour.

All are knowable before kickoff and computable for every historical game from the
`games` + `venues` tables (no new data source), so they're real model inputs. Fits
the slow-start thesis: early kickoffs + long westward travel tend to dampen first
halves. The backtest decides whether they actually matter.
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import pandas as pd

from ..db.models import Game, Venue
from ..db.store import session_scope

SITUATIONAL_COLS = [
    "home_rest_days", "away_rest_days", "home_short_week", "away_short_week",
    "home_off_bye", "away_off_bye", "away_travel_dist", "away_tz_shift",
    "kickoff_local_hour", "early_kickoff",
]


def haversine(lat1, lon1, lat2, lon2) -> Optional[float]:
    """Great-circle distance in miles, or None if any coord is missing."""
    if any(v is None or pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
        return None
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def _load() -> tuple:
    with session_scope() as s:
        games = pd.DataFrame(
            s.query(Game.id, Game.season, Game.week, Game.start_date,
                    Game.venue_id, Game.home_team, Game.away_team).all(),
            columns=["id", "season", "week", "start_date", "venue_id",
                     "home_team", "away_team"])
        venues = pd.DataFrame(
            s.query(Venue.id, Venue.latitude, Venue.longitude).all(),
            columns=["venue_id", "lat", "lon"])
    return games, venues


def _rest_days(games: pd.DataFrame) -> pd.DataFrame:
    """Per (game, team) days since that team's previous game this season."""
    home = games[["id", "season", "start_date", "home_team"]].rename(
        columns={"home_team": "team"})
    away = games[["id", "season", "start_date", "away_team"]].rename(
        columns={"away_team": "team"})
    long = pd.concat([home, away], ignore_index=True).sort_values(
        ["season", "team", "start_date"], na_position="last")
    long["prev"] = long.groupby(["season", "team"])["start_date"].shift(1)
    long["rest_days"] = (long["start_date"] - long["prev"]).dt.days
    return long[["id", "team", "rest_days"]]


def situational_frame() -> pd.DataFrame:
    """One row per game id with the situational columns."""
    games, venues = _load()
    games["start_date"] = pd.to_datetime(games["start_date"])
    vcoord = venues.set_index("venue_id")

    # team's modal home venue per season (their "home base")
    home_base = (games.dropna(subset=["venue_id"])
                 .groupby(["season", "home_team"])["venue_id"]
                 .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None))

    rest = _rest_days(games)
    h_rest = rest.rename(columns={"team": "home_team", "rest_days": "home_rest_days"})
    a_rest = rest.rename(columns={"team": "away_team", "rest_days": "away_rest_days"})
    df = (games
          .merge(h_rest, on=["id", "home_team"], how="left")
          .merge(a_rest, on=["id", "away_team"], how="left"))

    def _coords(vid):
        if vid is None or vid not in vcoord.index:
            return (None, None)
        row = vcoord.loc[vid]
        return (row["lat"], row["lon"])

    rows = []
    for r in df.itertuples(index=False):
        glat, glon = _coords(r.venue_id)
        ahome = home_base.get((r.season, r.away_team))
        alat, alon = _coords(ahome)
        travel = haversine(alat, alon, glat, glon)
        tz = (glon - alon) / 15.0 if (glon is not None and alon is not None
                                      and not pd.isna(glon) and not pd.isna(alon)) else None
        local_hour = None
        if pd.notna(r.start_date) and glon is not None and not pd.isna(glon):
            local_hour = (r.start_date.hour + glon / 15.0) % 24
        rows.append({
            "id": r.id,
            "home_rest_days": r.home_rest_days,
            "away_rest_days": r.away_rest_days,
            "home_short_week": _flag(r.home_rest_days, lambda x: x < 6),
            "away_short_week": _flag(r.away_rest_days, lambda x: x < 6),
            "home_off_bye": _flag(r.home_rest_days, lambda x: x > 9),
            "away_off_bye": _flag(r.away_rest_days, lambda x: x > 9),
            "away_travel_dist": travel,
            "away_tz_shift": tz,
            "kickoff_local_hour": local_hour,
            "early_kickoff": 1 if (local_hour is not None and local_hour <= 13) else 0,
        })
    return pd.DataFrame(rows)


def _flag(v, pred) -> Optional[int]:
    if v is None or pd.isna(v):
        return None
    return 1 if pred(v) else 0
