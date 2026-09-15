"""Venue coordinates, checked BEFORE a weather backfill spends its requests.

Collecting perfectly correct weather for the wrong stadium is the expensive
failure mode here: every call succeeds, the numbers look plausible, and nothing
downstream can tell. `backfill.py::backfill_venues` falls back to CFBD's
`location["x"]` / `location["y"]`, and in GeoJSON `x` is conventionally
longitude -- so a swap is a live possibility rather than a hypothetical.

The pinned fixture below is a drift guard, not an independent survey: the values
were read from the audited production database on 2026-09-13 and cross-checked
against the cities they claim to be in. A tolerance of 0.05 degrees is about
5 km -- tight enough to catch a swap, a hemisphere flip or a wrong stadium, loose
enough that CFBD nudging a pin does not fail CI.
"""

from __future__ import annotations

import pytest

from beatvegas.etl.venues import PLAUSIBLE_LAT, PLAUSIBLE_LON, coord_problems, looks_swapped

# (venue_id, name, where, latitude, longitude) -- deliberately spread across the
# continent plus the two European neutral sites, because a bounds check that only
# ever sees the Midwest proves nothing about Honolulu or Dublin.
KNOWN = [
    (3653, "Albertsons Stadium", "Boise, ID", 43.6029, -116.1959),
    (3610, "Aloha Stadium", "Honolulu, HI", 21.3728, -157.9300),
    (3626, "Autzen Stadium", "Eugene, OR", 44.0583, -123.0685),
    (3504, "Aviva Stadium", "Dublin", 53.3352, -6.2284),
    (3632, "Beaver Stadium", "University Park, PA", 40.8122, -77.8561),
    (3634, "Ben Hill Griffin Stadium", "Gainesville, FL", 29.6499, -82.3486),
    (3646, "Boone Pickens Stadium", "Stillwater, OK", 36.1257, -97.0665),
    (3657, "Bryant-Denny Stadium", "Tuscaloosa, AL", 33.2083, -87.5504),
    (347, "Camp Randall Stadium", "Madison, WI", 43.0699, -89.4127),
    (3697, "Doak Campbell Stadium", "Tallahassee, FL", 30.4382, -84.3044),
    (3713, "Falcon Stadium", "Colorado Springs, CO", 38.9970, -104.8436),
    (3726, "Folsom Field", "Boulder, CO", 40.0095, -105.2669),
    (3785, "Jordan-Hare Stadium", "Auburn, AL", 32.6026, -85.4897),
    (3793, "Kinnick Stadium", "Iowa City, IA", 41.6586, -91.5511),
    (3795, "Kyle Field", "College Station, TX", 30.6099, -96.3404),
    (3799, "Lane Stadium", "Blacksburg, VA", 37.2200, -80.4181),
    (477, "Los Angeles Memorial Coliseum", "Los Angeles, CA", 34.0142, -118.2878),
    (3829, "Memorial Stadium", "Terre Haute, IN", 39.4747, -87.3670),
    (3558, "Michigan Stadium", "Ann Arbor, MI", 42.2658, -83.7487),
    (3853, "Neyland Stadium", "Knoxville, TN", 35.9550, -83.9250),
    (3855, "Notre Dame Stadium", "Notre Dame, IN", 41.6984, -86.2339),
    (3861, "Ohio Stadium", "Columbus, OH", 40.0016, -83.0197),
    (587, "Rice-Eccles Stadium", "Salt Lake City, UT", 40.7600, -111.8488),
    (1056, "Rose Bowl", "Pasadena, CA", 34.1613, -118.1676),
    (3917, "Sanford Stadium", "Athens, GA", 33.9498, -83.3734),
    (3994, "Williams-Brice Stadium", "Columbia, SC", 33.9730, -81.0192),
]
TOLERANCE_DEG = 0.05


def _as_rows(items):
    return [{"id": i, "name": n, "latitude": la, "longitude": lo} for i, n, _, la, lo in items]


def test_the_pinned_stadiums_are_all_plausible():
    assert coord_problems(_as_rows(KNOWN)) == []


def test_the_fixture_spans_the_continent():
    """A bounds check that never leaves the Midwest proves nothing."""
    lats = [la for *_, la, _ in KNOWN]
    lons = [lo for *_, lo in KNOWN]
    assert min(lats) < 25 and max(lats) > 50  # Honolulu .. Dublin
    assert min(lons) < -150 and max(lons) > -10  # Hawaii .. Ireland


def test_a_swapped_pair_is_caught():
    swapped = [{"id": 1, "name": "Kyle Field", "latitude": -96.3404, "longitude": 30.6099}]
    problems = coord_problems(swapped)
    assert len(problems) == 1 and "swapped" in problems[0][1]
    assert looks_swapped(-96.3404, 30.6099)


def test_a_correct_pair_does_not_look_swapped():
    for _, _, _, lat, lon in KNOWN:
        assert not looks_swapped(lat, lon)


def test_missing_coordinates_are_reported_separately_from_wrong_ones():
    rows = [
        {"id": 1, "name": "no coords", "latitude": None, "longitude": None},
        {"id": 2, "name": "off planet", "latitude": 999.0, "longitude": 0.0},
    ]
    kinds = dict(coord_problems(rows))
    assert kinds[1] == "missing"
    assert "out of range" in kinds[2]


@pytest.mark.parametrize("lat,lon", [(0.0, 0.0), (-33.9, 151.2), (55.7, 37.6)])
def test_places_we_never_play_are_rejected(lat, lon):
    """Null Island, Sydney, Moscow -- a fetch landing here means a bad join."""
    assert coord_problems([{"id": 9, "name": "x", "latitude": lat, "longitude": lon}])


def test_bounds_are_stated_not_guessed():
    assert PLAUSIBLE_LAT == (18.0, 62.0)
    assert PLAUSIBLE_LON == (-180.0, 15.0)
