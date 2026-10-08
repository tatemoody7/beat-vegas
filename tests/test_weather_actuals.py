"""`weather_actuals` (2026-10-08, roadmap v1.3): observed weather for the Salaga &
Howley history look. The pure pieces (the kickoff-hour window, the ERA5 and CFBD
row shapes, the checks), the staged fetch against fake sources, the promote, and
the one property everything rests on: nothing but the backfill reads the table."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, WeatherActual

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def W(load_script, tmp_path, monkeypatch):
    mod = load_script("backfill_weather_actuals")
    monkeypatch.setattr(mod, "STAGING", tmp_path / "staging.jsonl")
    monkeypatch.setattr(mod, "DONE", tmp_path / "staging.done")
    monkeypatch.setattr(mod, "SLEEP_S", 0)
    return mod


def _series(kickoff: datetime, offsets, **vals):
    from datetime import timedelta

    out = {}
    for off in offsets:
        t = kickoff.replace(minute=0) + timedelta(hours=off)
        out[t.strftime("%Y-%m-%dT%H")] = {
            "temperature_f": vals.get("temp", 60.0),
            "humidity_pct": vals.get("hum", 70.0),
            "dew_point_f": 50.0,
            "wind_mph": vals.get("wind", 8.0),
            "wind_gust_mph": vals.get("gust", 15.0),
            "wind_direction_deg": 180.0,
            "precipitation": vals.get("precip", 0.01),
        }
    return out


def test_kickoff_hour_and_a_window_that_crosses_midnight(W):
    k = datetime(2016, 11, 5, 23, 30)
    assert W.kickoff_hour(k) == datetime(2016, 11, 5, 23, 0)
    assert W.era5_window(k) == ("2016-11-05", "2016-11-06")  # +4 h is 03:00Z next day
    assert W.era5_window(datetime(2016, 11, 5, 0, 15)) == ("2016-11-04", "2016-11-05")  # -1 h
    assert W.OFFSETS == (-1, 0, 1, 2, 3, 4)


def test_era5_rows_cover_each_offset_and_drop_unpublished_hours(W):
    k = datetime(2016, 11, 5, 19, 30)
    series = _series(k, [-1, 0, 1, 2])  # +3 and +4 missing (not yet published)
    series[datetime(2016, 11, 5, 21).strftime("%Y-%m-%dT%H")]["temperature_f"] = None
    rows = W.era5_rows(7, k, series, 31.5, -97.1, "2026-10-08T00:00:00")
    assert [r["hour_offset"] for r in rows] == [-1, 0, 1]  # +2 had no temperature
    r0 = rows[1]
    assert r0["valid_time"] == "2016-11-05T19:00:00"
    assert r0["kickoff_utc"] == "2016-11-05T19:30:00"
    assert (r0["source"], r0["weather_model"]) == ("open_meteo_era5_archive", "era5")
    assert r0["precipitation_in"] == 0.01 and r0["humidity_pct"] == 70.0
    assert r0["game_indoors"] is None and r0["dataset_version"] == W.DATASET_VERSION


def test_cfbd_row_keeps_the_reading_as_reported_in_naive_utc(W):
    r = {
        "id": 400869090,
        "startTime": "2016-11-05T19:30:00.000Z",
        "gameIndoors": False,
        "temperature": 63,
        "humidity": 84,
        "dewPoint": 58,
        "windSpeed": 7,
        "windDirection": 190,
        "precipitation": 0,
        "snowfall": 0,
        "pressure": 1015.2,
        "weatherConditionCode": 3,
    }
    row = W.cfbd_row(r, datetime(2016, 11, 5, 19, 30), "2026-10-08T00:00:00")
    assert row["valid_time"] == "2016-11-05T19:30:00"
    assert (row["source"], row["hour_offset"]) == ("cfbd_games_weather", 0)
    assert (row["temperature_f"], row["humidity_pct"], row["wind_mph"]) == (63.0, 84.0, 7.0)
    assert row["weather_code"] == 3 and row["game_indoors"] is False
    assert row["wind_gust_mph"] is None and row["latitude"] is None


def test_dedupe_lets_the_last_write_win(W):
    a = {"game_id": 1, "source": "s", "hour_offset": 0, "dataset_version": "v", "temperature_f": 1}
    b = dict(a, temperature_f=2)
    c = dict(a, hour_offset=1)
    assert sorted(r["temperature_f"] for r in W.dedupe([a, b, c])) == [1, 2]


def test_check_flags_bad_values_and_measures_agreement(W):
    k = datetime(2019, 11, 17, 0, 0)
    era5 = W.era5_rows(1, k, _series(k, [0], temp=44.0, hum=60.0, wind=3.0), 34.3, -89.5, "t")
    cfbd = W.cfbd_row(
        {
            "id": 1,
            "startTime": "2019-11-17T00:00:00.000Z",
            "temperature": 42.8,
            "humidity": 61,
            "windSpeed": 0,
        },
        k,
        "t",
    )
    problems, summary = W.check(era5 + [cfbd])
    assert problems == []
    assert summary["games_in_both"] == 1
    assert summary["mean_abs_diff_temperature_f"] == 1.2
    assert summary["mean_abs_diff_wind_mph"] == 3.0
    bad = W.era5_rows(2, k, _series(k, [0], hum=140.0, wind=20.0, gust=12.0), 0, 0, "t")
    problems, _ = W.check(bad)
    assert any("humidity_pct=140.0" in p for p in problems)
    assert any("gust 12.0 < wind 20.0" in p for p in problems)


def test_era5_fetch_stages_rows_skips_domes_and_resumes(W, monkeypatch):
    k1, k2, k3 = datetime(2016, 9, 3, 16), datetime(2016, 9, 10, 23, 30), datetime(2016, 9, 17, 19)
    plan = {101: (2016, k1, 1), 102: (2016, k2, 1), 103: (2016, k3, 2)}
    venues = {
        1: {"dome": False, "lat": 30.6, "lon": -96.3, "name": "Kyle Field"},
        2: {"dome": True, "lat": 33.7, "lon": -84.4, "name": "a dome"},
    }
    calls = []

    def fake(lat, lon, lo, hi, **kw):
        calls.append((lo, hi, kw["models"], sorted(kw["variables"])))
        start = datetime.strptime(lo, "%Y-%m-%d")
        return _series(start, range(0, 48))

    monkeypatch.setattr(W, "fetch_hourly_series", fake)
    W.fetch_era5(plan, venues, set(), None)
    assert len(calls) == 2  # the dome costs no call
    assert calls[1][:2] == ("2016-09-10", "2016-09-11")
    assert calls[0][2] == "era5" and "relative_humidity_2m" in calls[0][3]
    staged = [json.loads(x) for x in W.STAGING.read_text().splitlines()]
    assert {r["game_id"] for r in staged} == {101, 102}
    assert len(staged) == 12
    done = W._load_done()
    assert done == {"era5|101", "era5|102", "era5|103"}
    W.fetch_era5(plan, venues, done, None)  # a re-run fetches nothing
    assert len(calls) == 2


def test_era5_fetch_stops_after_consecutive_failures(W, monkeypatch):
    from beatvegas.sources.weather import WeatherUnavailable

    monkeypatch.setattr(W, "MAX_CONSECUTIVE_FAILURES", 2)
    plan = {i: (2016, datetime(2016, 9, 3, 16), 1) for i in range(1, 6)}
    venues = {1: {"dome": False, "lat": 30.6, "lon": -96.3, "name": "Kyle Field"}}
    n = []

    def fail(*a, **k):
        n.append(1)
        raise WeatherUnavailable("HTTP 429")

    monkeypatch.setattr(W, "fetch_hourly_series", fail)
    W.fetch_era5(plan, venues, set(), None)
    assert len(n) == 2 and W._load_done() == set()  # nothing marked done


def test_era5_fetch_leaves_games_newer_than_the_archive_lag(W, monkeypatch):
    plan = {1: (2026, datetime.utcnow(), 1)}
    venues = {1: {"dome": False, "lat": 30.6, "lon": -96.3, "name": "Kyle Field"}}
    monkeypatch.setattr(W, "fetch_hourly_series", lambda *a, **k: pytest.fail("called"))
    W.fetch_era5(plan, venues, set(), None)
    assert W._load_done() == set()


def test_cfbd_fetch_keeps_only_planned_games_and_marks_each_season_type(W, monkeypatch):
    seen = []

    class _C:
        def game_weather(self, year, season_type="regular"):
            seen.append((year, season_type))
            return [
                {"id": 1, "startTime": "2016-09-03T16:00:00.000Z", "temperature": 90},
                {"id": 999, "startTime": "2016-09-03T16:00:00.000Z", "temperature": 80},
            ]

    import beatvegas.sources.cfbd as cfbd_mod

    monkeypatch.setattr(cfbd_mod, "CFBDClient", _C)
    plan = {1: (2016, datetime(2016, 9, 3, 16), 1)}
    assert W.fetch_cfbd(plan, 2016, 2016, set()) == 2  # game 1, regular + postseason
    assert seen == [(2016, "regular"), (2016, "postseason")]
    assert W._load_done() == {"cfbd|2016|regular", "cfbd|2016|postseason"}


def test_promote_writes_the_table_and_a_second_promote_replaces_it(W, monkeypatch):
    from contextlib import contextmanager

    from beatvegas.db.models import Game

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2016, week=1, home_team="A", away_team="B"))
        s.commit()

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    import beatvegas.db.store as store

    monkeypatch.setattr(store, "session_scope", scope)
    k = datetime(2016, 9, 3, 16)
    rows = W.era5_rows(1, k, _series(k, W.OFFSETS), 30.6, -96.3, "2026-10-08T00:00:00")
    W.STAGING.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    W.promote([W.SOURCE_ERA5])
    W.promote([W.SOURCE_ERA5])
    with Session(eng) as s:
        got = s.query(WeatherActual).order_by(WeatherActual.hour_offset).all()
        assert [g.hour_offset for g in got] == list(W.OFFSETS)
        assert got[1].valid_time == datetime(2016, 9, 3, 16)


def test_promote_refuses_a_staging_file_with_problems(W):
    k = datetime(2016, 9, 3, 16)
    rows = W.era5_rows(1, k, _series(k, [0], hum=140.0), 0, 0, "t")
    W.STAGING.write_text(json.dumps(rows[0]) + "\n")
    with pytest.raises(SystemExit):
        W.promote([W.SOURCE_ERA5])


def test_the_era5_variable_set_and_the_fixed_lead_refusal(monkeypatch):
    import beatvegas.sources.weather as wx

    sent = {}

    def fake_get(url, params, timeout):
        sent.update(params, url=url)
        return {"time": ["2016-09-03T16:00"], "relative_humidity_2m": [71]}

    monkeypatch.setattr(wx, "_get", fake_get)
    out = wx.fetch_hourly_series(
        30.6,
        -96.3,
        "2016-09-03",
        "2016-09-03",
        source=wx.SOURCE_ACTUAL,
        models="era5",
        variables=wx.ACTUAL_VARS,
    )
    assert sent["url"].startswith("https://archive-api.open-meteo.com")
    assert sent["models"] == "era5" and sent["timezone"] == "UTC"
    assert "relative_humidity_2m" in sent["hourly"] and "dew_point_2m" in sent["hourly"]
    assert out["2016-09-03T16"]["humidity_pct"] == 71
    with pytest.raises(ValueError):
        wx.fetch_hourly_series(
            1,
            1,
            "2024-09-03",
            "2024-09-03",
            source=wx.SOURCE_DECISION,
            lead_hours=24,
            variables=wx.ACTUAL_VARS,
        )


def test_the_table_is_unique_on_game_source_offset_and_version():
    cols = WeatherActual.__table__.columns
    for c in ("humidity_pct", "wind_gust_mph", "precipitation_in", "hour_offset", "source"):
        assert c in cols
    uq = [c for c in WeatherActual.__table__.constraints if c.name == "uq_weather_actual_reading"]
    assert uq and [col.name for col in uq[0].columns] == [
        "game_id",
        "source",
        "hour_offset",
        "dataset_version",
    ]


def test_nothing_but_the_backfill_reads_weather_actuals():
    """The table is a study input only. If a feature builder, scorer or the web
    ever reads it, observed (look-ahead) weather could reach the model -- that is a
    deliberate, registered activation, not a side effect of a backfill."""
    allowed = {
        "beatvegas/db/models.py",
        "scripts/backfill_weather_actuals.py",
    }
    hits = []
    for base in ("beatvegas", "scripts", "web/lib", "web/app"):
        for p in (ROOT / base).rglob("*"):
            if p.suffix not in {".py", ".ts", ".tsx"} or "node_modules" in p.parts:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if rel in allowed:
                continue
            if re.search(r"\bweather_actuals\b|\bWeatherActual\b", p.read_text(errors="ignore")):
                hits.append(rel)
    assert hits == [], hits


def test_a_truncated_final_staging_line_is_skipped_but_damage_elsewhere_raises(W):
    """A run cut off at its time limit (or cancelled) can stop mid-write; the
    resume must still check and promote. A broken line in the middle is not a
    cut-off, so it still stops everything."""
    good = json.dumps({"game_id": 1, "source": "s", "hour_offset": 0, "dataset_version": "v"})
    assert len(W.parse_staging(good + "\n" + good[:20])) == 1
    assert len(W.parse_staging(good + "\n\n" + good + "\n")) == 2
    with pytest.raises(json.JSONDecodeError):
        W.parse_staging(good[:20] + "\n" + good)
