"""The 'no Vegas line' rule — enforced, not just intended.

The BV line is only meaningful if it's independent of Vegas. These tests fail
loudly if a betting line ever becomes a model input.
"""
from beatvegas.etl.features import BANNED_LINE_COLS, FEATURE_COLS, MARKET_COLS
from beatvegas.model.bv_line import BV_FEATURE_COLS


def test_no_1h_line_in_any_model():
    # The 1H betting line must NEVER be a feature in any model — it's used only
    # post-prediction for the gap/grading.
    leaked = set(FEATURE_COLS) & BANNED_LINE_COLS
    assert not leaked, f"1H-line-derived columns in FEATURE_COLS: {leaked}"


def test_bv_line_is_market_blind():
    # The BV regressor must see no Vegas-derived input at all.
    leaked = (set(BV_FEATURE_COLS) & MARKET_COLS) | (set(BV_FEATURE_COLS) & BANNED_LINE_COLS)
    assert not leaked, f"BV line is not market-blind; leaked: {leaked}"


def test_market_features_are_exactly_known_set():
    # Provenance lock: if someone adds a new market-derived feature, they must
    # consciously add it to MARKET_COLS (or this test trips).
    present = MARKET_COLS & set(FEATURE_COLS)
    assert present == {"full_game_total", "proj_1h_ratio"}, (
        f"Unexpected market features in FEATURE_COLS: {present}")


def test_bv_features_are_classifier_features_minus_market():
    assert set(BV_FEATURE_COLS) == set(FEATURE_COLS) - MARKET_COLS
