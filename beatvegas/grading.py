"""Pure grading math: outcomes, CLV, and units for first-half under bets.

Kept dependency-free and unit-tested so the money logic is never in doubt.
Convention: real money only ever bets the UNDER (the project's market); the
paper OVER arms of H-NEGGAP-P (2026-09-28) pass `side="over"` and are graded by
the same functions. `clv_under` is closing - bet for EVERY row -- for an over
the favourable direction is the reverse, and the reader flips it.
"""

from __future__ import annotations

from typing import Optional


def american_to_decimal(price: int) -> float:
    return 1 + (100 / abs(price)) if price < 0 else 1 + (price / 100)


def under_result(actual_first_half_total: float, line: float) -> str:
    """'under' (win), 'over' (loss), or 'push' for an under bet at `line`."""
    if actual_first_half_total < line:
        return "under"
    if actual_first_half_total > line:
        return "over"
    return "push"


def bet_won(outcome: str, side: str = "under") -> Optional[bool]:
    """Did a bet on `side` win this OUTCOME ('under' / 'over' / 'push')? None on a push.
    The stored `result` column is the outcome, never the win/loss, so it reads the
    same whichever side was taken (H-NEGGAP-P's paper overs, 2026-09-28)."""
    if outcome == "push":
        return None
    return outcome == side


def units_won(
    actual_first_half_total: float, line: float, under_price: int = -110, side: str = "under"
) -> float:
    """Profit in units for a 1-unit bet on `side` at `under_price` -- the price of
    THAT side, despite the parameter's name (kept for the under-only callers).
    Push = 0, loss = -1."""
    won = bet_won(under_result(actual_first_half_total, line), side)
    if won is None:
        return 0.0
    if won:
        return american_to_decimal(under_price) - 1.0
    return -1.0


def trusted_first_half_total(
    first_half_total: Optional[float],
    home_points: Optional[float],
    away_points: Optional[float],
    source: Optional[str] = None,
) -> Optional[float]:
    """The game's 1H total if it can be trusted for grading, else None.

    A LINE-SCORE 0 with a non-zero final score is the known false-zero
    corruption (placeholder all-zero quarters) — grading it would fabricate an
    UNDER win. A play-by-play 0 grades normally: since 2026-09-20 the writer
    (`etl.first_half.attach_first_half`) persists a scoreless PBP half only when
    the feed's own running score reaches the stored final, and every legacy PBP
    zero on file (15 games, 2023-26) was checked against ESPN's box score and is
    a real scoreless half. 0-0 in a 0-0 final grades too."""
    if first_half_total is None:
        return None
    if source == "pbp":
        return first_half_total
    final_total = (home_points or 0) + (away_points or 0)
    if first_half_total == 0 and final_total > 0:
        return None
    return first_half_total


def clv_under(bet_line: float, closing_line: float) -> Optional[float]:
    """Closing line value for an UNDER, in points: simply closing - bet.

    MIND THE SIGN -- it is the opposite of the obvious guess, and the reporting
    layer had it backwards until 2026-09-13. For an under a HIGHER number is
    easier to win, so a line that FALLS after you bet leaves you holding the
    better ticket: bet u28.5, close 27.5, this returns -1.0, and you have a
    point of cushion the closing bettor does not.

    So NEGATIVE is the good direction here. Kept as closing - bet because that
    is the plain factual difference; web/lib/decision-quality.ts::favourable
    owns the interpretation, and flips it for display."""
    if bet_line is None or closing_line is None:
        return None
    return closing_line - bet_line


def price_clv_under(
    open_fair_under: Optional[float], close_fair_under: Optional[float]
) -> Optional[float]:
    """No-vig PRICE CLV for an UNDER, in probability points. Isolates the JUICE
    dimension: positive = the under's no-vig fair price rose from open to close
    (the market moved toward the under), so an early under locked the cheaper
    side. Does NOT capture line movement — pair it with clv_under (points)."""
    if open_fair_under is None or close_fair_under is None:
        return None
    return close_fair_under - open_fair_under
