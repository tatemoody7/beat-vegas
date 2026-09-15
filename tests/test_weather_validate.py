"""The gust check was loosened, so these tests pin what it must still catch.

A gust below the mean wind is physically impossible, but two different things
produce it. Open-Meteo works in m/s and converts, so on a calm hour where gust
equals wind the rounding inverts them by a tenth -- measured on the real
near-kickoff backfill, 15 of 4,227 rows (0.35%), every deficit 0.1-0.3 mph. The
real failure is `gfs_seamless` at 48h and beyond, where gust and mean wind come
from different model runs: 32% of samples inverted, deficits out to 2.7 mph.

Their magnitudes OVERLAP at the low end, so a tolerance alone cannot tell them
apart. The rate is what separates them, and a loosened check that could no longer
see the gfs population would be worse than the strict one it replaced.
"""

from __future__ import annotations

import pytest

validate = pytest.importorskip("scripts.weather_validate", reason="scripts not importable")


def _rows(pairs, lead=0):
    return [
        {
            "game_id": i,
            "lead_hours": lead,
            "dome": False,
            "wind_mph": w,
            "wind_gust_mph": g,
            "temperature_f": 60.0,
            "precipitation": 0.0,
        }
        for i, (w, g) in enumerate(pairs)
    ]


def test_calm_hour_rounding_passes():
    """15 tenths-of-a-mph inversions in 4,227 rows is unit conversion."""
    rows = _rows([(5.0, 6.0)] * 999 + [(5.4, 5.1)])
    assert validate.check_envelopes(rows) is True


def test_a_single_large_inversion_fails_however_rare():
    """One gust 2.7mph under its own mean wind is not rounding."""
    rows = _rows([(5.0, 6.0)] * 999 + [(8.0, 5.3)])
    assert validate.check_envelopes(rows) is False


def test_the_gfs_population_still_fails():
    """32% inverted, deficits 0.1-2.7mph -- the failure this tolerance must not hide."""
    bad = [(10.0, 10.0 - d) for d in (0.1, 0.2, 0.4, 0.7, 0.8, 1.7, 2.3, 2.7)]
    rows = _rows(bad + [(5.0, 9.0)] * 17)
    assert validate.check_envelopes(rows) is False


def test_many_tiny_inversions_fail_on_rate_alone():
    """Every deficit inside the tolerance, but far too many of them."""
    rows = _rows([(5.0, 4.9)] * 100 + [(5.0, 9.0)] * 100)
    assert validate.check_envelopes(rows) is False


def test_thresholds_are_stated_not_guessed():
    assert validate.GUST_TOLERANCE_MPH == 0.5
    assert validate.GUST_INVERSION_RATE_MAX == 0.01


def test_a_dome_carrying_weather_fails():
    rows = _rows([(5.0, 9.0)])
    rows[0].update(dome=True, temperature_f=72.0, wind_mph=0.0)
    assert validate.check_envelopes(rows) is False


def test_a_temperature_outside_the_band_fails():
    rows = _rows([(5.0, 9.0)])
    rows[0]["temperature_f"] = 240.0
    assert validate.check_envelopes(rows) is False


def test_a_lead_0_row_flagged_decision_safe_fails():
    rows = _rows([(5.0, 9.0)])
    rows[0]["decision_safe"] = True
    assert validate.check_decision_safety(rows) is False


def test_fixed_lead_rows_may_be_decision_safe():
    rows = _rows([(5.0, 9.0)], lead=72)
    rows[0]["decision_safe"] = True
    assert validate.check_decision_safety(rows) is True
