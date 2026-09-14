"""Venue coordinate sanity — the check that runs before a weather backfill.

`scripts/backfill.py::backfill_venues` takes lat/lon from CFBD's `latitude` /
`longitude` when present and otherwise falls back to `location["x"]` /
`location["y"]`. In GeoJSON, `x` is conventionally LONGITUDE, so that fallback
could silently store a swapped pair -- and a swap is invisible downstream: the
weather fetch succeeds, returns perfectly good data, and attributes it to the
wrong hemisphere.

Audited against the live database on 2026-09-13: 720 venues used by 2023-26
games, lat 21.29 to 53.34, lon -157.82 to -0.28, every extreme legitimate
(Aloha Stadium Honolulu, Aviva Dublin, Wembley London), zero swaps. This module
exists so that stays true rather than being rechecked by hand.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

# Everything Beat Vegas schedules sits in North America plus the odd European
# neutral site. A swapped US pair lands near lat -87, far outside this.
PLAUSIBLE_LAT = (18.0, 62.0)
PLAUSIBLE_LON = (-180.0, 15.0)


def coord_problems(venues: Iterable[Dict]) -> List[Tuple[int, str]]:
    """(venue_id, what is wrong) for every venue that cannot be fetched safely.

    Takes dicts with `id`, `name`, `latitude`, `longitude`. A venue with NO
    coordinates is reported as `missing` -- it is unfetchable but not wrong --
    so a caller can count the two separately.
    """
    out: List[Tuple[int, str]] = []
    for v in venues:
        lat, lon = v.get("latitude"), v.get("longitude")
        vid = v.get("id")
        if lat is None or lon is None:
            out.append((vid, "missing"))
            continue
        if looks_swapped(lat, lon):
            # Report this first and by name: it is the failure this module exists
            # for, and "out of range" would bury the one actionable diagnosis.
            out.append((vid, f"latitude/longitude look swapped: {lat}, {lon}"))
            continue
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            out.append((vid, f"out of range: {lat}, {lon}"))
            continue
        if not (PLAUSIBLE_LAT[0] <= lat <= PLAUSIBLE_LAT[1]):
            out.append((vid, f"implausible latitude {lat} (swapped lat/lon?)"))
            continue
        if not (PLAUSIBLE_LON[0] <= lon <= PLAUSIBLE_LON[1]):
            out.append((vid, f"implausible longitude {lon}"))
    return out


def looks_swapped(lat: Optional[float], lon: Optional[float]) -> bool:
    """True when the pair is implausible as given but plausible reversed."""
    if lat is None or lon is None:
        return False
    bad_now = not (PLAUSIBLE_LAT[0] <= lat <= PLAUSIBLE_LAT[1]) or not (
        PLAUSIBLE_LON[0] <= lon <= PLAUSIBLE_LON[1]
    )
    good_flipped = (PLAUSIBLE_LAT[0] <= lon <= PLAUSIBLE_LAT[1]) and (
        PLAUSIBLE_LON[0] <= lat <= PLAUSIBLE_LON[1]
    )
    return bad_now and good_flipped
