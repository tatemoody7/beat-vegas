"""Green/red factor-board tinting — a pure EXPLAINER, never a ranking signal.

Each factor's color comes from how far this game's value sits from the factor's
historical median, signed by its pre-registered `direction` so that "more
under-favorable" is always green and "hurts the under" is always red:

    lean = direction * (value - median) / spread

Continuous factors get a tinted *continuum* (intensity scales with |lean|);
genuinely binary factors (dome, short week) get hard green/red; and unproven
`hypothesis` factors (explosive/turnovers/havoc) are forced amber so a green
tint can never fool the reader before the real-line ledger has spoken.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .ledger import tier_from_evidence
from .registry import Factor, factor_by_name

# The curated set shown on the card, in display order (Tier 1 → Tier 2 → amber
# hypotheses). The per-side PBP metrics stay off the card to avoid clutter; the
# matchup-level hypotheses (mm_*) stand in for them. Expanded in later phases.
BOARD_FACTOR_NAMES: List[str] = [
    # Tier 1 — proven (pace, weather, efficiency/scoring levels)
    "combined_sec_play",
    "combined_plays",
    "wx_wind",
    "wx_precip",
    "wx_temp",
    "wx_dome",
    "combined_off_ppa",
    "combined_def_ppa",
    "combined_fh_offense",
    "combined_fh_defense",
    # Tier 2 — context
    "home_short_week",
    "away_short_week",
    # unverified hypotheses (amber until the real ledger speaks)
    "mm_explosive_edge",
    "mm_havoc",
    # situational thesis (travel / early kickoff) — amber; available for every
    # game incl. weeks 1-2 and FBS-vs-FCS via etl/context.py
    "away_travel_dist",
    "kickoff_local_hour",
]

_NEUTRAL_EPS = 0.15  # |lean| at/below this reads as neutral
_INTENSITY_CAP = 2.0  # a lean of this many spreads = full tint

_DIR_WORD = {
    "green": "helps",
    "red": "hurts",
    "neutral": "is neutral for",
    "amber": "unproven for",
    "unknown": "",
}


@dataclass(frozen=True)
class Tint:
    color: str  # green | red | neutral | amber | unknown
    intensity: float  # 0..1 tint strength
    lean: float  # signed; under-favorable is positive
    sentence: str  # plain-English template, filled


def _isnan(v) -> bool:
    return isinstance(v, float) and math.isnan(v)


def _fill(factor: Factor, value, color: str) -> str:
    if not factor.sentence:
        return ""
    try:
        return factor.sentence.format(value=value, dir=_DIR_WORD.get(color, ""))
    except (KeyError, ValueError, IndexError):
        return factor.sentence


def tint_factor(factor: Factor, value, median=None, spread=None) -> Tint:
    """Color + intensity for one factor on one game."""
    if value is None or _isnan(value):
        return Tint("unknown", 0.0, 0.0, "")

    if factor.binary:
        if not bool(value):
            return Tint("neutral", 0.0, 0.0, _fill(factor, value, "neutral"))
        color = "green" if factor.direction > 0 else "red" if factor.direction < 0 else "neutral"
        intensity = 1.0 if color != "neutral" else 0.0
        return Tint(color, intensity, float(factor.direction), _fill(factor, value, color))

    # continuous — needs a reference; without one we can't tint
    if median is None or spread is None or spread == 0 or _isnan(median) or _isnan(spread):
        color = "amber" if factor.hypothesis else "unknown"
        return Tint(color, 0.0, 0.0, _fill(factor, value, color))

    z = (float(value) - float(median)) / float(spread)
    lean = factor.direction * z
    intensity = min(1.0, abs(lean) / _INTENSITY_CAP)

    if factor.hypothesis:
        return Tint("amber", intensity, lean, _fill(factor, value, "amber"))
    if lean > _NEUTRAL_EPS:
        color = "green"
    elif lean < -_NEUTRAL_EPS:
        color = "red"
    else:
        color = "neutral"
    return Tint(color, intensity if color != "neutral" else 0.0, lean, _fill(factor, value, color))


def _robust_spread(s: pd.Series) -> float:
    """IQR/1.349 (≈ std for a normal), falling back to std then 1.0."""
    s = s.dropna().astype(float)
    if len(s) < 2:
        return 0.0
    iqr = float(s.quantile(0.75) - s.quantile(0.25))
    if iqr > 0:
        return iqr / 1.349
    sd = float(s.std())
    return sd if sd > 0 else 0.0


def factor_references(df: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
    """Per board-factor (median, spread) over the historical frame.

    These are the 'typical' anchors the tinting compares each game against — so
    a windy game reads green relative to HISTORY, not relative to this week's
    slate. Only board factors present in the frame are included.
    """
    out: Dict[str, Tuple[float, float]] = {}
    for name in BOARD_FACTOR_NAMES:
        if name not in df.columns:
            continue
        col = pd.to_numeric(df[name], errors="coerce").dropna()
        if col.empty:
            continue
        out[name] = (float(col.median()), _robust_spread(col))
    return out


def build_factor_board(
    row: pd.Series,
    refs: Optional[Dict[str, Tuple[float, float]]],
    ledger: Optional[Dict[str, Dict]] = None,
) -> List[Dict]:
    """The per-game factor board: each curated factor, tinted, in display order.

    Pure explainer — never affects the rank. When a credibility-ledger entry
    exists for a factor it's attached as `live` (real-line n/mean/CI/cooling) and
    can promote the factor's displayed tier; otherwise `live` is None. Factors
    with no value (or no reference for a continuous one) are dropped rather than
    shown as empty 'unknown' rows.
    """
    refs = refs or {}
    ledger = ledger or {}
    board: List[Dict] = []
    for name in BOARD_FACTOR_NAMES:
        factor = factor_by_name(name)
        if factor is None or name not in row.index:
            continue
        value = row.get(name)
        # Inactive binary factors (no dome, no short week) are noise — drop them.
        if factor.binary and (value is None or _isnan(value) or not bool(value)):
            continue
        median, spread = refs.get(name, (None, None))
        tint = tint_factor(factor, value, median=median, spread=spread)
        if tint.color == "unknown":
            continue
        rec = ledger.get(name)
        live = None
        tier = factor.tier
        if rec:
            live = {
                "n": rec.get("n"),
                "mean": rec.get("mean"),
                "lo": rec.get("lo"),
                "hi": rec.get("hi"),
                "cooling": bool(rec.get("cooling", False)),
            }
            tier = tier_from_evidence(factor.tier, int(rec.get("hits", 0)), int(rec.get("n", 0)))
        board.append(
            {
                "key": factor.name,
                "label": factor.description,
                "family": factor.family,
                "tier": tier,
                "direction": factor.direction,
                "hypothesis": factor.hypothesis,
                "binary": factor.binary,
                "value": round(float(value), 2),
                "color": tint.color,
                "intensity": round(tint.intensity, 3),
                "lean": round(tint.lean, 3),
                "sentence": tint.sentence,
                "live": live,
            }
        )
    return board


def historical_references(min_games: int = 0) -> Dict[str, Tuple[float, float]]:
    """`factor_references` over the whole historical feature frame, fail-soft.

    The tint compares a game against HISTORY, so both writers of a board card
    (model rows in model/score.py, derived rows in scripts/post_derived_lines.py
    and the week sim) need the same anchors. CFBD calls behind the frame are
    disk-cached. Any problem -> {} : the card still posts, its continuous
    factors just untinted."""
    try:
        from ..etl.features import build_feature_frame

        return factor_references(build_feature_frame(min_games=min_games))
    except Exception as e:  # noqa: BLE001 - the tint is cosmetic, never fatal
        print(f"[board] factor references unavailable ({e!r}) — cards untinted")
        return {}
