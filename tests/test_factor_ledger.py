"""Tests for the factor credibility ledger's statistical core.

Each factor-state's real-line 1H-under record is a Beta-binomial posterior with a
prior centered at the -110 breakeven (0.524, ~20 pseudo-games). A factor is only
"promoted" when it has enough real games AND its one-sided 95% credible lower
bound clears breakeven — the prior's shrinkage is what stops small samples (and
the multiple-comparisons garden of forks) from promoting noise.
"""

from __future__ import annotations

import pandas as pd

from beatvegas.factors.ledger import (
    BREAKEVEN,
    beta_posterior,
    grade_ledger,
    green_mask,
    is_cooling,
    is_promoted,
    ledger_row,
    tier_from_evidence,
)


def test_prior_is_centered_near_breakeven():
    # No evidence => posterior is the prior, sitting essentially at breakeven.
    p = beta_posterior(0, 0)
    assert abs(p["mean"] - 0.525) < 0.005
    assert p["lo"] < BREAKEVEN < p["hi"]  # wide CI straddling breakeven
    assert p["n"] == 0


def test_strong_evidence_shifts_mean_up_and_lower_bound_clears():
    p = beta_posterior(30, 40)  # 75% over 40 real games
    assert p["mean"] > 0.6
    assert p["lo"] > BREAKEVEN  # even the 2.5th pct is above breakeven
    assert p["p_beat"] > 0.95  # P(true rate > breakeven)


def test_small_sample_never_promotes():
    # A perfect 5/5 record is still too little to promote (n floor).
    assert is_promoted(5, 5) is False
    assert is_promoted(13, 24) is False  # just under the n floor


def test_clear_winner_promotes_at_floor():
    assert is_promoted(20, 25) is True  # 80% over 25 games clears comfortably


def test_breakeven_rate_does_not_promote_even_with_volume():
    # ~52% over 50 games is breakeven noise, not an edge.
    assert is_promoted(26, 50) is False


def test_cooling_flag_fires_when_recent_dips_below_breakeven():
    # All-time looks like an edge, but the recent window has gone cold.
    assert is_cooling(recent_hits=3, recent_n=10, alltime_mean=0.58) is True
    assert is_cooling(recent_hits=7, recent_n=10, alltime_mean=0.58) is False  # recent still hot
    assert is_cooling(recent_hits=3, recent_n=5, alltime_mean=0.58) is False  # too few recent


# --- green-state bucketing + single-axis tiering -----------------------------


def test_green_mask_continuous_top_third():
    vals = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9.0])
    mask = green_mask(vals, direction=1, binary=False)  # high = under-favorable
    assert mask.iloc[-1]  # 9 is green
    assert not mask.iloc[0]  # 1 is not
    assert mask.sum() == 3  # top third of 9


def test_green_mask_direction_negative_flips():
    vals = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9.0])
    mask = green_mask(vals, direction=-1, binary=False)  # low = under-favorable
    assert mask.iloc[0]
    assert not mask.iloc[-1]


def test_green_mask_binary_is_active_state():
    vals = pd.Series([0, 1, 0, 1.0])
    mask = green_mask(vals, direction=-1, binary=True)
    assert list(mask) == [False, True, False, True]


def test_green_mask_direction_zero_has_no_green():
    # Hypotheses (no pre-registered direction) can't be graded — never green.
    vals = pd.Series([1, 2, 3.0])
    assert green_mask(vals, direction=0, binary=False).sum() == 0


def test_tier_promotes_proven_factor_to_one():
    assert tier_from_evidence(base_tier=3, hits=20, n=25) == 1


def test_tier_keeps_base_when_not_promoted():
    assert tier_from_evidence(base_tier=3, hits=5, n=10) == 3
    assert tier_from_evidence(base_tier=1, hits=0, n=0) == 1  # base belief unchanged


def test_ledger_row_assembles_posterior_tier_and_cooling():
    row = ledger_row("wx_wind", base_tier=1, hits=26, n=40, recent_hits=3, recent_n=12)
    assert row["factor"] == "wx_wind"
    assert row["n"] == 40 and row["hits"] == 26
    assert row["tier"] == 1  # promoted
    assert 0 < row["post_lo"] < row["post_mean"] < row["post_hi"] < 1
    assert row["recent_n"] == 12
    assert row["drift_flag"] is True  # all-time edge but recent 3/12 has cooled


def test_grade_ledger_counts_green_state_unders():
    # wx_wind (direction +1): green = highest-wind third (ids 6,7,8); all went under.
    df = pd.DataFrame(
        {
            "id": list(range(9)),
            "order": list(range(9)),
            "wx_wind": [0, 1, 2, 3, 4, 5, 6, 7, 8.0],
        }
    )
    outcomes = {i: (1 if i >= 6 else 0) for i in range(9)}
    rows = grade_ledger(df, outcomes)
    wind = next(r for r in rows if r["factor"] == "wx_wind")
    assert wind["n"] == 3
    assert wind["hits"] == 3


def test_grade_ledger_skips_factors_absent_from_frame():
    df = pd.DataFrame({"id": [0, 1], "order": [0, 1], "wx_wind": [1.0, 9.0]})
    outcomes = {0: 0, 1: 1}
    rows = grade_ledger(df, outcomes)
    assert all(r["factor"] != "combined_sec_play" for r in rows)  # not in frame
