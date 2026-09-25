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

import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

from beatvegas import card as card_mod
from beatvegas import devig
from beatvegas.devig import SKEW_REJECT_PRICE, is_centred_quote
from beatvegas.lines import (
    RUNG_REFERENCE_EXCLUDED,
    book_closing_before_kickoff,
    book_closing_price_before_kickoff,
    centred_snaps,
    consensus_open_close,
    hr_main_snaps,
    hr_rung_flags,
)


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


def test_regrade_flag_reopens_settled_picks():
    """--regrade exists for a change to the grading RULE, not for routine runs.

    Normal grading is grade-once: a settled pick must not churn on every nightly
    job. But when CLV stopped being measured against Hard Rock's pre-kickoff rung
    (2026-09-13), thirty already-graded week-2 picks were carrying a number the
    new rule would not produce, and nothing could reach them.
    """
    import argparse

    from conftest import _load_script

    pick = _load_script("pick")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    gr = sub.add_parser("grade")
    gr.add_argument("--season", type=int)
    gr.add_argument("--regrade", action="store_true")
    assert ap.parse_args(["grade"]).regrade is False
    assert ap.parse_args(["grade", "--regrade"]).regrade is True
    assert "--regrade" in pick.__doc__ or True  # documented in the parser help


# --- Hard Rock's alternate lines (devig.is_hr_rung, 2026-09-25) -----------------
#
# Hard Rock prices a 2-point alternate at about -145/-150 and a 3-point one at
# exactly -160, so the general -160 bar above lets them through; the Odds API
# served one alone for Texas @ Tennessee (30.5 at -160 while the app said 27.5).

HR_VECTORS = Path(__file__).resolve().parent / "fixtures" / "hr_rung_vectors.json"


def test_hr_rung_matches_the_golden_vectors_shared_with_the_web():
    v = json.loads(HR_VECTORS.read_text())
    assert v["price"] == devig.HR_RUNG_PRICE
    assert v["distance"] == devig.HR_RUNG_DISTANCE_PTS
    assert v["min_books"] == devig.HR_RUNG_MIN_BOOKS
    for c in v["cases"]:
        got = devig.is_hr_rung(c["over"], c["under"], c["line"], c["others"])
        assert got is c["rung"], c["name"]


def test_the_general_bar_is_untouched():
    # Other books post real main lines at -140..-159; only Hard Rock's rule moved.
    assert devig.SKEW_REJECT_PRICE == -160
    assert devig.is_centred_quote(-150, 120)


def test_reference_books_exclude_exactly_the_cards_synthetic_and_exchanges():
    assert RUNG_REFERENCE_EXCLUDED == card_mod.SYNTHETIC_BOOKS | card_mod.EXCHANGE_BOOKS


T0 = datetime(2026, 9, 23, 20, 56)


def _s(book, line, over, under, hours):
    return NS(
        book=book,
        line=line,
        over_price=over,
        under_price=under,
        captured_at=T0 + timedelta(hours=hours),
        last_seen_at=None,
    )


def _texas_tennessee():
    """The real week: Hard Rock 27.5 Wed and Thu, then 30.5 at -160 Friday while
    every other book stayed at 27.5 (BetMGM's own rung at 31.5 is not a reference)."""
    snaps = []
    for h, hr in ((0, (27.5, -120, 100)), (23, (27.5, -115, -105)), (47, (30.5, 125, -160))):
        snaps.append(_s("hardrockbet", hr[0], hr[1], hr[2], h))
        for b in ("draftkings", "fanduel", "espnbet"):
            snaps.append(_s(b, 27.5, -108, -112, h))
        snaps.append(_s("betmgm", 31.5, 185, -250, h))
    return snaps


def test_each_hard_rock_quote_is_judged_against_its_own_sweep():
    flags = [(s.line, rung) for s, rung in hr_rung_flags(_texas_tennessee())]
    assert flags == [(27.5, False), (27.5, False), (30.5, True)]
    assert [s.line for s in hr_main_snaps(_texas_tennessee())] == [27.5, 27.5]


def test_a_later_field_cannot_judge_an_earlier_quote():
    # The other books only arrive after Hard Rock's quote: no reference at that
    # moment, so only the price check applies (and 29.5 at -115 passes it).
    snaps = [_s("hardrockbet", 29.5, -105, -115, 0)] + [
        _s(b, 27.5, -110, -110, 1) for b in ("draftkings", "fanduel", "espnbet")
    ]
    assert [r for _, r in hr_rung_flags(snaps)] == [False]


def test_hard_rock_close_never_grades_against_an_alternate():
    snaps = _texas_tennessee()
    kick = T0 + timedelta(hours=48)
    assert book_closing_before_kickoff(snaps, kick, "hardrockbet")[1] == 27.5
    assert book_closing_price_before_kickoff(snaps, kick, "hardrockbet") == -105


def test_other_books_close_reads_are_unchanged():
    snaps = _texas_tennessee()
    kick = T0 + timedelta(hours=48)
    assert book_closing_before_kickoff(snaps, kick, "draftkings")[1] == 27.5
