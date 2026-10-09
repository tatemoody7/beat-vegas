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
from .trophy_games import load_pairs

SITUATIONAL_COLS = [
    "home_rest_days",
    "away_rest_days",
    "home_short_week",
    "away_short_week",
    "home_off_bye",
    "away_off_bye",
    "away_travel_dist",
    "away_tz_shift",
    "kickoff_local_hour",
    "early_kickoff",
    # schedule-derived context (offline; leak-free — prior games / static only)
    "home_revenge",
    "away_revenge",
    "home_opener",
    "away_opener",
    "night_game",
    "rivalry_game",
    "conference_game",
]

# Neither conference flag nor rivalry flag may know the future (strategic review,
# 2026-10-09): `conference_game` reads each game's OWN conference fields (CFBD sets
# them per season, so realignment is honoured); `rivalry_game` is the frozen list
# of named trophy games (`data/trophy_games.json`), not a count of meetings that
# included seasons after the game.
_INDEPENDENT = "FBS Independents"


def haversine(lat1, lon1, lat2, lon2) -> Optional[float]:
    """Great-circle distance in miles, or None if any coord is missing."""
    if any(v is None or pd.isna(v) for v in (lat1, lon1, lat2, lon2)):
        return None
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def _load(session=None, season: Optional[int] = None, min_season: Optional[int] = None) -> tuple:
    """games/venues frames. `session` reuses a caller's session (else opens
    one); `season` restricts the games to one season (enough for rest/travel/
    kickoff — the cross-season revenge flags then only see that season; the
    trophy-game rivalry and per-game conference flags need no other season)."""
    if session is None:
        with session_scope() as s:
            return _load(s, season, min_season)
    s = session
    q = s.query(
        Game.id,
        Game.season,
        Game.week,
        Game.start_date,
        Game.venue_id,
        Game.home_team,
        Game.away_team,
        Game.home_points,
        Game.away_points,
        Game.home_conference,
        Game.away_conference,
    )
    if season is not None:
        q = q.filter(Game.season == season)
    if min_season is not None:
        q = q.filter(Game.season >= int(min_season))
    games = pd.DataFrame(
        q.all(),
        columns=[
            "id",
            "season",
            "week",
            "start_date",
            "venue_id",
            "home_team",
            "away_team",
            "home_points",
            "away_points",
            "home_conference",
            "away_conference",
        ],
    )
    venues = pd.DataFrame(
        s.query(Venue.id, Venue.latitude, Venue.longitude).all(),
        columns=["venue_id", "lat", "lon"],
    )
    return games, venues


def _pair_key(a, b) -> tuple:
    """Order-independent team pair key."""
    return (a, b) if str(a) <= str(b) else (b, a)


def _revenge_and_rivalry(games: pd.DataFrame, trophy_pairs=None) -> pd.DataFrame:
    """Per-game home/away revenge flags + the trophy-game rivalry flag.

    revenge: in the two teams' most recent PRIOR meeting (earlier date), this
    side LOST (prior info only -> leak-free). rivalry: the pair plays for a
    named trophy (`data/trophy_games.json`, frozen 2026-10-09) -- a fact about
    the pair that no later meeting can change.
    """
    pairs = load_pairs() if trophy_pairs is None else trophy_pairs
    g = games.sort_values("start_date", na_position="last")
    last_meet: Dict[tuple, tuple] = {}  # pair -> (winner, loser) of last meeting
    rows = []
    for r in g.itertuples(index=False):
        pk = _pair_key(r.home_team, r.away_team)
        prev = last_meet.get(pk)
        home_rev = away_rev = 0
        if prev is not None:
            _, loser = prev
            home_rev = 1 if loser == r.home_team else 0
            away_rev = 1 if loser == r.away_team else 0
        rows.append(
            {
                "id": r.id,
                "home_revenge": home_rev,
                "away_revenge": away_rev,
                "rivalry_game": 1 if frozenset((r.home_team, r.away_team)) in pairs else 0,
            }
        )
        # update last meeting (skip ties / missing scores)
        hp, ap = r.home_points, r.away_points
        if pd.notna(hp) and pd.notna(ap) and hp != ap:
            winner = r.home_team if hp > ap else r.away_team
            loser = r.away_team if hp > ap else r.home_team
            last_meet[pk] = (winner, loser)
    return pd.DataFrame(rows, columns=["id", "home_revenge", "away_revenge", "rivalry_game"])


def same_conference(home_conf, away_conf) -> int:
    """1 when both teams sit in the same conference THAT SEASON; independents and
    unknowns never make a conference game."""
    if home_conf is None or away_conf is None or pd.isna(home_conf) or pd.isna(away_conf):
        return 0
    if home_conf == _INDEPENDENT:
        return 0
    return 1 if home_conf == away_conf else 0


def _opener(games: pd.DataFrame) -> pd.DataFrame:
    """Flag each team's first game of the season (leak-free; schedule-known)."""
    long = pd.concat(
        [
            games[["id", "season", "start_date", "home_team"]]
            .rename(columns={"home_team": "team"})
            .assign(side="home"),
            games[["id", "season", "start_date", "away_team"]]
            .rename(columns={"away_team": "team"})
            .assign(side="away"),
        ],
        ignore_index=True,
    ).sort_values(["season", "team", "start_date"], na_position="last")
    long["is_opener"] = (long.groupby(["season", "team"]).cumcount() == 0).astype(int)
    home = long[long.side == "home"][["id", "is_opener"]].rename(
        columns={"is_opener": "home_opener"}
    )
    away = long[long.side == "away"][["id", "is_opener"]].rename(
        columns={"is_opener": "away_opener"}
    )
    return home.merge(away, on="id", how="outer")


def _rest_days(games: pd.DataFrame) -> pd.DataFrame:
    """Per (game, team) days since that team's previous game this season."""
    home = games[["id", "season", "start_date", "home_team"]].rename(columns={"home_team": "team"})
    away = games[["id", "season", "start_date", "away_team"]].rename(columns={"away_team": "team"})
    long = pd.concat([home, away], ignore_index=True).sort_values(
        ["season", "team", "start_date"], na_position="last"
    )
    long["prev"] = long.groupby(["season", "team"])["start_date"].shift(1)
    long["rest_days"] = (long["start_date"] - long["prev"]).dt.days
    return long[["id", "team", "rest_days"]]


def situational_frame(
    session=None, season: Optional[int] = None, min_season: Optional[int] = None
) -> pd.DataFrame:
    """One row per game id with the situational columns.

    Default: every game in the DB via its own session (the feature frame).
    `session` + `season` let a caller (etl/context.py) compute the rest/travel/
    kickoff numbers for one season inside an open session."""
    games, venues = _load(session, season, min_season)
    if games.empty:
        return pd.DataFrame(columns=["id"] + SITUATIONAL_COLS)
    games["start_date"] = pd.to_datetime(games["start_date"])
    vcoord = venues.set_index("venue_id")

    # team's modal home venue per season (their "home base")
    home_base = (
        games.dropna(subset=["venue_id"])
        .groupby(["season", "home_team"])["venue_id"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
    )

    rest = _rest_days(games)
    h_rest = rest.rename(columns={"team": "home_team", "rest_days": "home_rest_days"})
    a_rest = rest.rename(columns={"team": "away_team", "rest_days": "away_rest_days"})
    df = games.merge(h_rest, on=["id", "home_team"], how="left").merge(
        a_rest, on=["id", "away_team"], how="left"
    )

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
        tz = (
            (glon - alon) / 15.0
            if (glon is not None and alon is not None and not pd.isna(glon) and not pd.isna(alon))
            else None
        )
        local_hour = None
        if pd.notna(r.start_date) and glon is not None and not pd.isna(glon):
            local_hour = (r.start_date.hour + glon / 15.0) % 24
        rows.append(
            {
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
                "night_game": 1 if (local_hour is not None and local_hour >= 18) else 0,
                # that season's conferences, from the game row (CFBD per season)
                "conference_game": same_conference(r.home_conference, r.away_conference),
            }
        )
    df_base = pd.DataFrame(rows)
    df_base = df_base.merge(_revenge_and_rivalry(games), on="id", how="left").merge(
        _opener(games), on="id", how="left"
    )
    return df_base


def _flag(v, pred) -> Optional[int]:
    if v is None or pd.isna(v):
        return None
    return 1 if pred(v) else 0
