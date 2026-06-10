from beatvegas.grading import (
    american_to_decimal,
    clv_under,
    price_clv_under,
    under_result,
    units_won,
)


def test_american_to_decimal():
    assert round(american_to_decimal(-110), 4) == 1.9091
    assert american_to_decimal(100) == 2.0
    assert american_to_decimal(150) == 2.5


def test_under_result():
    assert under_result(20, 24.5) == "under"
    assert under_result(28, 24.5) == "over"
    assert under_result(24, 24) == "push"


def test_units_won():
    assert round(units_won(20, 24.5), 4) == 0.9091  # under wins at -110
    assert units_won(28, 24.5) == -1.0  # under loses
    assert units_won(24, 24.0) == 0.0  # push
    assert round(units_won(20, 24.5, under_price=-105), 4) == 0.9524


def test_clv_under():
    # Bet under 23.5, line closed at 25 -> you got a softer (higher) number.
    assert clv_under(23.5, 25.0) == 1.5
    # Line dropped after you bet -> negative CLV for an under.
    assert clv_under(25.0, 23.5) == -1.5
    assert clv_under(None, 24.0) is None


def test_price_clv_under():
    # Under's fair price rose open->close: positive (you locked the cheaper side).
    assert round(price_clv_under(0.48, 0.50), 4) == 0.02
    # Fell: negative.
    assert round(price_clv_under(0.51, 0.49), 4) == -0.02
    assert price_clv_under(None, 0.5) is None
    assert price_clv_under(0.5, None) is None
