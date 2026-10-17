"""The consensus fair-price engine (beatvegas/consensus.py, docs/CONSENSUS.md).

The first test works one pick by hand so the arithmetic in the module can be
read against something a person checked; the rest pin each rule Tate set on
2026-10-07: Hard Rock and Fliff never count, only centred quotes, at least three
books, at most 1.5 points of conversion, a 2-hour close window, multiplicative
de-vig, and a push returns the stake.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from beatvegas import consensus as C

KICK = datetime(2026, 10, 10, 19, 30)

# A hand-made table around 27.5: the chance a first half lands on each integer.
MASS = {k: 0.0 for k in range(18, 38)}
MASS.update({26: 0.05, 27: 0.06, 28: 0.05})
TABLE = C.HalfPointTable(
    {
        "version": "test",
        "markets": {
            "1H_total": {
                "centers": {"27.5": {"n": 1000, "mass": {str(k): v for k, v in MASS.items()}}}
            },
            "full_game_total": {
                "centers": {"52.5": {"n": 1000, "mass": {str(k): 0.02 for k in range(44, 62)}}}
            },
        },
    }
)


def snap(book, line, over, under, minutes_before=30, seen_minutes_before=None, market="1H_total"):
    cap = KICK - timedelta(minutes=minutes_before)
    seen = None if seen_minutes_before is None else KICK - timedelta(minutes=seen_minutes_before)
    return SimpleNamespace(
        book=book,
        line=line,
        over_price=over,
        under_price=under,
        captured_at=cap,
        last_seen_at=seen,
        market=market,
    )


def test_one_pick_worked_by_hand():
    """Under 27.5 at -110, three books at the close:
    - A: 28.0, -110/-110 -> fair under given a decision 0.500; the push at 28
      (0.05) is removed: P(total <= 27) = 0.500 * 0.95 = 0.4750. Moving to 27.5
      adds nothing (no integer in [27.5, 28)).
    - B: 27.0, -110/-110 -> 0.500 * (1 - 0.06) = 0.4700 = P(total <= 26); to
      27.5 adds the 27 mass: 0.4700 + 0.06 = 0.5300.
    - C: 27.5, over -120 / under +100 -> implied 0.54545 / 0.50000, total
      1.04545, fair under 0.50000 / 1.04545 = 0.47826; a half-point line has no
      push, so it stands.
    Median 0.47826. EV at -110 (profit 0.90909 per unit):
    0.47826 * 0.90909 - 0.52174 = -0.08696 per unit."""
    snaps = [
        snap("draftkings", 28.0, -110, -110),
        snap("fanduel", 27.0, -110, -110),
        snap("betmgm", 27.5, -120, 100),
    ]
    r = C.consensus_reading(snaps, KICK, "1H_total", 27.5, "under", -110, TABLE)
    assert r.excluded is None
    assert r.books == 3
    assert r.center_line == 27.5
    assert r.p_win == pytest.approx(0.47826, abs=1e-5)
    assert r.p_push == 0.0
    assert r.ev == pytest.approx(-0.08696, abs=1e-5)
    assert r.book_list == ["betmgm", "draftkings", "fanduel"]


def test_the_over_is_the_complement_less_the_push():
    snaps = [
        snap("draftkings", 28.0, -110, -110),
        snap("fanduel", 28.0, -110, -110),
        snap("betmgm", 28.0, -110, -110),
    ]
    under = C.consensus_reading(snaps, KICK, "1H_total", 28.0, "under", -110, TABLE)
    over = C.consensus_reading(snaps, KICK, "1H_total", 28.0, "over", -110, TABLE)
    # Fair under given a decision is 0.5 at 28 with a 0.05 push: each side wins 0.475.
    assert under.p_win == pytest.approx(0.475)
    assert over.p_win == pytest.approx(0.475)
    assert under.p_push == over.p_push == pytest.approx(0.05)
    # A push returns the stake: EV = 0.475 * 0.90909 - 0.475.
    assert under.ev == pytest.approx(0.475 * (100 / 110) - 0.475)


def test_hard_rock_fliff_and_the_synthetic_consensus_never_count():
    snaps = [
        snap("hardrockbet", 27.5, -110, -110),
        snap("fliff", 27.5, -110, -110),
        snap("consensus", 27.5, -110, -110),
        snap("draftkings", 27.5, -110, -110),
        snap("fanduel", 27.5, -110, -110),
    ]
    r = C.consensus_reading(snaps, KICK, "1H_total", 27.5, "under", -110, TABLE)
    assert r.excluded == C.EX_FEW_BOOKS
    assert r.books == 2


def test_an_off_centre_rung_is_not_a_quote():
    snaps = [
        snap("draftkings", 27.5, -110, -110),
        snap("fanduel", 27.5, -110, -110),
        snap("betmgm", 27.5, 130, -170),
    ]
    assert (
        C.consensus_reading(snaps, KICK, "1H_total", 27.5, "under", -110, TABLE).excluded
        == C.EX_FEW_BOOKS
    )


def test_a_book_more_than_one_and_a_half_points_away_is_left_out():
    snaps = [
        snap("draftkings", 27.5, -110, -110),
        snap("fanduel", 27.5, -110, -110),
        snap("betmgm", 29.5, -110, -110),
    ]
    r = C.consensus_reading(snaps, KICK, "1H_total", 27.5, "under", -110, TABLE)
    assert r.excluded == C.EX_FAR and r.books == 2
    snaps[2] = snap("betmgm", 29.0, -110, -110)  # exactly 1.5 away counts
    assert C.consensus_reading(snaps, KICK, "1H_total", 27.5, "under", -110, TABLE).books == 3


def test_the_close_window_is_two_hours_and_a_later_confirmation_counts():
    old = [
        snap(b, 27.5, -110, -110, minutes_before=200) for b in ("draftkings", "fanduel", "betmgm")
    ]
    assert (
        C.consensus_reading(old, KICK, "1H_total", 27.5, "under", -110, TABLE).excluded
        == C.EX_STALE
    )
    # Same quotes, re-confirmed unchanged 40 minutes before kickoff: they count.
    seen = [
        snap(b, 27.5, -110, -110, minutes_before=200, seen_minutes_before=40)
        for b in ("draftkings", "fanduel", "betmgm")
    ]
    r = C.consensus_reading(seen, KICK, "1H_total", 27.5, "under", -110, TABLE)
    assert r.excluded is None
    assert r.close_at == KICK - timedelta(minutes=40)


def test_a_quote_after_kickoff_never_counts():
    snaps = [snap(b, 27.5, -110, -110) for b in ("draftkings", "fanduel")] + [
        snap("betmgm", 27.5, -110, -110, minutes_before=-10)
    ]
    assert (
        C.consensus_reading(snaps, KICK, "1H_total", 27.5, "under", -110, TABLE).excluded
        == C.EX_FEW_BOOKS
    )


def test_each_book_counts_once_at_its_newest_centred_quote():
    snaps = [
        snap("draftkings", 26.5, -110, -110, minutes_before=100),
        snap("draftkings", 27.5, -110, -110, minutes_before=20),
        snap("fanduel", 27.5, -110, -110),
        snap("betmgm", 27.5, -110, -110),
    ]
    r = C.consensus_reading(snaps, KICK, "1H_total", 27.5, "under", -110, TABLE)
    assert r.books == 3 and r.center_line == 27.5


def test_no_kickoff_no_line_and_no_price_are_recorded_not_raised():
    snaps = [snap(b, 27.5, -110, -110) for b in ("draftkings", "fanduel", "betmgm")]
    assert (
        C.consensus_reading(snaps, None, "1H_total", 27.5, "under", -110, TABLE).excluded
        == C.EX_NO_KICKOFF
    )
    assert (
        C.consensus_reading(snaps, KICK, "1H_total", None, "under", -110, TABLE).excluded
        == C.EX_NO_LINE
    )
    r = C.consensus_reading(snaps, KICK, "1H_total", 27.5, "under", None, TABLE)
    assert r.excluded is None and r.p_win is not None and r.ev is None


def test_hard_rock_reading_uses_its_own_main_quote():
    snaps = [snap("hardrockbet", 27.5, -110, -110), snap("draftkings", 27.5, -130, 110)]
    r = C.hr_reading(snaps, KICK, "1H_total", 27.5, "under", -110, TABLE)
    assert r.excluded is None and r.books == 1
    assert r.p_win == pytest.approx(0.5)
    assert r.ev == pytest.approx(0.5 * (100 / 110) - 0.5)
    none = C.hr_reading(
        [snap("draftkings", 27.5, -110, -110)], KICK, "1H_total", 27.5, "under", -110, TABLE
    )
    assert none.excluded == C.EX_NO_HR_CLOSE


def test_convert_under_moves_mass_both_ways():
    assert C.convert_under(MASS, 27.5, 0.5, 28.5) == pytest.approx(0.55)  # adds the 28 mass
    assert C.convert_under(MASS, 27.5, 0.5, 26.5) == pytest.approx(0.44)  # removes the 27 mass
    assert C.convert_under(MASS, 27.5, 0.5, 27.5) == pytest.approx(0.5)
    assert C.convert_under({}, 27.5, 0.5, 28.0) is None


def test_a_center_the_table_lacks_falls_back_to_the_nearest():
    assert TABLE.nearest_center("1H_total", 31.0) == 27.5
    assert TABLE.mass("nonexistent_market", 27.5) == {}


def test_fields_for_pick_names_every_column_and_never_fails_without_a_table():
    pick = SimpleNamespace(market="1H", side="under", line=27.5, price=-110)
    snaps = [snap(b, 27.5, -110, -110) for b in ("draftkings", "fanduel", "betmgm", "hardrockbet")]
    f = C.fields_for_pick(snaps, KICK, pick, TABLE)
    assert set(f) == {
        "cons_version",
        "cons_books",
        "cons_line",
        "cons_close_at",
        "cons_p_win",
        "cons_p_push",
        "ev_cons",
        "ev_hr",
        "cons_excluded",
    }
    assert f["cons_version"] == C.CONSENSUS_VERSION and f["cons_books"] == 3
    assert f["ev_hr"] == pytest.approx(f["ev_cons"])


def test_the_frozen_table_is_the_one_the_version_names():
    t = C.HalfPointTable.load()
    assert t.version == C.HALFPOINT_VERSION
    # Every first-half center between 21 and 35 has its key numbers on file.
    for c in (21.0, 24.0, 27.5, 31.0, 35.0):
        assert t.nearest_center("1H_total", c) == c
    # 24 is a key first-half number: far more often landed on than 25.
    m = t.mass("1H_total", 24.5)
    assert m[24] > 5 * m[25]


# --- market_close: the Market Research benchmark (fact-check audit 2026-10-17) ---


def test_market_close_is_the_median_of_three_or_more_books_inside_two_hours():
    snaps = [
        snap("draftkings", 27.5, -110, -110),
        snap("fanduel", 28.5, -110, -110),
        snap("betmgm", 27.5, -110, -110),
        snap("bovada", 28.0, -110, -110),
    ]
    mc = C.market_close(snaps, KICK)
    assert mc is not None
    assert mc.line == 27.75 and mc.books == 4


def test_market_close_ignores_hard_rock_fliff_and_stale_books():
    snaps = [
        snap("draftkings", 27.5, -110, -110),
        snap("fanduel", 27.5, -110, -110),
        snap("hardrockbet", 30.5, -110, -110),
        snap("fliff", 30.5, -110, -110),
        # Last confirmed three hours out: outside the judge's window.
        snap("betmgm", 26.5, -110, -110, minutes_before=180),
    ]
    assert C.market_close(snaps, KICK) is None  # two books left, fewer than three


def test_market_close_counts_a_late_confirmation_of_an_old_quote():
    snaps = [
        snap("draftkings", 27.5, -110, -110, minutes_before=600, seen_minutes_before=20),
        snap("fanduel", 27.5, -110, -110),
        snap("betmgm", 28.5, -110, -110),
    ]
    mc = C.market_close(snaps, KICK)
    assert mc is not None and mc.line == 27.5 and mc.books == 3


def test_market_close_skips_off_centre_rungs():
    snaps = [
        snap("draftkings", 27.5, -110, -110),
        snap("fanduel", 27.5, -110, -110),
        snap("betmgm", 23.5, -295, 210),  # a rung, not a main line
        snap("bovada", 28.5, -110, -110),
    ]
    mc = C.market_close(snaps, KICK)
    assert mc is not None and mc.books == 3 and mc.line == 27.5
