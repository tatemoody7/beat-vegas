"""weather_obs: the lead is part of the key, and the model does not move with it.

Two separate things had been conflated in the old single-row-per-game `weather`
table: what the conditions WERE around kickoff, and what the forecast SAID while
a bet was still placeable. They answer different questions, and using the first
to argue an edge is look-ahead bias. So the lead is in the primary key, and
`decision_safe` is stored rather than inferred at query time.

The last test is the one that keeps the two decisions apart: repairing the data
must not, by itself, move the live model.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Weather, WeatherObs
from beatvegas.etl import features
from beatvegas.sources.weather import SOURCE_DECISION, SOURCE_NEAR_KICKOFF

backfill = pytest.importorskip("scripts.backfill_weather", reason="scripts not importable")


VENUE = {"dome": False, "lat": 30.6, "lon": -96.3, "name": "Kyle Field"}
DOME = {"dome": True, "lat": 29.7, "lon": -95.4, "name": "a dome"}
KICK = datetime(2024, 10, 12, 19, 0)


def test_a_near_kickoff_row_is_never_decision_safe():
    r = backfill._row(1, 0, KICK, SOURCE_NEAR_KICKOFF, None, VENUE, {"temperature_f": 70.0})
    assert r["decision_safe"] is False
    assert r["forecast_asof"] is None  # there is no run time to claim
    assert r["lead_hours"] == 0


def test_a_fixed_lead_row_carries_its_run_time_and_model():
    r = backfill._row(1, 72, KICK, SOURCE_DECISION, "icon_seamless", VENUE, {"temperature_f": 70.0})
    assert r["decision_safe"] is True
    assert r["forecast_asof"] == datetime(2024, 10, 9, 19, 0).isoformat()
    assert r["weather_model"] == "icon_seamless"


def test_provenance_is_stored_not_joined():
    """Six months from now, `78.1` has to say what it is on its own."""
    r = backfill._row(1, 0, KICK, SOURCE_NEAR_KICKOFF, None, VENUE, {"temperature_f": 78.1})
    for field in ("valid_time", "source", "latitude", "longitude", "retrieved_at"):
        assert r[field] is not None, field
    assert (r["latitude"], r["longitude"]) == (VENUE["lat"], VENUE["lon"])


def test_a_dome_stores_no_weather():
    """A 72F/0mph placeholder teaches the model that 'calm and mild' means dome."""
    r = backfill._row(1, 0, KICK, SOURCE_NEAR_KICKOFF, None, DOME, None)
    assert r["dome"] is True
    assert (r["temperature_f"], r["wind_mph"], r["wind_gust_mph"], r["precipitation"]) == (
        None,
        None,
        None,
        None,
    )


def test_a_refetched_venue_season_supersedes_its_earlier_rows(tmp_path, monkeypatch):
    staging = tmp_path / "s.jsonl"
    old = backfill._row(7, 0, KICK, SOURCE_NEAR_KICKOFF, None, VENUE, {"temperature_f": 50.0})
    new = backfill._row(7, 0, KICK, SOURCE_NEAR_KICKOFF, None, VENUE, {"temperature_f": 70.0})
    staging.write_text(json.dumps(old) + "\n" + json.dumps(new) + "\n")
    monkeypatch.setattr(backfill, "STAGING", staging)
    rows = backfill._parse_rows(None)
    assert len(rows) == 1 and rows[0]["temperature_f"] == 70.0


def test_resume_skips_venue_seasons_already_finished(tmp_path, monkeypatch):
    done = tmp_path / "d.done"
    done.write_text("3795|2024|0\n3795|2024|72\n")
    monkeypatch.setattr(backfill, "DONE", done)
    assert backfill._load_done() == {"3795|2024|0", "3795|2024|72"}


def test_promote_filters_to_the_requested_leads(tmp_path, monkeypatch):
    staging = tmp_path / "s.jsonl"
    staging.write_text(
        "\n".join(
            json.dumps(backfill._row(i, lead, KICK, SOURCE_NEAR_KICKOFF, None, VENUE, {"temperature_f": 60.0}))
            for i, lead in [(1, 0), (2, 24), (3, 72)]
        )
    )
    monkeypatch.setattr(backfill, "STAGING", staging)
    assert {r["lead_hours"] for r in backfill._parse_rows([0, 24])} == {0, 24}


# --------------------------------------------------------------------------- #
# Repairing the data must not, by itself, move the model
# --------------------------------------------------------------------------- #
def _frame(monkeypatch, eng):
    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s

    monkeypatch.setattr(features, "session_scope", scope)
    return pd.DataFrame(
        {
            "id": [1, 2],
            "season": [2026, 2026],
            "week": [3, 3],
            "home_team": ["A", "C"],
            "away_team": ["B", "D"],
        }
    )


def test_the_default_arm_reads_the_legacy_table_and_ignores_weather_obs(monkeypatch):
    """WEATHER_OBS_LEAD_HOURS is None, so a freshly backfilled weather_obs
    changes nothing until someone explicitly turns it on."""
    assert features.WEATHER_OBS_LEAD_HOURS is None
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Weather(game_id=1, temperature_f=55.0, wind_mph=12.0, precipitation=0.1, dome=False))
        # the repaired value for the same game, sitting in the new table
        s.add(
            WeatherObs(
                game_id=1,
                lead_hours=0,
                temperature_f=78.1,
                wind_mph=4.0,
                wind_gust_mph=9.0,
                precipitation=0.0,
                dome=False,
                decision_safe=False,
            )
        )
        s.commit()
    df = _frame(monkeypatch, eng)
    out = features._merge_tempo_weather(df.copy()).set_index("id")
    assert out.loc[1, "wx_temp"] == 55.0  # legacy, untouched
    assert np.isnan(out.loc[1, "wx_gust"])  # the legacy table has no gust at all


def test_naming_a_lead_switches_the_arm(monkeypatch):
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Weather(game_id=1, temperature_f=55.0, wind_mph=12.0, precipitation=0.1, dome=False))
        for lead, temp in ((0, 78.1), (72, 71.0)):
            s.add(
                WeatherObs(
                    game_id=1,
                    lead_hours=lead,
                    temperature_f=temp,
                    wind_mph=4.0,
                    wind_gust_mph=9.0,
                    precipitation=0.0,
                    dome=False,
                    decision_safe=lead > 0,
                )
            )
        s.commit()
    df = _frame(monkeypatch, eng)
    near = features._merge_tempo_weather(df.copy(), 0).set_index("id")
    decision = features._merge_tempo_weather(df.copy(), 72).set_index("id")
    assert near.loc[1, "wx_temp"] == 78.1
    assert decision.loc[1, "wx_temp"] == 71.0
    assert near.loc[1, "wx_gust"] == 9.0


def test_gust_is_available_but_not_yet_a_model_feature():
    """Adding wx_gust to the model is part of activation, not of the repair."""
    assert "wx_gust" not in features.FEATURE_COLS
