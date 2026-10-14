"""scripts/probe_alt_totals_h1.py: pure parsing only (the network call is never made here)."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "probe_alt", Path(__file__).resolve().parents[1] / "scripts" / "probe_alt_totals_h1.py"
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def _event(main, alt):
    def mk(key, pairs):
        outs = []
        for pt, over, under in pairs:
            outs += [
                {"name": "Over", "point": pt, "price": over},
                {"name": "Under", "point": pt, "price": under},
            ]
        return {"key": key, "outcomes": outs}

    return {
        "away_team": "A",
        "home_team": "B",
        "commence_time": "2026-10-17T19:30:00Z",
        "bookmakers": [
            {
                "key": "hardrockbet",
                "markets": [mk("totals_h1", main), mk("alternate_totals_h1", alt)],
            }
        ],
    }


def test_a_rung_fed_row_with_the_main_line_still_in_the_ladder():
    r = probe.summarize(
        _event([(30.5, -160, 125)], [(27.5, -110, -110), (30.5, -160, 125), (24.5, 135, -170)])
    )
    assert r["fed"] == (30.5, -160, 125) and r["fed_is_rung"] is True
    assert r["main_in_ladder"] == [27.5] and r["ladder_points"] == 3
    assert "on 1; the alternate ladder still carried a main-priced line on 1" in probe.verdict([r])


def test_a_main_fed_row_and_no_ladder():
    r = probe.summarize(_event([(27.5, -110, -110)], []))
    assert r["fed_is_rung"] is False and r["main_in_ladder"] == []


def test_the_cap_holds_the_credit_budget():
    assert probe.CREDITS_PER_EVENT * probe.MAX_EVENTS == 24
