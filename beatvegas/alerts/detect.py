"""Pure detection of alert-worthy line events at the consensus level.

Consensus (median across books), not per-book, so you get one clean alert per
game rather than a stream of per-book noise. Two kinds: a 1H total was newly
posted (no prior consensus), or it moved by >= threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Alert:
    game_id: int
    kind: str  # 'posted' | 'move'
    matchup: str
    new_line: float
    old_line: Optional[float] = None
    model_score: Optional[int] = None


def detect_line_alerts(
    prev: Dict[int, Optional[float]],
    new: Dict[int, float],
    matchups: Dict[int, str],
    threshold: float = 1.0,
    scores: Optional[Dict[int, int]] = None,
) -> List[Alert]:
    """`prev`/`new`: game_id -> consensus 1H line (prev may be missing/None for a
    newly posted game). Returns posted + significant-move alerts."""
    scores = scores or {}
    alerts: List[Alert] = []
    for gid, new_line in new.items():
        if new_line is None:
            continue
        old = prev.get(gid)
        mu = matchups.get(gid, f"game {gid}")
        if old is None:
            alerts.append(Alert(gid, "posted", mu, new_line, model_score=scores.get(gid)))
        elif abs(new_line - old) >= threshold:
            alerts.append(
                Alert(gid, "move", mu, new_line, old_line=old, model_score=scores.get(gid))
            )
    return alerts


def format_alert(a: Alert) -> str:
    score = f" · under score {a.model_score}" if a.model_score is not None else ""
    if a.kind == "posted":
        return f"🆕 1H total posted: {a.matchup} — {a.new_line:g}{score}"
    arrow = "↑" if a.new_line > (a.old_line or 0) else "↓"
    return f"📉 1H line move: {a.matchup} — {a.old_line:g} {arrow} {a.new_line:g}{score}"


# --- Hard Rock "lines dropped" detection ------------------------------------
# The workflow trigger: the moment Hard Rock POSTS a line for a game/market, so
# Tate can bet the opener before it moves. This is first-appearance detection
# (not consensus movement): alert for games that have a HR line now but didn't
# before. `prev_ids` is the set of game ids already seen with a HR line.


@dataclass
class PostedAlert:
    game_id: int
    matchup: str
    line: float
    market: str  # 'full_game' | '1H'
    book: str


def detect_posted(
    prev_ids,
    new_lines: Dict[int, float],
    matchups: Dict[int, str],
    market: str,
    book: str,
) -> List[PostedAlert]:
    """Games with a line NOW that weren't in `prev_ids` -> newly posted."""
    seen = set(prev_ids or ())
    out: List[PostedAlert] = []
    for gid, line in new_lines.items():
        if line is None or gid in seen:
            continue
        out.append(PostedAlert(gid, matchups.get(gid, f"game {gid}"), float(line), market, book))
    return out


def detect_full_game_posted(prev_ids, new_lines, matchups, book: str = "hardrockbet"):
    return detect_posted(prev_ids, new_lines, matchups, "full_game", book)


def detect_first_half_posted(prev_ids, new_lines, matchups, book: str = "hardrockbet"):
    return detect_posted(prev_ids, new_lines, matchups, "1H", book)


def format_posted_summary(alerts: List[PostedAlert]) -> Optional[str]:
    """One concise push summarising a batch of newly-posted HR lines (None if empty)."""
    if not alerts:
        return None
    label = "full-game" if alerts[0].market == "full_game" else "1H"
    n = len(alerts)
    sample = "; ".join(f"{a.matchup} {a.line:g}" for a in alerts[:3])
    more = f" (+{n - 3} more)" if n > 3 else ""
    plural = "s" if n != 1 else ""
    return f"Hard Rock {label} lines are LIVE — {n} game{plural}: {sample}{more}"
