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
    kind: str                       # 'posted' | 'move'
    matchup: str
    new_line: float
    old_line: Optional[float] = None
    model_score: Optional[int] = None


def detect_line_alerts(prev: Dict[int, Optional[float]],
                       new: Dict[int, float],
                       matchups: Dict[int, str],
                       threshold: float = 1.0,
                       scores: Optional[Dict[int, int]] = None) -> List[Alert]:
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
            alerts.append(Alert(gid, "posted", mu, new_line,
                                model_score=scores.get(gid)))
        elif abs(new_line - old) >= threshold:
            alerts.append(Alert(gid, "move", mu, new_line, old_line=old,
                                model_score=scores.get(gid)))
    return alerts


def format_alert(a: Alert) -> str:
    score = f" · under score {a.model_score}" if a.model_score is not None else ""
    if a.kind == "posted":
        return f"🆕 1H total posted: {a.matchup} — {a.new_line:g}{score}"
    arrow = "↑" if a.new_line > (a.old_line or 0) else "↓"
    return (f"📉 1H line move: {a.matchup} — {a.old_line:g} {arrow} {a.new_line:g}"
            f"{score}")
