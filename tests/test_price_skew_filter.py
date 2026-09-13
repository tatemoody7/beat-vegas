"""An off-centre rung is not a line (2026-09-13).

A book's MAIN total prices both sides near -110. A feed sometimes serves a rung
of the alternate ladder instead: the line moves several points and the price goes
lopsided to compensate. Measured live on 2026-09-12, Tulsa @ Sam Houston, 29 min
before kickoff -- eight books at 26.5 around -120/-110, Hard Rock at 20.5
(-275/+220) and BetMGM at 21.5 (-250/+185), every one of them a single point with
two outcomes and a fresh last_update. The feed is faithful; those two books
genuinely publish a rung as their main number.

The PRICE is the tell, and it needs no reference -- one quote can be judged on
its own. Threshold from 1,504 pre-kickoff week-2 quotes: no centred quote was
worse than -150, rungs ran to -375 with a -250 median.
"""

import statistics
from types import SimpleNamespace as NS

from beatvegas.devig import SKEW_REJECT_PRICE, is_centred_quote
from beatvegas.lines import centred_snaps, consensus_open_close


def test_a_normal_quote_is_centred():
    assert is_centred_quote(-110, -110)
    assert is_centred_quote(-130, +105)
    assert is_centred_quote(-150, +125)  # the worst centred quote actually observed


def test_the_real_rungs_are_rejected():
    assert not is_centred_quote(-275, 220)  # Hard Rock, Tulsa @ Sam Houston
    assert not is_centred_quote(-250, 185)  # BetMGM, same game, same minute
    assert not is_centred_quote(-375, 260)  # BetMGM, ODU @ Virginia Tech


def test_the_threshold_sits_between_them():
    assert is_centred_quote(SKEW_REJECT_PRICE, 130)
    assert not is_centred_quote(SKEW_REJECT_PRICE - 1, 130)


def test_a_quote_it_cannot_judge_is_kept():
    # Rejecting a positively-identified pathology, never data we cannot assess.
    assert is_centred_quote(None, None)
    assert is_centred_quote(-110, None)


def _snap(book, line, over, under, cap):
    return NS(
        book=book, line=line, over_price=over, under_price=under, captured_at=cap, last_seen_at=None
    )


def test_a_late_rung_does_not_become_the_closing_line():
    # The real shape of Tulsa @ Sam Houston: everyone at 26.5 all week, then Hard
    # Rock alone drops to 20.5 at -275/+220 half an hour before kickoff. The
    # close must stay 26.5 -- the market did not move.
    snaps = [
        _snap("draftkings", 26.5, -125, 105, 1),
        _snap("fanduel", 26.5, -122, 100, 1),
        _snap("hardrockbet", 26.5, -120, -105, 1),
        _snap("draftkings", 26.5, -125, 105, 9),
        _snap("fanduel", 26.5, -122, 100, 9),
        _snap("hardrockbet", 20.5, -275, 220, 9),
    ]
    assert consensus_open_close(snaps) == (26.5, 26.5)


def test_a_book_still_contributes_its_last_centred_quote():
    # Dropping the rung, not the book: Hard Rock's 26.5 still counts toward the
    # median, so filtering does not quietly thin the consensus.
    snaps = [
        _snap("hardrockbet", 27.5, -110, -110, 1),
        _snap("hardrockbet", 26.5, -115, -105, 5),
        _snap("hardrockbet", 20.5, -275, 220, 9),
    ]
    assert consensus_open_close(snaps) == (27.5, 26.5)


def test_a_real_line_move_is_not_filtered():
    # A book genuinely 2 points off the field at normal juice is an OPINION, and
    # must survive: 31 of the 203 off-centre week-2 quotes looked like this.
    snaps = [
        _snap("draftkings", 28.5, -110, -110, 1),
        _snap("fanduel", 28.5, -110, -110, 1),
        _snap("bovada", 26.5, -115, -105, 1),
    ]
    assert consensus_open_close(snaps) == (28.5, 28.5)
    assert len(centred_snaps(snaps)) == 3


def test_all_rungs_falls_back_rather_than_returning_nothing():
    snaps = [_snap("betmgm", 21.5, -250, 185, 1), _snap("hardrockbet", 20.5, -275, 220, 1)]
    assert len(centred_snaps(snaps)) == 2
    assert consensus_open_close(snaps) == (statistics.median([21.5, 20.5]),) * 2
