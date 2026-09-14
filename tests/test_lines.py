from datetime import datetime
from types import SimpleNamespace as S

import pytest

from beatvegas.lines import (
    closing_before_kickoff,
    consensus_fair_under_open_close,
    consensus_open_close,
    fair_under_before_kickoff,
)


def snap(book, line, day, over=-110, under=-110):
    return S(
        book=book,
        line=line,
        captured_at=datetime(2024, 11, day, 12, 0),
        over_price=over,
        under_price=under,
    )


def test_consensus_uses_first_and_last_per_book():
    snaps = [
        snap("dk", 24.5, 1),
        snap("dk", 25.5, 5),  # dk: open 24.5, close 25.5
        snap("fd", 25.0, 1),
        snap("fd", 26.0, 5),  # fd: open 25.0, close 26.0
        snap("mgm", 24.0, 2),
        snap("mgm", 25.0, 4),  # mgm: open 24.0, close 25.0
    ]
    opening, closing = consensus_open_close(snaps)
    assert opening == 24.5  # median(24.5, 25.0, 24.0)
    assert closing == 25.5  # median(25.5, 26.0, 25.0)


def test_consensus_empty():
    assert consensus_open_close([]) == (None, None)


def test_consensus_single_book_single_obs():
    assert consensus_open_close([snap("dk", 27.0, 3)]) == (27.0, 27.0)


def test_closing_ignores_post_kickoff_snapshots():
    kickoff = datetime(2024, 11, 5, 12, 0)
    snaps = [
        snap("dk", 24.5, 1),  # open, pre-kickoff
        snap("dk", 25.5, 5),  # last pre-kickoff (== kickoff)
        snap("dk", 30.0, 6),  # POST-kickoff: must be ignored
    ]
    opening, closing, closing_at = closing_before_kickoff(snaps, kickoff)
    assert opening == 24.5
    assert closing == 25.5  # not 30.0
    assert closing_at == datetime(2024, 11, 5, 12, 0)


def test_closing_falls_back_when_all_post_kickoff():
    kickoff = datetime(2024, 11, 1, 0, 0)
    snaps = [snap("dk", 26.0, 5)]  # only post-kickoff data we have
    opening, closing, _ = closing_before_kickoff(snaps, kickoff)
    assert opening == 26.0 and closing == 26.0


def test_closing_handles_no_kickoff():
    opening, closing, closing_at = closing_before_kickoff([snap("dk", 27.0, 3)], None)
    assert (opening, closing) == (27.0, 27.0)
    assert closing_at == datetime(2024, 11, 3, 12, 0)


def test_fair_under_open_close_flat_prices_is_half():
    # All -110/-110: fair under is ~0.5 at open and close regardless of line.
    snaps = [snap("dk", 24.5, 1), snap("dk", 26.0, 5)]
    fo, fc = consensus_fair_under_open_close(snaps)
    assert fo == fc  # no juice movement
    assert abs(fo - 0.5) < 1e-6


def test_fair_under_open_close_tracks_price_movement():
    # dk opens with the under FAVORED (under -120, over +100 -> fair-under > 0.5)
    # and closes balanced; fair-under should fall from open to close.
    snaps = [
        snap("dk", 25.0, 1, over=100, under=-120),
        snap("dk", 25.0, 5, over=-110, under=-110),
    ]
    fo, fc = consensus_fair_under_open_close(snaps)
    assert fo > fc
    assert fo > 0.5
    assert abs(fc - 0.5) < 1e-6


def test_fair_under_skips_snaps_missing_prices():
    snaps = [snap("dk", 25.0, 1, over=None, under=None)]
    assert consensus_fair_under_open_close(snaps) == (None, None)


def test_fair_under_before_kickoff_ignores_post_kickoff():
    kickoff = datetime(2024, 11, 5, 12, 0)
    snaps = [
        snap("dk", 25.0, 1, over=100, under=-120),  # open, under favored
        snap("dk", 25.0, 5, over=-110, under=-110),  # close, == kickoff
        snap("dk", 25.0, 6, over=-120, under=100),  # POST-kickoff: ignored
    ]
    fo, fc = fair_under_before_kickoff(snaps, kickoff)
    assert fo > fc
    assert abs(fc - 0.5) < 1e-6  # the balanced close, not the post-kickoff snap


def test_closing_at_uses_last_seen_when_the_line_was_confirmed_later():
    """A pre-kick poll that finds the number unchanged writes no row; it stamps
    last_seen_at on the existing one. The close timestamp must reflect that."""
    kickoff = datetime(2024, 11, 5, 12, 0)
    s = snap("dk", 24.5, 1)
    s.last_seen_at = datetime(2024, 11, 5, 11, 30)  # confirmed 30 min before kick
    opening, closing, closing_at = closing_before_kickoff([s], kickoff)
    assert (opening, closing) == (24.5, 24.5)
    assert closing_at == datetime(2024, 11, 5, 11, 30)


def test_closing_at_ignores_a_post_kickoff_last_seen():
    kickoff = datetime(2024, 11, 5, 12, 0)
    s = snap("dk", 24.5, 1)
    s.last_seen_at = datetime(2024, 11, 5, 13, 0)  # stray in-game poll
    _, _, closing_at = closing_before_kickoff([s], kickoff)
    assert closing_at == datetime(2024, 11, 1, 12, 0)


def test_book_closing_uses_one_books_pre_kick_snapshots_only():
    from beatvegas.lines import book_closing_before_kickoff

    kickoff = datetime(2024, 11, 5, 12, 0)
    snaps = [
        snap("dk", 24.5, 1),
        snap("hardrockbet", 25.5, 2),
        snap("hardrockbet", 23.5, 4),
        snap("hardrockbet", 30.0, 6),
    ]  # last one is post-kick
    opening, closing, closing_at = book_closing_before_kickoff(snaps, kickoff, "hardrockbet")
    assert (opening, closing) == (25.5, 23.5)
    assert closing_at == datetime(2024, 11, 4, 12, 0)
    assert book_closing_before_kickoff(snaps, kickoff, "fanduel") == (None, None, None)


def test_book_closing_price_is_the_books_latest_pre_kick_under_price():
    from beatvegas.lines import book_closing_price_before_kickoff

    kickoff = datetime(2024, 11, 5, 12, 0)
    snaps = [
        snap("dk", 24.5, 1, under=-115),
        snap("hardrockbet", 25.5, 2, under=-112),
        snap("hardrockbet", 23.5, 4, under=-108),
        snap("hardrockbet", 30.0, 6, under=-130),  # in-game: ignored
    ]
    assert book_closing_price_before_kickoff(snaps, kickoff, "hardrockbet") == -108
    assert book_closing_price_before_kickoff(snaps, kickoff, "fanduel") is None


def test_book_closing_price_skips_unpriced_rows_and_is_none_when_all_unpriced():
    from beatvegas.lines import book_closing_price_before_kickoff

    kickoff = datetime(2024, 11, 5, 12, 0)
    snaps = [
        snap("hardrockbet", 24.5, 2, under=-105),
        snap("hardrockbet", 24.0, 4, under=None),  # newest pre-kick row carries no price
    ]
    assert book_closing_price_before_kickoff(snaps, kickoff, "hardrockbet") == -105
    assert book_closing_price_before_kickoff([snaps[1]], kickoff, "hardrockbet") is None
    assert book_closing_price_before_kickoff([], kickoff, "hardrockbet") is None


# --- Off-centre rungs: strict for one book, lenient for a consensus -----------
#
# The Hard Rock close-poll window is the whole reason centred_snaps exists, and
# it was exactly where the lenient `ok or list(snaps)` fallback defeated it: HR
# serves an off-centre ladder rung on 26 of 28 quotes inside 3 h of kickoff, so
# "nothing centred" is the NORMAL case for a single-book close, not an edge one.


def test_centred_snaps_strict_returns_empty_when_nothing_is_centred():
    from beatvegas.lines import centred_snaps

    rungs = [
        snap("hardrockbet", 22.5, 2, over=-275, under=220),
        snap("hardrockbet", 22.5, 4, over=-260, under=210),
    ]
    assert centred_snaps(rungs) == rungs  # lenient: a consensus still gets a number
    assert centred_snaps(rungs, strict=True) == []


def test_book_closing_refuses_a_rung_rather_than_returning_it():
    """The real Oregon State / Texas Tech shape: every HR quote inside the close
    window is a rung at 22.5 priced -275/+220, while the centred close was 28.5.
    Before the strict flag this returned 22.5 and every caller believed it."""
    from beatvegas.lines import book_closing_before_kickoff

    kickoff = datetime(2024, 11, 5, 12, 0)
    rungs = [
        snap("hardrockbet", 22.5, 2, over=-275, under=220),
        snap("hardrockbet", 22.5, 4, over=-260, under=210),
    ]
    assert book_closing_before_kickoff(rungs, kickoff, "hardrockbet") == (None, None, None)


def test_book_closing_still_finds_the_last_centred_quote():
    """Strict drops the rungs, not the book: a book that went off-centre late
    still closes at its last real number."""
    from beatvegas.lines import book_closing_before_kickoff

    kickoff = datetime(2024, 11, 5, 12, 0)
    snaps = [
        snap("hardrockbet", 28.5, 1, under=-115),
        snap("hardrockbet", 28.0, 2, under=-110),
        snap("hardrockbet", 22.5, 4, over=-275, under=220),  # rung, dropped
    ]
    opening, closing, _at = book_closing_before_kickoff(snaps, kickoff, "hardrockbet")
    assert (opening, closing) == (28.5, 28.0)


def test_book_closing_price_refuses_a_rungs_lopsided_price():
    """A rung's price is the one number that was never on offer at the main
    total, and this helper's whole job is to record what the bettor was charged."""
    from beatvegas.lines import book_closing_price_before_kickoff

    kickoff = datetime(2024, 11, 5, 12, 0)
    rung_only = [snap("hardrockbet", 22.5, 4, over=-275, under=220)]
    assert book_closing_price_before_kickoff(rung_only, kickoff, "hardrockbet") is None

    mixed = [
        snap("hardrockbet", 28.0, 2, under=-110),
        snap("hardrockbet", 22.5, 4, over=-275, under=220),
    ]
    assert book_closing_price_before_kickoff(mixed, kickoff, "hardrockbet") == -110


# --- as-of reads: what could have been seen at a decision time ---------------
#
# The leak this guards against is the one that makes a backtest look excellent:
# Game.spread and Game.full_game_total are MUTABLE single columns holding the
# last capture that touched them, so reading either while claiming to price a
# game on Tuesday puts Saturday's number in a Tuesday feature. Measured on 2026,
# a game's spread moves a median 1.5 pts over its snapshot history.


def snap_at(book, line, day, hour=12, spread=None, over=-110, under=-110):
    return S(
        book=book,
        line=line,
        spread=spread,
        captured_at=datetime(2024, 11, day, hour, 0),
        over_price=over,
        under_price=under,
    )


def test_as_of_is_strict_and_never_falls_back():
    """pre_kickoff returns everything when nothing qualifies, so a consensus
    caller still gets a number. Here that would hand back quotes from AFTER the
    decision time -- the exact leak. Empty must mean empty."""
    from beatvegas.lines import as_of, pre_kickoff

    snaps = [snap_at("dk", 24.5, 4), snap_at("fd", 25.0, 5)]
    t = datetime(2024, 11, 1, 12, 0)  # before every snapshot
    assert as_of(snaps, t) == []
    assert pre_kickoff(snaps, t) == snaps  # the contrast, pinned on purpose


def test_as_of_admits_the_boundary_and_excludes_the_future():
    from beatvegas.lines import as_of

    snaps = [snap_at("dk", 24.5, 4), snap_at("dk", 23.5, 5), snap_at("dk", 30.0, 6)]
    got = as_of(snaps, datetime(2024, 11, 5, 12, 0))
    assert [s.line for s in got] == [24.5, 23.5]  # inclusive at t, nothing after


def test_as_of_excludes_an_unstamped_snapshot():
    """A row with no captured_at cannot be PROVEN to precede t, and an
    unprovable timestamp is not evidence."""
    from beatvegas.lines import as_of

    unstamped = S(
        book="dk", line=24.5, spread=None, captured_at=None, over_price=-110, under_price=-110
    )
    assert as_of([unstamped], datetime(2024, 11, 5, 12, 0)) == []


def test_as_of_refuses_a_null_decision_time():
    """None would silently admit every snapshot -- a leak that looks like a
    successful call."""
    from beatvegas.lines import as_of

    with pytest.raises(ValueError):
        as_of([snap_at("dk", 24.5, 4)], None)


def test_consensus_as_of_takes_each_books_latest_quote_at_that_moment():
    from beatvegas.lines import consensus_as_of

    snaps = [
        snap_at("dk", 24.5, 1),
        snap_at("dk", 26.5, 4),  # dk moved up
        snap_at("fd", 25.0, 1),
        snap_at("fd", 27.0, 6),  # fd's move is AFTER t
        snap_at("mgm", 26.0, 2),
    ]
    line, _ = consensus_as_of(snaps, datetime(2024, 11, 5, 12, 0))
    assert line == 26.0  # median(26.5, 25.0, 26.0) — fd still on its opener

    later, _ = consensus_as_of(snaps, datetime(2024, 11, 7, 12, 0))
    assert later == 26.5  # median(26.5, 27.0, 26.0)


def test_consensus_as_of_drops_off_centre_rungs():
    from beatvegas.lines import consensus_as_of

    snaps = [
        snap_at("dk", 26.5, 4),
        snap_at("fd", 26.0, 4),
        snap_at("hardrockbet", 20.5, 4, over=-275, under=220),  # a rung
    ]
    line, _ = consensus_as_of(snaps, datetime(2024, 11, 5, 12, 0))
    assert line == 26.25  # median of the two real numbers, not 26.0


def test_consensus_as_of_spread_is_none_when_no_book_carries_one():
    """odds_snapshots.spread is NULL for every row before 2026, so a historical
    as-of read has no spread at all -- which is exactly why Game.spread_open
    exists. Returning 0.0 or silently borrowing Game.spread would be the bug."""
    from beatvegas.lines import consensus_as_of

    line, spread = consensus_as_of([snap_at("dk", 26.5, 4)], datetime(2024, 11, 5, 12, 0))
    assert line == 26.5 and spread is None

    priced = [snap_at("dk", 26.5, 4, spread=-7.0), snap_at("fd", 26.0, 4, spread=-7.5)]
    _, spread = consensus_as_of(priced, datetime(2024, 11, 5, 12, 0))
    assert spread == -7.25


def test_decision_times_bracket_the_production_build_slots():
    from beatvegas.lines import DECISION_OFFSETS_H, decision_times

    kick = datetime(2024, 11, 9, 19, 0)  # Saturday 7pm
    ts = decision_times(kick)
    assert set(ts) == set(DECISION_OFFSETS_H)
    assert ts["t_minus_72"] == datetime(2024, 11, 6, 19, 0)  # Wednesday
    assert ts["t_minus_3"] == datetime(2024, 11, 9, 16, 0)
    assert all(t < kick for t in ts.values())


def test_opening_as_of_is_the_earliest_centred_quote():
    from beatvegas.lines import opening_as_of

    snaps = [
        snap_at("hardrockbet", 20.5, 1, over=-275, under=220),  # a rung, earliest
        snap_at("dk", 24.5, 2),
        snap_at("fd", 27.0, 6),
    ]
    line, _spread, at = opening_as_of(snaps)
    assert at == datetime(2024, 11, 2, 12, 0), "the rung must not set the opening time"
    assert line == 24.5
    assert opening_as_of([]) == (None, None, None)


def test_an_as_of_read_never_sees_a_snapshot_from_after_the_decision_time():
    """The leak test itself, as a property over the whole grid. If this ever
    fails, every backtest number downstream is fiction."""
    from beatvegas.lines import as_of, decision_times

    kick = datetime(2024, 11, 9, 19, 0)
    snaps = [snap_at("dk", 20.0 + d, d, hour=h) for d in range(1, 10) for h in (3, 15)]
    for label, t in decision_times(kick).items():
        for sn in as_of(snaps, t):
            assert sn.captured_at <= t, label
