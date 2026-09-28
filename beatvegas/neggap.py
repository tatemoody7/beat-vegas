"""H-NEGGAP-P: paper OVERS on the negative-gap band, logged beside the champion.

Registry row H-NEGGAP-P; design in docs/NEGGAP_PAPER.md; constants in
beatvegas/backtest/stopping.py::NEGGAP. Three nested arms on the card item's gap
(Hard Rock's MAIN first-half line minus our number): gap < 0, <= -1.75, <= -3.
One paper OVER per game per arm at Hard Rock's OVER price as captured at the
build, written to `challenger_picks` (side='over') and NEVER to `manual_picks`,
so nothing that feeds the bankroll, the cap, Results or H-STOP-2 can see a row.

Every row here is PAPER. There is no real-money path through this file, no flag
that could create one, and `docs/BETTING_POLICY.md` (first-half unders) is not
amended by anything in it. Collection is OFF unless NEGGAP_COLLECT=1 is set in
the environment (card.yml sets it for the decision builds).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .backtest.stopping import NEGGAP
from .challenger_picks import add_challenger_pick, existing_challenger_pick
from .hardrock import HR_BOOK_KEY

ARMS: Tuple[Tuple[str, float], ...] = tuple(
    (label, float(NEGGAP["arm_gap_max"][label])) for label in NEGGAP["arms"]
)


def collection_enabled() -> bool:
    """NEGGAP_COLLECT=1 switches the over arms on; unset is off (the default)."""
    return os.environ.get("NEGGAP_COLLECT") == "1"


def arm_hits(gap: Optional[float]) -> List[str]:
    """The arms a gap belongs to, nested: -4 is in all three, -2 in two, -1 in one,
    0 or above in none. `arm_gap_max` 0.0 means strictly negative."""
    if gap is None:
        return []
    out = []
    for label, mx in ARMS:
        if (gap < 0) if mx == 0.0 else (gap <= mx):
            out.append(label)
    return out


def in_universe(it: Dict) -> bool:
    """H-PCT-U's universe with an over price: Hard Rock's NEWEST quote is its
    main line, the model read the game, and the over side is priced."""
    return bool(
        it.get("hr_centred")
        and it.get("hr_live")
        and it.get("hr_line") is not None
        and it.get("bv_line") is not None
        and it.get("hr_over_price") is not None
        and it.get("gap_basis") == "hardrock"
        and it.get("gap") is not None
    )


def log_neggap_picks(
    session, card: Dict, now: datetime, window_hours: Optional[float] = None
) -> Dict[str, int]:
    """Insert the arms' paper OVERS for this build. Mirrors
    scripts/build_card.py::log_paper_picks: the same paper window (a game
    kicking off beyond `window_hours` waits for the next build), one row per
    game per arm, deduplicated per arm by existing_challenger_pick. Returns
    {arm: rows inserted}. Never touches `manual_picks`."""
    added: Dict[str, int] = {}
    for it in card.get("items", []):
        if not in_universe(it):
            continue
        if window_hours is not None and it.get("kick"):
            kick = datetime.fromisoformat(it["kick"].replace("Z", "+00:00")).replace(tzinfo=None)
            if kick - now > timedelta(hours=window_hours):
                continue
        arms = arm_hits(float(it["gap"]))
        if not arms:
            continue
        gid = int(it["game_id"])
        for arm in arms:
            if existing_challenger_pick(session, gid, arm) is not None:
                continue
            add_challenger_pick(
                session,
                arm=arm,
                game_id=gid,
                season=int(card["season"]),
                week=int(card["week"]),
                home_team=it["home"],
                away_team=it["away"],
                side="over",
                market="1H",
                line=float(it["hr_line"]),
                price=int(it["hr_over_price"]),
                book=HR_BOOK_KEY,
                slot=card.get("slot"),
                placed_at=now,
                blocker=None,
                arm_line_at_pick=float(it["bv_line"]),
                champion_line_at_pick=float(it["bv_line"]),
                gap_at_pick=float(it["gap"]),
            )
            added[arm] = added.get(arm, 0) + 1
    return added


def summary_line(added: Dict[str, int], enabled: bool) -> Optional[str]:
    """The card summary's one line about the arms."""
    if not enabled:
        return "  NEGGAP (H-NEGGAP-P, paper overs): off (NEGGAP_COLLECT unset); no row written"
    if not added:
        return "  NEGGAP (H-NEGGAP-P, paper overs): nothing new to log"
    return "  NEGGAP (H-NEGGAP-P, paper overs): " + ", ".join(
        f"{a} +{n}" for a, n in sorted(added.items())
    )
