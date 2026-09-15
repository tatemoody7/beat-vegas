"""The verdict gates live twice — model/score.py (Python) and web/lib/verdict.ts
(the This Week page). They are POINT gates from the validated top-20%-by-gap
rule, never sigma thresholds. This test reads the TypeScript constants by regex
and fails the moment the two drift apart. The same guard covers the fair-price
constants and book sets hand-mirrored from beatvegas/card.py into
web/lib/lineCheck.ts and web/lib/books.ts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Union

import pytest

from beatvegas.ci import SLOT_GATE_ET, SLOT_WEEKDAY_ET
from beatvegas.hardrock import HR_BOOK_KEY
from beatvegas.model import score

_TS = Path(__file__).resolve().parent.parent / "web" / "lib" / "verdict.ts"
_BOOKS_TS = _TS.parent / "books.ts"
_LINE_CHECK_TS = _TS.parent / "lineCheck.ts"
_CARD_TS = _TS.parent / "card.ts"
_GRADE_TS = _TS.parent / "grade.ts"
_EDGE_TS = _TS.parent / "edge.ts"
_CARD_PY = Path(__file__).resolve().parent.parent / "beatvegas" / "card.py"

PARITY = {
    "BET_GAP_PTS": score.BET_GAP_PTS,
    "STRONG_GAP_PTS": score.STRONG_GAP_PTS,
    "WATCH_GAP_PTS": score.WATCH_GAP_PTS,
    "MODEL_BET_THRESHOLD": score.MODEL_BET_THRESHOLD,
    "WEEKLY_BET_CAP": score.WEEKLY_BET_CAP,
    "HR_OFF_MARKET_PTS": score.HR_OFF_MARKET_PTS,
    "MIN_GAMES_FOR_MODEL": score.MIN_GAMES_FOR_MODEL,
    # The money gate that MIN_GAMES_FOR_MODEL deliberately is NOT: the model
    # scores a week-1 game, real money will not take one.
    "MIN_GAMES_FOR_REAL_MONEY": score.MIN_GAMES_FOR_REAL_MONEY,
    "EV_FLOOR": score.EV_FLOOR,
    "BREAK_EVEN_EV": score.BREAK_EVEN_EV,
    "BET_MIN_EV": score.BET_MIN_EV,
}


def _ts_const(src: Union[str, Path], name: str, _depth: int = 0) -> float:
    """The numeric value of `export const <name> = <number>;` in a TS source
    (pass the source text, or the path to read it from).

    One level of ALIAS is resolved: `export const BET_MIN_EV = EV_FLOOR;` reads
    as EV_FLOOR's value. Without this an alias silently escapes the parity guard
    -- which is how FAIR_EV_FLOOR and EDGE_SCORE_MIN have never been checked --
    and an aliased gate constant is exactly the kind that must not drift."""
    if isinstance(src, Path):
        src = src.read_text()
    m = re.search(rf"export\s+const\s+{name}\s*=\s*(-?[0-9.]+)\s*;", src)
    if m:
        return float(m.group(1))
    alias = re.search(rf"export\s+const\s+{name}\s*=\s*([A-Z_][A-Z0-9_]*)\s*;", src)
    assert alias and _depth < 3, (
        f"{name} is not exported as a numeric const or a single-name alias "
        "(it must be one of those, for this parity guard)"
    )
    return _ts_const(src, alias.group(1), _depth + 1)


@pytest.mark.parametrize("name", sorted(PARITY))
def test_python_gate_matches_verdict_ts(name):
    if not _TS.exists():
        pytest.skip(f"{_TS} not present in this checkout")
    src = _TS.read_text()
    assert _ts_const(src, name) == pytest.approx(PARITY[name]), name


@pytest.mark.parametrize("name", ["SCORE_BET_MIN", "SCORE_WATCH_MIN"])
def test_grade_bands_match_grade_ts(name):
    """The coloured score bands (70 green / 55 amber) live in web/lib/grade.ts
    and beatvegas/model/score.py; the card and the site must colour alike."""
    assert _GRADE_TS.exists(), f"{_GRADE_TS} is missing — this parity guard must not vanish"
    assert _ts_const(_GRADE_TS, name) == pytest.approx(getattr(score, name)), name


def test_score_is_gap_only_on_both_sides():
    """edge.ts and card.py both scale the score off the same expression and
    neither carries a price bonus: the score is the gap alone (2026-09-09)."""
    for path in (_EDGE_TS, _CARD_PY):
        assert path.exists(), f"{path} is missing — this parity guard must not vanish"
        src = path.read_text()
        assert re.search(
            r"SCORE_PER_GAP_PT\s*=\s*\(\s*SCORE_BET_MIN\s*-\s*50\s*\)\s*/\s*BET_GAP_PTS", src
        ), path.name
        assert "PRICE_BONUS_CAP" not in src, f"{path.name} still carries a price bonus"


def test_gates_are_ordered_points_not_sigmas():
    assert score.WATCH_GAP_PTS < score.BET_GAP_PTS < score.STRONG_GAP_PTS
    assert not hasattr(score, "OPPORTUNITY_Z")  # the sigma gate is gone for good


def test_every_numeric_gate_in_verdict_ts_is_mirrored():
    """A new `export const X_PTS = 0.5` in verdict.ts must land in PARITY (and in
    model/score.py), or the Friday card routine and the site can disagree."""
    if not _TS.exists():
        pytest.skip(f"{_TS} not present in this checkout")
    src = _TS.read_text()
    exported = set(re.findall(r"export\s+const\s+([A-Z_]+)\s*=\s*-?[0-9.]+\s*;", src))
    missing = exported - set(PARITY)
    assert not missing, f"numeric gates in verdict.ts without a Python mirror: {sorted(missing)}"


def test_exchange_books_match_books_ts():
    """card.EXCHANGE_BOOKS (exchange-first fair price) mirrors web/lib/books.ts
    EXCHANGE_KEYS — the site's Line Check must pick the same exchanges. A missing
    books.ts is a FAILURE, not a skip: renaming the file must not silently
    delete the guard."""
    from beatvegas import card

    assert _BOOKS_TS.exists(), f"{_BOOKS_TS} is missing — this parity guard must not vanish with it"
    m = re.search(r"EXCHANGE_KEYS = new Set\(\[(.*?)\]\)", _BOOKS_TS.read_text(), re.S)
    assert m, "EXCHANGE_KEYS not found in books.ts"
    keys = set(re.findall(r'"([a-z_]+)"', m.group(1)))
    assert keys == set(card.EXCHANGE_BOOKS)


def test_fair_price_constants_match_line_check_ts():
    """The fair-price windows and the exchange quality guards are hand-mirrored
    into web/lib/lineCheck.ts (beatvegas/card.py is the original). Drift here
    means the card and the Line Check page disagree about which books may price
    Hard Rock's number, or about which exchange quotes count as a fair price."""
    from beatvegas import card

    assert _LINE_CHECK_TS.exists(), f"{_LINE_CHECK_TS} is missing — the guard must not vanish"
    src = _LINE_CHECK_TS.read_text()
    for name, expected in (
        ("FAIR_PRICE_LINE_WINDOW", card.FAIR_PRICE_LINE_WINDOW),
        ("FAIR_PRICE_WIDE_WINDOW", card.FAIR_PRICE_WIDE_WINDOW),
        ("EXCHANGE_MAX_HOLD", card.EXCHANGE_MAX_HOLD),
        ("EXCHANGE_MAX_AGE_H", card.EXCHANGE_MAX_AGE_H),
    ):
        assert _ts_const(src, name) == pytest.approx(expected), name


def test_non_exchange_fair_price_exclusions_match_line_check_ts():
    """card.FAIR_PRICE_EXCLUDED is the FULL list. lineCheck.ts already filters
    Hard Rock, the synthetic aggregate and the exchanges through HR_KEYS /
    isSynthetic / isExchange, so its own set holds exactly the REMAINDER — hence
    the _EXTRA name. A set called FAIR_PRICE_EXCLUDED there would read as the
    full list and mislead anyone diffing the two."""
    from beatvegas import card

    assert _LINE_CHECK_TS.exists(), f"{_LINE_CHECK_TS} is missing — the guard must not vanish"
    m = re.search(
        r"FAIR_PRICE_EXCLUDED_EXTRA = new Set\(\[(.*?)\]\)", _LINE_CHECK_TS.read_text(), re.S
    )
    assert m, "FAIR_PRICE_EXCLUDED_EXTRA not found in lineCheck.ts"
    keys = set(re.findall(r'"([a-z_]+)"', m.group(1)))
    assert keys == (
        set(card.FAIR_PRICE_EXCLUDED)
        - set(card.EXCHANGE_BOOKS)
        - set(card.SYNTHETIC_BOOKS)
        - {HR_BOOK_KEY}
    )


def _ts_weekday_map(src: str, name: str):
    """`export const <name>: Readonly<Record<string, number>> = { Tue: 1035, ... }`
    parsed into a plain dict."""
    m = re.search(rf"export\s+const\s+{name}[^=]*=\s*\{{(.*?)\}}\s*;", src, re.S)
    assert m, f"{name} is not exported as an object literal (it must be, for this parity guard)"
    return {k: int(v) for k, v in re.findall(r"(\w+)\s*:\s*(-?\d+)", m.group(1))}


def test_build_gate_closes_match_card_ts():
    """web/lib/card.ts BUILD_GATE_CLOSE_ET_MIN (per ET weekday, the minute when
    "no card yet today" stops being "the build has not run") mirrors the closes
    of beatvegas/ci.py SLOT_GATE_ET, keyed through SLOT_WEEKDAY_ET. Drift means
    the banner calls a card stale while that day's cron can still build, or the
    reverse — and on Saturday that is the morning Tate bets off."""
    assert _CARD_TS.exists(), f"{_CARD_TS} is missing — the guard must not vanish"
    expected = {}
    for slot, weekday in SLOT_WEEKDAY_ET.items():
        close = SLOT_GATE_ET[slot][1]
        expected[weekday] = close.hour * 60 + close.minute
    assert _ts_weekday_map(_CARD_TS.read_text(), "BUILD_GATE_CLOSE_ET_MIN") == expected


def test_card_ts_has_no_build_day_for_every_unscheduled_weekday():
    """Every weekday WITHOUT a scheduled build must be absent from the TS map:
    that absence is what tells the banner yesterday's card is still current on
    Sunday, Monday and Wednesday. A stray key there would warn all day on a day
    nothing was ever going to build."""
    built = set(SLOT_WEEKDAY_ET.values())
    idle = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"} - built
    ts_map = _ts_weekday_map(_CARD_TS.read_text(), "BUILD_GATE_CLOSE_ET_MIN")
    assert idle.isdisjoint(ts_map), f"{sorted(idle & set(ts_map))} have no build but are gated"


def test_the_two_money_constants_measure_different_things():
    """BET_MIN_EV is the LIVE bar and it sits on the price-vs-market-fair metric,
    so it is deliberately BELOW zero -- paying the vig is not optional. It equals
    EV_FLOOR today, which keeps behaviour unchanged while giving the bar one name
    that the board, the card, the kill price and the logger all read.

    BREAK_EVEN_EV is the arithmetic reference for a wager's true EV. Nothing
    gates on it yet because `ev` cannot express it: measured 2026-09-13, zero of
    42 priced rows on the live week-2 card cleared ev >= 0, because ev >= 0 asks
    Hard Rock to beat the no-vig consensus. Wiring it needs a calibrated
    P(under). If you are here to "fix" BET_MIN_EV up to zero, read the note in
    model/score.py first -- it makes the system bet nothing, for the wrong reason."""
    assert score.BREAK_EVEN_EV == 0.0
    assert score.BET_MIN_EV == score.EV_FLOOR
    assert score.BET_MIN_EV < score.BREAK_EVEN_EV


def test_bet_branch_gates_on_bet_min_ev_not_ev_floor():
    """Source-text guard, the same shape as test_score_is_gap_only_on_both_sides.

    The BET branch must test the money constant. EV_FLOOR still exists and still
    describes the price landscape (the pos/fair/neg chips), so a grep for the
    name is not enough -- this pins the branch itself."""
    if not _TS.exists():
        pytest.skip(f"{_TS} not present in this checkout")
    src = _TS.read_text()
    assert "i.ev >= BET_MIN_EV" in src, "verdict.ts BET branch must gate on BET_MIN_EV"
    card = _CARD_PY.read_text()
    assert "ev >= BET_MIN_EV" in card, "card.py is_bet must gate on BET_MIN_EV"
