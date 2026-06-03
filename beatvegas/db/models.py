"""SQLAlchemy schema for Beat Vegas. Classic Column style for broad compatibility."""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)          # CFBD team id
    school = Column(String, nullable=False, index=True)
    conference = Column(String)


class Venue(Base):
    __tablename__ = "venues"
    id = Column(Integer, primary_key=True)          # CFBD venue id
    name = Column(String)
    city = Column(String)
    state = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    dome = Column(Boolean)


class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True)          # CFBD game id
    season = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    season_type = Column(String)                    # regular / postseason
    start_date = Column(DateTime)
    neutral_site = Column(Boolean)
    venue_id = Column(Integer, ForeignKey("venues.id"))

    home_team = Column(String, index=True)
    away_team = Column(String, index=True)
    home_team_id = Column(Integer)
    away_team_id = Column(Integer)

    # Final (full-game) scores.
    home_points = Column(Integer)
    away_points = Column(Integer)

    # Derived first-half points (from play-by-play, period <= 2).
    home_first_half_points = Column(Integer)
    away_first_half_points = Column(Integer)
    first_half_total = Column(Integer)
    first_half_source = Column(String)              # 'pbp' | 'linescores'

    # Full-game closing total from CFBD /lines (consensus/best available).
    full_game_total = Column(Float)
    full_game_total_book = Column(String)

    __table_args__ = (UniqueConstraint("id", name="uq_game_id"),)


class TeamWeekFeature(Base):
    """Season-to-date / lagged team metrics, keyed by season+week+team.
    Built leak-free: only data available before that week's kickoff."""
    __tablename__ = "team_week_features"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    team = Column(String, nullable=False, index=True)

    seconds_per_play = Column(Float)
    plays_per_game = Column(Float)
    off_success_rate = Column(Float)
    def_success_rate = Column(Float)
    off_epa_per_play = Column(Float)
    def_epa_per_play = Column(Float)
    off_explosiveness = Column(Float)
    def_explosiveness = Column(Float)
    first_quarter_pf = Column(Float)
    first_quarter_pa = Column(Float)
    first_half_pf = Column(Float)
    first_half_pa = Column(Float)
    sp_overall = Column(Float)
    sp_offense = Column(Float)
    sp_defense = Column(Float)
    run_rate = Column(Float)

    __table_args__ = (
        UniqueConstraint("season", "week", "team", name="uq_team_week"),
    )


class TeamTempo(Base):
    """Pace metrics scraped from TeamRankings, as-of a date (leak-free)."""
    __tablename__ = "team_tempo"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, index=True)
    week = Column(Integer, index=True)
    team = Column(String, index=True)            # mapped to CFBD school name
    seconds_per_play = Column(Float)
    plays_per_game = Column(Float)
    as_of_date = Column(String)
    captured_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("season", "week", "team", name="uq_tempo_week"),
    )


class Weather(Base):
    __tablename__ = "weather"
    game_id = Column(Integer, ForeignKey("games.id"), primary_key=True)
    temperature_f = Column(Float)
    wind_mph = Column(Float)
    precipitation = Column(Float)
    dome = Column(Boolean)


class OddsSnapshot(Base):
    """One row per (game, book, market) observation. Repeated polling builds the
    full movement history; the earliest captured_at = posting time."""
    __tablename__ = "odds_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    book = Column(String)
    market = Column(String)                         # e.g. '1H_total'
    line = Column(Float)
    over_price = Column(Integer)
    under_price = Column(Integer)
    captured_at = Column(DateTime, index=True)


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    model_version = Column(String, index=True)
    under_probability = Column(Float)
    under_score = Column(Integer)             # 0-100 display score
    projected_first_half_total = Column(Float)
    bv_line = Column(Float)                   # calibrated independent 1H projection
    bv_gap = Column(Float)                     # line_used - bv_line (under direction)
    bv_lo = Column(Float)                      # 80% prediction band lower bound
    bv_hi = Column(Float)                      # 80% prediction band upper bound
    bv_sigma = Column(Float)                   # residual std (gap noise scale)
    line_used = Column(Float)
    rank = Column(Integer)
    factors_json = Column(String)             # per-game factor payload for cards
    created_at = Column(DateTime)


class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    model_version = Column(String, index=True)
    actual_first_half_total = Column(Integer)
    line_used = Column(Float)
    line_kind = Column(String)                      # 'proxy' | 'real'
    under_hit = Column(Boolean)
    closing_line = Column(Float)
    closing_captured_at = Column(DateTime)          # when the closing snapshot landed
    clv = Column(Float)
    units = Column(Float)


class ManualPick(Base):
    """Your own first-half bets, logged for grading vs the real result + CLV."""
    __tablename__ = "manual_picks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    season = Column(Integer, index=True)
    week = Column(Integer)
    home_team = Column(String)
    away_team = Column(String)
    side = Column(String, default="under")      # under (this project's market)
    line = Column(Float)                         # the 1H total you bet
    price = Column(Integer, default=-110)
    stake = Column(Float, default=1.0)
    book = Column(String)
    placed_at = Column(DateTime)
    note = Column(String)                        # your reason — for later review

    # Snapshot of the model's read at log time (frozen; survives re-scoring).
    model_score_at_pick = Column(Integer)
    model_line_at_pick = Column(Float)

    # Filled by `pick.py grade`.
    graded = Column(Boolean, default=False)
    actual_first_half_total = Column(Integer)
    result = Column(String)                      # under / over / push
    units = Column(Float)
    closing_line = Column(Float)
    clv = Column(Float)


class BvAdjustment(Base):
    """A manual nudge to the BV line for one game (e.g. a confirmed QB-out the
    model can't see). Display-only: shifts the shown BV line + gap, clearly
    labeled. Latest row per game_id wins."""
    __tablename__ = "bv_adjustments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    delta_pts = Column(Float)                    # added to bv_line (− = lower scoring)
    reason = Column(String)
    created_at = Column(DateTime)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String, index=True)
    train_window = Column(String)
    test_window = Column(String)
    metrics_json = Column(String)
    notes = Column(String)
    created_at = Column(DateTime)
