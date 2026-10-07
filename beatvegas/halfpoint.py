"""Build the half-point value table (docs/CONSENSUS.md): how often a total lands
on each integer, for games whose market expected about the same total.

The consensus engine (beatvegas/consensus.py) uses it to move a fair price from
one line to another -- a book closing under 28.0 at -110 says something about
under 27.5 only once you know how often a first half lands on exactly 27 or 28.

Inputs, Tate's call (2026-10-07): FBS-vs-FBS games 2013-2025 (never the season
being tested), trusted first-half totals only.
- Full game: the expected total is the game's closing full-game total; the
  outcome is the final total.
- First half: no real first-half line exists before 2023, so the expected first
  half is the closing full-game total times the step share in
  data/multiplier.json (0.4975, or 0.5375 when the closing spread is 21+). That
  proxy only chooses WHICH games describe the shape near a line; nothing is
  graded against it (the proxy era's lesson, CLAUDE.md "Honest status").

For each half-point center c, the games whose expected total lies within
WINDOW_PTS of c give the empirical mass P(total == k) for integers within
SPAN_PTS of c. A center with fewer than MIN_N games is left out, and the engine
falls back to the nearest center the table has. Pure functions only; the
script scripts/build_halfpoint_table.py reads the games and writes the JSON.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

WINDOW_PTS = 1.0
SPAN_PTS = 8
MIN_N = 300


def expected_first_half(
    full_game_total: Optional[float],
    spread: Optional[float],
    base: float,
    blowout: float,
    cut: float,
) -> Optional[float]:
    """The step-share proxy for the first-half expectation; None without a total."""
    if full_game_total is None:
        return None
    share = blowout if spread is not None and abs(spread) >= cut else base
    return full_game_total * share


def half_grid(lo: float, hi: float) -> List[float]:
    """Every half-point value from floor-to-half(lo) to ceil-to-half(hi)."""
    start = math.floor(lo * 2) / 2
    end = math.ceil(hi * 2) / 2
    n = int(round((end - start) * 2))
    return [start + i / 2 for i in range(n + 1)]


def market_table(
    pairs: Sequence[Tuple[float, float]],
    window: float = WINDOW_PTS,
    span: int = SPAN_PTS,
    min_n: int = MIN_N,
) -> Dict[str, dict]:
    """{center: {"n": games, "mass": {k: P(total == k)}}} from (expected,
    actual) pairs. Mass is over the n games in the window; integers outside
    c +/- span are not stored (they are never needed: the engine converts at
    most 1.5 points, plus the push at either end)."""
    if not pairs:
        return {}
    exps = [e for e, _ in pairs]
    out: Dict[str, dict] = {}
    for c in half_grid(min(exps), max(exps)):
        sel = [int(round(a)) for e, a in pairs if abs(e - c) <= window + 1e-9]
        if len(sel) < min_n:
            continue
        counts = Counter(sel)
        n = len(sel)
        lo, hi = int(math.floor(c - span)), int(math.ceil(c + span))
        out[f"{c:.1f}"] = {
            "n": n,
            "mass": {str(k): counts.get(k, 0) / n for k in range(lo, hi + 1)},
        }
    return out


def push_rates(table: Dict[str, dict]) -> Dict[str, float]:
    """For each integer center, the chance of landing exactly on it -- the push
    rate a whole-number line at that center would carry (a sanity read)."""
    out = {}
    for c, entry in table.items():
        cf = float(c)
        if abs(cf - round(cf)) < 1e-9:
            out[c] = entry["mass"].get(str(int(round(cf))), 0.0)
    return out


def pairs_from_rows(
    rows: Iterable[dict], base: float, blowout: float, cut: float
) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """(first-half pairs, full-game pairs) from game rows carrying
    full_game_total, spread, fh_trusted (the trusted first-half total or None)
    and final_total."""
    fh: List[Tuple[float, float]] = []
    fg: List[Tuple[float, float]] = []
    for r in rows:
        fgt = _num(r.get("full_game_total"))
        if fgt is None:
            continue
        final = _num(r.get("final_total"))
        if final is not None:
            fg.append((fgt, final))
        e1 = expected_first_half(fgt, _num(r.get("spread")), base, blowout, cut)
        half = _num(r.get("fh_trusted"))
        if e1 is not None and half is not None:
            fh.append((e1, half))
    return fh, fg


def _num(v) -> Optional[float]:
    """A float, or None for None and NaN (a pandas frame hands back NaN for a
    missing number even after .where(notna, None) on a float column)."""
    if v is None:
        return None
    f = float(v)
    return None if math.isnan(f) else f
