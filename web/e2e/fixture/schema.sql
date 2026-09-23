-- GENERATED FILE -- do not edit by hand.
--
-- The Postgres schema the e2e lane seeds (web/e2e/fixture/seed.mjs), dumped
-- from beatvegas/db/models.py as beatvegas.db.store.init_db() applies it
-- (create_all + _MIGRATIONS + the expression indexes) by
-- scripts/dump_e2e_schema.py, using the pgserver-bundled pg_dump.
--
-- Regenerate after any change to models.py or store._MIGRATIONS:
--     PYTHONPATH=. .venv/bin/python scripts/dump_e2e_schema.py
-- tests/test_e2e_schema_parity.py fails until you do.
--
-- Applied with `psql -v ON_ERROR_STOP=1 -f` against an EMPTY database or one
-- that only ever held this schema: the DROP/CREATE SCHEMA below wipes it.

DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;

--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: app_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_settings (
    key character varying(32) NOT NULL,
    value text NOT NULL,
    note text,
    updated_at timestamp without time zone
);

--
-- Name: bv_adjustments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bv_adjustments (
    id integer NOT NULL,
    game_id integer,
    delta_pts double precision,
    reason character varying,
    created_at timestamp without time zone
);

--
-- Name: bv_adjustments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bv_adjustments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: bv_adjustments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bv_adjustments_id_seq OWNED BY public.bv_adjustments.id;

--
-- Name: cards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cards (
    id integer NOT NULL,
    season integer NOT NULL,
    week integer NOT NULL,
    built_at timestamp without time zone NOT NULL,
    payload text NOT NULL
);

--
-- Name: cards_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: cards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cards_id_seq OWNED BY public.cards.id;

--
-- Name: challenger_picks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.challenger_picks (
    id integer NOT NULL,
    arm character varying,
    game_id integer,
    season integer,
    week integer,
    home_team character varying,
    away_team character varying,
    side character varying,
    market character varying,
    line double precision,
    price integer,
    stake double precision,
    book character varying,
    slot character varying,
    placed_at timestamp without time zone,
    blocker character varying,
    arm_line_at_pick double precision,
    champion_line_at_pick double precision,
    c_prior double precision,
    c_season double precision,
    in_season_n integer,
    in_season_weight double precision,
    gap_at_pick double precision,
    graded boolean,
    actual_first_half_total integer,
    result character varying,
    units double precision,
    opening_line double precision,
    closing_line double precision,
    clv double precision,
    clv_prob double precision,
    closing_price integer
);

--
-- Name: challenger_picks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.challenger_picks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: challenger_picks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.challenger_picks_id_seq OWNED BY public.challenger_picks.id;

--
-- Name: factor_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.factor_ledger (
    id integer NOT NULL,
    factor character varying,
    n integer,
    hits integer,
    post_mean double precision,
    post_lo double precision,
    post_hi double precision,
    tier integer,
    recent_n integer,
    recent_mean double precision,
    drift_flag boolean,
    created_at timestamp without time zone
);

--
-- Name: factor_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.factor_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: factor_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.factor_ledger_id_seq OWNED BY public.factor_ledger.id;

--
-- Name: factor_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.factor_scores (
    id integer NOT NULL,
    run_id character varying,
    kind character varying,
    factor character varying,
    family character varying,
    leak_free boolean,
    market boolean,
    forward_only boolean,
    n integer,
    top_under_pct double precision,
    top_roi double precision,
    auc double precision,
    corr double precision,
    perm_importance double precision,
    stability_std double precision,
    rank integer,
    metrics_json character varying,
    created_at timestamp without time zone
);

--
-- Name: factor_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.factor_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: factor_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.factor_scores_id_seq OWNED BY public.factor_scores.id;

--
-- Name: fh_team_game; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fh_team_game (
    id integer NOT NULL,
    game_id integer,
    season integer,
    week integer,
    off_team character varying,
    def_team character varying,
    is_home boolean,
    source character varying,
    n_plays integer,
    epa double precision,
    success double precision,
    explosive double precision,
    pass_rate double precision,
    early_success double precision,
    third_conv double precision,
    havoc_suffered double precision,
    turnovers double precision,
    opening_score integer,
    opening_3out integer,
    redzone_td double precision,
    fourth_go double precision
);

--
-- Name: fh_team_game_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fh_team_game_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: fh_team_game_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fh_team_game_id_seq OWNED BY public.fh_team_game.id;

--
-- Name: game_previews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.game_previews (
    id integer NOT NULL,
    game_id integer,
    season integer,
    week integer,
    qb_out boolean,
    qb_out_detail character varying,
    news_json character varying,
    injuries_json character varying,
    updated_at timestamp without time zone
);

--
-- Name: game_previews_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.game_previews_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: game_previews_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.game_previews_id_seq OWNED BY public.game_previews.id;

--
-- Name: game_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.game_records (
    id integer NOT NULL,
    game_id integer,
    season integer,
    week integer,
    captured_at timestamp without time zone,
    model_version character varying,
    engine character varying,
    features_json character varying,
    line double precision,
    line_kind character varying,
    bv_line double precision,
    bv_gap double precision,
    bv_gap_z double precision,
    under_score integer,
    first_half_total integer,
    under_hit boolean,
    outcome character varying,
    graded_at timestamp without time zone
);

--
-- Name: game_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.game_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: game_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.game_records_id_seq OWNED BY public.game_records.id;

--
-- Name: games; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.games (
    id integer NOT NULL,
    season integer NOT NULL,
    week integer NOT NULL,
    season_type character varying,
    start_date timestamp without time zone,
    neutral_site boolean,
    venue_id integer,
    home_team character varying,
    away_team character varying,
    home_team_id integer,
    away_team_id integer,
    home_points integer,
    away_points integer,
    home_first_half_points integer,
    away_first_half_points integer,
    first_half_total integer,
    first_half_source character varying,
    full_game_total double precision,
    full_game_total_book character varying,
    spread double precision,
    full_game_total_source character varying,
    spread_source character varying,
    spread_open double precision,
    spread_open_source character varying
);

--
-- Name: games_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.games_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: games_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.games_id_seq OWNED BY public.games.id;

--
-- Name: manual_picks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manual_picks (
    id integer NOT NULL,
    game_id integer,
    season integer,
    week integer,
    home_team character varying,
    away_team character varying,
    side character varying,
    market character varying,
    line double precision,
    price integer,
    stake double precision,
    is_paper boolean,
    is_bonus boolean,
    book character varying,
    placed_at timestamp without time zone,
    note character varying,
    model_score_at_pick integer,
    model_line_at_pick double precision,
    graded boolean,
    actual_first_half_total integer,
    result character varying,
    units double precision,
    closing_line double precision,
    closing_captured_at timestamp without time zone,
    closing_price integer,
    price_provenance character varying,
    clv double precision,
    clv_prob double precision,
    factors_json_at_pick character varying,
    opening_line double precision,
    verdict_at_pick character varying(8),
    reason character varying(16),
    gap_at_pick double precision,
    ev_at_pick double precision,
    hr_line_at_pick double precision,
    blocker character varying(16)
);

--
-- Name: manual_picks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.manual_picks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: manual_picks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.manual_picks_id_seq OWNED BY public.manual_picks.id;

--
-- Name: model_artifacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_artifacts (
    id integer NOT NULL,
    engine character varying,
    model_version character varying,
    season integer,
    week integer,
    fitted_at timestamp without time zone,
    n_rows integer,
    min_game_date character varying(10),
    max_game_date character varying(10),
    feature_hash character varying(32),
    n_features integer,
    fingerprint_json text,
    metrics_json text,
    sklearn_version character varying,
    blob bytea
);

--
-- Name: model_artifacts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_artifacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: model_artifacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_artifacts_id_seq OWNED BY public.model_artifacts.id;

--
-- Name: model_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_runs (
    id integer NOT NULL,
    version character varying,
    train_window character varying,
    test_window character varying,
    metrics_json character varying,
    notes character varying,
    created_at timestamp without time zone
);

--
-- Name: model_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: model_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_runs_id_seq OWNED BY public.model_runs.id;

--
-- Name: odds_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.odds_snapshots (
    id integer NOT NULL,
    game_id integer,
    book character varying,
    market character varying,
    line double precision,
    spread double precision,
    over_price integer,
    under_price integer,
    captured_at timestamp without time zone,
    last_seen_at timestamp without time zone
);

--
-- Name: odds_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.odds_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: odds_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.odds_snapshots_id_seq OWNED BY public.odds_snapshots.id;

--
-- Name: postmortem_buckets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.postmortem_buckets (
    id integer NOT NULL,
    run_id character varying,
    computed_at timestamp without time zone,
    scope character varying NOT NULL,
    segment character varying NOT NULL,
    proxy_kind character varying NOT NULL,
    selection character varying NOT NULL,
    dimension character varying NOT NULL,
    bucket character varying NOT NULL,
    bucket_order integer,
    n integer,
    unders integer,
    overs integer,
    pushes integer,
    under_pct double precision,
    units double precision,
    roi double precision,
    ci_lo double precision,
    ci_hi double precision,
    post_mean double precision,
    p_beat double precision,
    stat_win double precision,
    stat_loss double precision,
    med_win double precision,
    med_loss double precision,
    effect double precision,
    p_value double precision,
    q_value double precision,
    delta double precision
);

--
-- Name: postmortem_buckets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.postmortem_buckets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: postmortem_buckets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.postmortem_buckets_id_seq OWNED BY public.postmortem_buckets.id;

--
-- Name: postmortem_games; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.postmortem_games (
    id integer NOT NULL,
    run_id character varying,
    scope character varying NOT NULL,
    game_id integer NOT NULL,
    season integer,
    week integer,
    home_team character varying,
    away_team character varying,
    division character varying,
    fh double precision,
    bv_line double precision,
    under_score double precision,
    spread double precision,
    spread_abs double precision,
    full_game_total double precision,
    neutral_site boolean,
    pace_spp double precision,
    pace_plays double precision,
    wx_temp double precision,
    wx_wind double precision,
    wx_precip double precision,
    dome double precision,
    off_ppa double precision,
    def_ppa double precision,
    fh_pf_sum double precision,
    fh_pa_sum double precision,
    fh_off_epa_mean double precision,
    fh_off_success_mean double precision,
    returning_pct double precision,
    kick_hour_et double precision,
    line_flat double precision,
    line_step double precision,
    gap_flat double precision,
    gap_step double precision,
    outcome_flat character varying,
    outcome_step character varying,
    units_flat double precision,
    units_step double precision,
    line_real double precision,
    gap_real double precision,
    outcome_real character varying,
    units_real double precision,
    pts double precision,
    line_fg double precision,
    gap_fg double precision,
    outcome_fg character varying,
    units_fg double precision,
    hr_open double precision,
    hr_close double precision,
    hr_move double precision,
    outcome_hr_close character varying,
    units_hr_close double precision,
    blocker_dim character varying,
    qualifies boolean,
    over_cap boolean,
    cap_rank double precision,
    resid double precision,
    kick character varying,
    tier character varying,
    blocker character varying,
    ev double precision,
    gap double precision,
    hr_line double precision,
    hr_price integer,
    market_line double precision,
    close_line double precision,
    derived_line double precision,
    fh_share double precision,
    outcome_hr character varying,
    outcome_market character varying,
    outcome_close character varying,
    units_hr double precision,
    units_market double precision,
    units_close double precision,
    hr_vs_market character varying,
    followed_system boolean,
    rules_json text
);

--
-- Name: postmortem_games_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.postmortem_games_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: postmortem_games_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.postmortem_games_id_seq OWNED BY public.postmortem_games.id;

--
-- Name: postmortem_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.postmortem_runs (
    id integer NOT NULL,
    run_id character varying,
    computed_at timestamp without time zone NOT NULL,
    scope character varying NOT NULL,
    params_json text,
    notes_json text,
    dropped_json text,
    n_games integer,
    n_buckets integer
);

--
-- Name: postmortem_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.postmortem_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: postmortem_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.postmortem_runs_id_seq OWNED BY public.postmortem_runs.id;

--
-- Name: predictions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.predictions (
    id integer NOT NULL,
    game_id integer,
    model_version character varying,
    under_probability double precision,
    under_score integer,
    projected_first_half_total double precision,
    bv_line double precision,
    bv_gap double precision,
    bv_lo double precision,
    bv_hi double precision,
    bv_sigma double precision,
    bv_intercept double precision,
    line_used double precision,
    rank integer,
    factors_json character varying,
    created_at timestamp without time zone
);

--
-- Name: predictions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.predictions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: predictions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.predictions_id_seq OWNED BY public.predictions.id;

--
-- Name: results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.results (
    id integer NOT NULL,
    game_id integer,
    model_version character varying,
    market character varying,
    actual_first_half_total integer,
    line_used double precision,
    line_kind character varying,
    under_hit boolean,
    closing_line double precision,
    closing_captured_at timestamp without time zone,
    closing_price integer,
    clv double precision,
    clv_prob double precision,
    units double precision
);

--
-- Name: results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.results_id_seq OWNED BY public.results.id;

--
-- Name: team_tempo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_tempo (
    id integer NOT NULL,
    season integer,
    week integer,
    team character varying,
    seconds_per_play double precision,
    plays_per_game double precision,
    as_of_date character varying,
    captured_at timestamp without time zone
);

--
-- Name: team_tempo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.team_tempo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: team_tempo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.team_tempo_id_seq OWNED BY public.team_tempo.id;

--
-- Name: team_week_features; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_week_features (
    id integer NOT NULL,
    season integer NOT NULL,
    week integer NOT NULL,
    team character varying NOT NULL,
    seconds_per_play double precision,
    plays_per_game double precision,
    off_success_rate double precision,
    def_success_rate double precision,
    off_epa_per_play double precision,
    def_epa_per_play double precision,
    off_explosiveness double precision,
    def_explosiveness double precision,
    first_quarter_pf double precision,
    first_quarter_pa double precision,
    first_half_pf double precision,
    first_half_pa double precision,
    sp_overall double precision,
    sp_offense double precision,
    sp_defense double precision,
    run_rate double precision
);

--
-- Name: team_week_features_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.team_week_features_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: team_week_features_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.team_week_features_id_seq OWNED BY public.team_week_features.id;

--
-- Name: teams; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teams (
    id integer NOT NULL,
    school character varying NOT NULL,
    conference character varying
);

--
-- Name: teams_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.teams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: teams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.teams_id_seq OWNED BY public.teams.id;

--
-- Name: venues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venues (
    id integer NOT NULL,
    name character varying,
    city character varying,
    state character varying,
    latitude double precision,
    longitude double precision,
    dome boolean,
    elevation double precision,
    grass boolean,
    capacity integer
);

--
-- Name: venues_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.venues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: venues_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.venues_id_seq OWNED BY public.venues.id;

--
-- Name: weather; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weather (
    game_id integer NOT NULL,
    temperature_f double precision,
    wind_mph double precision,
    precipitation double precision,
    dome boolean
);

--
-- Name: weather_obs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weather_obs (
    id integer NOT NULL,
    game_id integer NOT NULL,
    lead_hours integer NOT NULL,
    valid_time timestamp without time zone,
    model_run_time timestamp without time zone,
    available_at timestamp without time zone,
    decision_safe boolean NOT NULL,
    temperature_f double precision,
    wind_mph double precision,
    wind_gust_mph double precision,
    precipitation double precision,
    dome boolean,
    source character varying,
    weather_model character varying,
    dataset_version character varying,
    latitude double precision,
    longitude double precision,
    retrieved_at timestamp without time zone
);

--
-- Name: weather_obs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weather_obs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: weather_obs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weather_obs_id_seq OWNED BY public.weather_obs.id;

--
-- Name: bv_adjustments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bv_adjustments ALTER COLUMN id SET DEFAULT nextval('public.bv_adjustments_id_seq'::regclass);

--
-- Name: cards id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cards ALTER COLUMN id SET DEFAULT nextval('public.cards_id_seq'::regclass);

--
-- Name: challenger_picks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.challenger_picks ALTER COLUMN id SET DEFAULT nextval('public.challenger_picks_id_seq'::regclass);

--
-- Name: factor_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_ledger ALTER COLUMN id SET DEFAULT nextval('public.factor_ledger_id_seq'::regclass);

--
-- Name: factor_scores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_scores ALTER COLUMN id SET DEFAULT nextval('public.factor_scores_id_seq'::regclass);

--
-- Name: fh_team_game id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fh_team_game ALTER COLUMN id SET DEFAULT nextval('public.fh_team_game_id_seq'::regclass);

--
-- Name: game_previews id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.game_previews ALTER COLUMN id SET DEFAULT nextval('public.game_previews_id_seq'::regclass);

--
-- Name: game_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.game_records ALTER COLUMN id SET DEFAULT nextval('public.game_records_id_seq'::regclass);

--
-- Name: games id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.games ALTER COLUMN id SET DEFAULT nextval('public.games_id_seq'::regclass);

--
-- Name: manual_picks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_picks ALTER COLUMN id SET DEFAULT nextval('public.manual_picks_id_seq'::regclass);

--
-- Name: model_artifacts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_artifacts ALTER COLUMN id SET DEFAULT nextval('public.model_artifacts_id_seq'::regclass);

--
-- Name: model_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_runs ALTER COLUMN id SET DEFAULT nextval('public.model_runs_id_seq'::regclass);

--
-- Name: odds_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.odds_snapshots ALTER COLUMN id SET DEFAULT nextval('public.odds_snapshots_id_seq'::regclass);

--
-- Name: postmortem_buckets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.postmortem_buckets ALTER COLUMN id SET DEFAULT nextval('public.postmortem_buckets_id_seq'::regclass);

--
-- Name: postmortem_games id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.postmortem_games ALTER COLUMN id SET DEFAULT nextval('public.postmortem_games_id_seq'::regclass);

--
-- Name: postmortem_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.postmortem_runs ALTER COLUMN id SET DEFAULT nextval('public.postmortem_runs_id_seq'::regclass);

--
-- Name: predictions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.predictions ALTER COLUMN id SET DEFAULT nextval('public.predictions_id_seq'::regclass);

--
-- Name: results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.results ALTER COLUMN id SET DEFAULT nextval('public.results_id_seq'::regclass);

--
-- Name: team_tempo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_tempo ALTER COLUMN id SET DEFAULT nextval('public.team_tempo_id_seq'::regclass);

--
-- Name: team_week_features id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_week_features ALTER COLUMN id SET DEFAULT nextval('public.team_week_features_id_seq'::regclass);

--
-- Name: teams id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams ALTER COLUMN id SET DEFAULT nextval('public.teams_id_seq'::regclass);

--
-- Name: venues id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venues ALTER COLUMN id SET DEFAULT nextval('public.venues_id_seq'::regclass);

--
-- Name: weather_obs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_obs ALTER COLUMN id SET DEFAULT nextval('public.weather_obs_id_seq'::regclass);

--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (key);

--
-- Name: bv_adjustments bv_adjustments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bv_adjustments
    ADD CONSTRAINT bv_adjustments_pkey PRIMARY KEY (id);

--
-- Name: cards cards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cards
    ADD CONSTRAINT cards_pkey PRIMARY KEY (id);

--
-- Name: challenger_picks challenger_picks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.challenger_picks
    ADD CONSTRAINT challenger_picks_pkey PRIMARY KEY (id);

--
-- Name: factor_ledger factor_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_ledger
    ADD CONSTRAINT factor_ledger_pkey PRIMARY KEY (id);

--
-- Name: factor_scores factor_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_scores
    ADD CONSTRAINT factor_scores_pkey PRIMARY KEY (id);

--
-- Name: fh_team_game fh_team_game_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fh_team_game
    ADD CONSTRAINT fh_team_game_pkey PRIMARY KEY (id);

--
-- Name: game_previews game_previews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.game_previews
    ADD CONSTRAINT game_previews_pkey PRIMARY KEY (id);

--
-- Name: game_records game_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.game_records
    ADD CONSTRAINT game_records_pkey PRIMARY KEY (id);

--
-- Name: manual_picks manual_picks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_picks
    ADD CONSTRAINT manual_picks_pkey PRIMARY KEY (id);

--
-- Name: model_artifacts model_artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_artifacts
    ADD CONSTRAINT model_artifacts_pkey PRIMARY KEY (id);

--
-- Name: model_runs model_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_runs
    ADD CONSTRAINT model_runs_pkey PRIMARY KEY (id);

--
-- Name: odds_snapshots odds_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.odds_snapshots
    ADD CONSTRAINT odds_snapshots_pkey PRIMARY KEY (id);

--
-- Name: postmortem_buckets postmortem_buckets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.postmortem_buckets
    ADD CONSTRAINT postmortem_buckets_pkey PRIMARY KEY (id);

--
-- Name: postmortem_games postmortem_games_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.postmortem_games
    ADD CONSTRAINT postmortem_games_pkey PRIMARY KEY (id);

--
-- Name: postmortem_runs postmortem_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.postmortem_runs
    ADD CONSTRAINT postmortem_runs_pkey PRIMARY KEY (id);

--
-- Name: predictions predictions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.predictions
    ADD CONSTRAINT predictions_pkey PRIMARY KEY (id);

--
-- Name: results results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_pkey PRIMARY KEY (id);

--
-- Name: team_tempo team_tempo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_tempo
    ADD CONSTRAINT team_tempo_pkey PRIMARY KEY (id);

--
-- Name: team_week_features team_week_features_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_week_features
    ADD CONSTRAINT team_week_features_pkey PRIMARY KEY (id);

--
-- Name: teams teams_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (id);

--
-- Name: fh_team_game uq_fh_team_game; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fh_team_game
    ADD CONSTRAINT uq_fh_team_game UNIQUE (game_id, off_team);

--
-- Name: games uq_game_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.games
    ADD CONSTRAINT uq_game_id PRIMARY KEY (id);

--
-- Name: odds_snapshots uq_odds_snapshot; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.odds_snapshots
    ADD CONSTRAINT uq_odds_snapshot UNIQUE (game_id, book, market, captured_at);

--
-- Name: team_week_features uq_team_week; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_week_features
    ADD CONSTRAINT uq_team_week UNIQUE (season, week, team);

--
-- Name: team_tempo uq_tempo_week; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_tempo
    ADD CONSTRAINT uq_tempo_week UNIQUE (season, week, team);

--
-- Name: venues venues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venues
    ADD CONSTRAINT venues_pkey PRIMARY KEY (id);

--
-- Name: weather_obs weather_obs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_obs
    ADD CONSTRAINT weather_obs_pkey PRIMARY KEY (id);

--
-- Name: weather weather_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather
    ADD CONSTRAINT weather_pkey PRIMARY KEY (game_id);

--
-- Name: ix_bv_adjustments_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bv_adjustments_game_id ON public.bv_adjustments USING btree (game_id);

--
-- Name: ix_cards_season_week_built; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cards_season_week_built ON public.cards USING btree (season, week, built_at);

--
-- Name: ix_challenger_picks_arm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_challenger_picks_arm ON public.challenger_picks USING btree (arm);

--
-- Name: ix_challenger_picks_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_challenger_picks_game_id ON public.challenger_picks USING btree (game_id);

--
-- Name: ix_challenger_picks_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_challenger_picks_season ON public.challenger_picks USING btree (season);

--
-- Name: ix_factor_ledger_factor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_factor_ledger_factor ON public.factor_ledger USING btree (factor);

--
-- Name: ix_factor_scores_factor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_factor_scores_factor ON public.factor_scores USING btree (factor);

--
-- Name: ix_factor_scores_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_factor_scores_run_id ON public.factor_scores USING btree (run_id);

--
-- Name: ix_fh_team_game_def_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fh_team_game_def_team ON public.fh_team_game USING btree (def_team);

--
-- Name: ix_fh_team_game_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fh_team_game_game_id ON public.fh_team_game USING btree (game_id);

--
-- Name: ix_fh_team_game_off_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fh_team_game_off_team ON public.fh_team_game USING btree (off_team);

--
-- Name: ix_fh_team_game_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fh_team_game_season ON public.fh_team_game USING btree (season);

--
-- Name: ix_game_previews_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_game_previews_game_id ON public.game_previews USING btree (game_id);

--
-- Name: ix_game_previews_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_game_previews_season ON public.game_previews USING btree (season);

--
-- Name: ix_game_records_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_game_records_game_id ON public.game_records USING btree (game_id);

--
-- Name: ix_game_records_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_game_records_season ON public.game_records USING btree (season);

--
-- Name: ix_games_away_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_games_away_team ON public.games USING btree (away_team);

--
-- Name: ix_games_home_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_games_home_team ON public.games USING btree (home_team);

--
-- Name: ix_games_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_games_season ON public.games USING btree (season);

--
-- Name: ix_games_week; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_games_week ON public.games USING btree (week);

--
-- Name: ix_manual_picks_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_manual_picks_game_id ON public.manual_picks USING btree (game_id);

--
-- Name: ix_manual_picks_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_manual_picks_season ON public.manual_picks USING btree (season);

--
-- Name: ix_model_artifacts_engine; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_model_artifacts_engine ON public.model_artifacts USING btree (engine);

--
-- Name: ix_model_artifacts_feature_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_model_artifacts_feature_hash ON public.model_artifacts USING btree (feature_hash);

--
-- Name: ix_model_runs_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_model_runs_version ON public.model_runs USING btree (version);

--
-- Name: ix_odds_snapshots_captured_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_odds_snapshots_captured_at ON public.odds_snapshots USING btree (captured_at);

--
-- Name: ix_odds_snapshots_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_odds_snapshots_game_id ON public.odds_snapshots USING btree (game_id);

--
-- Name: ix_pm_bucket_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pm_bucket_lookup ON public.postmortem_buckets USING btree (scope, segment, proxy_kind, selection, dimension);

--
-- Name: ix_postmortem_buckets_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_postmortem_buckets_run_id ON public.postmortem_buckets USING btree (run_id);

--
-- Name: ix_postmortem_games_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_postmortem_games_game_id ON public.postmortem_games USING btree (game_id);

--
-- Name: ix_postmortem_games_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_postmortem_games_run_id ON public.postmortem_games USING btree (run_id);

--
-- Name: ix_postmortem_games_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_postmortem_games_scope ON public.postmortem_games USING btree (scope);

--
-- Name: ix_postmortem_runs_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_postmortem_runs_run_id ON public.postmortem_runs USING btree (run_id);

--
-- Name: ix_postmortem_runs_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_postmortem_runs_scope ON public.postmortem_runs USING btree (scope);

--
-- Name: ix_predictions_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_predictions_game_id ON public.predictions USING btree (game_id);

--
-- Name: ix_predictions_model_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_predictions_model_version ON public.predictions USING btree (model_version);

--
-- Name: ix_results_game_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_results_game_id ON public.results USING btree (game_id);

--
-- Name: ix_results_model_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_results_model_version ON public.results USING btree (model_version);

--
-- Name: ix_team_tempo_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_team_tempo_season ON public.team_tempo USING btree (season);

--
-- Name: ix_team_tempo_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_team_tempo_team ON public.team_tempo USING btree (team);

--
-- Name: ix_team_tempo_week; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_team_tempo_week ON public.team_tempo USING btree (week);

--
-- Name: ix_team_week_features_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_team_week_features_season ON public.team_week_features USING btree (season);

--
-- Name: ix_team_week_features_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_team_week_features_team ON public.team_week_features USING btree (team);

--
-- Name: ix_team_week_features_week; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_team_week_features_week ON public.team_week_features USING btree (week);

--
-- Name: ix_teams_school; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teams_school ON public.teams USING btree (school);

--
-- Name: ix_weather_obs_decision_safe; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_obs_decision_safe ON public.weather_obs USING btree (decision_safe);

--
-- Name: ix_weather_obs_game_lead; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_weather_obs_game_lead ON public.weather_obs USING btree (game_id, lead_hours);

--
-- Name: uq_challenger_pick_per_arm; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_challenger_pick_per_arm ON public.challenger_picks USING btree (game_id, COALESCE(market, '1H'::character varying), arm);

--
-- Name: uq_manual_pick_per_ledger; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_manual_pick_per_ledger ON public.manual_picks USING btree (game_id, COALESCE(market, '1H'::character varying), COALESCE(is_paper, false));

--
-- Name: uq_weather_obs_reading; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_weather_obs_reading ON public.weather_obs USING btree (game_id, lead_hours, COALESCE(source, ''::character varying), COALESCE(weather_model, ''::character varying), COALESCE(model_run_time, '1970-01-01 00:00:00'::timestamp without time zone));

--
-- Name: bv_adjustments bv_adjustments_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bv_adjustments
    ADD CONSTRAINT bv_adjustments_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: challenger_picks challenger_picks_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.challenger_picks
    ADD CONSTRAINT challenger_picks_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: fh_team_game fh_team_game_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fh_team_game
    ADD CONSTRAINT fh_team_game_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: game_previews game_previews_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.game_previews
    ADD CONSTRAINT game_previews_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: game_records game_records_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.game_records
    ADD CONSTRAINT game_records_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: games games_venue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.games
    ADD CONSTRAINT games_venue_id_fkey FOREIGN KEY (venue_id) REFERENCES public.venues(id);

--
-- Name: manual_picks manual_picks_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_picks
    ADD CONSTRAINT manual_picks_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: odds_snapshots odds_snapshots_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.odds_snapshots
    ADD CONSTRAINT odds_snapshots_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: predictions predictions_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.predictions
    ADD CONSTRAINT predictions_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: results results_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: weather weather_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather
    ADD CONSTRAINT weather_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- Name: weather_obs weather_obs_game_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weather_obs
    ADD CONSTRAINT weather_obs_game_id_fkey FOREIGN KEY (game_id) REFERENCES public.games(id);

--
-- PostgreSQL database dump complete
--
