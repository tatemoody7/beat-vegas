"""The one code path that writes a `manual_picks` row.

`scripts/pick.py add` (Tate's own bets, from the terminal) and
`scripts/build_card.py` (the cloud card's PAPER picks) both insert through
`add_pick`, so the decision-tracking snapshot (reason / verdict / gap / ev /
Hard Rock line) and the paper-stake rule live in exactly one place.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .db.models import ManualPick

PAPER_STAKE = 1.0  # paper picks stake one flat unit so they grade as +/-1u


def existing_pick(
    session,
    game_id: int,
    market: str = "1H",
    side: str = "under",
    is_paper: Optional[bool] = None,
):
    """The first pick already logged on this game/market (legacy rows with a
    NULL market count as 1H), or None. Used as the duplicate guard by both the
    terminal `pick.py add` and the card's paper logging.

    `is_paper` scopes the guard to ONE ledger: the card's paper pick on a game
    must never block Tate's real ticket on it (and vice versa). None = any
    ledger (legacy behaviour). Legacy rows with a NULL is_paper count as real."""
    q = (
        session.query(ManualPick)
        .filter(ManualPick.game_id == game_id, ManualPick.side == side)
        .filter((ManualPick.market == market) | (ManualPick.market.is_(None)))
    )
    if is_paper is True:
        q = q.filter(ManualPick.is_paper.is_(True))
    elif is_paper is False:
        q = q.filter((ManualPick.is_paper.is_(False)) | (ManualPick.is_paper.is_(None)))
    return q.order_by(ManualPick.id).first()


def add_pick(
    session,
    *,
    game_id: Optional[int],
    season: int,
    week: Optional[int],
    home_team: str,
    away_team: str,
    line: float,
    price: Optional[int] = -110,
    stake: float = 1.0,
    is_paper: bool = False,
    market: str = "1H",
    book: Optional[str] = None,
    note: Optional[str] = None,
    reason: str = "manual",
    verdict: Optional[str] = None,
    gap: Optional[float] = None,
    ev: Optional[float] = None,
    hr_line: Optional[float] = None,
    placed_at: Optional[datetime] = None,
    blocker: Optional[str] = None,
    factors_json: Optional[str] = None,
) -> ManualPick:
    """Insert (and flush) one under pick. A paper pick always stakes
    `PAPER_STAKE` regardless of `stake` — nothing is at risk, and a flat unit
    keeps its record comparable. Does NOT check for duplicates: callers decide
    (see `existing_pick`)."""
    pick = ManualPick(
        game_id=game_id,
        season=season,
        week=week,
        home_team=home_team,
        away_team=away_team,
        side="under",
        market=market,
        line=line,
        price=price,
        stake=PAPER_STAKE if is_paper else stake,
        is_paper=bool(is_paper),
        book=book,
        placed_at=placed_at or datetime.utcnow(),
        note=note,
        graded=False,
        reason=reason or "manual",
        verdict_at_pick=verdict,
        gap_at_pick=gap,
        ev_at_pick=ev,
        hr_line_at_pick=hr_line,
        blocker=blocker,
        factors_json_at_pick=factors_json,
    )
    session.add(pick)
    session.flush()
    return pick
