"""The weather gate asks WHEN, not WHETHER.

The values in the legacy table are wrong and the repair is verified against
ground truth elsewhere, so this report must never be readable as "the fix did
not improve MAE, therefore keep the wrong data". These tests pin that framing
into the artefact itself, because a framing that lives only in a docstring is
the one that gets lost.
"""

from __future__ import annotations

import pytest

from beatvegas.backtest import weather_gate as G


def test_the_incumbent_arm_is_the_legacy_table():
    assert G.WEATHER_ARMS[0] is None
    assert G._tag(None) == "legacy"
    assert G._tag(0) == "lead0" and G._tag(72) == "lead72"


def test_evaluate_refuses_without_the_incumbent():
    with pytest.raises(ValueError, match="incumbent"):
        G.evaluate([2023], 2024, arms=[0, 72], frames={}, closes=None)


def _report(**over):
    base = {
        "kind": "weather_gate",
        "train_seasons": [2023, 2024],
        "test_season": 2025,
        "bet_gap_pts": 1.75,
        "eyeballable_movers": G.EYEBALLABLE_MOVERS,
        "n_test": 600,
        "n_with_close": 400,
        "results": [
            {
                "arm": "legacy", "lead_hours": None, "is_incumbent": True, "decision_safe": False,
                "coverage": {"n_rows": 600, "n_with_temp": 230, "share": 0.38},
                "n": 600, "mae": 9.10, "mae_incumbent": 9.10, "bias": -0.20,
                "bias_incumbent": -0.20, "paired_gain": {}, "n_changed": 0,
                "gate": {"n_priced": 400, "mean_gap": 0.4, "n_clearing": 40,
                         "n_clearing_incumbent": 40, "n_crossing": 0, "crossing_ids": []},
            },
            {
                "arm": "lead72", "lead_hours": 72, "is_incumbent": False, "decision_safe": True,
                "coverage": {"n_rows": 600, "n_with_temp": 580, "share": 0.97},
                "n": 600, "mae": 9.12, "mae_incumbent": 9.10, "bias": -0.18,
                "bias_incumbent": -0.20, "paired_gain": {}, "n_changed": 512,
                "gate": {"n_priced": 400, "mean_gap": 0.4, "n_clearing": 43,
                         "n_clearing_incumbent": 40, "n_crossing": 3,
                         "crossing_ids": [1, 2, 3]},
            },
        ],
        "caveats": ["MAE is near-blind to a change of this kind."],
    }
    base.update(over)
    return base


def test_the_report_says_it_is_not_a_correctness_test():
    md = G.render_markdown(_report())
    assert "not a correctness test" in md.lower()
    assert "timing" in md.lower()


def test_a_worse_mae_still_reads_as_promotable_when_few_games_move():
    """lead72 has the WORSE MAE here (9.12 vs 9.10) and only 3 crossings."""
    md = G.render_markdown(_report())
    assert "promote now is defensible" in md


def test_many_movers_defer_to_after_the_card():
    r = _report()
    r["results"][1]["gate"]["n_crossing"] = 40
    md = G.render_markdown(r)
    assert "after the next card settles" in md


def test_decision_safety_is_visible_per_arm():
    md = G.render_markdown(_report())
    header, *rows = [ln for ln in md.splitlines() if ln.startswith("|")]
    assert "decision-safe" in header
    assert any("lead72" in r and "| yes " in r for r in rows)
    assert any("legacy" in r and "| no " in r for r in rows)


def test_thin_coverage_is_caveated_rather_than_read_as_a_null():
    rows = [
        {"arm": "legacy", "lead_hours": None, "coverage": {"n_rows": 10, "n_with_temp": 4, "share": 0.4}, "gate": {"n_priced": 5}},
        {"arm": "lead72", "lead_hours": 72, "coverage": {"n_rows": 10, "n_with_temp": 1, "share": 0.1}, "gate": {"n_priced": 5}},
    ]
    caveats = " ".join(G._caveats(rows, 2025))
    assert "absence, not evidence" in caveats
    assert "lead72" in caveats
    assert "legacy" not in caveats  # the incumbent's own coverage is the thing being fixed


def test_a_pre_2024_test_season_is_flagged_as_temperature_only():
    caveats = " ".join(G._caveats([{"arm": "lead72", "lead_hours": 72,
                                    "coverage": {"share": 1.0, "n_with_temp": 1, "n_rows": 1},
                                    "gate": {"n_priced": 1}}], 2023))
    assert "predates the fixed-lead data" in caveats


def test_an_arm_with_an_empty_training_season_is_called_starved_not_weak():
    """Leads 24/72 hold nothing before 2024, yet their OVERALL share reads 60% --
    comfortably above any threshold. The per-season split is what catches it."""
    rows = [
        {"arm": "legacy", "lead_hours": None,
         "coverage": {"share": 0.34, "n_with_temp": 250, "n_rows": 744, "by_train_season": {}},
         "gate": {"n_priced": 622}},
        {"arm": "lead72", "lead_hours": 72,
         "coverage": {"share": 0.60, "n_with_temp": 446, "n_rows": 744,
                      "by_train_season": {"2023": 0.0, "2024": 0.97, "2025": 0.96}},
         "gate": {"n_priced": 622}},
    ]
    caveats = " ".join(G._caveats(rows, 2025, [2023, 2024]))
    assert "lead72" in caveats and "2023" in caveats
    assert "handicapped, not a null result" in caveats


def test_an_arm_covering_its_whole_train_window_is_not_flagged():
    rows = [
        {"arm": "legacy", "lead_hours": None,
         "coverage": {"share": 0.34, "n_with_temp": 1, "n_rows": 1, "by_train_season": {}},
         "gate": {"n_priced": 622}},
        {"arm": "lead72", "lead_hours": 72,
         "coverage": {"share": 0.96, "n_with_temp": 1, "n_rows": 1,
                      "by_train_season": {"2024": 0.97, "2025": 0.96}},
         "gate": {"n_priced": 622}},
    ]
    caveats = " ".join(G._caveats(rows, 2025, [2024]))
    assert "handicapped" not in caveats
