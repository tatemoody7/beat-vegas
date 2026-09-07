"""config.example.yaml IS the production Odds API config: the GitHub Actions jobs
have no config.yaml, so a stray edit here silently drops Hard Rock (us2) or
switches the 1H market. Pin the two values prod relies on."""

from pathlib import Path

import yaml

EXAMPLE = Path(__file__).resolve().parent.parent / "config.example.yaml"


def _odds_api():
    return yaml.safe_load(EXAMPLE.read_text())["odds_api"]


def test_regions_include_us2_for_hard_rock():
    regions = [r.strip() for r in _odds_api()["regions"].split(",")]
    assert "us2" in regions


def test_market_is_first_half_totals():
    assert _odds_api()["markets"] == "totals_h1"
