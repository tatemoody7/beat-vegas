"""Pure grading math: outcomes, CLV, and units for first-half under bets.

Kept dependency-free and unit-tested so the money logic is never in doubt.
Convention: we only ever bet the UNDER (the project's market).
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


def units_won(actual_first_half_total: float, line: float, under_price: int = -110) -> float:
    """Profit in units for a 1-unit UNDER bet (push = 0, loss = -1)."""
    res = under_result(actual_first_half_total, line)
    if res == "push":
        return 0.0
    if res == "under":
        return american_to_decimal(under_price) - 1.0
    return -1.0


def clv_under(bet_line: float, closing_line: float) -> Optional[float]:
    """Closing line value for an UNDER, in points. Positive = the line CLOSED
    HIGHER than where you bet it, i.e. you got the under at a softer number."""
    if bet_line is None or closing_line is None:
        return None
    return closing_line - bet_line
