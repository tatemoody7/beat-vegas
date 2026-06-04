"""Tests for the green/red factor board metadata layered onto the registry.

The board is a pure EXPLAINER: it never changes the rank. Each factor carries
pre-registered display metadata — a green/red `direction` (sign such that
`direction * (value - median)` positive means more under-favorable), a `binary`
flag (hard green/red for dome / short week), a `hypothesis` flag (unverified —
rendered amber until the real-line ledger speaks), a base display `tier`, and a
plain-English `sentence` template.
"""

from __future__ import annotations

import pandas as pd

from beatvegas.factors.board import build_factor_board, factor_references, tint_factor
from beatvegas.factors.registry import factor_by_name
from beatvegas.model.score import _factors


def test_board_metadata_defaults():
    f = factor_by_name("week")
    assert f.direction == 0  # unknown/neutral until pre-registered
    assert f.binary is False
    assert f.hypothesis is False
    assert f.tier == 3  # speculative by default
    assert f.sentence == ""


def test_tier1_pace_directions():
    spp = factor_by_name("combined_sec_play")
    assert spp.tier == 1
    assert spp.direction == 1  # more seconds/play = slower = helps the under
    plays = factor_by_name("combined_plays")
    assert plays.tier == 1
    assert plays.direction == -1  # more plays = more scoring = hurts the under


def test_tier1_weather_metadata():
    wind = factor_by_name("wx_wind")
    assert wind.tier == 1
    assert wind.direction == 1  # higher wind suppresses passing = helps the under
    assert factor_by_name("wx_precip").direction == 1
    assert factor_by_name("wx_temp").direction == -1  # cold helps; hotter hurts
    dome = factor_by_name("wx_dome")
    assert dome.tier == 1
    assert dome.binary is True  # controlled conditions = hard green/red, not a continuum


def test_tier1_efficiency_and_scoring_levels():
    # The accepted correction: efficiency/scoring LEVELS join pace+weather in Tier 1.
    off = factor_by_name("combined_off_ppa")
    assert off.tier == 1
    assert off.direction == -1  # more efficient offenses = more points = hurts the under
    deff = factor_by_name("combined_def_ppa")
    assert deff.tier == 1
    assert deff.direction == -1  # higher PPA allowed = weaker defense = hurts the under
    assert factor_by_name("combined_fh_offense").tier == 1
    assert factor_by_name("combined_fh_defense").tier == 1


def test_hypothesis_factors_flagged_amber():
    # explosive / turnovers / havoc are unverified hypotheses, never plain-green.
    assert factor_by_name("home_fh_off_explosive").hypothesis is True
    assert factor_by_name("home_fh_off_turnovers").hypothesis is True
    assert factor_by_name("home_fh_off_pass_rate").hypothesis is True
    assert factor_by_name("mm_havoc").hypothesis is True
    assert factor_by_name("mm_explosive_edge").hypothesis is True


def test_binary_situational_flags():
    assert factor_by_name("home_short_week").binary is True
    assert factor_by_name("away_short_week").binary is True


def test_tier1_factors_have_sentence_templates():
    for name in ("combined_sec_play", "wx_wind", "combined_off_ppa"):
        assert factor_by_name(name).sentence, f"{name} needs a plain-English template"


def test_factor_by_name_unknown_returns_none():
    assert factor_by_name("nope_not_a_factor") is None


def test_dome_direction_favors_over():
    # Dome = controlled conditions, a slight lean toward the OVER.
    assert factor_by_name("wx_dome").direction == -1


# --- tinting (sign x intensity vs historical median) -------------------------


def test_tint_continuous_green_when_under_favorable():
    wind = factor_by_name("wx_wind")  # direction +1: more wind helps the under
    t = tint_factor(wind, value=20.0, median=8.0, spread=6.0)
    assert t.color == "green"
    assert t.lean > 0
    assert 0 < t.intensity <= 1.0


def test_tint_continuous_red_when_against_under():
    plays = factor_by_name("combined_plays")  # direction -1: more plays hurts
    t = tint_factor(plays, value=150.0, median=125.0, spread=10.0)
    assert t.color == "red"
    assert t.lean < 0


def test_tint_neutral_near_median():
    wind = factor_by_name("wx_wind")
    t = tint_factor(wind, value=8.2, median=8.0, spread=6.0)
    assert t.color == "neutral"
    assert abs(t.lean) < 0.1


def test_tint_hypothesis_is_amber_not_green():
    expl = factor_by_name("home_fh_off_explosive")
    t = tint_factor(expl, value=0.2, median=0.1, spread=0.03)
    assert t.color == "amber"  # never plain green, even when "favorable"


def test_tint_binary_dome_hard_red_when_active():
    dome = factor_by_name("wx_dome")  # binary, direction -1
    on = tint_factor(dome, value=1.0, median=0.0, spread=None)
    assert on.color == "red"
    assert on.intensity == 1.0
    off = tint_factor(dome, value=0.0, median=0.0, spread=None)
    assert off.color in ("neutral", "unknown")


def test_tint_missing_value_is_unknown():
    wind = factor_by_name("wx_wind")
    t = tint_factor(wind, value=None, median=8.0, spread=6.0)
    assert t.color == "unknown"
    assert t.intensity == 0.0


def test_tint_fills_sentence_with_value_and_direction():
    wind = factor_by_name("wx_wind")
    t = tint_factor(wind, value=20.0, median=8.0, spread=6.0)
    assert "20" in t.sentence
    assert "helps" in t.sentence  # green => "helps"


# --- references + board emission ---------------------------------------------


def test_factor_references_median_and_robust_spread():
    df = pd.DataFrame(
        {
            "wx_wind": [0.0, 5.0, 10.0, 15.0, 20.0],
            "combined_plays": [120.0, 122.0, 125.0, 128.0, 130.0],
            "season": [2023] * 5,
            "under": [0, 1, 0, 1, 0],
        }
    )
    refs = factor_references(df)
    assert "wx_wind" in refs and "combined_plays" in refs
    med, spread = refs["wx_wind"]
    assert med == 10.0
    assert spread > 0


def test_build_factor_board_tints_present_factors():
    refs = {"wx_wind": (8.0, 6.0), "combined_plays": (125.0, 10.0)}
    row = pd.Series({"wx_wind": 20.0, "combined_plays": 150.0, "week": 5})
    board = build_factor_board(row, refs)
    keys = {b["key"] for b in board}
    assert "wx_wind" in keys
    assert "week" not in keys  # not a board factor
    wind = next(b for b in board if b["key"] == "wx_wind")
    assert wind["color"] == "green"
    assert wind["tier"] == 1
    assert wind["value"] == 20.0
    assert wind["live"] is None
    assert "20" in wind["sentence"]


def test_build_factor_board_drops_unknown_values():
    refs = {"wx_wind": (8.0, 6.0)}
    row = pd.Series({"wx_wind": float("nan")})
    board = build_factor_board(row, refs)
    assert all(b["key"] != "wx_wind" for b in board)


def test_factors_includes_factor_board_when_refs_given():
    refs = {"wx_wind": (8.0, 6.0)}
    row = pd.Series({"wx_wind": 18.0, "bv_line": 24.0})
    fac = _factors(row, line=26.0, refs=refs)
    assert "factor_board" in fac
    assert any(b["key"] == "wx_wind" for b in fac["factor_board"])


def test_factors_factor_board_empty_without_refs():
    fac = _factors(pd.Series({"bv_line": 24.0}), line=26.0)
    assert fac["factor_board"] == []


def test_build_factor_board_drops_inactive_binary():
    # A non-dome, normal-rest game shouldn't list "Dome" / "short week" rows.
    row = pd.Series({"wx_dome": 0.0, "home_short_week": 0.0})
    board = build_factor_board(row, {})
    assert all(b["key"] not in ("wx_dome", "home_short_week") for b in board)


def test_build_factor_board_keeps_active_binary():
    row = pd.Series({"wx_dome": 1.0})
    board = build_factor_board(row, {})
    assert any(b["key"] == "wx_dome" and b["color"] == "red" for b in board)


def test_build_factor_board_attaches_live_and_promotes_tier():
    # A real-line track record promotes a base Tier-2 factor to Tier 1.
    ledger = {
        "home_short_week": {
            "n": 30,
            "hits": 22,
            "mean": 0.66,
            "lo": 0.55,
            "hi": 0.76,
            "cooling": False,
        }
    }
    row = pd.Series({"home_short_week": 1.0})
    board = build_factor_board(row, {}, ledger=ledger)
    f = next(b for b in board if b["key"] == "home_short_week")
    assert f["live"]["n"] == 30
    assert f["tier"] == 1  # promoted from base tier 2


def test_build_factor_board_passes_cooling_flag():
    ledger = {
        "combined_sec_play": {
            "n": 40,
            "hits": 18,
            "mean": 0.50,
            "lo": 0.42,
            "hi": 0.58,
            "cooling": True,
        }
    }
    row = pd.Series({"combined_sec_play": 31.0})
    board = build_factor_board(row, {"combined_sec_play": (28.0, 3.0)}, ledger=ledger)
    f = next(b for b in board if b["key"] == "combined_sec_play")
    assert f["live"]["cooling"] is True
