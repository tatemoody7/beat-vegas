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


# --- the cap side, which had no test at all ---------------------------------
#
# The "bonus bets do not spend a cap slot" rule lives in THREE places that must
# agree: build_card.real_bets_this_week (the card), the web POST cap query, and
# picks.countsAgainstCap (the display). Only the grading floor above was tested.
# A bonus bet quietly consuming a slot means a real bet Tate wanted gets
# blocked, which is a silent loss of an opportunity rather than a visible error.


def _pick(session, gid, **kw):
    """A pick plus the game row its foreign key needs."""
    from beatvegas.db.models import Game, ManualPick

    if session.get(Game, gid) is None:
        session.add(Game(id=gid, season=2026, week=2, home_team="H", away_team="A"))
        session.flush()
    defaults = dict(
        game_id=gid,
        season=2026,
        week=2,
        side="under",
        market="1H",
        line=27.5,
        price=-110,
        stake=1.0,
        is_paper=False,
        graded=False,
    )
    defaults.update(kw)
    session.add(ManualPick(**defaults))


def test_a_bonus_bet_does_not_consume_a_weekly_cap_slot(db):
    from conftest import _load_script

    build_card = _load_script("build_card")
    store = db
    with store.session_scope() as s:
        _pick(s, 101)  # a real bankroll bet -> holds a slot
        _pick(s, 102, is_bonus=True)  # a bonus bet         -> must not
        _pick(s, 103, is_paper=True)  # paper               -> must not
        _pick(s, 104, market="full")  # full game           -> must not
    with store.session_scope() as s:
        held = build_card.real_bets_this_week(s, 2026, 2)
    assert held == {101}


def test_a_legacy_null_is_bonus_row_still_holds_its_slot(db):
    """Rows predating the is_bonus column carry NULL, and NULL is not false in
    SQL. If the filter missed them, every pre-migration real bet would stop
    counting against the cap and the sixth bet of a week would go through."""
    from conftest import _load_script

    build_card = _load_script("build_card")
    store = db
    with store.session_scope() as s:
        _pick(s, 201, is_bonus=None)
        _pick(s, 202, is_paper=None)
    with store.session_scope() as s:
        assert build_card.real_bets_this_week(s, 2026, 2) == {201, 202}
