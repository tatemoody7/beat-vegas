from datetime import datetime
from types import SimpleNamespace as S

from beatvegas.lines import consensus_open_close


def snap(book, line, day):
    return S(book=book, line=line, captured_at=datetime(2024, 11, day, 12, 0))


def test_consensus_uses_first_and_last_per_book():
    snaps = [
        snap("dk", 24.5, 1), snap("dk", 25.5, 5),     # dk: open 24.5, close 25.5
        snap("fd", 25.0, 1), snap("fd", 26.0, 5),     # fd: open 25.0, close 26.0
        snap("mgm", 24.0, 2), snap("mgm", 25.0, 4),   # mgm: open 24.0, close 25.0
    ]
    opening, closing = consensus_open_close(snaps)
    assert opening == 24.5      # median(24.5, 25.0, 24.0)
    assert closing == 25.5      # median(25.5, 26.0, 25.0)


def test_consensus_empty():
    assert consensus_open_close([]) == (None, None)


def test_consensus_single_book_single_obs():
    assert consensus_open_close([snap("dk", 27.0, 3)]) == (27.0, 27.0)
