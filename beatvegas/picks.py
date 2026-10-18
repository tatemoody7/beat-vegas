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

import json
import os
from datetime import datetime, timezone
from typing import Optional

from .consensus import fields_for_pick
from .db.models import AppSetting, JudgeReadingAudit, ManualPick, OddsSnapshot
from .grading import (
    clv_under,
    price_clv_under,
    trusted_first_half_total,
    under_result,
    units_won,
)
from .hardrock import normalize_book
from .lines import (
    CLOSE_EXCLUDED_BOOKS,
    book_closing_price_before_kickoff,
    closing_before_kickoff,
    fair_under_before_kickoff,
)

PAPER_STAKE = 1.0  # paper picks stake one flat unit so they grade as +/-1u


def bet_at_from_et(text: Optional[str]) -> Optional[datetime]:
    """`--bet-at "2026-09-25T16:10"` (Eastern wall clock, minute precision) to the
    naive-UTC value manual_picks.bet_at stores. None for None/blank; ValueError
    on a malformed string. Mirrors web/lib/et.ts etLocalToUtc."""
    if text is None or not str(text).strip():
        return None
    from .ci import ET  # local: picks.py must not depend on the CI module at import

    local = datetime.strptime(str(text).strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=ET)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


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


def model_read(session, game_id: Optional[int], market: str = "1H") -> Optional[float]:
    """OUR number (bv_line) to freeze onto a pick right now. Mirrors
    web/lib/picks.ts createPick so a terminal pick and a website pick carry the
    same snapshot.

    The model is 1H-only, so a full-game ticket gets None. Prefers the MODEL row
    over the display-only `derived_lines` row (the same rule board.ts uses:
    post_derived_lines writes seconds after scoring, so ordering on recency
    alone picks the reference row), newest first, with `line_used` as the
    bv_line fallback for legacy rows predating the calibrated line.

    Until 2026-10-04 this also returned the classifier's 0-100 under_score for
    `model_score_at_pick`; the classifier is retired
    (docs/CLASSIFIER_RETIREMENT.md) and that column stays NULL on new rows."""
    if game_id is None or (market or "1H") != "1H":
        return None
    row = _model_row(session, game_id)
    if row is None:
        return None
    bv_line, line_used, _refit = row
    return bv_line if bv_line is not None else line_used


def model_refit_id(session, game_id: Optional[int], market: str = "1H") -> Optional[int]:
    """`predictions.refit_id` of the SAME row `model_read` freezes the number
    from (2026-10-04) — which weekly refit the pick was logged against. None
    when there is no model row, the row predates the column, or the market is
    not the model's."""
    if game_id is None or (market or "1H") != "1H":
        return None
    row = _model_row(session, game_id)
    if row is None or row[2] is None:
        return None
    return int(row[2])


def _model_row(session, game_id: int):
    """(bv_line, line_used, refit_id) of the prediction row the pick is logged
    against: the model row over the display-only reference row, newest first —
    one ordering rule for every field frozen onto a ticket. Only the champion's
    versions are read (`CHAMPION_READ_VERSIONS`): a shadow engine's row is never
    frozen onto a ticket."""
    from .card import REFERENCE_MODEL_VERSION  # local: picks.py must not depend on the card
    from .db.models import Prediction
    from .model.score import CHAMPION_READ_VERSIONS

    return (
        session.query(Prediction.bv_line, Prediction.line_used, Prediction.refit_id)
        .filter(
            Prediction.game_id == game_id,
            Prediction.model_version.in_(CHAMPION_READ_VERSIONS),
        )
        .order_by(
            (Prediction.model_version == REFERENCE_MODEL_VERSION).asc(),
            Prediction.created_at.desc(),
        )
        .first()
    )


def freeze_factors(chips: Optional[dict], prediction: Optional[dict], features: Optional[dict]):
    """The JSON frozen onto a paper or challenger pick at the build
    (`factors_json_at_pick`, 2026-10-04): one dict with three keys so the
    post-mortem can slice by the market read, by the prediction's factor
    payload and by the model's own input vector long after the lines, the
    predictions row and the factor board have moved on.

      chips:    the market chips build_card has always frozen (unchanged shape)
      factors:  `predictions.factors_json` for the game as of the build, parsed
                (None when the prediction carries none)
      features: BV_FEATURE_COLS -> value for the game as scored, from the
                game's `game_records.features_json` (None when the game has no
                record; build_card counts those in its log line)

    NaN is refused (`allow_nan=False`): a frozen vector with NaN in it would
    not round-trip, and record_fields already cleaned the record to None."""
    import json

    f = (prediction or {}).get("factors")
    if f is None:
        f = (prediction or {}).get("factors_json")
    if isinstance(f, str):
        try:
            f = json.loads(f)
        except (TypeError, ValueError):
            f = None
    payload = {
        "chips": chips,
        "factors": f if isinstance(f, dict) else None,
        "features": features if isinstance(features, dict) else None,
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False)


def add_pick(
    session,
    *,
    game_id: Optional[int],
    season: int,
    week: Optional[int],
    home_team: str,
    away_team: str,
    line: float,
    price: Optional[int] = None,
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
    bet_at: Optional[datetime] = None,
    refit_id: Optional[int] = None,
    arm: Optional[str] = None,
) -> ManualPick:
    """Insert (and flush) one under pick. A paper pick always stakes
    `PAPER_STAKE` regardless of `stake` — nothing is at risk, and a flat unit
    keeps its record comparable. Does NOT check for duplicates: callers decide
    (see `existing_pick`).

    `model_line` freezes OUR number at log time. It was the one part of the
    snapshot only the website wrote (web/lib/picks.ts createPick), so until
    2026-09-13 every card paper pick and every `pick.py add` left it NULL — which
    prints "—" in the picks table and drops the whole paper ledger out of
    decision-quality's agreed/against split, since that filters on
    `model_line_at_pick != null`. Callers get it from `model_read` (terminal) or
    off the card item (build_card). `model_score_at_pick` is never written any
    more (classifier retired 2026-10-04); legacy rows keep theirs."""
    pick = ManualPick(
        arm=arm,
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
        # When the ticket was written, if that is not now (naive UTC; None =
        # logged at bet time). See the ManualPick.bet_at column comment.
        bet_at=bet_at,
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
        # Which weekly refit the number came from (model_refit_id / the card
        # item's prediction row). 2026-10-04.
        refit_id=refit_id,
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
    side: str = "under",
) -> dict:
    """Pure: the graded ManualPick fields for one pick + its line snapshots.
    `price` None (an unpriced line) grades the result and CLV but no units.
    `side` is "under" for every ledger row real money can hold; the H-NEGGAP-P
    paper OVERS (challenger_picks, 2026-09-28) pass "over": `result` stays the
    OUTCOME, units pay the over, and the no-vig price CLV flips sign (the over's
    fair price is one minus the under's). Stored `clv` is closing - bet for both.

    A BONUS bet is floored at zero units: the book funded the stake, so a loss
    costs nothing. The win side needs no adjustment - `units_won` already
    returns profit only, which is exactly what a bonus bet pays (the stake is
    not returned). Without the floor a losing $20 bonus would book -2 units
    against a bankroll that never lost them, and the whole point of this ledger
    is that the bankroll curve is true."""
    units = None if price is None else stake * units_won(actual_first_half, line, price, side)
    if units is not None and is_bonus:
        units = max(0.0, units)
    clv_prob = price_clv_under(fair_open, fair_close)
    if clv_prob is not None and side == "over":
        clv_prob = -clv_prob
    return {
        "actual_first_half_total": actual_first_half,
        "result": under_result(actual_first_half, line),
        "units": units,
        "opening_line": opening,
        "closing_line": closing,
        "clv": clv_under(line, closing) if closing is not None else None,
        "clv_prob": clv_prob,
        # Stored beside `price`, never into it. See the ManualPick column comment.
        "closing_price": closing_price,
    }


# The judge's columns (beatvegas/consensus.py::pick_fields), in the order the
# audit JSON lists them. Write-once: see apply_judge_reading.
JUDGE_FIELDS = (
    "cons_version",
    "cons_books",
    "cons_line",
    "cons_close_at",
    "cons_p_win",
    "cons_p_push",
    "ev_cons",
    "ev_hr",
    "cons_excluded",
)
JUDGE_REASONS = ("grade", "regrade", "backfill")
_FLOAT_TOL = 1e-9


def _judge_value(v):
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _same_judge_value(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None:
            return a is b
        return abs(float(a) - float(b)) <= _FLOAT_TOL
    return a == b


def apply_judge_reading(session, pick, fields: dict, *, reason: str, run_id=None) -> str:
    """Write the judge's columns ONCE; later recomputations are audited, not written.

    The 2026 programme's evidence is each pick's `ev_cons` as first read. A
    pick's reading could be recomputed three ways -- `grade_pick` at grading
    time (after `consensus_backfill` has usually read it an hour past kickoff),
    `pick.py grade --regrade`, and `consensus_backfill --write` without
    `--missing-only` -- and until 2026-10-18 each of them overwrote the columns
    in place, so a changed past reading left no trace. Now:

    - `cons_version` NULL (never read): every field in `fields` is written.
      Returns "written".
    - already read and `fields` agree with the stored values (floats within
      1e-9, datetimes equal): nothing happens. Returns "same".
    - already read and something differs: the pick is left exactly as it was
      and one `judge_reading_audit` row records the stored and the computed
      values, which fields differ, the reason and the run id. Returns "audited".

    `reason` is one of JUDGE_REASONS; `run_id` defaults to GITHUB_RUN_ID or '-'.
    """
    if reason not in JUDGE_REASONS:
        raise ValueError(f"unknown judge reason {reason!r}; expected one of {JUDGE_REASONS}")
    if getattr(pick, "cons_version", None) is None:
        for k in JUDGE_FIELDS:
            setattr(pick, k, fields.get(k))
        return "written"
    stored = {k: getattr(pick, k, None) for k in JUDGE_FIELDS}
    computed = {k: fields.get(k) for k in JUDGE_FIELDS}
    changed = [k for k in JUDGE_FIELDS if not _same_judge_value(stored[k], computed[k])]
    if not changed:
        return "same"
    session.add(
        JudgeReadingAudit(
            ledger="manual" if isinstance(pick, ManualPick) else "challenger",
            pick_id=pick.id,
            computed_at=datetime.utcnow(),
            run_id=str(run_id or os.environ.get("GITHUB_RUN_ID") or "-"),
            reason=reason,
            changed=",".join(changed),
            stored_json=json.dumps({k: _judge_value(v) for k, v in stored.items()}, default=str),
            computed_json=json.dumps(
                {k: _judge_value(v) for k, v in computed.items()}, default=str
            ),
        )
    )
    return "audited"


def grade_pick(session, pick, game, judge_reason: str = "grade") -> bool:
    """Grade one ungraded pick against its (finished) game in place. Returns
    True when the pick was graded, False when the game isn't gradeable yet (not
    finished, or a known-false 1H zero — never grade that).

    `pick` is a ManualPick or a ChallengerPick: this reads only the decision
    fields both carry and writes only the names `graded_pick_fields` returns, so
    the H-INSEASON challenger arms are graded by the champion's own code instead
    of a second implementation that could drift from it. It never queries or
    writes a ledger table itself, so passing one row can never touch the other.

    Rules, shared by the terminal grader and the week-sim reveal:
    - a full-game ticket grades the final total; a 1H ticket grades the TRUSTED
      1H total (`grading.trusted_first_half_total`);
    - opening/closing come from PRE-KICKOFF snapshots only (a poll that ran
      after kickoff must not pollute the closing line / CLV);
    - the closing LINE is the centred CONSENSUS close from pre-kickoff snapshots
      (never a single book's rung -- see the comment below), and the time that
      close was last confirmed is stored in `closing_captured_at` so a stale
      "close" can be told from one inside lines.REAL_1H_CLOSE_WINDOW_H;
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
    # so a book still contributes its last real number. Since 2026-10-11 the close
    # also never counts Hard Rock, Fliff or the feed's synthetic consensus row
    # (lines.CLOSE_EXCLUDED_BOOKS, the judge's own set): Hard Rock's late rungs
    # pass the centred filter at -140/-160 and sit 1-1.5 points under the market.
    opening, closing, closing_at = closing_before_kickoff(
        snaps, game.start_date, exclude=CLOSE_EXCLUDED_BOOKS
    )
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
    side = (getattr(pick, "side", None) or "under").lower()
    closing_price = (
        book_closing_price_before_kickoff(snaps, game.start_date, book, side=side) if book else None
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
        side=side,
    ).items():
        setattr(pick, k, v)
    # The age of the close is a fact about the close, stored beside it. A dropped
    # pre-kick poll makes Friday's sweep quote "the close" silently otherwise.
    pick.closing_captured_at = closing_at
    # Line value at the wager's exact terms (beatvegas/consensus.py): the 2026
    # research program's judge, read from the same pre-kick snapshots. It never
    # blocks a grade -- a missing reading records why in `cons_excluded` -- and
    # it is WRITE-ONCE: consensus_backfill usually read the pick an hour after
    # kickoff, and a grade (or regrade) that computes something else is audited,
    # never written (apply_judge_reading).
    apply_judge_reading(
        session, pick, fields_for_pick(snaps, game.start_date, pick), reason=judge_reason
    )
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
