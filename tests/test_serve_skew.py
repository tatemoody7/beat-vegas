"""B-SERVE: the regressor never sees an input that is NaN at serving and present
in training, and the guard for the class fails a scoring run that would."""

import numpy as np
import pandas as pd

from beatvegas.etl import features as F
from beatvegas.model.bv_line import BV_FEATURE_COLS


def test_the_57_serve_unavailable_columns_are_out_of_the_regressor():
    assert len(F.SERVE_UNAVAILABLE_COLS) == 57
    assert set(F.FH_FACTOR_COLS) <= set(F.SERVE_UNAVAILABLE_COLS)
    assert set(F.MATCHUP_COLS) <= set(F.SERVE_UNAVAILABLE_COLS)
    assert not set(F.SERVE_UNAVAILABLE_COLS) & set(BV_FEATURE_COLS)
    assert not F.MARKET_COLS & set(BV_FEATURE_COLS)
    # they are still FEATURE_COLS (the classifier keeps them until it is retired)
    assert set(F.SERVE_UNAVAILABLE_COLS) <= set(F.FEATURE_COLS)


def _frame():
    rows = []
    for season, week, played in (
        (2025, 5, True),
        (2025, 6, True),
        (2026, 3, True),
        (2026, 4, False),
    ):
        for i in range(10):
            rows.append(
                {
                    "season": season,
                    "week": week,
                    "first_half_total": 30.0 if played else np.nan,
                    "clean": 1.0,
                    "sometimes": np.nan if i == 0 else 2.0,
                    "skewed": np.nan if not played else 3.0,
                }
            )
    return pd.DataFrame(rows)


def test_report_flags_a_column_missing_at_serving_and_present_in_training():
    df = _frame()
    rep = F.serve_skew_report(df, 2026, 4, ["clean", "sometimes", "skewed"])
    assert rep.attrs["n_target"] == 10 and rep.attrs["n_train"] == 20
    assert rep.loc["skewed", "target_nan"] == 1.0 and rep.loc["skewed", "train_nan"] == 0.0
    assert F.serve_skew_violations(rep) == ["skewed"]


def test_a_column_that_is_sometimes_missing_everywhere_is_not_a_violation():
    df = _frame()
    rep = F.serve_skew_report(df, 2026, 4, ["clean", "sometimes"])
    assert F.serve_skew_violations(rep) == []


def test_no_target_rows_means_nothing_to_flag():
    df = _frame()
    rep = F.serve_skew_report(df, 2026, 9, ["skewed"])
    assert F.serve_skew_violations(rep) == []
