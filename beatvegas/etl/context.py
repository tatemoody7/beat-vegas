"""Per-game board context for rows the model cannot score.

The feature frame only produces factor values for games both teams have played
>= min_games of — so weeks 1-2 and every FBS-vs-FCS card used to show dashes.
`context_for_games` rebuilds the same factor inputs straight from the tables,
for any game (played or not, FBS or not), one season-week at a time:

  * pace        combined_sec_play / combined_plays   (team_tempo, that week)
  * weather     wx_temp / wx_wind / wx_precip / wx_dome (+ `dome` bool) (weather)
  * efficiency  home/away/combined off_ppa + def_ppa  (prior season, CFBD — via
                features.quality_prior_frame; optional, pre-fetched by the caller)
  * situational home/away_rest_days, away_travel_dist, away_tz_shift,
                kickoff_local_hour, home/away_short_week + the `spot` string
  * 1H priors   home/away_fh_pf/pa + combined_fh_offense/defense — season-to-date
                from week 3, else the PRIOR season's per-game 1H means, tagged
                by fh_prior_source / fh_source_home / fh_source_away.

Everything is a plain Python number, string, bool or None — never NaN — so the
dict can go straight into factors_json (see json_safe). Display + explainer
only: nothing here feeds a model.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from ..db.models import Game, TeamTempo, Weather
from .features import quality_prior_frame
from .situational import situational_frame

# Week from which a team's own season-to-date 1H record replaces the prior season.
SEASON_TO_DATE_FROM_WEEK = 3

# Situational numbers copied into the card payload, by feature-frame name.
SITUATIONAL_KEYS = (
    "home_rest_days",
    "away_rest_days",
    "home_short_week",
    "away_short_week",
    "away_travel_dist",
    "away_tz_shift",
    "kickoff_local_hour",
)

Pair = Tuple[str, str]  # (home_team, away_team)


# --------------------------------------------------------------------------- #
# JSON hygiene
# --------------------------------------------------------------------------- #
def _num(v) -> Optional[float]:
    """Plain float or None (NaN/inf/None/pd.NA -> None)."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        return None
    f = float(v)
    return None if math.isinf(f) else f


def json_safe(obj: Any) -> Any:
    """Recursively scrub a payload for json.dumps: NaN/inf -> None, numpy
    scalars -> Python, tuples -> lists. Strings/bools/None pass through."""
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (str, bool)) or obj is None:
        return obj
    if isinstance(obj, int):
        return int(obj)
    if hasattr(obj, "item") and not isinstance(obj, float):  # numpy scalar
        try:
            obj = obj.item()
        except (TypeError, ValueError):
            return None
        return json_safe(obj)
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    try:
        return None if pd.isna(obj) else obj
    except (TypeError, ValueError):
        return obj


def _mean(vals: Iterable) -> Optional[float]:
    xs = [float(v) for v in vals if v is not None and not pd.isna(v)]
    return sum(xs) / len(xs) if xs else None


def _sum2(a, b) -> Optional[float]:
    return None if (a is None or b is None) else a + b


# --------------------------------------------------------------------------- #
# Games in scope
# --------------------------------------------------------------------------- #
def _games(session, season: int, week: int, game_ids: Iterable[int]) -> Dict[int, Pair]:
    ids = [int(g) for g in game_ids]
    if not ids:
        return {}
    rows = (
        session.query(Game.id, Game.home_team, Game.away_team)
        .filter(Game.season == season, Game.week == week, Game.id.in_(ids))
        .all()
    )
    return {int(gid): (home, away) for gid, home, away in rows}


# --------------------------------------------------------------------------- #
# Pace + weather
# --------------------------------------------------------------------------- #
def pace_for_games(session, season: int, week: int, games: Dict[int, Pair]) -> Dict[int, Dict]:
    """combined_sec_play (mean of the sides present) + combined_plays (sum of the
    sides present) from team_tempo for that exact (season, week) — the same join
    features._merge_tempo_weather makes."""
    teams = sorted({t for pair in games.values() for t in pair})
    if not teams:
        return {}
    tempo = {
        team: (spp, plays)
        for team, spp, plays in session.query(
            TeamTempo.team, TeamTempo.seconds_per_play, TeamTempo.plays_per_game
        )
        .filter(TeamTempo.season == season, TeamTempo.week == week, TeamTempo.team.in_(teams))
        .all()
    }
    out: Dict[int, Dict] = {}
    for gid, (home, away) in games.items():
        h, a = tempo.get(home, (None, None)), tempo.get(away, (None, None))
        spp = _mean([h[0], a[0]])
        plays = [_num(h[1]), _num(a[1])]
        plays = [p for p in plays if p is not None]
        out[gid] = {
            "combined_sec_play": spp,
            "combined_plays": sum(plays) if plays else None,
        }
    return out


def weather_for_games(session, game_ids: Iterable[int]) -> Dict[int, Dict]:
    ids = [int(g) for g in game_ids]
    if not ids:
        return {}
    out: Dict[int, Dict] = {}
    for gid, temp, wind, precip, dome in (
        session.query(
            Weather.game_id,
            Weather.temperature_f,
            Weather.wind_mph,
            Weather.precipitation,
            Weather.dome,
        )
        .filter(Weather.game_id.in_(ids))
        .all()
    ):
        dome_b = None if dome is None else bool(dome)
        out[int(gid)] = {
            "wx_temp": _num(temp),
            "wx_wind": _num(wind),
            "wx_precip": _num(precip),
            "wx_dome": None if dome_b is None else (1.0 if dome_b else 0.0),
            "dome": dome_b,
        }
    return out


# --------------------------------------------------------------------------- #
# Prior-season efficiency (CFBD, season-1 -> this season)
# --------------------------------------------------------------------------- #
def prior_season_efficiency(season: int, client=None) -> Dict[str, Dict[str, Optional[float]]]:
    """{team: {off_ppa, def_ppa}} from the PRIOR season's CFBD advanced stats,
    through the same season+1 join the feature frame uses. FAIL-SOFT: any CFBD
    problem (no key, 5xx, network) returns {} so the caller drops the efficiency
    keys instead of the row."""
    try:
        if client is None:
            from ..sources.cfbd import CFBDClient

            client = CFBDClient()
        q = quality_prior_frame(client, [season - 1])
    except Exception as e:  # noqa: BLE001 - display-only enrichment must never kill the run
        print(f"[context] prior-season efficiency unavailable ({e!r}) — skipping PPA keys")
        return {}
    if q.empty or "join_season" not in q.columns:
        return {}
    q = q[q["join_season"] == season]
    out: Dict[str, Dict[str, Optional[float]]] = {}
    for r in q.itertuples(index=False):
        out[str(r.team)] = {
            "off_ppa": _num(getattr(r, "off_ppa", None)),
            "def_ppa": _num(getattr(r, "def_ppa", None)),
        }
    return out


def _efficiency_for_games(games: Dict[int, Pair], eff: Dict[str, Dict]) -> Dict[int, Dict]:
    out: Dict[int, Dict] = {}
    for gid, (home, away) in games.items():
        h, a = eff.get(home, {}), eff.get(away, {})
        d = {
            "home_off_ppa": _num(h.get("off_ppa")),
            "home_def_ppa": _num(h.get("def_ppa")),
            "away_off_ppa": _num(a.get("off_ppa")),
            "away_def_ppa": _num(a.get("def_ppa")),
        }
        d["combined_off_ppa"] = _sum2(d["home_off_ppa"], d["away_off_ppa"])
        d["combined_def_ppa"] = _sum2(d["home_def_ppa"], d["away_def_ppa"])
        out[gid] = d
    return out


# --------------------------------------------------------------------------- #
# Situational numbers (rest, travel, tz, kickoff) + the `spot` chip
# --------------------------------------------------------------------------- #
def _spot_str(d: Dict) -> Optional[str]:
    """Same rendering as model/score._spot_str, on plain numbers."""
    parts = []
    hr, ar = d.get("home_rest_days"), d.get("away_rest_days")
    if hr is not None and ar is not None:
        parts.append(f"rest {int(hr)}/{int(ar)}")
    trav = d.get("away_travel_dist")
    if trav is not None:
        parts.append(f"trav {int(trav)}mi")
    hour = d.get("kickoff_local_hour")
    if hour is not None:
        parts.append(f"~{int(round(hour)):02d}:00 kick")
    return " · ".join(parts) if parts else None


def situational_for_games(session, season: int, game_ids: Iterable[int]) -> Dict[int, Dict]:
    ids = {int(g) for g in game_ids}
    if not ids:
        return {}
    frame = situational_frame(session=session, season=season)
    out: Dict[int, Dict] = {}
    if frame.empty:
        return out
    frame = frame[frame["id"].isin(ids)]
    for r in frame.to_dict("records"):
        d = {k: _num(r.get(k)) for k in SITUATIONAL_KEYS}
        d["spot"] = _spot_str(d)
        out[int(r["id"])] = d
    return out


# --------------------------------------------------------------------------- #
# 1H scoring priors: season-to-date from week 3, else prior season
# --------------------------------------------------------------------------- #
def _team_fh_rows(session, seasons: List[int], teams: List[str]) -> Dict[Tuple[int, str], List]:
    """{(season, team): [(week, pf, pa), ...]} over PLAYED games (both sides'
    1H points known) in `seasons` involving `teams`."""
    out: Dict[Tuple[int, str], List] = {}
    if not seasons or not teams:
        return out
    rows = (
        session.query(
            Game.season,
            Game.week,
            Game.home_team,
            Game.away_team,
            Game.home_first_half_points,
            Game.away_first_half_points,
        )
        .filter(
            Game.season.in_(seasons),
            Game.home_first_half_points.isnot(None),
            Game.away_first_half_points.isnot(None),
            (Game.home_team.in_(teams)) | (Game.away_team.in_(teams)),
        )
        .all()
    )
    for season, week, home, away, hfh, afh in rows:
        if home in teams:
            out.setdefault((season, home), []).append((week, hfh, afh))
        if away in teams:
            out.setdefault((season, away), []).append((week, afh, hfh))
    return out


def _side_prior(
    rows: Dict[Tuple[int, str], List], team: str, season: int, week: int
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """(fh_pf, fh_pa, source) for one team before `week` of `season`."""
    if week >= SEASON_TO_DATE_FROM_WEEK:
        std = [r for r in rows.get((season, team), []) if r[0] is not None and r[0] < week]
        if std:
            return _mean(r[1] for r in std), _mean(r[2] for r in std), "season_to_date"
    prior = rows.get((season - 1, team), [])
    if prior:
        return _mean(r[1] for r in prior), _mean(r[2] for r in prior), "prior_season"
    return None, None, None


def _aggregate_source(*sources: Optional[str]) -> Optional[str]:
    present = {s for s in sources if s}
    if not present:
        return None
    return present.pop() if len(present) == 1 else "mixed"


def fh_priors_for_games(session, season: int, week: int, games: Dict[int, Pair]) -> Dict[int, Dict]:
    """home/away_fh_pf/pa (+ combined_fh_offense/defense) per game, tagged with
    where they came from: season-to-date (from week 3, when the team has a
    played game) else the prior season's per-game means. Per-side sources in
    fh_source_home/away; fh_prior_source is the game-level summary
    ('season_to_date' | 'prior_season' | 'mixed' | None)."""
    teams = sorted({t for pair in games.values() for t in pair})
    rows = _team_fh_rows(session, [season, season - 1], teams)
    out: Dict[int, Dict] = {}
    for gid, (home, away) in games.items():
        hpf, hpa, hsrc = _side_prior(rows, home, season, week)
        apf, apa, asrc = _side_prior(rows, away, season, week)
        out[gid] = {
            "home_fh_pf": hpf,
            "home_fh_pa": hpa,
            "away_fh_pf": apf,
            "away_fh_pa": apa,
            "combined_fh_offense": _sum2(hpf, apf),
            "combined_fh_defense": _sum2(hpa, apa),
            "fh_source_home": hsrc,
            "fh_source_away": asrc,
            "fh_prior_source": _aggregate_source(hsrc, asrc),
        }
    return out


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def context_for_games(
    session,
    season: int,
    week: int,
    game_ids: Iterable[int],
    efficiency: Optional[Dict[str, Dict]] = None,
) -> Dict[int, Dict]:
    """{game_id: context dict} for the given games of one (season, week).

    `efficiency` is the pre-fetched {team: {off_ppa, def_ppa}} map from
    prior_season_efficiency(); when None the PPA keys are left out entirely (the
    caller decides whether to spend the CFBD call). Unknown game ids are skipped.
    Each per-factor block is independent — a missing source drops its keys to
    None, never the game."""
    games = _games(session, season, week, game_ids)
    if not games:
        return {}
    ids = list(games)
    pace = pace_for_games(session, season, week, games)
    wx = weather_for_games(session, ids)
    sit = situational_for_games(session, season, ids)
    fh = fh_priors_for_games(session, season, week, games)
    eff = _efficiency_for_games(games, efficiency) if efficiency is not None else {}

    out: Dict[int, Dict] = {}
    for gid in ids:
        d: Dict[str, Any] = {}
        d.update(pace.get(gid, {"combined_sec_play": None, "combined_plays": None}))
        d.update(
            wx.get(
                gid,
                {
                    "wx_temp": None,
                    "wx_wind": None,
                    "wx_precip": None,
                    "wx_dome": None,
                    "dome": None,
                },
            )
        )
        d.update(sit.get(gid, {**{k: None for k in SITUATIONAL_KEYS}, "spot": None}))
        d.update(fh.get(gid, {}))
        if gid in eff:
            d.update(eff[gid])
        out[gid] = json_safe(d)
    return out
