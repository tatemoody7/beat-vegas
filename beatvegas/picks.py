"""The one code path that writes a `manual_picks` row — and the one that grades it.

`scripts/pick.py add` (Tate's own bets, from the terminal) and
`scripts/build_card.py` (the cloud card's PAPER picks) both insert through
`add_pick`, so the decision-tracking snapshot (reason / verdict / gap / ev /
Hard Rock line) and the paper-stake rule live in exactly one place.

`scripts/pick.py grade` (production) and `beatvegas/pipeline.py` (the week-sim
reveal) both grade through `grade_pick`, so the closing-line / Hard Rock /
unpriced-ticket rules live in exactly one place too.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .db.models import ManualPick, OddsSnapshot
from .grading import (
    clv_under,
    price_clv_under,
    trusted_first_half_total,
    under_result,
    units_won,
)
from .hardrock import HR_BOOK_KEY, normalize_book
from .lines import (
    book_closing_before_kickoff,
    book_closing_price_before_kickoff,
    closing_before_kickoff,
    fair_under_before_kickoff,
)

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


def graded_pick_fields(
    actual_first_half, line, price, stake, opening, closing, fair_open=None, fair_close=None
) -> dict:
    """Pure: the graded ManualPick fields for one pick + its line snapshots.
    `price` None (an unpriced line) grades the result and CLV but no units."""
    return {
        "actual_first_half_total": actual_first_half,
        "result": under_result(actual_first_half, line),
        "units": None if price is None else stake * units_won(actual_first_half, line, price),
        "opening_line": opening,
        "closing_line": closing,
        "clv": clv_under(line, closing) if closing is not None else None,
        "clv_prob": price_clv_under(fair_open, fair_close),
    }


def grade_pick(session, pick: ManualPick, game) -> bool:
    """Grade one ungraded pick against its (finished) game in place. Returns
    True when the pick was graded, False when the game isn't gradeable yet (not
    finished, or a known-false 1H zero — never grade that).

    Rules, shared by the terminal grader and the week-sim reveal:
    - a full-game ticket grades the final total; a 1H ticket grades the TRUSTED
      1H total (`grading.trusted_first_half_total`);
    - opening/closing come from PRE-KICKOFF snapshots only (a poll that ran
      after kickoff must not pollute the closing line / CLV);
    - a Hard Rock ticket grades against Hard Rock's OWN pre-kick close when the
      per-game close polls captured one (the number you could have bet), else
      the consensus close;
    - a pick logged on an unpriced Hard Rock line (price NULL) takes HR's own
      pre-kick closing price when one was captured; if none was, it grades for
      the record only (units stay None) rather than raising."""
    is_full = (pick.market or "1H") == "full"
    if is_full:
        if game.home_points is None or game.away_points is None:
            return False  # game not finished
        actual = game.home_points + game.away_points
        snap_market = "full_game_total"
    else:
        actual = trusted_first_half_total(
            game.first_half_total, game.home_points, game.away_points, game.first_half_source
        )
        if actual is None:
            return False  # not finished, or a known-false 0 — never grade it
        snap_market = "1H_total"
    snaps = (
        session.query(OddsSnapshot)
        .filter(OddsSnapshot.game_id == pick.game_id, OddsSnapshot.market == snap_market)
        .all()
    )
    opening, closing, _closing_at = closing_before_kickoff(snaps, game.start_date)
    if normalize_book(pick.book) == HR_BOOK_KEY:
        hr_open, hr_close, _ = book_closing_before_kickoff(snaps, game.start_date, HR_BOOK_KEY)
        if hr_close is not None:
            opening, closing = hr_open, hr_close
        if pick.price is None:
            pick.price = book_closing_price_before_kickoff(snaps, game.start_date, HR_BOOK_KEY)
    fair_open, fair_close = fair_under_before_kickoff(snaps, game.start_date)
    for k, v in graded_pick_fields(
        actual, pick.line, pick.price, pick.stake, opening, closing, fair_open, fair_close
    ).items():
        setattr(pick, k, v)
    pick.graded = True
    return True
