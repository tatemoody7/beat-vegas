"""Assemble a leak-free per-game feature frame for the 1H-under model.

Two feature families, both strictly using pre-kickoff information:
  1. Season-to-date 1H/full scoring (expanding mean over the team's *prior*
     games this season, shifted to exclude the current game).
  2. Prior-season team quality/efficiency (SP+, advanced PPA/success/explosive)
     joined from season-1 — a stable preseason prior with zero same-season leak.

Target: under = realized 1H total < proxy 1H line (0.52 * full-game total).
Unplayed games (no 1H result yet) stay in the frame with under = NaN so the
upcoming slate can be scored; trainers/graders go through training_frame().
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np
import pandas as pd

from ..db.models import Game, TeamTempo, Venue, Weather, WeatherObs
from ..db.store import session_scope
from ..sources.cfbd import CFBDClient
from ..sources.season_stats import (
    advanced_frame,
    returning_frame,
    roster_experience_frame,
    sp_frame,
    talent_frame,
)
from .fbs import filter_fbs_games, load_fbs_teams
from .fh_factors import FH_METRICS, fh_factor_frame
from .proxy_line import proxy_total
from .situational import situational_frame

# Feature columns handed to the model (filled below).
FEATURE_COLS: List[str] = [
    "full_game_total",
    "week",
    "neutral_site",
    "proj_1h_total",
    "proj_1h_ratio",
    "home_fh_pf",
    "home_fh_pa",
    "away_fh_pf",
    "away_fh_pa",
    "combined_fh_offense",
    "combined_fh_defense",
    "home_full_pf",
    "home_full_pa",
    "away_full_pf",
    "away_full_pa",
    "home_sp_off",
    "home_sp_def",
    "away_sp_off",
    "away_sp_def",
    "home_off_ppa",
    "home_def_ppa",
    "away_off_ppa",
    "away_def_ppa",
    "home_off_success",
    "away_off_success",
    "combined_off_ppa",
    "combined_def_ppa",
    "home_returning_ppa",
    "away_returning_ppa",
    # situational (schedule-derived; fully historical)
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
    # pace + weather (populated by scripts/backfill_enrichment.py)
    "combined_sec_play",
    "combined_plays",
    "wx_temp",
    "wx_wind",
    "wx_precip",
    "wx_dome",
    # era: 2023 NCAA running-clock rule cut ~8 plays/game (scoring-regime shift)
    "era_post2023",
    # --- easy free adds (Phase 1 deepen) -----------------------------------
    # schedule-derived context (offline; leak-free). NB: openers are excluded —
    # the min_games filter removes every team's first game, so they're inert here.
    "home_revenge",
    "away_revenge",
    "night_game",
    "rivalry_game",
    "conference_game",
    # venue metadata (CFBD /venues; static, leak-free)
    "venue_elevation",
    "venue_grass",
    "venue_capacity",
    # talent + roster experience (preseason-known; same-season, leak-free)
    "home_talent",
    "away_talent",
    "home_roster_exp",
    "away_roster_exp",
    "home_roster_upperclass",
    "away_roster_upperclass",
]

# --- the "no Vegas line" rule -------------------------------------------------
# The BV line is our OWN number; if it learned from Vegas it wouldn't be
# independent and the gap would be circular. MARKET_COLS are the only
# Vegas-derived entries in FEATURE_COLS — the BV regressor must exclude them
# (see model/bv_line.BV_FEATURE_COLS). The classifier may keep them: it is
# explicitly the market-relative model (target = 1H < proxy_line).
# First-half PBP factors (Phase 2): season-to-date offense + defense-allowed for
# each metric, leak-free. Generated to keep names consistent with fh_factors.
FH_FACTOR_COLS = [
    f"{side}_fh_{role}_{m}"
    for side in ("home", "away")
    for role in ("off", "def")
    for m in FH_METRICS
]
FEATURE_COLS += FH_FACTOR_COLS

# Matchup interactions (Phase 2b): offense vs the opponent's defense-allowed, for
# each of the two teams summed -> "how much edge the offenses have over the
# defenses they face" in the 1H. High edge -> expect more early scoring (over);
# the model learns the under direction. Built from FH factors, so leak-free.
MATCHUP_COLS = ["mm_explosive_edge", "mm_epa_edge", "mm_success_edge", "mm_pace", "mm_havoc"]
FEATURE_COLS += MATCHUP_COLS

# SERVING SKEW (B-SERVE, 2026-09-22). fh_factor_frame joins the first-half PBP
# season-to-date aggregates onto games BY THE GAME'S OWN ID: a played game has a
# play-by-play row and receives its teams' prior-game means; an UPCOMING game has
# no play-by-play row yet, so the join finds nothing and every one of these
# columns is NaN on every row the live model scores -- while every training row
# (all played) carries them. 100% NaN on the 58 scored week-4 rows, 0.0% NaN on
# 2023-25 weeks 4+. HistGradientBoosting learns a routing direction for missing
# values only from missing values it sees in training, so the live model sent
# every game down 57 branches it never trained; masking these columns on played
# rows moved the calibrated prediction by -1.99 / -1.30 / -2.58 points (2026 /
# 2025 / 2024) while MAE improved. They leave the regressor's inputs
# (model/bv_line.BV_FEATURE_COLS); the classifier keeps FEATURE_COLS and is
# being retired. `serve_skew_report` below is the guard for the CLASS.
SERVE_UNAVAILABLE_COLS = list(FH_FACTOR_COLS) + list(MATCHUP_COLS)

MARKET_COLS = {"full_game_total", "proj_1h_ratio"}

# Names derived from the 1H BETTING line. These must NEVER be a feature in ANY
# model — they're used only post-prediction for the gap/grading. The guard test
# in tests/test_features.py enforces this.
BANNED_LINE_COLS = {
    "line_used",
    "closing_line",
    "consensus_line",
    "totals_h1",
    "proxy_line",
    "open_line",
    "cur_line",
    "bv_gap",
    "bv_line",
}


def _load_all_games(fbs_only: bool = True) -> pd.DataFrame:
    """Every game row the engine may see. `fbs_only` (default) drops any game
    where either team was not FBS that season — see etl/fbs.py for why."""
    df = _query_games()
    if fbs_only:
        df = filter_fbs_games(df, load_fbs_teams())
    return df


def _query_games() -> pd.DataFrame:
    with session_scope() as s:
        q = s.query(
            Game.id,
            Game.season,
            Game.week,
            Game.start_date,
            Game.neutral_site,
            Game.home_team,
            Game.away_team,
            Game.home_points,
            Game.away_points,
            Game.home_first_half_points,
            Game.away_first_half_points,
            Game.first_half_total,
            Game.full_game_total,
            Game.spread,
            Game.venue_id,
            Game.first_half_source,
        )
        df = pd.DataFrame(
            q.all(),
            columns=[
                "id",
                "season",
                "week",
                "start_date",
                "neutral_site",
                "home_team",
                "away_team",
                "home_points",
                "away_points",
                "home_fh",
                "away_fh",
                "first_half_total",
                "full_game_total",
                "spread",
                "venue_id",
                "first_half_source",  # 'pbp' | 'linescores' — selected for the residual-model
                # training frame added in the next PR (unused here so far)
            ],
        )
        venues = pd.DataFrame(
            s.query(Venue.id, Venue.elevation, Venue.grass, Venue.capacity).all(),
            columns=["venue_id", "venue_elevation", "venue_grass", "venue_capacity"],
        )
    df["neutral_site"] = df["neutral_site"].fillna(False).astype(int)
    df = _merge_venue_meta(df, venues)
    df["venue_grass"] = df["venue_grass"].map({True: 1.0, False: 0.0})
    return df


def _merge_venue_meta(df: pd.DataFrame, venues: pd.DataFrame) -> pd.DataFrame:
    """Left-join venue metadata, coercing the join key so an object-dtype
    venue_id (psycopg returns object for a nullable int) merges cleanly with
    Venue.id's int64 — otherwise pandas raises on the dtype mismatch."""
    for d in (df, venues):
        d["venue_id"] = pd.to_numeric(d["venue_id"], errors="coerce").astype("float64")
    return df.merge(venues, on="venue_id", how="left")


def _team_long(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team) with that team's 1H/full points for & against."""
    home = pd.DataFrame(
        {
            "id": df["id"],
            "season": df["season"],
            "week": df["week"],
            "start_date": df["start_date"],
            "team": df["home_team"],
            "fh_pf": df["home_fh"],
            "fh_pa": df["away_fh"],
            "full_pf": df["home_points"],
            "full_pa": df["away_points"],
        }
    )
    away = pd.DataFrame(
        {
            "id": df["id"],
            "season": df["season"],
            "week": df["week"],
            "start_date": df["start_date"],
            "team": df["away_team"],
            "fh_pf": df["away_fh"],
            "fh_pa": df["home_fh"],
            "full_pf": df["away_points"],
            "full_pa": df["home_points"],
        }
    )
    return pd.concat([home, away], ignore_index=True)


_STD_COLS = ["fh_pf", "fh_pa", "full_pf", "full_pa"]

# How many synthetic "games" of prior-season form seed the season-to-date window.
#
# 0.0 reproduces the unseeded expanding mean EXACTLY, so it is the incumbent and
# the honest default: the seed does not go live until a walk-forward report says
# it should (scripts/level_anchor_gate.py). See _season_to_date for the problem
# it addresses.
PRIOR_SEASON_WEIGHT = 0.0

# Which weather_obs LEAD feeds the model, or None for the legacy `weather` table.
#
# None reproduces today's frame exactly, so the incumbent is an ARM of this
# experiment rather than a separate code path -- the same shape as
# PRIOR_SEASON_WEIGHT above. Repairing the weather DATA and letting the model use
# the repaired values are two different decisions: the backfill writes weather_obs,
# which nothing reads, and only this constant moves the live model.
#
# LEAD 0 IS REFUSED HERE, not merely discouraged. It is the near-kickoff series,
# which tracks what actually happened rather than what was knowable while a bet
# was placeable -- feeding it to a model that prices real money is look-ahead
# bias, and a rule that lives only in a comment is the kind that drifts. The
# production choices are None, 24 and 72. A diagnostic read of lead 0 (football
# modelling, data quality) must ask for it explicitly and can never be the basis
# of a promotion. See scripts/weather_gate.py.
WEATHER_OBS_LEAD_HOURS: Optional[int] = None

DIAGNOSTIC_LEAD_HOURS = 0  # near-kickoff: benchmark only, never production


def check_weather_lead(lead: Optional[int], allow_diagnostic: bool = False) -> Optional[int]:
    """Refuse a weather lead that must never price real money."""
    if lead == DIAGNOSTIC_LEAD_HOURS and not allow_diagnostic:
        raise ValueError(
            "weather lead 0 is the near-kickoff series and is not decision-safe: it "
            "describes what happened, not what was knowable at bet time. Use None "
            "(legacy), 24 or 72, or pass allow_diagnostic=True for a benchmark read "
            "that may not be promoted."
        )
    return lead


def _prior_season_means(long: pd.DataFrame) -> pd.DataFrame:
    """Each team's PRIOR-season mean of every _STD_COLS metric, keyed to the
    season it may be used in.

    Same zero-leak construction as quality_prior_frame: a season's finished
    aggregate is stamped with `season + 1`, so it can only ever join to the
    FOLLOWING season's games. Unplayed rows carry NaN and mean() skips them."""
    g = long.groupby(["season", "team"], sort=False)[_STD_COLS].mean().reset_index()
    g["season"] = g["season"] + 1  # usable from the next season on
    return g.rename(columns={c: c + "_prior" for c in _STD_COLS})


def _season_to_date(long: pd.DataFrame, prior_weight: float = 0.0) -> pd.DataFrame:
    """Expanding mean of each metric over the team's prior games this season,
    optionally seeded with `prior_weight` synthetic games of prior-season form.

    THE PROBLEM. `shift(1)` is what keeps this leak-free and it is not negotiable
    -- but it also makes game 1 of every season NaN and game 2 a one-game mean.
    That propagates into h/a_fh_pf_std, and from there into proj_1h_total and
    proj_1h_ratio, so 68 of the regressor's 115 features are NaN at zero games
    played. Measured cost: about 1 point of bv_line per game of season-to-date
    data, and 2.84 of the 3.40-point live-vs-backtest gap swing in 2026.

    THE SEED. A team's prior-season mean enters as `prior_weight` synthetic
    observations, so game 1 reads the prior-season mean, game 2 reads a weighted
    blend, and the prior's share decays as k/(n+k) with no discontinuity at any
    seam. Deliberately NOT a special case for weeks 1-2: a rule that applies only
    early creates a break the tree can learn as a week-number artifact, and the
    same computation must run at train and predict time or the model is fitted on
    observed values and asked to score estimated ones.

    prior_weight=0.0 is an exact no-op -- (0*prior + sum) / (0 + n) is the
    unseeded mean -- which is what makes the incumbent the gate's own baseline
    rather than a separate code path."""
    long = long.sort_values(["season", "team", "week", "start_date"], na_position="last")
    if prior_weight:
        long = long.merge(_prior_season_means(long), on=["season", "team"], how="left")
    grp = long.groupby(["season", "team"], sort=False)
    out = long[["id", "season", "team"]].copy()
    for col in _STD_COLS:
        # shift(1) excludes the current game -> strictly prior info only.
        # transform preserves the original row index (no misalignment).
        if not prior_weight:
            out[col + "_std"] = grp[col].transform(lambda s: s.shift(1).expanding().mean())
            continue
        # Sum and COUNT of the prior games, kept apart so the seed can be added
        # with its own weight.
        #
        # fillna(0) before the sum is load-bearing: expanding().sum() over a
        # window with no non-NaN value returns NaN, not 0, so the FIRST game of
        # every season -- the one this whole function exists to fix -- would
        # propagate NaN through the blend and land exactly where it started.
        # Filling with 0 makes a missing game contribute nothing to the sum,
        # which is what prior_n already assumes by counting only notna().
        prior_sum = grp[col].transform(lambda s: s.shift(1).fillna(0).expanding().sum())
        prior_n = grp[col].transform(lambda s: s.shift(1).notna().expanding().sum())
        seed = long[col + "_prior"]
        seeded = (prior_weight * seed + prior_sum) / (prior_weight + prior_n)
        # A team with no prior season (a new FBS member, or the first season in
        # the frame) keeps the unseeded value -- including its NaN. Inventing a
        # league-average prior there would be a different feature, not this one.
        unseeded = (prior_sum / prior_n).where(prior_n > 0)
        out[col + "_std"] = seeded.where(seed.notna(), unseeded)
    out["games_played"] = grp.cumcount()
    return out


# Wind-speed bands (mph): [0,10) -> 0, [10,15) -> 1, [15,20) -> 2, 20+ -> 3.
WIND_BAND_EDGES = (10.0, 15.0, 20.0)


def wind_band(w) -> np.ndarray:
    """Band index for each wind speed (float array; NaN stays NaN)."""
    vals = pd.to_numeric(pd.Series(w), errors="coerce").astype(float).to_numpy()
    out = np.digitize(np.nan_to_num(vals, nan=-1.0), WIND_BAND_EDGES).astype(float)
    out[np.isnan(vals)] = np.nan
    return out


def _weather_frame(s, lead: Optional[int]) -> pd.DataFrame:
    """The weather columns, from whichever table this arm reads."""
    if lead is None:
        return pd.DataFrame(
            s.query(
                Weather.game_id,
                Weather.temperature_f,
                Weather.wind_mph,
                Weather.precipitation,
                Weather.dome,
            ).all(),
            columns=["game_id", "wx_temp", "wx_wind", "wx_precip", "wx_dome"],
        ).assign(wx_gust=np.nan)
    # weather_obs may hold SEVERAL readings for one (game, lead) -- a different
    # model, provider or run is kept rather than overwritten. Take the most
    # recently retrieved, deterministically, so a feature frame never depends on
    # row order.
    rows = (
        s.query(
            WeatherObs.game_id,
            WeatherObs.temperature_f,
            WeatherObs.wind_mph,
            WeatherObs.precipitation,
            WeatherObs.dome,
            WeatherObs.wind_gust_mph,
        )
        .filter(WeatherObs.lead_hours == lead)
        .order_by(WeatherObs.retrieved_at.desc(), WeatherObs.id.desc())
        .all()
    )
    return pd.DataFrame(
        rows,
        columns=["game_id", "wx_temp", "wx_wind", "wx_precip", "wx_dome", "wx_gust"],
    ).drop_duplicates(subset=["game_id"], keep="first")


def _merge_tempo_weather(df: pd.DataFrame, weather_lead: Optional[int] = None) -> pd.DataFrame:
    """Exact (season, week, team) join for pace + (game_id) join for weather."""
    with session_scope() as s:
        tempo = pd.DataFrame(
            s.query(
                TeamTempo.season,
                TeamTempo.week,
                TeamTempo.team,
                TeamTempo.seconds_per_play,
                TeamTempo.plays_per_game,
            ).all(),
            columns=["season", "week", "team", "sec_play", "plays"],
        )
        wx = _weather_frame(s, weather_lead)

    for side in ("home", "away"):
        t = tempo.rename(
            columns={
                "team": f"{side}_team",
                "sec_play": f"{side}_sec_play",
                "plays": f"{side}_plays",
            }
        )
        df = df.merge(t, on=["season", "week", f"{side}_team"], how="left")
    df["combined_sec_play"] = df[["home_sec_play", "away_sec_play"]].mean(axis=1)
    df["combined_plays"] = df[["home_plays", "away_plays"]].sum(axis=1, min_count=1)

    if not wx.empty:
        df = df.merge(wx, left_on="id", right_on="game_id", how="left")
    else:
        for c in ("wx_temp", "wx_wind", "wx_precip", "wx_dome", "wx_gust"):
            df[c] = pd.NA
    # dome -> numeric for the model (True/False/NA -> 1.0/0.0/NaN)
    df["wx_dome"] = df["wx_dome"].map({True: 1.0, False: 0.0})
    # A dome has no weather: null whatever the row stores (legacy rows carried a
    # 72F / 0 mph placeholder) so the model never learns "72 and calm = dome".
    dome = df["wx_dome"] == 1.0
    df.loc[dome, ["wx_temp", "wx_wind", "wx_precip", "wx_gust"]] = np.nan
    # Extra (non-FEATURE_COLS) column: coarse wind band for display / analysis.
    df["wx_wind_band"] = wind_band(df["wx_wind"])
    return df


def quality_prior_frame(client: CFBDClient, seasons: List[int]) -> pd.DataFrame:
    """SP+ + advanced efficiency per (season, team), with `join_season` =
    season + 1: a season's full-year stats are only ever joined to the FOLLOWING
    season's games (a stable preseason prior, zero same-season leak). Shared by
    build_feature_frame and etl/context.py so the two can never drift."""
    sp = sp_frame(client, seasons)
    adv = advanced_frame(client, seasons)
    quality = sp.merge(adv, on=["season", "team"], how="outer")
    quality["join_season"] = quality["season"] + 1  # use as next season's prior
    return quality


def apply_min_games(df: pd.DataFrame, min_games: int) -> pd.DataFrame:
    """Keep games where BOTH teams have played >= min_games this season."""
    return df[(df["h_games_played"] >= min_games) & (df["a_games_played"] >= min_games)]


def played_mask(df: pd.DataFrame) -> pd.Series:
    """Rows with a realized 1H result — i.e. a defined `under` target."""
    if "under" in df.columns:
        return df["under"].notna()
    return df["first_half_total"].notna()


def training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """The rows a trainer/grader may use: played games only, `under` as int.

    build_feature_frame keeps the upcoming (unplayed) slate so it can be scored;
    every fit / backtest / factor scan must go through this (or played_mask) so a
    NaN target never reaches a model or a hit-rate."""
    out = df[played_mask(df)].copy()
    out["under"] = out["under"].astype(int)
    return out


def build_feature_frame(
    min_games: int = 2,
    seasons: Optional[range] = None,
    client: Optional[CFBDClient] = None,
    fbs_only: bool = True,
    prior_weight: float = PRIOR_SEASON_WEIGHT,
    weather_lead: Optional[int] = WEATHER_OBS_LEAD_HOURS,
    allow_diagnostic_lead: bool = False,
) -> pd.DataFrame:
    check_weather_lead(weather_lead, allow_diagnostic_lead)
    games = _load_all_games(fbs_only=fbs_only)
    std = _season_to_date(_team_long(games), prior_weight=prior_weight)

    # Merge season-to-date stats back, matching each side on its own team name.
    df = games.copy()
    home_only = std.rename(columns={"team": "home_team"})
    away_only = std.rename(columns={"team": "away_team"})
    home_only = home_only.add_prefix("h_").rename(
        columns={"h_id": "id", "h_season": "season", "h_home_team": "home_team"}
    )
    away_only = away_only.add_prefix("a_").rename(
        columns={"a_id": "id", "a_season": "season", "a_away_team": "away_team"}
    )
    df = df.merge(
        home_only[
            [
                "id",
                "home_team",
                "h_fh_pf_std",
                "h_fh_pa_std",
                "h_full_pf_std",
                "h_full_pa_std",
                "h_games_played",
            ]
        ],
        on=["id", "home_team"],
        how="left",
    )
    df = df.merge(
        away_only[
            [
                "id",
                "away_team",
                "a_fh_pf_std",
                "a_fh_pa_std",
                "a_full_pf_std",
                "a_full_pa_std",
                "a_games_played",
            ]
        ],
        on=["id", "away_team"],
        how="left",
    )

    # Prior-season quality priors (season-1), leak-free.
    if client is None:
        client = CFBDClient()
    yrs = sorted(games["season"].unique().tolist())
    prior_yrs = [y - 1 for y in yrs]
    quality = quality_prior_frame(client, sorted(set(yrs + prior_yrs)))

    for side in ["home", "away"]:
        q = quality.add_prefix(f"{side}_q_")
        df = df.merge(
            q,
            left_on=["season", f"{side}_team"],
            right_on=[f"{side}_q_join_season", f"{side}_q_team"],
            how="left",
        )

    # Returning production — SAME-season prior (known preseason, leak-free).
    ret = returning_frame(client, yrs)
    for side in ["home", "away"]:
        rr = ret.add_prefix(f"{side}_r_")
        df = df.merge(
            rr,
            left_on=["season", f"{side}_team"],
            right_on=[f"{side}_r_season", f"{side}_r_team"],
            how="left",
        )

    # Talent composite + roster experience — also preseason-known (SAME season).
    tal = talent_frame(client, yrs)
    exp = roster_experience_frame(client, yrs)
    preseason = tal.merge(exp, on=["season", "team"], how="outer")
    for side in ["home", "away"]:
        p = preseason.add_prefix(f"{side}_p_")
        df = df.merge(
            p,
            left_on=["season", f"{side}_team"],
            right_on=[f"{side}_p_season", f"{side}_p_team"],
            how="left",
        )

    # --- assemble model features -------------------------------------
    df["home_fh_pf"] = df["h_fh_pf_std"]
    df["home_fh_pa"] = df["h_fh_pa_std"]
    df["away_fh_pf"] = df["a_fh_pf_std"]
    df["away_fh_pa"] = df["a_fh_pa_std"]
    # Same convention as the fh_* block: <side>_full_pa is that team's OWN
    # points allowed (the registry describes it that way). The two columns used
    # to be crossed (home <- away's PA and vice versa) — a label fix only; the
    # model saw both columns either way, so its information content is unchanged.
    df["home_full_pf"] = df["h_full_pf_std"]
    df["home_full_pa"] = df["h_full_pa_std"]
    df["away_full_pf"] = df["a_full_pf_std"]
    df["away_full_pa"] = df["a_full_pa_std"]

    # Expected 1H points: blend each team's offense with opponent's defense.
    df["exp_1h_home"] = (df["h_fh_pf_std"] + df["a_fh_pa_std"]) / 2
    df["exp_1h_away"] = (df["a_fh_pf_std"] + df["h_fh_pa_std"]) / 2
    df["proj_1h_total"] = df["exp_1h_home"] + df["exp_1h_away"]
    df["proj_1h_ratio"] = df["proj_1h_total"] / df["full_game_total"]
    df["combined_fh_offense"] = df["h_fh_pf_std"] + df["a_fh_pf_std"]
    df["combined_fh_defense"] = df["h_fh_pa_std"] + df["a_fh_pa_std"]

    df["home_sp_off"] = df["home_q_sp_offense"]
    df["home_sp_def"] = df["home_q_sp_defense"]
    df["away_sp_off"] = df["away_q_sp_offense"]
    df["away_sp_def"] = df["away_q_sp_defense"]
    df["home_off_ppa"] = df["home_q_off_ppa"]
    df["home_def_ppa"] = df["home_q_def_ppa"]
    df["away_off_ppa"] = df["away_q_off_ppa"]
    df["away_def_ppa"] = df["away_q_def_ppa"]
    df["home_off_success"] = df["home_q_off_success"]
    df["away_off_success"] = df["away_q_off_success"]
    df["combined_off_ppa"] = df["home_q_off_ppa"] + df["away_q_off_ppa"]
    df["combined_def_ppa"] = df["home_q_def_ppa"] + df["away_q_def_ppa"]
    df["home_returning_ppa"] = df["home_r_returning_ppa"]
    df["away_returning_ppa"] = df["away_r_returning_ppa"]

    df["home_talent"] = df["home_p_talent"]
    df["away_talent"] = df["away_p_talent"]
    df["home_roster_exp"] = df["home_p_roster_exp"]
    df["away_roster_exp"] = df["away_p_roster_exp"]
    df["home_roster_upperclass"] = df["home_p_roster_upperclass"]
    df["away_roster_upperclass"] = df["away_p_roster_upperclass"]

    # Era flag: post-2023 running-clock rule (leak-free; season known pre-kickoff).
    df["era_post2023"] = (df["season"] >= 2023).astype(float)

    # --- pace (TeamRankings) + weather (Open-Meteo): real model inputs -----
    # combined_sec_play/combined_plays/wx_* are in FEATURE_COLS. In-season the
    # upcoming week's rows come from enrich_tempo.py / enrich_weather.py
    # (sunday.yml) — a missing row means NaN inputs, not an error.
    df = _merge_tempo_weather(df, weather_lead)

    # --- situational features (schedule-derived; real model inputs) ---
    df = df.merge(situational_frame(), on="id", how="left")

    # --- first-half PBP factors (season-to-date off + def-allowed) ----------
    fh = fh_factor_frame()
    if "id" in fh.columns and len(fh.columns) > 1:
        df = df.merge(fh, on="id", how="left")

        def _edge(metric):
            return (df[f"home_fh_off_{metric}"] - df[f"away_fh_def_{metric}"]) + (
                df[f"away_fh_off_{metric}"] - df[f"home_fh_def_{metric}"]
            )

        if "home_fh_off_explosive" in df.columns:
            df["mm_explosive_edge"] = _edge("explosive")
            df["mm_epa_edge"] = _edge("epa")
            df["mm_success_edge"] = _edge("success")
            df["mm_pace"] = df["home_fh_off_n_plays"] + df["away_fh_off_n_plays"]
            df["mm_havoc"] = df["home_fh_def_havoc_suffered"] + df["away_fh_def_havoc_suffered"]

    # --- target + filters --------------------------------------------
    # UNPLAYED games stay in the frame: the upcoming week has a full-game total
    # (the Sunday opener) but no 1H result yet, and it is exactly what
    # score_slate must score. Those rows carry `under` = NaN; anything that
    # trains or grades must drop them (training_frame / played_mask).
    df["full_game_total"] = pd.to_numeric(df["full_game_total"], errors="coerce")
    df["first_half_total"] = pd.to_numeric(df["first_half_total"], errors="coerce")
    df = df[df["full_game_total"].notna() & (df["full_game_total"] > 0)].copy()
    df["proxy_line"] = df.apply(
        lambda r: proxy_total(r["full_game_total"], spread=r.get("spread")), axis=1
    )
    played = df["first_half_total"].notna()
    df = df[~(played & (df["first_half_total"] == df["proxy_line"]))]  # drop pushes (played only)
    played = df["first_half_total"].notna()
    df["under"] = np.where(
        played, (df["first_half_total"] < df["proxy_line"]).astype(float), np.nan
    )

    df = apply_min_games(df, min_games)
    if seasons is not None:
        df = df[df["season"].isin(list(seasons))]

    # Model columns must be clean numeric floats (NaN, never pd.NA / None / bool).
    # Any feature not yet produced (e.g. PBP factors before backfill) -> NaN
    # column so df[FEATURE_COLS] never KeyErrors.
    for c in FEATURE_COLS:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Train/serve skew guard (B-SERVE)


def serve_skew_report(
    df: pd.DataFrame, season: int, week: int, cols: Sequence[str]
) -> pd.DataFrame:
    """Per column: the NaN share on the rows about to be SCORED (`season`/`week`)
    against the NaN share on the rows the model TRAINS on (played rows of prior
    seasons). A column near 1.0 on the left and near 0.0 on the right is an
    input the model will route through branches it never saw in training."""
    present = [c for c in cols if c in df.columns]
    needed = {"season", "week", "first_half_total"}
    if not present or not needed <= set(df.columns):
        # A frame with none of the inputs, or without the columns that define
        # "scored" and "played" (a stubbed test frame), has nothing to check.
        out = pd.DataFrame(columns=["target_nan", "train_nan"])
        out.attrs["n_target"] = 0
        out.attrs["n_train"] = 0
        return out
    target = df[(df["season"] == int(season)) & (df["week"] == int(week))]
    train = df[(df["season"] < int(season)) & played_mask(df)]
    out = pd.DataFrame(
        {
            "target_nan": target[present].isna().mean() if len(target) else float("nan"),
            "train_nan": train[present].isna().mean() if len(train) else float("nan"),
        }
    )
    out.index.name = "column"
    out.attrs["n_target"] = int(len(target))
    out.attrs["n_train"] = int(len(train))
    return out


def serve_skew_violations(
    report: pd.DataFrame, target_min: float = 0.9, train_max: float = 0.1
) -> list:
    """Columns that are NaN on more than `target_min` of the scored rows and on
    less than `train_max` of the training rows. Any entry is a defect: the live
    model would score every game through a branch it never trained."""
    if report.empty or report.attrs.get("n_target", 0) == 0:
        return []
    bad = report[(report["target_nan"] > target_min) & (report["train_nan"] < train_max)]
    return sorted(bad.index.tolist())
