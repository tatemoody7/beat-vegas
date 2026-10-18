"""SQLAlchemy schema for Beat Vegas. Classic Column style for broad compatibility."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
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
    # IANA zone (CFBD /venues `timezone`, 2026-10-17): the venue's real wall clock
    # for kickoff_local_hour / away_tz_shift. NULL when CFBD has none -- those
    # features go NaN, never a longitude guess (etl/situational.py).
    timezone = Column(String)


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
    first_half_source = Column(String)  # 'pbp' | 'linescores' | 'linescores_verified' (grading.py)

    # Full-game total: the Sunday/card-day opener capture (Odds API / DK) or
    # CFBD /lines (consensus/best available) when nothing live was captured.
    full_game_total = Column(Float)
    full_game_total_book = Column(String)
    # Point spread, home-relative signed (negative = home favored). Drives the
    # spread-adjusted 1H multiplier (favorites score relatively more early).
    spread = Column(Float)
    # Who last wrote the total / spread: 'cfbd' | 'oddsapi' | 'dk'. A live
    # source (oddsapi/dk) is protected from Monday's CFBD upsert — see
    # beatvegas/line_sources.py.
    full_game_total_source = Column(String)
    spread_source = Column(String)
    # The OPENING spread, and the reason it is a separate column rather than a
    # reading of `spread` above.
    #
    # `spread` is MUTABLE: every capture that carries one overwrites it, so what
    # is stored is whatever the last run before the row went quiet happened to
    # see — effectively a closing number, with no timestamp saying so. Any model
    # that reads it while pretending to price a game on Tuesday is using
    # Saturday's information. Measured on 2026 (the only season carrying
    # per-snapshot spreads): the spread moves a median 1.5 points over a game's
    # snapshot history, 3.0 at the 90th percentile, and only 4 of 142 games
    # never moved at all. Since spread is the primary driver of the first-half
    # share, that leak flows straight into the target.
    #
    # `spread_open` is IMMUTABLE by construction — an opening line is a
    # historical fact, so it is a legitimate as-of feature at the one timestamp
    # the pre-2026 snapshot history cannot otherwise supply. Written only where
    # NULL (scripts/backfill_spread_open.py); re-running never churns it.
    spread_open = Column(Float)
    spread_open_source = Column(String)
    # CFBD's homeConference / awayConference for the game (2026-10-04): the
    # conference the team belonged to THAT season, as /games reports it, so a
    # slice by conference does not read today's membership onto an old row.
    # Filled by scripts/backfill.py on upsert; NULL on rows older than the column.
    home_conference = Column(String)
    away_conference = Column(String)
    # CFBD's pregame Elo per side (2026-10-06, H-ELO-F): `/games`
    # homePregameElo / awayPregameElo, set before kickoff (leak-free as of the
    # game). Read by the H-ELO-F study arm only; not a champion input.
    home_pregame_elo = Column(Float)
    away_pregame_elo = Column(Float)

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


class WeatherObs(Base):
    """Weather for a game AT A STATED LEAD, with the provenance to prove it.

    The legacy `weather` table stored four bare numbers keyed by game, which made
    two different things indistinguishable six months later: what the conditions
    WERE around kickoff, and what the forecast SAID while a bet was still
    placeable. Those answer different questions, and using the first to argue an
    edge is look-ahead bias. So the lead is part of the key and `decision_safe`
    is stored rather than inferred.

    `lead_hours = 0` is the near-kickoff series, which tracks actual conditions
    (measured 1.82F / 1.55mph from the ERA5 actual, closer than a 1-day-lead
    forecast). It is NEVER decision-safe and may never feed a real-money model --
    `etl.features.WEATHER_OBS_LEAD_HOURS` refuses it outright.

    THREE DIFFERENT TIMES, and conflating them is how false precision gets in:
      lead_hours      the NOMINAL horizon we asked for. Always known. Never
                      inferred from anything else.
      model_run_time  when the run behind this value initialised. NULL unless the
                      source actually states it -- Open-Meteo does not, for the
                      `_previous_dayN` variables.
      available_at    when that run became publicly usable, which is LATER than
                      the run time (a global model takes hours to finish and
                      distribute). NULL until a source gives it.
    `available_at <= decision_time` is the invariant worth having. Until
    available_at is populated, the nominal lead is the weaker guarantee we
    actually have, and the docs say so rather than pretending otherwise.

    Keyed on a surrogate id, NOT (game_id, lead_hours): comparing ICON against
    GFS, changing provider, or keeping two runs of the same horizon all have to
    be possible without overwriting history. The uniqueness constraint lives in
    store.py as an expression index, because Postgres treats NULLs as distinct.
    """

    __tablename__ = "weather_obs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    lead_hours = Column(Integer, nullable=False)  # nominal; 0 = near kickoff
    valid_time = Column(DateTime)  # the kickoff hour this value describes (UTC)
    model_run_time = Column(DateTime)  # nullable -- only when the source states it
    available_at = Column(DateTime)  # nullable -- when that run became public
    decision_safe = Column(Boolean, nullable=False, default=False)
    temperature_f = Column(Float)
    wind_mph = Column(Float)
    wind_gust_mph = Column(Float)
    precipitation = Column(Float)
    dome = Column(Boolean)
    source = Column(String)  # beatvegas.sources.weather.SOURCE_*
    weather_model = Column(String)  # Open-Meteo `models=`, where pinned
    dataset_version = Column(String)  # bump when the fetch methodology changes
    latitude = Column(Float)  # the coordinates actually used, not a join at read time
    longitude = Column(Float)
    retrieved_at = Column(DateTime)

    __table_args__ = (
        Index("ix_weather_obs_game_lead", "game_id", "lead_hours"),
        Index("ix_weather_obs_decision_safe", "decision_safe"),
    )


class ArmPosition(Base):
    """Where each registered hypothesis stood at one Monday read (2026-10-14,
    programme step 10): ONE row per hypothesis per read date, written only by the
    Monday workflow (`scripts/protocol_position.py --write` for the six arms,
    `scripts/pricing_check.py --write` for H-PRICE-HR) and read by the site, the
    Monday read and the January review -- one source, so none of them can
    disagree. A retry on the same day rewrites the row (unique on hypothesis +
    read_date) with the newer run id; nothing here recomputes a position.
    """

    __tablename__ = "arm_positions"
    __table_args__ = (
        UniqueConstraint("hypothesis", "read_date", name="uq_arm_position_per_read_date"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    hypothesis = Column(String, nullable=False, index=True)  # registry id
    standard = Column(
        String, nullable=False
    )  # sprt (an arm) | pricing (H-PRICE-HR) | exploratory (H-ARM-EVP)
    read_date = Column(String, nullable=False)  # YYYY-MM-DD, the UTC date of the read
    read_at = Column(DateTime, nullable=False)  # naive UTC
    run_id = Column(String)  # GITHUB_RUN_ID of the writer, '-' locally
    state = Column(String)  # protocol state word or the pricing verdict word
    label = Column(String)  # the human label the report prints
    logged = Column(Integer)
    readings = Column(Integer)
    weeks = Column(Integer)
    excluded = Column(Integer)
    pending = Column(Integer)
    needed = Column(Integer)  # readings before the first decision window (30) / opportunities (40)
    llr = Column(Float)
    mean_ev = Column(Float)
    ev_lo = Column(Float)
    ev_hi = Column(Float)
    next_read = Column(String)  # YYYY-MM-DD
    payload_json = Column(Text)  # the writer's full line, for the record


class ShortlistEntry(Base):
    """One entry of a frozen research-shortlist publication (H-1H-SHORTLIST, website plan PR D,
    Tate 2026-10-15): the top 10 first-half unders a scheduled card's price-first ranking put on
    top. Written once per card by `scripts/publish_shortlist.py` (insert-only: a card that already
    has rows is never re-ranked or rewritten) and read by the site. The publication-level columns
    repeat on every row so the whole publication, and its sha256, can be rebuilt from the rows
    (`shortlist.publication_from_rows`)."""

    __tablename__ = "shortlist_entries"
    __table_args__ = (UniqueConstraint("card_id", "game_id", name="uq_shortlist_entry_per_card"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(Integer, nullable=False, index=True)  # cards.id this ranking read
    season = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False)
    slot = Column(String, nullable=False)  # tue_pm | thu_pm | fri_pm | sat_am
    published_at = Column(DateTime, nullable=False)  # naive UTC
    card_built = Column(String)  # the card's built_at, ISO (the decision time of the analysis)
    pool_size = Column(Integer)  # games the ranking considered
    method = Column(String)
    publication_sha256 = Column(String, nullable=False)
    game_id = Column(Integer, nullable=False, index=True)
    rank = Column(Integer, nullable=False)  # R1..R10, the research rank (never the Board's)
    label = Column(String, nullable=False)
    payload_json = Column(Text, nullable=False)  # the frozen entry: price, analysis, why_rank


class BuildForecast(Base):
    """The forecast a card build SAW: one row per game per build that fetched it.

    Written by `beatvegas.wx_paper.capture` during each decision build (registry
    rows H-ARM-WX1H / H-ARM-WXFG, Tate's calls of 2026-10-09). Decision-safe by
    construction: `fetched_at` is the build's own clock and always precedes the
    kickoff it describes. Kept out of `weather_obs` on purpose: that table's
    backfill deletes and rewrites rows by lead, and its studies read fixed
    leads, so build-time rows there could be wiped or mixed into a frozen study.
    Nothing but the weather arms reads it.
    """

    __tablename__ = "build_forecasts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    fetched_at = Column(DateTime, nullable=False)  # the build's clock, naive UTC
    kickoff = Column(DateTime)  # the game's start_date when fetched (naive UTC)
    lead_hours = Column(Float)  # kickoff - fetched_at, in hours
    slot = Column(String)  # the build that fetched it
    temperature_f = Column(Float)
    wind_mph = Column(Float)  # sustained 10 m wind at the kickoff hour
    wind_gust_mph = Column(Float)
    precipitation = Column(Float)
    dome = Column(Boolean)
    latitude = Column(Float)
    longitude = Column(Float)
    source = Column(String)  # beatvegas.sources.weather.SOURCE_FORECAST
    weather_model = Column(String)  # pinned, as weather_obs's history

    __table_args__ = (Index("ix_build_forecasts_game_fetched", "game_id", "fetched_at"),)


class WeatherActual(Base):
    """OBSERVED weather around a played game, hour by hour -- a study table.

    Written by scripts/backfill_weather_actuals.py (2026-10-08, roadmap v1.3) for
    the Salaga & Howley history look (docs/LITERATURE.md): wind and rain averaged
    over the game, temperature and humidity at kickoff. NOTHING ELSE READS IT. It
    is kept out of `weather` (the champion reads that table) and out of
    `weather_obs` (studies read that table's newest lead-0 row per game, which
    ERA5 rows would shadow), so filling it can never move the model or a frozen
    study.

    These are actuals, never decision-safe: what the conditions WERE, not what
    anyone could have known before kickoff.

    Two sources, side by side (a cross-check, not a blend):
      open_meteo_era5_archive  ERA5 reanalysis, hourly, `models=era5` pinned so
                               every season comes from one model; one row per
                               hour from `hour_offset` -1 to +4 around the
                               kickoff hour (offset 0 = the UTC hour the game
                               kicks off in).
      cfbd_games_weather       CFBD /games/weather, one reading per game
                               (provider unnamed), stored at hour_offset 0.
    """

    __tablename__ = "weather_actuals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    source = Column(String, nullable=False)
    hour_offset = Column(Integer, nullable=False)  # hours from the kickoff hour
    valid_time = Column(DateTime)  # the UTC hour this row describes
    kickoff_utc = Column(DateTime)  # Game.start_date as fetched (naive UTC)
    temperature_f = Column(Float)
    humidity_pct = Column(Float)
    dew_point_f = Column(Float)
    wind_mph = Column(Float)
    wind_gust_mph = Column(Float)
    wind_direction_deg = Column(Float)
    precipitation_in = Column(Float)  # ERA5: the hour's total; CFBD: as reported
    snowfall_in = Column(Float)  # CFBD only, as reported
    pressure = Column(Float)  # CFBD only, as reported (unit undocumented)
    weather_code = Column(Integer)  # CFBD weatherConditionCode
    game_indoors = Column(Boolean)  # CFBD gameIndoors; NULL for ERA5 rows
    latitude = Column(Float)  # the coordinates actually used (ERA5 rows)
    longitude = Column(Float)
    weather_model = Column(String)  # Open-Meteo `models=` (era5)
    dataset_version = Column(String, nullable=False)
    retrieved_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "source",
            "hour_offset",
            "dataset_version",
            name="uq_weather_actual_reading",
        ),
        Index("ix_weather_actuals_game", "game_id"),
    )


class OddsSnapshot(Base):
    """One row per (game, book, market) observation. Repeated polling builds the
    full movement history; the earliest captured_at = posting time."""

    __tablename__ = "odds_snapshots"
    # DB-level backstop against duplicate captures: GHA concurrency groups
    # already serialize the writers, but one misconfigured/parallel run must not
    # silently double the movement history. (Each poll writes at most one row
    # per (game, book, market), so legit rows never share a captured_at.)
    __table_args__ = (
        UniqueConstraint("game_id", "book", "market", "captured_at", name="uq_odds_snapshot"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    book = Column(String)
    # '1H_total' | 'full_game_total' | 'full_game_spread' | 'full_game_ml'
    # (the last two since 2026-10-07, roadmap step 4; every reader filters on it)
    market = Column(String)
    # The total for a totals market; the HOME point for 'full_game_spread'
    # (negative = home favoured); NULL for 'full_game_ml'.
    line = Column(Float)
    spread = Column(Float)  # home-relative spread (full_game_total rows)
    over_price = Column(Integer)  # totals markets only
    under_price = Column(Integer)
    # Side markets ('full_game_spread', 'full_game_ml'): each team's price.
    home_price = Column(Integer)
    away_price = Column(Integer)
    captured_at = Column(DateTime, index=True)
    # Snapshots are written on CHANGE only, so a pre-kick poll that finds the
    # number unchanged leaves no row; it stamps the moment it re-confirmed this
    # one instead. lines.closing_before_kickoff reads it as the close time.
    last_seen_at = Column(DateTime)
    # Capture provenance (2026-10-11, docs/program/CAPTURE_DESIGN_2026-10.md).
    # Three stamps, three meanings: `captured_at` is OUR first poll that saw
    # this price state; `last_seen_at` is our last poll that still saw it
    # unchanged; `feed_updated_at` is The Odds API's `last_update` for the quote
    # at that first capture -- the PROVIDER's last observation of the book, not
    # when the book posted it, and never overwritten. A later poll that finds
    # the same price under a newer provider stamp records that stamp in
    # `feed_reseen_at` (the newest such stamp), so the original freshness
    # reading survives. Availability in the Florida app is a fourth fact no
    # column holds. `event_id` is the feed's own key for the event.
    event_id = Column(String)
    feed_updated_at = Column(DateTime)
    feed_reseen_at = Column(DateTime)


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
    # The global calibration intercept bv_line_for_slate ADDED to this row
    # (bias_corrections(train)['global']). Stored so the raw, pre-intercept
    # prediction stays recoverable as bv_line - bv_intercept: H-INSEASON-P's
    # arms need raw residuals, and re-deriving them would mean refitting.
    bv_intercept = Column(Float)
    line_used = Column(Float)
    rank = Column(Integer)
    factors_json = Column(String)  # per-game factor payload for cards
    # Model identity (2026-10-04): which weekly refit produced this number.
    # `refit_id` is the `model_runs.id` scripts/weekly_update.py wrote for the
    # run that scored this row; `fingerprint` is that run's data-only frame
    # digest (etl/frame_fingerprint.fingerprint_hash). `model_version` stays the
    # engine's tag; these two say WHICH fit of it. NULL on rows scored before
    # the columns existed, and on a caller that scores outside weekly_update.
    refit_id = Column(Integer)
    fingerprint = Column(String)
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
    # The book's own closing PRICE, kept separate from the price at the DECISION.
    # Until 2026-09-14 a Hard Rock pick logged without a price had `price`
    # BACKFILLED with this value at grading time, which makes any price-based CLV
    # identically zero by construction and erases the difference between the two.
    # `price` is now never overwritten -- unknown stays NULL -- and the close
    # lives here.
    closing_price = Column(Integer)
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
    # No column default: an unpriced Hard Rock line is logged as NULL and the
    # Monday grader fills it from HR's pre-kick close (callers pass -110 themselves).
    price = Column(Integer)
    stake = Column(Float, default=1.0)
    # Paper pick: nothing at risk, staked ONE flat unit so it grades as +/-1u
    # on its own record. Every ledger consumer must split on is_paper.
    is_paper = Column(Boolean, default=False)
    # Bonus/free bet: the book funded the stake, so a LOSS costs nothing and a
    # WIN pays the profit only (the stake is not returned). Graded by
    # picks.graded_pick_fields, which floors units at 0 for these. It is a real
    # ticket, so is_paper stays False - but it risks no bankroll, so it does
    # not consume one of the week's five real-money cap slots.
    is_bonus = Column(Boolean, default=False)
    book = Column(String)
    placed_at = Column(DateTime)  # when the row was LOGGED (the server's clock)
    # When the ticket was WRITTEN, when that is not the log time (2026-09-28).
    # Two week-4 tickets were bet Friday at the card's numbers and logged the
    # next morning, when the server judged the live Saturday read and stamped
    # WATCH -- two on-policy bets read as overrides. NULL = logged at bet time.
    # The ledger's hours-before-kickoff and the verdict snapshot use this when
    # set (web/lib/pickRules.ts verdictAtBetTime); placed_at stays the log time.
    bet_at = Column(DateTime)
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
    # When the consensus close above was last confirmed pre-kickoff (the freshest
    # centred pre-kick snapshot / last_seen_at). H-STOP-2's line-value clock
    # counts a pick only when this sits inside lines.REAL_1H_CLOSE_WINDOW_H of
    # kickoff; the clv column itself is stored whatever the age, so the history
    # stays comparable and the age can be cut afterwards. 2026-09-22.
    closing_captured_at = Column(DateTime)
    # The book's own closing PRICE, kept separate from the price at the DECISION.
    # Until 2026-09-14 a Hard Rock pick logged without a price had `price`
    # BACKFILLED with this value at grading time, which makes any price-based CLV
    # identically zero by construction and erases the difference between the two.
    # `price` is now never overwritten -- unknown stays NULL -- and the close
    # lives here.
    closing_price = Column(Integer)
    # Where `price` came from: 'logged' (given at decision time), 'backfilled_close'
    # (written by the pre-2026-09-14 grader and therefore NOT a decision price),
    # or 'unknown' (pre-dates this column and could not be reconstructed).
    # scripts/reconstruct_pick_prices.py classifies the rows that pre-date the fix;
    # anything not 'logged' must be excluded from price-based CLV rather than
    # quietly diluting it toward zero.
    price_provenance = Column(String)
    # What an audit could not verify about a real ticket (2026-10-17).
    audit_flag = Column(Text)
    # Why the pick is left out of every record ('alt_line'; 2026-10-17).
    excluded_reason = Column(Text)
    clv = Column(Float)  # points CLV (closing_line - bet_line)
    clv_prob = Column(Float)  # no-vig PRICE CLV, in prob points (juice only)

    # Decision-quality snapshot (Phase 4b). factors_json_at_pick freezes the
    # factor board at log time (forward-only); opening_line filled at grading.
    factors_json_at_pick = Column(String)
    opening_line = Column(Float)
    # The weekly refit the pick was logged against (predictions.refit_id of the
    # model row read at log time; 2026-10-04). Copied, never joined later: the
    # prediction row is delete-then-insert on every re-score.
    refit_id = Column(Integer)

    # Decision tracking (shared contract with web/ — names are exact). What the
    # board said at log time, so hit rate can be split by why the bet was made.
    verdict_at_pick = Column(String(8))  # BET | WATCH | PASS
    reason = Column(String(16))  # model_gap | price_edge | manual
    gap_at_pick = Column(Float)  # bv_gap (points) shown at log time
    ev_at_pick = Column(Float)  # no-vig EV of the under at log time
    hr_line_at_pick = Column(Float)  # Hard Rock's line at log time
    # Paper ledger only: which gate blocked a real bet on this qualifying game
    # (Hard Rock's 1H line >= BET_GAP_PTS above ours). none = it was a BET;
    # price | off_market | qb_out | cap (6th+ by gap that week). NULL on real
    # picks and legacy rows. The post-mortem groups the paper record by it.
    blocker = Column(String(16))

    # Line value at the wager's exact terms (beatvegas/consensus.py, docs/CONSENSUS.md;
    # 2026-10-07). The research program's judge: EV per unit of this line and price
    # against the median de-vigged close of every counted book (Hard Rock and Fliff
    # excluded), converted through the half-point table. Written at grading and by
    # scripts/consensus_backfill.py; `cons_version` names the engine that wrote them.
    cons_version = Column(String(8))
    cons_books = Column(Integer)  # books counted in the median
    cons_line = Column(Float)  # the median of those books' closing lines
    cons_close_at = Column(DateTime)  # the newest counted confirmation before kickoff
    cons_p_win = Column(Float)  # consensus fair chance this wager wins
    cons_p_push = Column(Float)  # ...and pushes (integer lines only)
    ev_cons = Column(Float)  # EV per unit vs the consensus close: the judge
    ev_hr = Column(Float)  # EV per unit vs Hard Rock's own closing main quote (secondary)
    cons_excluded = Column(String(32))  # why there is no reading (few_books, ...)
    # The registered protocol arm a PAPER pick belongs to (docs/HYPOTHESES.md,
    # e.g. 'H-ARM-1HU'; 2026-10-08). Written by the card build from the arm's
    # first eligible build on; NULL on real tickets and on development rows.
    arm = Column(String(16))


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
    # Which 1H engine produced that bv_line: 'bv_line' (incumbent, market-blind)
    # or 'residual' (market-residual). Stamped PER ROW, because under the
    # residual engine a row with no real posted 1H line falls back to the
    # incumbent. NULL on records frozen before this field existed.
    engine = Column(String)
    features_json = Column(String)  # leak-free feature vector, as-of kickoff
    line = Column(Float)  # 1H line at snapshot
    line_kind = Column(String)  # 'hr_1h' | 'observed_1h' | 'derived_fg' | 'proxy'
    bv_line = Column(Float)
    bv_gap = Column(Float)
    bv_gap_z = Column(Float)
    under_score = Column(Integer)
    # The conferences as `games` carries them at snapshot time (2026-10-04),
    # so a slice of the frozen records by conference needs no join.
    home_conference = Column(String)
    away_conference = Column(String)
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
    # One grading run's rows share a run_id (2026-10-04; GITHUB_RUN_ID, or a
    # UTC stamp off the runner). Rows are kept, never replaced: readers take
    # the newest run_id (factors.ledger.load_ledger, web/lib/decision-quality.ts)
    # and the history says how each factor's posterior moved week to week.
    # NULL on rows written before the column existed (the last overwrite).
    run_id = Column(String, index=True)
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


class ChallengerPick(Base):
    """A paper pick from one arm of the H-INSEASON challenger family.

    DELIBERATELY NOT A COLUMN ON `manual_picks`. Four arms plus the champion's
    own paper pick are all `is_paper=true` on the same game and market, which
    `uq_manual_pick_per_ledger` forbids outright -- but the reason for a separate
    table is stronger than the index: every query that feeds the bankroll, the
    5-bet cap, Results and H-STOP's observation set reads `manual_picks`, and a
    single missed `arm IS NULL` filter would contaminate the champion's clock.
    Isolation here is structural rather than remembered.

    Never real money. `is_paper` is not a column because there is no other kind.
    Registry row H-INSEASON-P; spec in docs/INSEASON_PAPER.md.
    """

    __tablename__ = "challenger_picks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    arm = Column(String, index=True)  # 'k25' | 'k50' | 'k100' | 'k200'
    game_id = Column(Integer, ForeignKey("games.id"), index=True)
    season = Column(Integer, index=True)
    week = Column(Integer)
    home_team = Column(String)
    away_team = Column(String)
    side = Column(String, default="under")
    market = Column(String, default="1H")

    # Frozen at the decision, exactly as the champion's paper ledger freezes them.
    line = Column(Float)  # the Hard Rock 1H total the arm would have taken
    price = Column(Integer)
    stake = Column(Float, default=1.0)  # one flat unit, so units/ROI compare
    book = Column(String)
    slot = Column(String)  # which build made the decision
    placed_at = Column(DateTime)
    blocker = Column(String)  # the gate that would have blocked a real bet

    # The arm's own read, and the champion's beside it for the paired diagnostic.
    arm_line_at_pick = Column(Float)  # the arm's bv_line
    champion_line_at_pick = Column(Float)  # the champion's bv_line, same build
    c_prior = Column(Float)
    c_season = Column(Float)
    in_season_n = Column(Integer)  # completed games the arm could see
    in_season_weight = Column(Float)  # w = n / (n + k)
    gap_at_pick = Column(Float)
    # When the consensus close was last confirmed pre-kick (grade_pick writes it
    # for every ledger); the H-NEGGAP-P line-value clock cuts on its age. 2026-09-28.
    closing_captured_at = Column(DateTime)
    # The same frozen snapshot manual_picks carries (2026-10-04): the market
    # chips, the prediction's factors and the model's input vector at the
    # build (`picks.freeze_factors`), and the weekly refit the number came from.
    factors_json_at_pick = Column(Text)
    refit_id = Column(Integer)

    # Every field `picks.graded_pick_fields` returns, under the same names, so
    # `picks.grade_pick` grades an arm's observation with the champion's own code
    # rather than a copy of it. tests/test_challenger.py pins the correspondence.
    graded = Column(Boolean, default=False)
    actual_first_half_total = Column(Integer)
    result = Column(String)  # under / over / push
    units = Column(Float)
    opening_line = Column(Float)
    closing_line = Column(Float)
    clv = Column(Float)  # closing - bet; for an under, NEGATIVE is favourable
    clv_prob = Column(Float)
    closing_price = Column(Integer)

    # Line value at the wager's exact terms (beatvegas/consensus.py, docs/CONSENSUS.md;
    # 2026-10-07). The research program's judge: EV per unit of this line and price
    # against the median de-vigged close of every counted book (Hard Rock and Fliff
    # excluded), converted through the half-point table. Written at grading and by
    # scripts/consensus_backfill.py; `cons_version` names the engine that wrote them.
    cons_version = Column(String(8))
    cons_books = Column(Integer)  # books counted in the median
    cons_line = Column(Float)  # the median of those books' closing lines
    cons_close_at = Column(DateTime)  # the newest counted confirmation before kickoff
    cons_p_win = Column(Float)  # consensus fair chance this wager wins
    cons_p_push = Column(Float)  # ...and pushes (integer lines only)
    ev_cons = Column(Float)  # EV per unit vs the consensus close: the judge
    ev_hr = Column(Float)  # EV per unit vs Hard Rock's own closing main quote (secondary)
    cons_excluded = Column(String(32))  # why there is no reading (few_books, ...)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String, index=True)
    train_window = Column(String)
    test_window = Column(String)
    metrics_json = Column(String)
    notes = Column(String)
    created_at = Column(DateTime)


class ModelArtifact(Base):
    """One fitted model per refit: the joblib blob plus the training fingerprint
    it was fitted on (model/artifacts.py). The scoring job refits from scratch
    every run; this is the record of WHAT it fitted on, so a refit is
    reproducible and a quiet mid-season correction to the training history
    shows up as a moved fingerprint (n_rows / max_game_date / feature_hash) in
    the job log. Written only by an engine that hands score_slate a fitted
    model (the residual engine); the incumbent writes nothing here.

    Retention: ~300 KB per row, about six rows a week under the residual
    engine (one per card-day re-score); nothing reads old blobs, so prune
    rows older than the current season after it ends."""

    __tablename__ = "model_artifacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    engine = Column(String, index=True)  # config model.engine that produced it
    model_version = Column(String)  # the engine's version tag (resid_v1)
    season = Column(Integer)  # the slate scored, not the training seasons
    week = Column(Integer)
    fitted_at = Column(DateTime)
    n_rows = Column(Integer)
    min_game_date = Column(String(10))  # ISO YYYY-MM-DD of the training rows
    max_game_date = Column(String(10))
    feature_hash = Column(String(32), index=True)
    n_features = Column(Integer)
    fingerprint_json = Column(Text)
    metrics_json = Column(Text)
    sklearn_version = Column(String)
    blob = Column(LargeBinary)  # joblib dump of the fitted regressor


class GamePreview(Base):
    """Pre-kickoff research context for a game (news + injuries + QB-out), pulled
    from ESPN by scripts/research_preview.py. DISPLAY ONLY — never a model input
    (ESPN is unofficial, fail-silent). One row per game, refreshed each run."""

    __tablename__ = "game_previews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True, unique=True)
    season = Column(Integer, index=True)
    week = Column(Integer)
    # True = a starting QB listed out; NULL = unknown (2026-10-17: the injury
    # feed is a five-row teaser, so it can never show a QB is playing). No
    # default: a False here would claim "clear" for every unread game.
    qb_out = Column(Boolean)
    qb_out_detail = Column(String)
    news_json = Column(String)  # {"home": [...], "away": [...]}
    injuries_json = Column(String)  # {"home": [...], "away": [...], "covered": bool}
    updated_at = Column(DateTime)


class Card(Base):
    """One built bet card (scripts/build_card.py, `.github/workflows/card.yml`):
    the week's ranked BET / EDGE / PASS items as JSON, exactly what the Board's
    card view renders. Every build appends a row (history); the newest
    (season, week) row is the live card. Schema: beatvegas/card.py::build_card."""

    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    built_at = Column(DateTime, nullable=False)
    payload = Column(Text, nullable=False)  # JSON, the build_card contract

    __table_args__ = (Index("ix_cards_season_week_built", "season", "week", "built_at"),)


class AppSetting(Base):
    """One row per operational switch (key -> text value). The first and, so far,
    only key is `rule_paused`: while its value is the string "true", every
    real-money first-half pick is refused server-side (web/lib/pickRules.ts and
    scripts/pick.py) and paper picks continue. Toggled by scripts/rule_pause.py.
    docs/STOPPING_RULE.md says when it is thrown."""

    __tablename__ = "app_settings"
    key = Column(String(32), primary_key=True)
    value = Column(Text, nullable=False)
    note = Column(Text)
    updated_at = Column(DateTime)  # naive UTC, like every other timestamp here


class AppSettingLog(Base):
    """Append-only history of `app_settings` (2026-10-04). `app_settings` is
    one row per key, overwritten in place, so a gauge's past values -- when the
    close poll last fired each Saturday, how the credit count ran down -- were
    gone the moment the next write landed. Every writer (beatvegas/ops.py
    record_gauge; the Vercel cron route's `last_dispatch_*`) appends a row here
    beside its upsert. Never read by a gate; evidence only."""

    __tablename__ = "app_settings_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(32), index=True, nullable=False)
    value = Column(Text, nullable=False)
    note = Column(Text)
    written_at = Column(DateTime, index=True)  # naive UTC


class OddsSpend(Base):
    """One row per priced Odds API response (2026-10-18, final-2026 plan C11):
    the credit ledger. Written by `sources/odds.py::OddsAPIClient._record_spend`
    from inside the client, so every pull -- live jobs, research sweeps, archive
    buys, probes -- lands here with the credits the provider billed
    (`x-requests-last`) and the balance after. `app_settings.odds_credits_remaining`
    is the balance at the start of a run; this is the itemised spend. Read by the
    budget controller (`beatvegas/credit_plan.py`), the digest and the final
    report; never by a gate."""

    __tablename__ = "odds_spend"
    __table_args__ = (Index("ix_odds_spend_job_at", "job", "spent_at"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    spent_at = Column(DateTime, nullable=False, index=True)  # naive UTC
    run_id = Column(String(32))  # GITHUB_RUN_ID or '-'
    job = Column(String(16))  # card | lines_watch | sunday | research | archive | probe | hand
    script = Column(String(64))  # sys.argv[0] basename
    endpoint = Column(String(24), nullable=False)  # events | odds | event_odds | hist_*
    markets = Column(String(128))
    regions = Column(String(64))
    bookmakers = Column(Text)
    events = Column(Integer)  # events in the response (1 for a per-event call)
    credits = Column(Integer)  # x-requests-last
    remaining_after = Column(Integer)  # x-requests-remaining
    used_after = Column(Integer)  # x-requests-used
    purpose = Column(String(32))  # research purpose when the call fed research_snapshots
    params_json = Column(Text)  # event id, historical date; never the key
    http_status = Column(Integer)


class ResearchSnapshot(Base):
    """Research capture no frozen reader touches (2026-10-18, final-2026 plan
    C11). The same shape as `odds_snapshots` plus the `purpose` that asked for
    it, the `region` of the call, the `odds_spend` row that paid and the
    `source` (live poll or historical archive). Markets add `alt_1H_total` (one
    row per ladder rung), `team_total` and `team_total_1h` (with `team`). cv1,
    pv1, the HT1H trigger and the card read `odds_snapshots` only; cv2 and the
    2027 designs read this table at the final read. Written only by
    `beatvegas/research_capture.py`."""

    __tablename__ = "research_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "book",
            "market",
            "team",
            "line",
            "captured_at",
            "purpose",
            name="uq_research_snapshot",
        ),
        Index("ix_research_game_market_at", "game_id", "market", "captured_at"),
        Index("ix_research_purpose_at", "purpose", "captured_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), index=True)  # NULL until matched
    event_id = Column(String(64), index=True)  # the feed's event id
    book = Column(String)
    market = Column(String)
    team = Column(String(64), nullable=False, default="")  # team totals only
    line = Column(Float)
    spread = Column(Float)
    over_price = Column(Integer)
    under_price = Column(Integer)
    home_price = Column(Integer)
    away_price = Column(Integer)
    captured_at = Column(DateTime, index=True)  # poll clock, or the archive envelope's stamp
    last_seen_at = Column(DateTime)  # live purposes only (write-on-change)
    feed_updated_at = Column(DateTime)
    feed_reseen_at = Column(DateTime)
    purpose = Column(String(32), nullable=False)
    region = Column(String(16))  # eu | us | us2 | us_ex | books | unknown
    request_id = Column(Integer, ForeignKey("odds_spend.id"))
    source = Column(String(8), nullable=False, default="live")  # live | historical


class JudgeReadingAudit(Base):
    """What a later recomputation of the judge WOULD have written (2026-10-18,
    final-2026 plan PR-01). The judge's columns on `manual_picks` and
    `challenger_picks` (`cons_*`, `ev_cons`, `ev_hr`, `cons_excluded`) are
    write-once: the first reading of a pick is the evidence, and nothing
    overwrites it -- not a regrade, not a backfill, not grading a pick the
    backfill already read. When a recomputation differs from what is stored, the
    difference lands here instead, so a reading that would have changed is a
    visible event with a run id, never a silent rewrite. Identical recomputations
    write nothing. Readers: the Monday read's appendix and the final report; no
    gate, position or page reads it."""

    __tablename__ = "judge_reading_audit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger = Column(String(16), nullable=False, index=True)  # manual | challenger
    pick_id = Column(Integer, nullable=False, index=True)
    computed_at = Column(DateTime, nullable=False)  # naive UTC
    run_id = Column(String(32))  # GITHUB_RUN_ID of the writer, '-' by hand
    reason = Column(String(16), nullable=False)  # grade | regrade | backfill
    changed = Column(Text, nullable=False)  # comma-separated field names that differ
    stored_json = Column(Text, nullable=False)  # the columns as they stand (kept)
    computed_json = Column(Text, nullable=False)  # what this run computed (not written)


class InjurySnapshot(Base):
    """The whole Rotowire injury report, one row per research_preview run
    (2026-10-04). game_previews keeps only the per-game extract and is
    overwritten every build, so there was no way to see what the QB-out gate
    read on Tuesday once Friday's build had replaced it. `slot` is the card
    build that fetched it (SLOT env from card.yml; NULL on a hand run);
    `report_json` is the raw list the source returned ([] on an empty feed,
    which is itself the evidence an outage leaves)."""

    __tablename__ = "injury_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, index=True)
    week = Column(Integer)
    slot = Column(String(16))
    captured_at = Column(DateTime, index=True)  # naive UTC
    source = Column(String(32))  # 'rotowire'
    report_json = Column(Text)


class PollLog(Base):
    """One row per 1H sweep of scripts/poll_lines.py (2026-10-04): the numbers
    the run already prints (`events_total=… in_window=… new_snapshots=…
    unchanged=… credits_spent=…`), kept so coverage and credit spend can be
    read as a series instead of one run log at a time. `mode` is the sweep
    mode string (`close<=120m`, `sweep<=6d`); `run_id` is GITHUB_RUN_ID."""

    __tablename__ = "poll_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    captured_at = Column(DateTime, index=True)  # naive UTC
    market = Column(String(16))  # '1H_total'
    mode = Column(String(32))
    events_in_window = Column(Integer)
    events_polled = Column(Integer)
    new_snapshots = Column(Integer)
    unchanged = Column(Integer)
    credits_spent = Column(Integer)
    run_id = Column(String(32))


class PostMortemRun(Base):
    """One post-mortem computation per scope (scripts/post_mortem.py, Monday
    grade.yml). Delete-then-insert per scope, so each scope has exactly one live
    run and the web never has to pick a "latest". notes_json carries the change
    flags, caveats, the overfitting control and the live-scope diagnostics."""

    __tablename__ = "postmortem_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True)
    computed_at = Column(DateTime, nullable=False)
    scope = Column(String, index=True, nullable=False)  # 'hist_2023_25' | 'live_<season>'
    params_json = Column(Text)
    notes_json = Column(Text)
    dropped_json = Column(Text)
    n_games = Column(Integer)
    n_buckets = Column(Integer)


class PostMortemBucket(Base):
    """Tidy outcomes-by-bucket rows: for each scope x segment (fbs_only | all |
    live) x grading line (flat | step | hr | market | market_close) x selection
    rule x dimension x bucket: n, W-L-P, hit rate with a Wilson interval and the
    ledger's Beta posterior, units and ROI. dimension 'all' is the headline
    record; 'wl_contrast' rows hold the wins-vs-losses statistics instead."""

    __tablename__ = "postmortem_buckets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True)
    computed_at = Column(DateTime)
    scope = Column(String, nullable=False)
    segment = Column(String, nullable=False)
    proxy_kind = Column(String, nullable=False)
    selection = Column(String, nullable=False)
    dimension = Column(String, nullable=False)
    bucket = Column(String, nullable=False)
    bucket_order = Column(Integer)
    n = Column(Integer)
    unders = Column(Integer)
    overs = Column(Integer)
    pushes = Column(Integer)
    under_pct = Column(Float)
    units = Column(Float)
    roi = Column(Float)
    ci_lo = Column(Float)
    ci_hi = Column(Float)
    post_mean = Column(Float)
    p_beat = Column(Float)
    stat_win = Column(Float)
    stat_loss = Column(Float)
    med_win = Column(Float)
    med_loss = Column(Float)
    effect = Column(Float)
    p_value = Column(Float)
    q_value = Column(Float)
    delta = Column(Float)

    __table_args__ = (
        Index("ix_pm_bucket_lookup", "scope", "segment", "proxy_kind", "selection", "dimension"),
    )


class PostMortemGame(Base):
    """Per-game detail behind the buckets: both proxy lines, both gradings and
    the covariates (historical scope); Hard Rock / consensus / close gradings
    (live scope). followed_system marks the cap-5 fair-proxy pick (hist) or the
    card BET tier (live). rules_json = {rule_proxy: bool}."""

    __tablename__ = "postmortem_games"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True)
    scope = Column(String, index=True, nullable=False)
    game_id = Column(Integer, index=True, nullable=False)
    season = Column(Integer)
    week = Column(Integer)
    home_team = Column(String)
    away_team = Column(String)
    division = Column(String)
    fh = Column(Float)
    bv_line = Column(Float)
    under_score = Column(Float)
    spread = Column(Float)
    spread_abs = Column(Float)
    full_game_total = Column(Float)
    neutral_site = Column(Boolean)
    pace_spp = Column(Float)
    pace_plays = Column(Float)
    wx_temp = Column(Float)
    wx_wind = Column(Float)
    wx_precip = Column(Float)
    dome = Column(Float)
    off_ppa = Column(Float)
    def_ppa = Column(Float)
    fh_pf_sum = Column(Float)
    fh_pa_sum = Column(Float)
    fh_off_epa_mean = Column(Float)
    fh_off_success_mean = Column(Float)
    returning_pct = Column(Float)
    kick_hour_et = Column(Float)
    line_flat = Column(Float)
    line_step = Column(Float)
    gap_flat = Column(Float)
    gap_step = Column(Float)
    outcome_flat = Column(String)
    outcome_step = Column(String)
    units_flat = Column(Float)
    units_step = Column(Float)
    line_real = Column(Float)
    gap_real = Column(Float)
    outcome_real = Column(String)
    units_real = Column(Float)
    # full-game under on the same picks at the real full-game close (2026-09-07)
    pts = Column(Float)
    line_fg = Column(Float)
    gap_fg = Column(Float)
    outcome_fg = Column(String)
    units_fg = Column(Float)
    # live scope (2026-09-07): Hard Rock's own opener, pre-kick close and move,
    # graded at that close; plus the paper-ledger blocker dimension.
    hr_open = Column(Float)
    hr_close = Column(Float)
    hr_move = Column(Float)
    outcome_hr_close = Column(String)
    units_hr_close = Column(Float)
    blocker_dim = Column(String)
    qualifies = Column(Boolean)
    over_cap = Column(Boolean)
    cap_rank = Column(Float)
    resid = Column(Float)
    kick = Column(String)
    tier = Column(String)
    blocker = Column(String)
    ev = Column(Float)
    gap = Column(Float)
    hr_line = Column(Float)
    hr_price = Column(Integer)
    market_line = Column(Float)
    close_line = Column(Float)
    derived_line = Column(Float)
    fh_share = Column(Float)
    outcome_hr = Column(String)
    outcome_market = Column(String)
    outcome_close = Column(String)
    units_hr = Column(Float)
    units_market = Column(Float)
    units_close = Column(Float)
    hr_vs_market = Column(String)
    followed_system = Column(Boolean)
    rules_json = Column(Text)
