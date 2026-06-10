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
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)  # CFBD team id
    school = Column(String, nullable=False, index=True)
    conference = Column(String)


class Venue(Base):
    __tablename__ = "venues"
    id = Column(Integer, primary_key=True)  # CFBD venue id
    name = Column(String)
    city = Column(String)
    state = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    dome = Column(Boolean)
    elevation = Column(Float)  # meters (CFBD /venues)
    grass = Column(Boolean)  # natural grass surface (vs turf)
    capacity = Column(Integer)


class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True)  # CFBD game id
    season = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    season_type = Column(String)  # regular / postseason
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
    first_half_source = Column(String)  # 'pbp' | 'linescores'

    # Full-game closing total from CFBD /lines (consensus/best available).
    full_game_total = Column(Float)
    full_game_total_book = Column(String)
    # Point spread, home-relative signed (negative = home favored). Drives the
    # spread-adjusted 1H multiplier (favorites score relatively more early).
    spread = Column(Float)

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

    __table_args__ = (UniqueConstraint("season", "week", "team", name="uq_team_week"),)


class FhTeamGame(Base):
    """First-half (period<=2) offensive aggregates for one team in one game.

    Two rows per game (home-offense, away-offense). The OFFENSE's metrics here
    double as the DEFENSE's "allowed" metrics for `def_team` — features.py builds
    season-to-date offense (rows where off_team=T) and defense-allowed (rows
    where def_team=T) expanding means, exactly like the existing fh_pf/fh_pa.
    Computed from play-by-play (cfbfastR parquet 2015-21, CFBD /plays 2022+);
    raw plays are processed transiently and not stored."""

    __tablename__ = "fh_team_game"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    season = Column(Integer, index=True)
    week = Column(Integer)
    off_team = Column(String, index=True)
    def_team = Column(String, index=True)
    is_home = Column(Boolean)
    source = Column(String)  # 'cfbfastr' | 'cfbd'

    n_plays = Column(Integer)  # 1H offensive plays (pace proxy)
    epa = Column(Float)  # mean EPA/play
    success = Column(Float)  # mean(EPA>0)
    explosive = Column(Float)  # mean(yards>=15)
    pass_rate = Column(Float)  # mean(is_pass)
    early_success = Column(Float)  # success on 1st/2nd down
    third_conv = Column(Float)  # 3rd-down conversion rate
    havoc_suffered = Column(Float)  # (TFL+PBU+turnover)/play against this O
    turnovers = Column(Float)  # 1H giveaways (count)
    opening_score = Column(Integer)  # opening drive scored (1/0)
    opening_3out = Column(Integer)  # opening drive <=3 plays, no score (1/0)
    redzone_td = Column(Float)  # 1H red-zone drives scoring a TD
    fourth_go = Column(Float)  # 4th-down go-for-it rate

    __table_args__ = (UniqueConstraint("game_id", "off_team", name="uq_fh_team_game"),)


class TeamTempo(Base):
    """Pace metrics scraped from TeamRankings, as-of a date (leak-free)."""

    __tablename__ = "team_tempo"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, index=True)
    week = Column(Integer, index=True)
    team = Column(String, index=True)  # mapped to CFBD school name
    seconds_per_play = Column(Float)
    plays_per_game = Column(Float)
    as_of_date = Column(String)
    captured_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("season", "week", "team", name="uq_tempo_week"),)


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
    market = Column(String)  # '1H_total' | 'full_game_total'
    line = Column(Float)  # the total for this market
    spread = Column(Float)  # home-relative spread (full_game rows)
    over_price = Column(Integer)
    under_price = Column(Integer)
    captured_at = Column(DateTime, index=True)


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    model_version = Column(String, index=True)
    under_probability = Column(Float)
    under_score = Column(Integer)  # 0-100 display score
    projected_first_half_total = Column(Float)
    bv_line = Column(Float)  # calibrated independent 1H projection
    bv_gap = Column(Float)  # line_used - bv_line (under direction)
    bv_lo = Column(Float)  # 80% prediction band lower bound
    bv_hi = Column(Float)  # 80% prediction band upper bound
    bv_sigma = Column(Float)  # residual std (gap noise scale)
    line_used = Column(Float)
    rank = Column(Integer)
    factors_json = Column(String)  # per-game factor payload for cards
    created_at = Column(DateTime)


class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    model_version = Column(String, index=True)
    market = Column(String, default="1H")  # '1H' | 'full' (the bet market graded)
    # The realized total for `market` (1H points, or full-game points). Named for
    # the original 1H-only ledger; for market='full' it holds the full-game total.
    actual_first_half_total = Column(Integer)
    line_used = Column(Float)
    line_kind = Column(String)  # 'proxy' | 'real'
    under_hit = Column(Boolean)
    closing_line = Column(Float)
    closing_captured_at = Column(DateTime)  # when the closing snapshot landed
    clv = Column(Float)  # points CLV (closing_line - bet_line)
    clv_prob = Column(Float)  # no-vig PRICE CLV, in prob points (juice only)
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
    side = Column(String, default="under")  # under (this project's market)
    market = Column(String, default="1H")  # '1H' | 'full' (first-half vs full-game)
    line = Column(Float)  # the total you bet (1H or full-game per `market`)
    price = Column(Integer, default=-110)
    stake = Column(Float, default=1.0)
    book = Column(String)
    placed_at = Column(DateTime)
    note = Column(String)  # your reason — for later review

    # Snapshot of the model's read at log time (frozen; survives re-scoring).
    model_score_at_pick = Column(Integer)
    model_line_at_pick = Column(Float)

    # Filled by `pick.py grade`.
    graded = Column(Boolean, default=False)
    actual_first_half_total = Column(Integer)
    result = Column(String)  # under / over / push
    units = Column(Float)
    closing_line = Column(Float)
    clv = Column(Float)  # points CLV (closing_line - bet_line)
    clv_prob = Column(Float)  # no-vig PRICE CLV, in prob points (juice only)

    # Decision-quality snapshot (Phase 4b). factors_json_at_pick freezes the
    # factor board at log time (forward-only); opening_line filled at grading.
    factors_json_at_pick = Column(String)
    opening_line = Column(Float)


class BvAdjustment(Base):
    """A manual nudge to the BV line for one game (e.g. a confirmed QB-out the
    model can't see). Display-only: shifts the shown BV line + gap, clearly
    labeled. Latest row per game_id wins."""

    __tablename__ = "bv_adjustments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    delta_pts = Column(Float)  # added to bv_line (− = lower scoring)
    reason = Column(String)
    created_at = Column(DateTime)


class FactorScore(Base):
    """One row per factor (or factor combination) evaluated by the ranking
    harness (scripts/rank_factors.py). `metrics_json` holds the full diagnostic
    payload; the scalar columns are denormalized so the UI/queries can sort
    without parsing JSON. Stored, never a model input."""

    __tablename__ = "factor_scores"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True)  # groups one rank_factors run
    kind = Column(String)  # 'univariate' | 'combo'
    factor = Column(String, index=True)  # column name, or 'a + b' combo key
    family = Column(String)
    leak_free = Column(Boolean)
    market = Column(Boolean)  # derived from a Vegas number
    forward_only = Column(Boolean)  # can't be backtested historically
    n = Column(Integer)  # out-of-sample sample size
    top_under_pct = Column(Float)  # under% in the top-fraction selection
    top_roi = Column(Float)  # ROI on that selection (-110)
    auc = Column(Float)  # walk-forward single/multi-feature AUC
    corr = Column(Float)  # Pearson corr(factor, under) OOS
    perm_importance = Column(Float)  # permutation importance in full GBM
    stability_std = Column(Float)  # std of per-season top under%
    rank = Column(Integer)
    metrics_json = Column(String)
    created_at = Column(DateTime)


class GameRecord(Base):
    """Immutable per-game snapshot — our own model-shaped record (plan Phase 0).

    Frozen pre-kickoff: the leak-free feature vector + the line + our as-of-then
    bv_line/bv_gap. The real 1H result + outcome are filled in AFTER the game
    (the only post-kickoff write). Cumulative from 2023 forward; the shared fuel
    for the Research records grid, the credibility ledger, and bv_line
    recalibration. A separate re-scoreable view re-runs the current model over
    these features — this row is never recomputed.
    """

    __tablename__ = "game_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    season = Column(Integer, index=True)
    week = Column(Integer)
    captured_at = Column(DateTime)  # when the pre-kickoff snapshot was frozen
    model_version = Column(String)  # model that produced the as-of bv_line
    features_json = Column(String)  # leak-free feature vector, as-of kickoff
    line = Column(Float)  # 1H line at snapshot
    line_kind = Column(String)  # 'observed_1h' | 'derived_fg' | 'proxy'
    bv_line = Column(Float)
    bv_gap = Column(Float)
    bv_gap_z = Column(Float)
    under_score = Column(Integer)
    # filled after the game (the only post-kickoff write):
    first_half_total = Column(Integer)
    under_hit = Column(Boolean)
    outcome = Column(String)  # 'under' | 'over' | 'push'
    graded_at = Column(DateTime)


class FactorLedger(Base):
    """The factor credibility ledger: one row per factor's real-line 1H-under
    record (graded by scripts/grade_factor_ledger.py). Cumulative across seasons
    (2023→now); a Beta-binomial posterior over the under hit rate when the factor
    is 'green'. Display + tiering only — never a model input, never moves the rank.
    """

    __tablename__ = "factor_ledger"
    id = Column(Integer, primary_key=True, autoincrement=True)
    factor = Column(String, index=True)  # column name
    n = Column(Integer)  # real-line green-state games graded
    hits = Column(Integer)  # of those, 1H unders that cashed (pushes dropped)
    post_mean = Column(Float)  # posterior mean hit rate
    post_lo = Column(Float)  # 2.5th pct (95% credible interval)
    post_hi = Column(Float)  # 97.5th pct
    tier = Column(Integer)  # displayed tier after evidence (1 if promoted)
    recent_n = Column(Integer)  # trailing-window games (decay detection)
    recent_mean = Column(Float)  # trailing-window hit rate
    drift_flag = Column(Boolean)  # "cooling": recent below breakeven, all-time above
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


class GamePreview(Base):
    """Pre-kickoff research context for a game (news + injuries + QB-out), pulled
    from ESPN by scripts/research_preview.py. DISPLAY ONLY — never a model input
    (ESPN is unofficial, fail-silent). One row per game, refreshed each run."""

    __tablename__ = "game_previews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True, unique=True)
    season = Column(Integer, index=True)
    week = Column(Integer)
    qb_out = Column(Boolean, default=False)
    qb_out_detail = Column(String)
    news_json = Column(String)  # {"home": [...], "away": [...]}
    injuries_json = Column(String)  # {"home": [...], "away": [...]}
    updated_at = Column(DateTime)
