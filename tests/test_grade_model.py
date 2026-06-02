from beatvegas.model.score import MODEL_BET_THRESHOLD, is_model_bet


def test_threshold_boundary():
    assert is_model_bet(MODEL_BET_THRESHOLD) is True
    assert is_model_bet(MODEL_BET_THRESHOLD - 1) is False


def test_high_score_is_bet():
    assert is_model_bet(70) is True


def test_none_and_low():
    assert is_model_bet(None) is False
    assert is_model_bet(40) is False


def test_custom_threshold():
    assert is_model_bet(60, threshold=65) is False
    assert is_model_bet(65, threshold=65) is True
