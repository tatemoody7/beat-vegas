"""H-ARM-1HO: the registered first-half OVERS arm -- the bottom-20% mirror.

Registry row H-ARM-1HO (docs/HYPOTHESES.md, ledger slot 2 of the 2026 protocol
p1, Tate's calls of 2026-10-08). The mirror of the first-half-unders arm
(H-ARM-1HU, the card's per-slate bar) over the SAME universe: every upcoming
game with a model read and Hard Rock's centred main first-half line. The floor
is the k-th SMALLEST gap with k = max(1, round(0.2 N)); every game whose gap is
at or below the floor AND below zero qualifies (ties qualify, uncapped), and
logs one paper OVER at Hard Rock's over price on that main line, captured at the
build. Rows go to `challenger_picks` (arm 'H-ARM-1HO', side over, market 1H) and
NEVER to `manual_picks`, so nothing that feeds the bankroll, the cap or Results'
real ledger can see one.

Every row here is PAPER. There is no real-money path through this file.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Set

from .card import parse_kick
from .challenger_picks import add_challenger_pick
from .db.models import ChallengerPick
from .hardrock import HR_BOOK_KEY
from .model.score import MODEL_VERSION, PCT_SHARE
from .picks import freeze_factors
from .protocol import ARM_1H_OVER

# The market read frozen beside each row (the chips the unders arm freezes).
_CHIP_KEYS = (
    "total_band",
    "hook_side",
    "key_dist",
    "full_game_total",
    "spread",
    "hr_vs_market",
    "fair_source",
    "fair_under",
    "market_line",
    "tier",
)


def slate_floor(gaps, share: float = PCT_SHARE) -> Optional[float]:
    """The mirror of model.score.slate_bar: the k-th SMALLEST gap with
    k = max(1, round(share * N)); None on an empty slate. Ties at the floor all
    qualify."""
    vals = sorted(float(g) for g in gaps if g is not None and not (isinstance(g, float) and g != g))
    if not vals:
        return None
    k = max(1, int(round(share * len(vals))))
    return vals[k - 1]


def in_slate(it: Dict[str, Any]) -> bool:
    """The per-slate bar's universe (card.py::build_card): a model read and
    Hard Rock's NEWEST quote is its main line (`hr_centred` implies `hr_live`
    and a line, and the gap is then on the Hard Rock basis)."""
    return bool(
        it.get("hr_centred") and it.get("bv_line") is not None and it.get("gap") is not None
    )


def select(items: Sequence[Dict[str, Any]], share: float = PCT_SHARE) -> Dict[str, Any]:
    """Pure: {floor, n, qualifying[]} for this build. A qualifier is in the
    slate, at or below the floor, below zero, and has an over price to log."""
    slate = [it for it in items if in_slate(it)]
    floor = slate_floor([it["gap"] for it in slate], share)
    quals = [
        it
        for it in slate
        if floor is not None
        and float(it["gap"]) <= floor
        and float(it["gap"]) < 0
        and it.get("hr_over_price") is not None
    ]
    return {"floor": floor, "n": len(slate), "qualifying": quals}


def _logged(session) -> Set[int]:
    """Games the arm already holds: one observation per game, whichever
    eligible build first saw it."""
    rows = (
        session.query(ChallengerPick.game_id)
        .filter(ChallengerPick.arm == ARM_1H_OVER, ChallengerPick.market == "1H")
        .all()
    )
    return {int(g) for (g,) in rows}


def log_overs_mirror(
    session,
    card: Dict,
    now: datetime,
    window_hours: Optional[float] = None,
    predictions: Sequence[Dict] = (),
) -> Dict[str, Any]:
    """Insert this build's H-ARM-1HO paper overs; the same paper window as the
    unders ledger (a game kicking off beyond `window_hours` waits for the next
    build). Returns {added, universe, floor, qualifying}."""
    sel = select(card.get("items", []))
    logged = _logged(session)
    pred_by_game = {
        int(p["game_id"]): p for p in predictions if p.get("model_version") == MODEL_VERSION
    }
    added = 0
    for it in sel["qualifying"]:
        gid = int(it["game_id"])
        if gid in logged:
            continue
        kick = parse_kick(it.get("kick"))
        if (
            window_hours is not None
            and kick is not None
            and kick - now > timedelta(hours=window_hours)
        ):
            continue
        pred = pred_by_game.get(gid)
        chips = {k: it.get(k) for k in _CHIP_KEYS}
        chips.update({"floor": sel["floor"], "universe_n": sel["n"]})
        add_challenger_pick(
            session,
            arm=ARM_1H_OVER,
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
            factors_json_at_pick=freeze_factors(chips, pred, it.get("features")),
            refit_id=(pred or {}).get("refit_id"),
        )
        added += 1
        logged.add(gid)
    return {
        "added": added,
        "universe": sel["n"],
        "floor": sel["floor"],
        "qualifying": len(sel["qualifying"]),
    }


def summary_line(stats: Optional[Dict[str, Any]]) -> str:
    """The card summary's line about the arm."""
    tag = f"  ARM {ARM_1H_OVER} (paper first-half overs, bottom-20% mirror)"
    if not stats:
        return f"{tag}: not run"
    floor = "—" if stats["floor"] is None else f"{stats['floor']:.2f}"
    return (
        f"{tag}: universe {stats['universe']}, floor {floor}, "
        f"{stats['qualifying']} qualify, +{stats['added']} logged"
    )


def arm_summary_lines(over: Optional[Dict[str, Any]], fg: Optional[Dict[str, Any]]) -> List[str]:
    """Both registered challenger-table arms' build lines (H-ARM-FGU's from fg_paper)."""
    from .fg_paper import arm_summary_line

    return [summary_line(over), arm_summary_line(fg)]
