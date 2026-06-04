from datetime import datetime
from types import SimpleNamespace as S

from beatvegas.lines import closing_before_kickoff, consensus_open_close


def snap(book, line, day):
    return S(book=book, line=line, captured_at=datetime(2024, 11, day, 12, 0))


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
