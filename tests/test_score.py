import numpy as np
import pandas as pd

from beatvegas.model.score import _weather_str, under_score


def test_weather_nan_dome_is_not_dome():
    # NaN wx_dome (no weather row) must NOT read as a dome
    assert _weather_str(pd.Series({"wx_dome": np.nan, "wx_temp": np.nan})) is None


def test_weather_real_dome_and_outdoor():
    assert _weather_str(pd.Series({"wx_dome": 1.0})) == "Dome"
    out = _weather_str(
        pd.Series({"wx_dome": 0.0, "wx_temp": 68.0, "wx_wind": 10.0, "wx_precip": 0.0})
    )
    assert out == "68°F · wind 10mph"


def test_breakeven_maps_to_50():
    assert under_score(0.524) == 50


def test_lean_under_above_50():
    assert under_score(0.60) == 65  # 50 + 0.076*200
    assert under_score(0.55) == 55


def test_lean_over_below_50():
    assert under_score(0.45) == 35
    assert under_score(0.50) == 45


def test_clipped_to_1_99():
    assert under_score(0.99) == 99
    assert under_score(0.01) == 1
