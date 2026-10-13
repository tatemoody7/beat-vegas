"""sources/weather.py::fetch_hourly_series_batch (2026-10-13): several venues in one
Open-Meteo request, matched back by position, with a coordinate check; a missing
or displaced block is None, never a neighbour's weather."""

from beatvegas.sources import weather as Wx


def _body(lat, lon, wind):
    return {
        "latitude": lat,
        "longitude": lon,
        "hourly": {
            "time": ["2026-10-17T19:00", "2026-10-17T20:00"],
            "temperature_2m": [60.0, 61.0],
            "wind_speed_10m": [wind, wind + 1],
            "wind_gusts_10m": [wind + 8, wind + 9],
            "precipitation": [0.0, 0.0],
        },
    }


def test_batch_returns_one_series_per_point_in_order(monkeypatch):
    seen = {}

    def fake_request(url, params, timeout, attempts):
        seen.update(params)
        return [_body(40.0, -83.0, 12.0), _body(41.0, -96.0, 5.0)]

    monkeypatch.setattr(Wx, "_request", fake_request)
    out = Wx.fetch_hourly_series_batch(
        [(40.0, -83.0), (41.0, -96.0)],
        "2026-10-17",
        "2026-10-17",
        models="icon_seamless",
        timeout=10,
        attempts=2,
    )
    assert seen["latitude"] == "40.0000,41.0000" and seen["longitude"] == "-83.0000,-96.0000"
    assert seen["timezone"] == "UTC" and seen["models"] == "icon_seamless"
    assert (
        out[0]["2026-10-17T19"]["wind_mph"] == 12.0 and out[1]["2026-10-17T20"]["wind_mph"] == 6.0
    )


def test_a_single_point_body_is_a_dict_and_still_one_series(monkeypatch):
    monkeypatch.setattr(Wx, "_request", lambda *a, **k: _body(40.0, -83.0, 9.0))
    out = Wx.fetch_hourly_series_batch([(40.0, -83.0)], "2026-10-17", "2026-10-17")
    assert len(out) == 1 and out[0]["2026-10-17T19"]["wind_mph"] == 9.0


def test_short_or_displaced_blocks_are_none_not_a_neighbours_weather(monkeypatch, capsys):
    # Three points asked; the body has two blocks and the second sits 2 degrees away.
    monkeypatch.setattr(
        Wx, "_request", lambda *a, **k: [_body(40.0, -83.0, 12.0), _body(43.0, -96.0, 30.0)]
    )
    out = Wx.fetch_hourly_series_batch(
        [(40.0, -83.0), (41.0, -96.0), (42.0, -70.0)], "2026-10-17", "2026-10-17"
    )
    assert out[0] is not None and out[1] is None and out[2] is None
    assert "discarded" in capsys.readouterr().out
    assert Wx.fetch_hourly_series_batch([], "2026-10-17", "2026-10-17") == []


def test_a_failed_request_raises_for_the_whole_batch(monkeypatch):
    def boom(*a, **k):
        raise Wx.WeatherUnavailable("down")

    monkeypatch.setattr(Wx, "_request", boom)
    try:
        Wx.fetch_hourly_series_batch([(40.0, -83.0), (41.0, -96.0)], "2026-10-17", "2026-10-17")
    except Wx.WeatherUnavailable:
        pass
    else:
        raise AssertionError("expected WeatherUnavailable")


def test_get_still_returns_the_hourly_block(monkeypatch):
    monkeypatch.setattr(Wx, "_request", lambda *a, **k: {"hourly": {"time": ["x"]}})
    assert Wx._get("u", {}, 1, 1) == {"time": ["x"]}
    monkeypatch.setattr(Wx, "_request", lambda *a, **k: [])
    assert Wx._get("u", {}, 1, 1) == {}
