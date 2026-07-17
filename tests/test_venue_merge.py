"""Venue-metadata merge must survive object-dtype venue_id.

Postgres (psycopg) hands back a nullable int column as object dtype when any
NULL is present, while Venue.id comes back int64 — a raw merge then raises
"merge on object and int64 columns". This bit grade_factor_ledger.py on the
week-sim sandbox. The join key is coerced so the merge is dtype-robust.
"""

from __future__ import annotations

import pandas as pd

from beatvegas.etl.features import _merge_venue_meta


def test_merge_venue_meta_handles_object_venue_id():
    games = pd.DataFrame({"id": [1, 2, 3], "venue_id": pd.Series([10, None, 11], dtype=object)})
    venues = pd.DataFrame({"venue_id": [10, 11], "venue_elevation": [5.0, 9.0]})

    out = _merge_venue_meta(games, venues)

    assert out.loc[out["id"] == 1, "venue_elevation"].iloc[0] == 5.0
    assert pd.isna(out.loc[out["id"] == 2, "venue_elevation"].iloc[0])  # null venue → no match
    assert out.loc[out["id"] == 3, "venue_elevation"].iloc[0] == 9.0
