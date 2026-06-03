"""Assemble a leak-free per-game feature frame for the 1H-under model.

Two feature families, both strictly using pre-kickoff information:
  1. Season-to-date 1H/full scoring (expanding mean over the team's *prior*
     games this season, shifted to exclude the current game).
  2. Prior-season team quality/efficiency (SP+, advanced PPA/success/explosive)
     joined from season-1 — a stable preseason prior with zero same-season leak.

Target: under = realized 1H total < proxy 1H line (0.52 * full-game total).
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from ..db.store import session_scope
from ..db.models import Game, TeamTempo, Weather
from .proxy_line import proxy_total
from .situational import SITUATIONAL_COLS, situational_frame
from ..sources.cfbd import CFBDClient
from ..sources.season_stats import advanced_frame, returning_frame, sp_frame

# Feature columns handed to the model (filled below).
FEATURE_COLS: List[str] = [
    "full_game_total", "week", "neutral_site",
    "proj_1h_total", "proj_1h_ratio",
    "home_fh_pf", "home_fh_pa", "away_fh_pf", "away_fh_pa",
    "combined_fh_offense", "combined_fh_defense",
    "home_full_pf", "home_full_pa", "away_full_pf", "away_full_pa",
    "home_sp_off", "home_sp_def", "away_sp_off", "away_sp_def",
    "home_off_ppa", "home_def_ppa", "away_off_ppa", "away_def_ppa",
    "home_off_success", "away_off_success",
    "combined_off_ppa", "combined_def_ppa",
    "home_returning_ppa", "away_returning_ppa",
    # situational (schedule-derived; fully historical)
    "home_rest_days", "away_rest_days", "home_short_week", "away_short_week",
    "home_off_bye", "away_off_bye", "away_travel_dist", "away_tz_shift",
    "kickoff_local_hour", "early_kickoff",
    # pace + weather (populated by scripts/backfill_enrichment.py)
    "combined_sec_play", "combined_plays",
    "wx_temp", "wx_wind", "wx_precip", "wx_dome",
    # era: 2023 NCAA running-clock rule cut ~8 plays/game (scoring-regime shift)
    "era_post2023",
]


def _load_all_games() -> pd.DataFrame:
    with session_scope() as s:
        q = s.query(
            Game.id, Game.season, Game.week, Game.start_date, Game.neutral_site,
            Game.home_team, Game.away_team, Game.home_points, Game.away_points,
            Game.home_first_half_points, Game.away_first_half_points,
            Game.first_half_total, Game.full_game_total,
        )
        df = pd.DataFrame(q.all(), columns=[
            "id", "season", "week", "start_date", "neutral_site",
            "home_team", "away_team", "home_points", "away_points",
            "home_fh", "away_fh", "first_half_total", "full_game_total",
        ])
    df["neutral_site"] = df["neutral_site"].fillna(False).astype(int)
    return df


def _team_long(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team) with that team's 1H/full points for & against."""
    home = pd.DataFrame({
        "id": df["id"], "season": df["season"], "week": df["week"],
        "start_date": df["start_date"], "team": df["home_team"],
        "fh_pf": df["home_fh"], "fh_pa": df["away_fh"],
        "full_pf": df["home_points"], "full_pa": df["away_points"],
    })
    away = pd.DataFrame({
        "id": df["id"], "season": df["season"], "week": df["week"],
        "start_date": df["start_date"], "team": df["away_team"],
        "fh_pf": df["away_fh"], "fh_pa": df["home_fh"],
        "full_pf": df["away_points"], "full_pa": df["home_points"],
    })
    return pd.concat([home, away], ignore_index=True)


def _season_to_date(long: pd.DataFrame) -> pd.DataFrame:
    """Expanding mean of each metric over the team's prior games this season."""
    long = long.sort_values(["season", "team", "week", "start_date"],
                            na_position="last")
    grp = long.groupby(["season", "team"], sort=False)
    out = long[["id", "season", "team"]].copy()
    for col in ["fh_pf", "fh_pa", "full_pf", "full_pa"]:
        # shift(1) excludes the current game -> strictly prior info only.
        # transform preserves the original row index (no misalignment).
        out[col + "_std"] = grp[col].transform(
            lambda s: s.shift(1).expanding().mean())
    out["games_played"] = grp.cumcount()
    return out


def _merge_tempo_weather(df: pd.DataFrame) -> pd.DataFrame:
    """Exact (season, week, team) join for pace + (game_id) join for weather."""
    with session_scope() as s:
        tempo = pd.DataFrame(
            s.query(TeamTempo.season, TeamTempo.week, TeamTempo.team,
                    TeamTempo.seconds_per_play, TeamTempo.plays_per_game).all(),
            columns=["season", "week", "team", "sec_play", "plays"])
        wx = pd.DataFrame(
            s.query(Weather.game_id, Weather.temperature_f, Weather.wind_mph,
                    Weather.precipitation, Weather.dome).all(),
            columns=["game_id", "wx_temp", "wx_wind", "wx_precip", "wx_dome"])

    for side in ("home", "away"):
        t = tempo.rename(columns={
            "team": f"{side}_team", "sec_play": f"{side}_sec_play",
            "plays": f"{side}_plays"})
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


def build_feature_frame(min_games: int = 2,
                        seasons: Optional[range] = None,
                        client: Optional[CFBDClient] = None) -> pd.DataFrame:
    games = _load_all_games()
    std = _season_to_date(_team_long(games))

    # Merge season-to-date stats back, matching each side on its own team name.
    df = games.copy()
    home_only = std.rename(columns={"team": "home_team"})
    away_only = std.rename(columns={"team": "away_team"})
    home_only = home_only.add_prefix("h_").rename(
        columns={"h_id": "id", "h_season": "season", "h_home_team": "home_team"})
    away_only = away_only.add_prefix("a_").rename(
        columns={"a_id": "id", "a_season": "season", "a_away_team": "away_team"})
    df = df.merge(home_only[["id", "home_team", "h_fh_pf_std", "h_fh_pa_std",
                             "h_full_pf_std", "h_full_pa_std", "h_games_played"]],
                  on=["id", "home_team"], how="left")
    df = df.merge(away_only[["id", "away_team", "a_fh_pf_std", "a_fh_pa_std",
                             "a_full_pf_std", "a_full_pa_std", "a_games_played"]],
                  on=["id", "away_team"], how="left")

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
            q, left_on=["season", f"{side}_team"],
            right_on=[f"{side}_q_join_season", f"{side}_q_team"], how="left")

    # Returning production — SAME-season prior (known preseason, leak-free).
    ret = returning_frame(client, yrs)
    for side in ["home", "away"]:
        rr = ret.add_prefix(f"{side}_r_")
        df = df.merge(
            rr, left_on=["season", f"{side}_team"],
            right_on=[f"{side}_r_season", f"{side}_r_team"], how="left")

    # --- assemble model features -------------------------------------
    df["home_fh_pf"] = df["h_fh_pf_std"]
    df["home_fh_pa"] = df["h_fh_pa_std"]
    df["away_fh_pf"] = df["a_fh_pf_std"]
    df["away_fh_pa"] = df["a_fh_pa_std"]
    df["home_full_pf"] = df["h_full_pf_std"]
    df["home_full_pa"] = df["a_full_pa_std"]  # opponent allows
    df["away_full_pf"] = df["a_full_pf_std"]
    df["away_full_pa"] = df["h_full_pa_std"]

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

    # Era flag: post-2023 running-clock rule (leak-free; season known pre-kickoff).
    df["era_post2023"] = (df["season"] >= 2023).astype(float)

    # --- display enrichment: pace (TeamRankings) + weather (Open-Meteo) ----
    # Joined for the card factor payload, NOT added to FEATURE_COLS (history
    # has no tempo/weather yet, so they'd be inert as model inputs).
    df = _merge_tempo_weather(df)

    # --- situational features (schedule-derived; real model inputs) ---
    df = df.merge(situational_frame(), on="id", how="left")

    # --- target + filters --------------------------------------------
    df = df[df["full_game_total"].notna() & df["first_half_total"].notna()
            & (df["full_game_total"] > 0)].copy()
    df["proxy_line"] = df["full_game_total"].apply(lambda t: proxy_total(t, 0.52))
    df = df[df["first_half_total"] != df["proxy_line"]]   # drop pushes
    df["under"] = (df["first_half_total"] < df["proxy_line"]).astype(int)

    df = df[(df["h_games_played"] >= min_games)
            & (df["a_games_played"] >= min_games)]
    if seasons is not None:
        df = df[df["season"].isin(list(seasons))]

    # Model columns must be clean numeric floats (NaN, never pd.NA / None / bool).
    for c in FEATURE_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.reset_index(drop=True)
