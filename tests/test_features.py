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
        f"Unexpected market features in FEATURE_COLS: {present}"
    )


def test_bv_features_are_classifier_features_minus_market_and_serve_unavailable():
    """Market-blind AND free of the inputs that are NaN at serving (B-SERVE)."""
    from beatvegas.etl.features import SERVE_UNAVAILABLE_COLS

    assert set(BV_FEATURE_COLS) == set(FEATURE_COLS) - MARKET_COLS - set(SERVE_UNAVAILABLE_COLS)


def test_feature_cols_unique():
    assert len(FEATURE_COLS) == len(set(FEATURE_COLS))


def test_every_feature_is_registered():
    # The ranking harness must be able to evaluate every model feature, so the
    # registry must cover all of FEATURE_COLS (keeps registry/features in sync).
    from beatvegas.factors.registry import default_registry

    registered = {f.name for f in default_registry()}
    missing = set(FEATURE_COLS) - registered
    assert not missing, f"FEATURE_COLS not in factor registry: {missing}"


def test_registry_has_no_banned_or_forward_only_market():
    # No registered factor may be a banned 1H-line column; market factors must
    # be flagged so the BV engine never trains on them.
    from beatvegas.factors.registry import default_registry

    for f in default_registry():
        assert f.name not in BANNED_LINE_COLS, f"banned col registered: {f.name}"
        if f.name in MARKET_COLS:
            assert f.market, f"{f.name} must be flagged market in the registry"
