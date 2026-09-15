"""H6 arithmetic and the pre-registered rule, pinned so neither can be tuned to the
numbers: favourable sign, per-build counts, first-to-call, matched pairs, the dated
refusal, and Holm across the six pairs."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from beatvegas.backtest import when_to_bet as W

KICK = datetime(2026, 10, 3, 19, 30)


def _rows(week, slot, built_at, games, tier="BET", clv_shift=0.0, fh=None, price=-110):
    """One build's items: hr_line = 44.5 + shift so its line value vs a 44.0 close
    is shift + 0.5; fh decides the outcome at that line."""
    out = []
    for gid in games:
        out.append(
            {
                "card_id": hash((week, slot, built_at)) % 10_000,
                "built_at": built_at,
                "slot": slot,
                "schedule": "four" if slot in W.FOUR_BUILD_SLOTS else "legacy",
                "week": week,
                "game_id": gid,
                "tier": tier,
                "hr_line": 44.5 + clv_shift,
                "hr_price": price,
                "fh": fh if fh is not None else (40.0 if gid % 2 else 50.0),
                "hr_close": 44.0,
                "close_line": 43.5,
                "kickoff": KICK,
            }
        )
    return out


def _frame(*blocks):
    return pd.DataFrame([r for b in blocks for r in b])


def test_favourable_line_value_is_positive_when_the_market_came_toward_the_under():
    assert W.favourable_clv(45.0, 44.0) == pytest.approx(1.0)
    assert W.favourable_clv(44.0, 45.0) == pytest.approx(-1.0)
    assert W.favourable_clv(None, 44.0) is None and W.favourable_clv(44.0, float("nan")) is None


def test_grade_uses_hard_rocks_number_and_price_and_leaves_unpriced_rows_ungraded():
    df = _frame(_rows(2, "fri_pm", KICK - timedelta(days=1), [1, 2], price=-120))
    df.loc[1, "hr_line"] = np.nan
    g = W.grade(df)
    assert g.loc[0, "outcome_hr"] == "under" and g.loc[0, "units_hr"] == pytest.approx(100 / 120)
    assert g.loc[0, "fav_clv_hr"] == pytest.approx(0.5) and g.loc[0, "fav_clv_mk"] == pytest.approx(
        1.0
    )
    assert g.loc[1, "outcome_hr"] is None and pd.isna(g.loc[1, "fav_clv_hr"])


def test_per_build_counts_wilson_and_keeps_edge_separate_from_bet():
    fri = KICK - timedelta(days=1)
    df = _frame(
        _rows(2, "fri_pm", fri, [1, 2, 3, 4], tier="BET"),
        _rows(2, "fri_pm", fri, [5, 6], tier="EDGE"),
        _rows(2, "fri_pm", fri, [7], tier="PASS"),
    )
    rows = {(r["slot"], r["tier"]): r for r in W.per_build(df, n_boot=100)}
    bet = rows[("fri_pm", "BET")]
    assert bet["n"] == 4 and bet["graded"] == 4 and (bet["under"], bet["over"]) == (2, 2)
    assert bet["hit"] == pytest.approx(0.5) and bet["hit_lo"] < 0.5 < bet["hit_hi"]
    assert bet["clv_hr"]["n"] == 4 and bet["clv_hr"]["mean"] == pytest.approx(0.5)
    assert rows[("fri_pm", "EDGE")]["n"] == 2
    assert ("fri_pm", "PASS") not in rows
    # every priced item, whatever its tier, so a build with no BET still has a row
    assert rows[("fri_pm", "ALL priced")]["n"] == 7


def test_first_qualified_names_the_earliest_build_and_counts_repeats():
    thu, fri, sat = (KICK - timedelta(days=d) for d in (2, 1, 0.3))
    df = _frame(
        _rows(2, "thu_pm", thu, [1]),
        _rows(2, "fri_pm", fri, [1, 2]),
        _rows(2, "sat_am", sat, [2]),
    )
    fq = W.first_qualified(df).set_index("game_id")
    assert fq.loc[1, "first_slot"] == "thu_pm" and fq.loc[1, "n_builds_bet"] == 2
    assert fq.loc[2, "first_slot"] == "fri_pm" and fq.loc[2, "n_builds_bet"] == 2


def test_matched_pairs_keeps_only_games_both_builds_took_and_the_last_build_per_slot():
    fri1, fri2, sat = (KICK - timedelta(hours=h) for h in (30, 26, 7))
    df = _frame(
        _rows(2, "fri_pm", fri1, [1, 2], clv_shift=-5.0),  # superseded by fri2
        _rows(2, "fri_pm", fri2, [1, 2, 3], clv_shift=0.0),
        _rows(2, "sat_am", sat, [2, 3, 4], clv_shift=0.5),
    )
    m = W.matched_pairs(df, "fri_pm", "sat_am")
    assert sorted(m.game_id) == [2, 3]
    assert np.allclose(m["fav_clv_hr_fri_pm"], 0.5)
    assert np.allclose(m["fav_clv_hr_sat_am"], 1.0)


def test_confirmatory_is_refused_before_the_dated_look():
    df = _frame(_rows(2, "fri_pm", KICK, [1]))
    c = W.confirmatory(df, today=date(2026, 11, 30))
    assert not c["ran"] and c["verdict"] == "NOT YET EVALUABLE" and "2026-12-07" in c["reasons"][0]


def _season(shifts, weeks=range(2, 14), games_per_week=6):
    """Every build takes the same games each week; a slot's line value is shifted."""
    blocks = []
    for wk in weeks:
        kick = KICK + timedelta(days=7 * (wk - 2))
        gids = [wk * 100 + i for i in range(games_per_week)]
        for slot, hours, shift in (
            ("tue_pm", 96, shifts.get("tue_pm", 0.0)),
            ("thu_pm", 48, shifts.get("thu_pm", 0.0)),
            ("fri_pm", 24, shifts.get("fri_pm", 0.0)),
            ("sat_am", 7, shifts.get("sat_am", 0.0)),
        ):
            rows = _rows(wk, slot, kick - timedelta(hours=hours), gids, clv_shift=shift)
            rng = np.random.default_rng(wk * 7 + hours)
            for r in rows:
                r["hr_line"] += float(rng.normal(0, 0.3))
            blocks.append(rows)
    return _frame(*blocks)


def test_confirmatory_names_a_build_that_beats_every_other_after_holm():
    df = _season({"fri_pm": 1.5})
    c = W.confirmatory(df, n_boot=300, today=date(2026, 12, 7))
    assert c["ran"] and c["best"] == "fri_pm" and c["verdict"] == "BEST BUILD: fri_pm"
    assert len(c["pairs"]) == 6 and all(p["n"] >= W.MIN_MATCHED for p in c["pairs"])


def test_confirmatory_prefers_nothing_when_the_builds_are_alike():
    df = _season({})
    c = W.confirmatory(df, n_boot=300, today=date(2026, 12, 7))
    assert c["ran"] and c["best"] is None and c["verdict"] == "NO BUILD PREFERRED"


def test_confirmatory_needs_the_matched_n_on_every_pair():
    df = _season({"fri_pm": 3.0}, weeks=range(2, 4))  # 12 matched games per pair
    c = W.confirmatory(df, n_boot=200, today=date(2026, 12, 7))
    assert c["best"] is None and any("below 20" in r for r in c["reasons"])
    assert all(p["p"] is None for p in c["pairs"])


def test_holm_is_applied_across_the_six_pairs():
    df = _season({"fri_pm": 1.5})
    c = W.confirmatory(df, n_boot=300, today=date(2026, 12, 7))
    for p in c["pairs"]:
        if p["p"] is not None:
            assert p["p_holm"] >= p["p"]


def test_render_markdown_carries_the_verdict_and_the_rule():
    df = _season({})
    r = {
        "season": 2026,
        "n_cards": 4,
        "n_rows": len(df),
        "n_priced": len(df),
        "n_graded": len(df),
        "per_build": W.per_build(df, n_boot=50),
        "first_qualified": W.first_qualified(df).to_dict("records"),
        "confirmatory": W.confirmatory(df, today=date(2026, 1, 1)),
        "generated_at": "now",
    }
    md = W.render_markdown(r)
    assert "## Verdict: **NOT YET EVALUABLE**" in md and "PRE-REGISTERED" in md
    assert "| 2 | tue_pm | four |" in md
