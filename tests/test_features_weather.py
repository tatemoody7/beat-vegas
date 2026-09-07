"""Dome games carry no weather: enrich_weather used to store a fake 72F / 0 mph /
0 in, which taught the model that '72 and calm' means dome. Domes now store NULL
temp/wind/precip, the feature frame nulls them regardless of what is stored, and
the wind band is an explicit extra column."""

from __future__ import annotations

from contextlib import contextmanager

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Weather
from beatvegas.db.store import _apply_migrations
from beatvegas.etl import features
from beatvegas.etl.features import FEATURE_COLS, WIND_BAND_EDGES, wind_band


def test_wind_band_edges():
    out = wind_band(np.array([0.0, 9.9, 10.0, 14.9, 15.0, 19.9, 20.0, 35.0, np.nan]))
    assert out.dtype == float
    assert list(out[:-1]) == [0, 0, 1, 1, 2, 2, 3, 3]
    assert np.isnan(out[-1])
    assert WIND_BAND_EDGES == (10.0, 15.0, 20.0)


def test_wind_band_accepts_a_series_with_missing_values():
    out = wind_band(pd.Series([12.0, None, 22.0]))
    assert list(out[[0, 2]]) == [1, 3] and np.isnan(out[1])


def test_wind_band_is_not_a_model_feature():
    assert "wx_wind_band" not in FEATURE_COLS


def test_merge_nulls_dome_weather_and_keeps_outdoor(monkeypatch):
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        # a legacy dome row that still carries the 72/0/0 placeholder
        s.add(Weather(game_id=1, temperature_f=72.0, wind_mph=0.0, precipitation=0.0, dome=True))
        s.add(Weather(game_id=2, temperature_f=55.0, wind_mph=12.0, precipitation=0.1, dome=False))
        s.commit()

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s

    monkeypatch.setattr(features, "session_scope", scope)
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "season": [2026] * 3,
            "week": [3] * 3,
            "home_team": ["A", "C", "E"],
            "away_team": ["B", "D", "F"],
        }
    )
    out = features._merge_tempo_weather(df).set_index("id")
    assert out.loc[1, "wx_dome"] == 1.0
    assert all(np.isnan(out.loc[1, c]) for c in ("wx_temp", "wx_wind", "wx_precip"))
    assert out.loc[2, "wx_dome"] == 0.0
    assert (out.loc[2, "wx_temp"], out.loc[2, "wx_wind"], out.loc[2, "wx_precip"]) == (
        55.0,
        12.0,
        0.1,
    )
    assert out.loc[2, "wx_wind_band"] == 1.0
    assert np.isnan(out.loc[1, "wx_wind_band"]) and np.isnan(out.loc[3, "wx_wind_band"])
    assert np.isnan(out.loc[3, "wx_dome"])  # no weather row -> unknown, not dome


def test_data_migration_nulls_placeholder_dome_rows_only():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Weather(game_id=1, temperature_f=72.0, wind_mph=0.0, precipitation=0.0, dome=True))
        s.add(Weather(game_id=2, temperature_f=72.0, wind_mph=0.0, precipitation=0.0, dome=False))
        s.add(Weather(game_id=3, temperature_f=55.0, wind_mph=12.0, precipitation=0.1, dome=False))
        s.commit()
    _apply_migrations(eng)
    with eng.connect() as c:
        rows = {
            r[0]: r[1:]
            for r in c.execute(
                text("SELECT game_id, temperature_f, wind_mph, precipitation FROM weather")
            )
        }
    assert rows[1] == (None, None, None)  # dome placeholder nulled
    assert rows[2] == (72.0, 0.0, 0.0)  # a genuinely calm 72F outdoor day stays
    assert rows[3] == (55.0, 12.0, 0.1)
    _apply_migrations(eng)  # idempotent
