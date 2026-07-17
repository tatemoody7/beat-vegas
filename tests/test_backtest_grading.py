"""Grading the backtest on real-where-present vs proxy lines + coverage split."""

import pandas as pd

from beatvegas.backtest.engine import grade_predictions


def _frame():
    # 4 games, one season. proxy_line = 0.52*full rounded to .5 (here just given).
    # first_half_total chosen so the real vs proxy line flips some outcomes.
    return pd.DataFrame(
        [
            # id, season, proxy_line, first_half_total, under_prob
            {
                "id": 1,
                "season": 2024,
                "proxy_line": 24.5,
                "first_half_total": 20,
                "under_prob": 0.9,
            },
            {
                "id": 2,
                "season": 2024,
                "proxy_line": 24.5,
                "first_half_total": 28,
                "under_prob": 0.8,
            },
            {
                "id": 3,
                "season": 2024,
                "proxy_line": 24.5,
                "first_half_total": 23,
                "under_prob": 0.7,
            },
            {
                "id": 4,
                "season": 2024,
                "proxy_line": 24.5,
                "first_half_total": 27,
                "under_prob": 0.6,
            },
        ]
    )


def test_all_proxy_when_no_real_lines():
    pg = _frame()
    _by, summary = grade_predictions(pg, top_frac=0.5, real_lines=None)
    assert summary["real_graded"] == 0
    assert summary["proxy_graded"] == 4
    assert summary["pct_real"] == 0.0
    assert (pg["line"] == pg["proxy_line"]).all()
    assert (pg["line_kind"] == "proxy").all()
    # under vs 24.5: g1(20)<24.5 win, g2(28) loss, g3(23) win, g4(27) loss = 2/4.
    assert summary["baseline_under_pct"] == 50.0


def test_real_line_overrides_and_flips_outcome():
    pg = _frame()
    # Real closing line for g4 is 30 (much higher) -> its under (27<30) now WINS.
    _by, summary = grade_predictions(pg, top_frac=0.5, real_lines={4: 30.0})
    assert summary["real_graded"] == 1
    assert summary["proxy_graded"] == 3
    assert summary["pct_real"] == 25.0
    g4 = pg[pg["id"] == 4].iloc[0]
    assert g4["line"] == 30.0 and g4["line_kind"] == "real"
    assert g4["under_graded"] == 1  # 27 < 30
    # now 3/4 unders win (g1,g3,g4)
    assert summary["baseline_under_pct"] == 75.0


def test_push_excluded_from_grading():
    pg = _frame()
    # Real line for g3 == its first_half_total (23) -> a push, dropped from counts.
    _by, summary = grade_predictions(pg, top_frac=0.5, real_lines={3: 23.0})
    assert summary["n_games"] == 4  # all games still counted in coverage
    assert summary["real_graded"] == 1
    # graded population excludes the push: g1 win, g2 loss, g4 loss = 1/3.
    assert summary["baseline_under_pct"] == round(100 / 3, 2)
