"""Reading and writing the H-INSEASON challenger ledger.

The mirror of `picks.py` for `challenger_picks`, kept as its own module for the
same reason the table is its own table: nothing that feeds the bankroll, the
5-bet cap, Results or H-STOP's observation set should be one import away from
these rows. Registry row H-INSEASON-P; spec in docs/INSEASON_PAPER.md.

Every row here is PAPER. There is no real-money path through this file and no
flag that could create one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .challenger import SeasonRead, season_read
from .db.models import ChallengerPick, Game, Prediction


def completed_season_rows(
    session, season: int, before: datetime, model_version: str
) -> List[Dict[str, Any]]:
    """The season's games whose result was on file STRICTLY BEFORE `before`.

    The as-of rule, enforced in SQL rather than remembered: a game contributes
    only if it kicked off before this build AND its first half is graded. No
    game can inform its own intercept, and no later game can inform an earlier
    one, because a build only ever sees its own past.
    """
    rows = (
        session.query(Prediction.bv_line, Prediction.bv_intercept, Game.first_half_total)
        .join(Game, Game.id == Prediction.game_id)
        .filter(
            Game.season == int(season),
            Game.start_date.isnot(None),
            Game.start_date < before,
            Game.first_half_total.isnot(None),
            Prediction.model_version == model_version,
            Prediction.bv_line.isnot(None),
            Prediction.bv_intercept.isnot(None),
        )
        .all()
    )
    return [{"bv_line": r[0], "bv_intercept": r[1], "first_half_total": r[2]} for r in rows]


def season_read_as_of(session, season: int, before: datetime, model_version: str) -> SeasonRead:
    """What the season has told us about the model's level, as of this build."""
    return season_read(completed_season_rows(session, season, before, model_version))


def current_intercept(session, season: int, model_version: str) -> Optional[float]:
    """`c_prior` for this season, read off the rows the champion just wrote.

    It is one number per season (the training window is prior seasons only), so
    any scored row of the season carries it.
    """
    row = (
        session.query(Prediction.bv_intercept)
        .join(Game, Game.id == Prediction.game_id)
        .filter(
            Game.season == int(season),
            Prediction.model_version == model_version,
            Prediction.bv_intercept.isnot(None),
        )
        .first()
    )
    return None if row is None else float(row[0])


def existing_challenger_pick(session, game_id: int, arm: str, market: str = "1H"):
    """This arm's already-logged observation on this game, or None.

    One canonical observation per decision per arm. Arms never block each other
    and can never block or be blocked by the champion's ledger -- different
    table entirely.
    """
    q = session.query(ChallengerPick).filter(
        ChallengerPick.game_id == int(game_id), ChallengerPick.arm == arm
    )
    if market == "1H":
        q = q.filter((ChallengerPick.market == "1H") | (ChallengerPick.market.is_(None)))
    else:
        q = q.filter(ChallengerPick.market == market)
    return q.first()


def add_challenger_pick(session, **fields: Any) -> ChallengerPick:
    """Insert one arm's paper observation. Stake is always one flat unit, so
    units and ROI are comparable to the champion's paper ledger."""
    fields.setdefault("side", "under")
    fields.setdefault("market", "1H")
    fields.setdefault("stake", 1.0)
    fields.setdefault("graded", False)
    fields.setdefault("placed_at", datetime.utcnow())
    row = ChallengerPick(**fields)
    session.add(row)
    session.flush()
    return row


def grade_challenger_picks(session, season: int, regrade: bool = False) -> int:
    """Grade the arms' observations with the champion's own grader.

    `picks.grade_pick` reads only the decision fields both ledgers carry and
    writes only the names `graded_pick_fields` returns, so the arms are settled
    by exactly the rules the real ledger is settled by -- the trusted 1H total,
    pre-kickoff snapshots only, consensus close for the line and the book's own
    close for the price. A second implementation here would be a second set of
    rules to keep in step, which is how the CLV sign got inverted once already.
    """
    from .picks import grade_pick  # local: keeps the money path out of import order

    q = session.query(ChallengerPick).filter(
        ChallengerPick.season == int(season), ChallengerPick.game_id.isnot(None)
    )
    if not regrade:
        q = q.filter(ChallengerPick.graded == False)  # noqa: E712
    graded = 0
    for p in q.all():
        g = session.query(Game).filter(Game.id == p.game_id).one_or_none()
        if g is not None and grade_pick(session, p, g):
            graded += 1
    return graded
