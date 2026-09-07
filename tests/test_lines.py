from datetime import datetime
from types import SimpleNamespace as S

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
