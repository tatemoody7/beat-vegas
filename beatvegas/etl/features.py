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

from typing import List, Optional

import numpy as np
import pandas as pd

from ..db.models import Game, TeamTempo, Venue, Weather
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


def _season_to_date(long: pd.DataFrame) -> pd.DataFrame:
    """Expanding mean of each metric over the team's prior games this season."""
    long = long.sort_values(["season", "team", "week", "start_date"], na_position="last")
    grp = long.groupby(["season", "team"], sort=False)
    out = long[["id", "season", "team"]].copy()
    for col in ["fh_pf", "fh_pa", "full_pf", "full_pa"]:
        # shift(1) excludes the current game -> strictly prior info only.
        # transform preserves the original row index (no misalignment).
        out[col + "_std"] = grp[col].transform(lambda s: s.shift(1).expanding().mean())
    out["games_played"] = grp.cumcount()
    return out


def _merge_tempo_weather(df: pd.DataFrame) -> pd.DataFrame:
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
        wx = pd.DataFrame(
            s.query(
                Weather.game_id,
                Weather.temperature_f,
                Weather.wind_mph,
                Weather.precipitation,
                Weather.dome,
            ).all(),
            columns=["game_id", "wx_temp", "wx_wind", "wx_precip", "wx_dome"],
        )

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
        for c in ("wx_temp", "wx_wind", "wx_precip", "wx_dome"):
            df[c] = pd.NA
    # dome -> numeric for the model (True/False/NA -> 1.0/0.0/NaN)
    df["wx_dome"] = df["wx_dome"].map({True: 1.0, False: 0.0})
    return df


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
) -> pd.DataFrame:
    games = _load_all_games(fbs_only=fbs_only)
    std = _season_to_date(_team_long(games))

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
    sp = sp_frame(client, sorted(set(yrs + prior_yrs)))
    adv = advanced_frame(client, sorted(set(yrs + prior_yrs)))
    quality = sp.merge(adv, on=["season", "team"], how="outer")
    quality["join_season"] = quality["season"] + 1  # use as next season's prior

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
    df = _merge_tempo_weather(df)

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
