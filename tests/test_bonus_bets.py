"""Bonus (free) bets must never book a loss.

The book funds the stake, so a losing bonus bet costs nothing and a winning one
pays the profit only — the stake is not returned. `units_won` already returns
profit-only, so the win side needs no adjustment; without the floor, though, a
losing $20 bonus would book -2 units against a bankroll that never lost them,
and the bankroll curve is the one number this whole system exists to keep
honest.
"""

import pytest

from beatvegas.picks import graded_pick_fields

LINE = 31.5
PRICE = -125  # 0.8 units profit per unit staked


def fields(actual, stake=2.0, is_bonus=False):
    return graded_pick_fields(
        actual, LINE, PRICE, stake, opening=None, closing=None, is_bonus=is_bonus
    )


def test_a_losing_bonus_bet_books_zero_not_a_loss():
    cash = fields(40.0)
    bonus = fields(40.0, is_bonus=True)
    assert cash["result"] == bonus["result"] == "over"  # the bet still lost
    assert cash["units"] == pytest.approx(-2.0)  # a real $20 ticket loses $20
    assert bonus["units"] == 0.0  # the bonus one cost nothing


def test_a_winning_bonus_bet_pays_the_same_profit_as_cash():
    """The stake is not returned on a bonus bet, and units_won is already
    profit-only, so the win side must be untouched."""
    cash = fields(20.0)
    bonus = fields(20.0, is_bonus=True)
    assert cash["units"] == pytest.approx(1.6)  # 2u x 0.8 = $16 on a $10 unit
    assert bonus["units"] == pytest.approx(1.6)


def test_a_push_is_zero_either_way():
    assert fields(LINE)["units"] == 0.0
    assert fields(LINE, is_bonus=True)["units"] == 0.0


def test_an_unpriced_bonus_bet_still_grades_the_result_without_units():
    out = graded_pick_fields(40.0, LINE, None, 2.0, None, None, is_bonus=True)
    assert out["result"] == "over" and out["units"] is None


def test_the_floor_is_off_by_default():
    """A plain ticket must keep losing money — the flag has to be explicit."""
    assert graded_pick_fields(40.0, LINE, PRICE, 1.0, None, None)["units"] == pytest.approx(-1.0)
