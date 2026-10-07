"""The half-point table builder (beatvegas/halfpoint.py, docs/CONSENSUS.md)."""

from __future__ import annotations

import pytest

from beatvegas import halfpoint as H


def test_the_first_half_expectation_uses_the_step_share():
    assert H.expected_first_half(50.0, -7.0, 0.4975, 0.5375, 21.0) == pytest.approx(24.875)
    assert H.expected_first_half(50.0, -21.0, 0.4975, 0.5375, 21.0) == pytest.approx(26.875)
    assert H.expected_first_half(50.0, None, 0.4975, 0.5375, 21.0) == pytest.approx(24.875)
    assert H.expected_first_half(None, -3.0, 0.4975, 0.5375, 21.0) is None


def test_half_grid():
    assert H.half_grid(26.2, 27.6) == [26.0, 26.5, 27.0, 27.5, 28.0]


def test_market_table_mass_and_minimum_n():
    pairs = [(27.0, 27.0)] * 200 + [(27.0, 24.0)] * 100 + [(40.0, 40.0)] * 10
    t = H.market_table(pairs, window=1.0, span=4, min_n=300)
    assert "27.0" in t and "40.0" not in t  # 10 games is under the minimum
    assert t["27.0"]["n"] == 300
    assert t["27.0"]["mass"]["27"] == pytest.approx(2 / 3)
    assert t["27.0"]["mass"]["24"] == pytest.approx(1 / 3)
    assert set(t["27.0"]["mass"]) == {str(k) for k in range(23, 32)}
    assert H.push_rates(t)["27.0"] == pytest.approx(2 / 3)


def test_pairs_skip_missing_values_including_nan():
    nan = float("nan")
    fh, fg = H.pairs_from_rows(
        [
            {"full_game_total": 50.0, "spread": -3.0, "fh_trusted": nan, "final_total": 48.0},
            {"full_game_total": nan},
            {"full_game_total": 60.0, "spread": nan, "fh_trusted": 31.0, "final_total": nan},
        ],
        0.4975,
        0.5375,
        21.0,
    )
    assert fg == [(50.0, 48.0)]
    assert fh == [(pytest.approx(29.85), 31.0)]
