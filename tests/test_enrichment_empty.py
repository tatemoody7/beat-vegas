"""Enrichment frame builders must keep their column schema even when the API
returns nothing — otherwise build_feature_frame's prefixed merges KeyError on
e.g. 'home_r_season' (only bites thin/sandbox data)."""

import pytest

from beatvegas.sources import season_stats

_EXPECTED = {
    "sp_frame": {"season", "team", "sp_overall", "sp_offense", "sp_defense"},
    "returning_frame": {
        "season",
        "team",
        "returning_ppa",
        "returning_pass_ppa",
        "returning_usage",
    },
    "talent_frame": {"season", "team", "talent"},
    "roster_experience_frame": {"season", "team", "roster_exp", "roster_upperclass"},
    "advanced_frame": {
        "season",
        "team",
        "off_ppa",
        "def_ppa",
        "off_success",
        "def_success",
        "off_explosive",
        "def_explosive",
    },
}


@pytest.fixture
def no_api(monkeypatch):
    # Bypass disk cache + the CFBD client entirely; every fetch returns no rows.
    monkeypatch.setattr(season_stats, "_cached", lambda name, fetch: [])


def test_enrichment_frames_keep_schema_when_empty(no_api):
    client = object()  # unused: _cached short-circuits before touching it
    for name, cols in _EXPECTED.items():
        fn = getattr(season_stats, name)
        df = fn(client, [2024])
        assert df.empty, f"{name} should be empty with no API data"
        missing = cols - set(df.columns)
        assert not missing, f"{name} missing columns when empty: {missing}"
