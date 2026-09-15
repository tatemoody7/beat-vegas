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

from .db.models import AppSetting, ManualPick, OddsSnapshot
from .grading import (
    clv_under,
    price_clv_under,
    trusted_first_half_total,
    under_result,
    units_won,
)
from .hardrock import normalize_book
from .lines import (
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


def model_read(session, game_id: Optional[int], market: str = "1H"):
    """(bv_line, under_score) to freeze onto a pick — OUR number and the model's
    score right now. Mirrors web/lib/picks.ts createPick so a terminal pick and a
    website pick carry the same snapshot.

    The model is 1H-only, so a full-game ticket gets (None, None). Prefers the
    MODEL row over the display-only `derived_lines` row (the same rule board.ts
    uses: post_derived_lines writes seconds after scoring, so ordering on
    recency alone picks the reference row), newest first, with `line_used` as the
    bv_line fallback for legacy rows predating the calibrated line."""
    if game_id is None or (market or "1H") != "1H":
        return None, None
    from .card import REFERENCE_MODEL_VERSION  # local: picks.py must not depend on the card
    from .db.models import Prediction

    row = (
        session.query(Prediction.bv_line, Prediction.under_score, Prediction.line_used)
        .filter(Prediction.game_id == game_id)
        .order_by(
            (Prediction.model_version == REFERENCE_MODEL_VERSION).asc(),
            Prediction.created_at.desc(),
        )
        .first()
    )
    if row is None:
        return None, None
    bv_line, under_score, line_used = row
    line = bv_line if bv_line is not None else line_used
    return line, None if under_score is None else int(under_score)


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
    is_bonus: bool = False,
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
    model_line: Optional[float] = None,
    model_score: Optional[int] = None,
) -> ManualPick:
    """Insert (and flush) one under pick. A paper pick always stakes
    `PAPER_STAKE` regardless of `stake` — nothing is at risk, and a flat unit
    keeps its record comparable. Does NOT check for duplicates: callers decide
    (see `existing_pick`).

    `model_line` / `model_score` freeze OUR number and the model's 0-100 score at
    log time. They were the one part of the snapshot only the website wrote
    (web/lib/picks.ts createPick), so until 2026-09-13 every card paper pick and
    every `pick.py add` left them NULL — which prints "—" in the picks table and
    drops the whole paper ledger out of decision-quality's agreed/against split,
    since that filters on `model_line_at_pick != null`. Callers get them from
    `model_read` (terminal) or off the card item (build_card)."""
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
        # Recorded here because this is the only moment it is knowable: after the
        # fact a stored price gives no clue whether it was the price at the
        # decision or something a later job wrote in.
        price_provenance="logged" if price is not None else "unknown",
        stake=PAPER_STAKE if is_paper else stake,
        is_paper=bool(is_paper),
        is_bonus=bool(is_bonus),
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
        model_line_at_pick=model_line,
        model_score_at_pick=model_score,
    )
    session.add(pick)
    session.flush()
    return pick


def graded_pick_fields(
    actual_first_half,
    line,
    price,
    stake,
    opening,
    closing,
    fair_open=None,
    fair_close=None,
    is_bonus: bool = False,
    closing_price=None,
) -> dict:
    """Pure: the graded ManualPick fields for one pick + its line snapshots.
    `price` None (an unpriced line) grades the result and CLV but no units.

    A BONUS bet is floored at zero units: the book funded the stake, so a loss
    costs nothing. The win side needs no adjustment - `units_won` already
    returns profit only, which is exactly what a bonus bet pays (the stake is
    not returned). Without the floor a losing $20 bonus would book -2 units
    against a bankroll that never lost them, and the whole point of this ledger
    is that the bankroll curve is true."""
    units = None if price is None else stake * units_won(actual_first_half, line, price)
    if units is not None and is_bonus:
        units = max(0.0, units)
    return {
        "actual_first_half_total": actual_first_half,
        "result": under_result(actual_first_half, line),
        "units": units,
        "opening_line": opening,
        "closing_line": closing,
        "clv": clv_under(line, closing) if closing is not None else None,
        "clv_prob": price_clv_under(fair_open, fair_close),
        # Stored beside `price`, never into it. See the ManualPick column comment.
        "closing_price": closing_price,
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
    # CLV is graded against the MARKET consensus, never a single book's close.
    #
    # A Hard Rock ticket used to grade at Hard Rock's own close, which reads like
    # the right idea -- you can only bet there, so that is your benchmark. It is
    # not: Hard Rock posts an off-centre rung as its main 1H total on 26 of 28
    # quotes inside 3 h of kickoff, and the close polls run inside 75 minutes. In
    # 2026 week 2 that put a rung in closing_line for every paper pick and
    # reported an average +1.67 points of line value where the market had
    # actually moved +0.43. Seven of eight sat at exactly -6.0: a constant rung
    # offset, not a line move. The six real tickets escaped only because their
    # `book` was NULL.
    #
    # consensus_open_close already drops non-centred quotes (lines.centred_snaps),
    # so a book still contributes its last real number.
    opening, closing, _closing_at = closing_before_kickoff(snaps, game.start_date)
    # THE CLOSING PRICE GOES IN ITS OWN COLUMN. It used to be written into
    # `pick.price` whenever a Hard Rock ticket had none, which silently turned the
    # price at the DECISION into the price at the CLOSE. Any price-based CLV over
    # those rows is then identically zero by construction -- and because nothing
    # marked them, they were indistinguishable from genuinely priced tickets and
    # would have diluted the metric toward zero, looking exactly like a null
    # result. An unknown decision price stays NULL; that is recoverable, a
    # fabricated one is not.
    #
    # Unlike the closing LINE (graded against consensus, because Hard Rock posts
    # an off-centre rung on 26 of 28 late quotes), the closing PRICE is correctly
    # the book's own: it is what you could have taken at that book at the close.
    book = normalize_book(pick.book)
    closing_price = (
        book_closing_price_before_kickoff(snaps, game.start_date, book) if book else None
    )
    fair_open, fair_close = fair_under_before_kickoff(snaps, game.start_date)
    for k, v in graded_pick_fields(
        actual,
        pick.line,
        pick.price,
        pick.stake,
        opening,
        closing,
        fair_open,
        fair_close,
        is_bonus=bool(getattr(pick, "is_bonus", False)),
        closing_price=closing_price,
    ).items():
        setattr(pick, k, v)
    pick.graded = True
    return True


RULE_PAUSED_KEY = "rule_paused"


def rule_paused(session) -> Optional[str]:
    """The note (or "") when real money is paused, None when it is not.

    Paused means the `rule_paused` row holds exactly the string "true" -- the
    Python writer controls the value, so nothing else is accepted. An absent row
    is "never switched on", not paused. A caller that cannot READ the row must
    refuse real money (fail closed); this helper does not swallow errors.
    """
    row = session.get(AppSetting, RULE_PAUSED_KEY)
    if row is None or (row.value or "").strip() != "true":
        return None
    return row.note or ""


def set_rule_paused(session, paused: bool, note: Optional[str] = None) -> AppSetting:
    """Write the switch. Idempotent: one row, replaced in place."""
    row = session.get(AppSetting, RULE_PAUSED_KEY)
    if row is None:
        row = AppSetting(key=RULE_PAUSED_KEY, value="false")
        session.add(row)
    row.value = "true" if paused else "false"
    row.note = (note or "").strip() or None
    row.updated_at = datetime.utcnow()
    return row
