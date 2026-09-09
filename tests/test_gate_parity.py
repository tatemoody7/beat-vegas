"""The verdict gates live twice — model/score.py (Python) and web/lib/verdict.ts
(the This Week page). They are POINT gates from the validated top-20%-by-gap
rule, never sigma thresholds. This test reads the TypeScript constants by regex
and fails the moment the two drift apart. The same guard covers the fair-price
constants and book sets hand-mirrored from beatvegas/card.py into
web/lib/lineCheck.ts and web/lib/books.ts."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from beatvegas.ci import SLOT_GATE_ET
from beatvegas.hardrock import HR_BOOK_KEY
from beatvegas.model import score

_TS = Path(__file__).resolve().parent.parent / "web" / "lib" / "verdict.ts"
_BOOKS_TS = _TS.parent / "books.ts"
_LINE_CHECK_TS = _TS.parent / "lineCheck.ts"
_CARD_TS = _TS.parent / "card.ts"

PARITY = {
    "BET_GAP_PTS": score.BET_GAP_PTS,
    "STRONG_GAP_PTS": score.STRONG_GAP_PTS,
    "WATCH_GAP_PTS": score.WATCH_GAP_PTS,
    "MODEL_BET_THRESHOLD": score.MODEL_BET_THRESHOLD,
    "WEEKLY_BET_CAP": score.WEEKLY_BET_CAP,
    "HR_OFF_MARKET_PTS": score.HR_OFF_MARKET_PTS,
    "MIN_GAMES_FOR_MODEL": score.MIN_GAMES_FOR_MODEL,
    "EV_FLOOR": score.EV_FLOOR,
}


def _ts_const(src: str, name: str) -> float:
    """The numeric value of `export const <name> = <number>;` in a TS source."""
    m = re.search(rf"export\s+const\s+{name}\s*=\s*(-?[0-9.]+)\s*;", src)
    assert m, f"{name} is not exported as a numeric const (it must be, for this parity guard)"
    return float(m.group(1))


@pytest.mark.parametrize("name", sorted(PARITY))
def test_python_gate_matches_verdict_ts(name):
    if not _TS.exists():
        pytest.skip(f"{_TS} not present in this checkout")
    src = _TS.read_text()
    assert _ts_const(src, name) == pytest.approx(PARITY[name]), name


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


def test_morning_gate_close_matches_card_ts():
    """web/lib/card.ts MORNING_GATE_CLOSE_ET_MIN (minutes after ET midnight when
    "no card yet today" stops being "the build has not run") mirrors the close
    of beatvegas/ci.py SLOT_GATE_ET["morning"]. Drift means the banner calls a
    card stale while the morning cron can still build, or the reverse."""
    assert _CARD_TS.exists(), f"{_CARD_TS} is missing — the guard must not vanish"
    close = SLOT_GATE_ET["morning"][1]
    expected = close.hour * 60 + close.minute
    assert _ts_const(_CARD_TS.read_text(), "MORNING_GATE_CLOSE_ET_MIN") == expected
