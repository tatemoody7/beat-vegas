"""post_derived_lines: derived-1H board rows.

`build_prediction_rows` maps posted full-game lines to derived-1H rows (model
fields absent, ranked low->high); the writer restricts the posted games to the
Hard Rock universe and merges the card's drivers (pace / weather / prior-season
efficiency / 1H priors / situational / form) into a JSON-clean factors_json.
"""

import importlib.util
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, OddsSnapshot, Prediction, TeamTempo, Venue, Weather
from beatvegas.etl.context import context_for_games
from beatvegas.etl.form import form_for_games
from beatvegas.factors.board import factor_references
from beatvegas.model.score import _factors, derived_factors

_ROOT = Path(__file__).resolve().parent.parent


def _load(script_name: str):
    path = _ROOT / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(script_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_prediction_rows():
    build = _load("post_derived_lines").build_prediction_rows
    # CFBD-shaped rows carry game_id directly (no name matching needed).
    fetched = [
        {"game_id": 1, "line": 50.5, "spread": -10.5},  # week 1
        {"game_id": 2, "line": 59.5, "spread": -6.5},  # week 1
        {"game_id": 3, "line": 44.0, "spread": -3.0},  # week 2 (filtered out)
    ]
    gmeta = {
        1: {"week": 1, "home": "LSU", "away": "Clemson"},
        2: {"week": 1, "home": "Auburn", "away": "Baylor"},
        3: {"week": 2, "home": "X", "away": "Y"},
    }
    rows = build(fetched, gmeta, week=1)

    assert len(rows) == 2  # week 2 dropped
    # ranked by lowest derived 1H first
    assert rows[0]["game_id"] == 1 and rows[0]["rank"] == 1
    assert rows[1]["game_id"] == 2 and rows[1]["rank"] == 2
    assert rows[0]["line_used"] < rows[1]["line_used"]

    # NO model fields present (they default to NULL in the DB)
    for d in rows:
        for k in ("under_score", "under_probability", "bv_line", "bv_gap"):
            assert k not in d

    f = json.loads(rows[0]["factors_json"])
    assert f["line_kind"] == "derived_fg"
    assert f["line"] == rows[0]["line_used"]
    assert f["full_game_total"] == 50.5 and f["spread"] == -10.5
    assert 0.48 <= f["fh_share"] <= 0.56


def test_build_prediction_rows_no_week_filter_keeps_all_matched():
    build = _load("post_derived_lines").build_prediction_rows
    fetched = [
        {"game_id": 1, "line": 50.0, "spread": 0.0},
        {"game_id": 99, "line": 48.0, "spread": 0.0},
    ]  # 99 not in gmeta
    gmeta = {1: {"week": 1, "home": "A", "away": "B"}}
    rows = build(fetched, gmeta, week=None)
    assert len(rows) == 1 and rows[0]["game_id"] == 1  # unmatched dropped


# --------------------------------------------------------------------------- #
# The posted universe is Hard Rock's, and every posted card carries real
# drivers (pace / weather / efficiency / 1H priors / situational / form) in a
# JSON payload with no NaN or Infinity anywhere.
# --------------------------------------------------------------------------- #


SEASON = 2026
_CAP = datetime(2026, 8, 25, 12)


def _snap(gid, book, market, line):
    return OddsSnapshot(
        game_id=gid, book=book, market=market, line=line, spread=-10.5, captured_at=_CAP
    )


@pytest.fixture
def session():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(
            [
                Venue(id=10, latitude=30.41, longitude=-91.18),
                Venue(id=20, latitude=34.68, longitude=-82.84),
            ]
        )
        # Prior season: played games so the 1H priors + form have something real.
        s.add_all(
            [
                Game(
                    id=901,
                    season=2025,
                    week=1,
                    start_date=datetime(2025, 9, 6, 23),
                    home_team="LSU",
                    away_team="Clemson",
                    venue_id=10,
                    home_first_half_points=17,
                    away_first_half_points=10,
                    first_half_total=27,
                ),
                Game(
                    id=902,
                    season=2025,
                    week=2,
                    start_date=datetime(2025, 9, 13, 23),
                    home_team="Clemson",
                    away_team="LSU",
                    venue_id=20,
                    home_first_half_points=14,
                    away_first_half_points=7,
                    first_half_total=21,
                ),
            ]
        )
        s.add_all(
            [
                Game(
                    id=1,
                    season=SEASON,
                    week=1,
                    start_date=datetime(2026, 8, 29, 23),
                    home_team="LSU",
                    away_team="Clemson",
                    venue_id=10,
                    full_game_total=50.5,
                    spread=-10.5,
                ),
                Game(
                    id=2,
                    season=SEASON,
                    week=1,
                    start_date=datetime(2026, 8, 29, 20),
                    home_team="Auburn",
                    away_team="Baylor",
                    venue_id=10,
                    full_game_total=59.5,
                ),
                Game(  # no Hard Rock full-game snapshot -> outside the universe
                    id=3,
                    season=SEASON,
                    week=1,
                    start_date=datetime(2026, 8, 29, 18),
                    home_team="Duke",
                    away_team="Elon",
                    venue_id=20,
                    full_game_total=44.0,
                ),
                Game(  # Hard Rock, but a different week
                    id=4,
                    season=SEASON,
                    week=2,
                    start_date=datetime(2026, 9, 5, 23),
                    home_team="Tulane",
                    away_team="Rice",
                    venue_id=10,
                    full_game_total=48.0,
                ),
                Game(  # gives Clemson a 2026 home base for the travel math
                    id=5,
                    season=SEASON,
                    week=2,
                    start_date=datetime(2026, 9, 5, 20),
                    home_team="Clemson",
                    away_team="Furman",
                    venue_id=20,
                    full_game_total=52.0,
                ),
            ]
        )
        s.add_all(
            [
                _snap(1, "hardrockbet", "full_game_total", 50.5),
                _snap(2, "hardrockbet", "full_game_total", 59.5),
                _snap(3, "draftkings", "full_game_total", 44.0),  # wrong book
                _snap(3, "hardrockbet", "1H_total", 23.0),  # wrong market
                _snap(4, "hardrockbet", "full_game_total", 48.0),
            ]
        )
        s.add_all(
            [
                TeamTempo(
                    season=SEASON, week=1, team="LSU", seconds_per_play=27.0, plays_per_game=71
                ),
                TeamTempo(
                    season=SEASON, week=1, team="Clemson", seconds_per_play=25.0, plays_per_game=75
                ),
            ]
        )
        s.add(Weather(game_id=1, temperature_f=90.0, wind_mph=8.0, precipitation=0.0, dome=False))
        s.commit()
        yield s


def _gmeta(session, season=SEASON):
    return {
        g.id: {"week": g.week, "home": g.home_team, "away": g.away_team, "season": g.season}
        for g in session.query(Game).filter(Game.season == season).all()
    }


def _refs():
    """Historical (median, spread) anchors, as factor_references builds them."""
    return factor_references(
        pd.DataFrame(
            {
                "combined_sec_play": [24.0, 26.0, 28.0, 30.0],
                "combined_plays": [130.0, 140.0, 150.0, 160.0],
                "wx_wind": [3.0, 6.0, 9.0, 12.0],
                "wx_temp": [50.0, 65.0, 75.0, 85.0],
                "wx_precip": [0.0, 0.0, 0.1, 0.4],
                "combined_off_ppa": [0.2, 0.4, 0.6, 0.8],
                "combined_def_ppa": [0.2, 0.4, 0.6, 0.8],
                "combined_fh_offense": [16.0, 20.0, 24.0, 28.0],
                "combined_fh_defense": [16.0, 20.0, 24.0, 28.0],
                "away_travel_dist": [100.0, 400.0, 700.0, 1200.0],
                "kickoff_local_hour": [12.0, 15.0, 18.0, 20.0],
            }
        )
    )


def test_hardrock_game_ids_is_the_posted_universe(session):
    mod = _load("post_derived_lines")
    # Only a hardrockbet full_game_total row qualifies a game.
    assert mod.hardrock_game_ids(session, SEASON, 1) == {1, 2}
    assert mod.hardrock_game_ids(session, SEASON, None) == {1, 2, 4}
    assert mod.hardrock_game_ids(session, 2099, None) == set()


def test_write_derived_rows_posts_only_hardrock_games(session):
    mod = _load("post_derived_lines")
    fetched = [
        {"game_id": 1, "line": 50.5, "spread": -10.5},
        {"game_id": 2, "line": 59.5, "spread": -6.5},
        {"game_id": 3, "line": 44.0, "spread": -3.0},  # no Hard Rock line
    ]
    n = mod.write_derived_rows(
        session,
        fetched,
        _gmeta(session),
        week=1,
        now=datetime.utcnow(),
        allowed_ids=mod.hardrock_game_ids(session, SEASON, 1),
    )
    session.commit()
    assert n == 2
    posted = {p.game_id for p in session.query(Prediction).all()}
    assert posted == {1, 2}


def test_card_dropped_when_a_game_leaves_the_hardrock_universe(session):
    mod = _load("post_derived_lines")
    fetched = [
        {"game_id": 1, "line": 50.5, "spread": -10.5},
        {"game_id": 3, "line": 44.0, "spread": -3.0},
    ]
    mod.write_derived_rows(
        session, fetched, _gmeta(session), week=1, now=datetime.utcnow(), allowed_ids={1, 3}
    )
    session.commit()
    assert {p.game_id for p in session.query(Prediction).all()} == {1, 3}
    # Game 3 loses its Hard Rock line: its stale card must go, not linger.
    mod.write_derived_rows(
        session, fetched, _gmeta(session), week=1, now=datetime.utcnow(), allowed_ids={1}
    )
    session.commit()
    assert {p.game_id for p in session.query(Prediction).all()} == {1}


def _no_nan(obj, path="root"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _no_nan(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _no_nan(v, f"{path}[{i}]")
    elif isinstance(obj, float):
        assert not math.isnan(obj) and not math.isinf(obj), f"non-finite at {path}"


def test_derived_factors_json_carries_real_drivers_and_is_json_clean(session):
    mod = _load("post_derived_lines")
    eff = {"LSU": {"off_ppa": 0.31, "def_ppa": 0.24}, "Clemson": {"off_ppa": 0.27, "def_ppa": 0.19}}
    mod.write_derived_rows(
        session,
        [{"game_id": 1, "line": 50.5, "spread": -10.5}],
        _gmeta(session),
        week=1,
        now=datetime.utcnow(),
        allowed_ids={1},
        efficiency=eff,
        refs=_refs(),
    )
    session.commit()
    raw = session.query(Prediction).filter(Prediction.game_id == 1).one().factors_json
    assert "NaN" not in raw and "Infinity" not in raw  # json.dumps default would emit these
    f = json.loads(raw)
    _no_nan(f)

    # derived-line provenance
    assert f["line_kind"] == "derived_fg" and f["full_game_total"] == 50.5
    # pace + weather
    assert f["combined_sec_play"] == pytest.approx(26.0)
    assert f["combined_plays"] == pytest.approx(146.0)
    assert f["wx_temp"] == 90.0 and f["wx_wind"] == 8.0 and f["dome"] is False
    # prior-season efficiency
    assert f["combined_off_ppa"] == pytest.approx(0.58)
    # 1H priors, tagged with where they came from
    assert f["combined_fh_offense"] == pytest.approx(24.0)  # LSU 12 + Clemson 12
    assert f["fh_prior_source"] == "prior_season"
    # situational
    assert f["away_travel_dist"] is not None and isinstance(f["spot"], str)
    # form + splits
    assert f["form_home"]["n"] == 2 and f["form_home"]["source"] == "prior_season"
    assert f["split_away"]["at_home"]["n"] == 1
    # tinted factor board
    assert f["factor_board"], "board must not be empty when references exist"
    keys = {b["key"] for b in f["factor_board"]}
    assert {"combined_sec_play", "combined_plays", "away_travel_dist"} <= keys


def test_model_row_factors_json_matches_the_derived_key_set(session):
    """A gbm row and a derived row must expose the SAME driver keys, so the card
    renders identically whichever wrote it."""

    ctx = context_for_games(session, SEASON, 1, [1])[1]
    frm = form_for_games(session, SEASON, 1, [1])[1]
    derived = derived_factors(24.5, 50.5, -10.5, 0.52, context=ctx, form=frm, refs=_refs())
    # A model row: a feature-frame-shaped Series full of NaN, filled from context.
    row = pd.Series(
        {c: float("nan") for c in ("proj_1h_total", "under_score", "combined_sec_play")},
        dtype=object,
    )
    model = _factors(row, 24.5, refs=_refs(), context=ctx, form=frm)
    derived_only = {"line", "line_kind", "full_game_total", "spread", "fh_share", "rank_basis"}
    driver_keys = set(derived) - derived_only
    assert driver_keys, "derived payload must carry driver keys"
    assert driver_keys <= set(model), sorted(driver_keys - set(model))
    # NaN row values are filled from context, not emitted as nulls.
    assert model["combined_sec_play"] == pytest.approx(26.0)
    _no_nan(model)
    assert "NaN" not in json.dumps(model)
