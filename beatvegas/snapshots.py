"""Decision-time state, one row per (build, game), read out of the `cards` payloads.

The `cards` table keeps every build as one JSON blob and the only reader before
2026-09-15 (`scripts/post_mortem.py::load_live`) kept the newest item per game,
which collapses the builds. The timing question ("which build should you act on?")
and the gate question ("what did each gate block, and how did those games do?")
both need the builds kept apart, so this module flattens them and attaches the two
closes a decision is graded against. It reads; it never writes. It is not the
`decision_snapshots` table of the roadmap -- that waits until these studies say it
is worth a table (docs/HYPOTHESES.md).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd
from sqlalchemy import text

from .ci import ET, SLOT_BUILD_ET, SLOT_GATE_ET
from .db.models import Card, Game, OddsSnapshot
from .grading import trusted_first_half_total
from .hardrock import HR_BOOK_KEY
from .lines import (
    REAL_1H_CLOSE_WINDOW_H,
    book_closing_before_kickoff,
    book_closing_price_before_kickoff,
    consensus_as_of,
    real_closes,
)

# The four whole-week decision builds (beatvegas/ci.py). Anything else is labelled
# so a study can keep it out of a comparison of the four: the retired week-1 morning
# schedule wrote no slot at all; week 2's Tuesday and Wednesday builds carry the
# pre-rename names `morning` / `afternoon` (2026-09-08/09, before PR #89) and are
# NOT relabelled as tue_pm -- the study says what it has, not what it would have
# been called; `manual` is a hand dispatch (always a preview).
FOUR_BUILD_SLOTS = ("tue_pm", "thu_pm", "fri_pm", "sat_am")
LEGACY_SLOTS = ("morning", "afternoon")

# Item fields copied straight off the card payload. Cards built before a field
# existed carry None for it (never inferred): `qb_out` since 2026-09-15,
# `hr_vs_market` / `gate_blocker` since 2026-09-07.
ITEM_FIELDS = (
    "away",
    "home",
    "kick",
    "tier",
    "blocker",
    "hr_line",
    "hr_price",
    "hr_open",
    "market_line",
    "fair_under",
    "fair_source",
    "hr_vs_market",
    "ev",
    "bv_line",
    "under_score",
    "games_played",
    "qb_out",
    "gap",
    "gap_basis",
    "kill_line",
    "kill_price",
    "qualifies",
    "paper_blocker",
    "paper_logged",
    "cap_rank",
    "over_cap",
    "gate_blocker",
    "full_game_total",
    "spread",
)


def schedule_of(slot: Optional[str]) -> str:
    """'four' for the four decision builds; 'legacy' for week 2's pre-rename
    `morning` / `afternoon` builds; 'daily' for the retired week-1 schedule (no
    slot on the payload); 'manual' for a dispatched preview."""
    if slot in FOUR_BUILD_SLOTS:
        return "four"
    if slot in LEGACY_SLOTS:
        return "legacy"
    if slot is None:
        return "daily"
    return "manual"


def hr_closes(session, game_ids: Sequence[int], kickoffs: Dict[int, datetime]) -> Dict[int, float]:
    """game_id -> Hard Rock's OWN pre-kickoff 1H close, strict centring
    (lines.book_closing_before_kickoff); games without one are simply absent.
    Moved here from scripts/post_mortem.py so the studies do not import a script."""
    if not game_ids:
        return {}
    by_game: Dict[int, List] = {}
    ids = list(game_ids)
    for i in range(0, len(ids), 1000):
        for snap in (
            session.query(OddsSnapshot)
            # Every book, not just Hard Rock: its alternate lines are told apart
            # by the distance from the other books (lines.hr_rung_flags).
            .filter(
                OddsSnapshot.market == "1H_total",
                OddsSnapshot.game_id.in_(ids[i : i + 1000]),
            )
            .all()
        ):
            by_game.setdefault(snap.game_id, []).append(snap)
    out: Dict[int, float] = {}
    for gid, snaps in by_game.items():
        _open, close, _at = book_closing_before_kickoff(snaps, kickoffs.get(gid), HR_BOOK_KEY)
        if close is not None:
            out[gid] = float(close)
    return out


def consensus_closes(
    session, game_ids: Sequence[int], kickoffs: Dict[int, datetime]
) -> Dict[int, float]:
    """game_id -> the consensus 1H close inside REAL_1H_CLOSE_WINDOW_H of kickoff
    (lines.real_closes); absent when no book closed the game. Never proxied."""
    return real_closes(session, game_ids, kickoffs, within_hours=REAL_1H_CLOSE_WINDOW_H)


def kickoffs_for(session, game_ids: Sequence[int]) -> Dict[int, datetime]:
    """game_id -> `games.start_date` (naive UTC) for every id that has one. The
    lookup every close reader needs first; a game without a kickoff is absent,
    and the readers treat an absent kickoff as 'no window can be proved'."""
    ids = [int(g) for g in game_ids]
    out: Dict[int, datetime] = {}
    for i in range(0, len(ids), 1000):
        for gid, start in (
            session.query(Game.id, Game.start_date).filter(Game.id.in_(ids[i : i + 1000])).all()
        ):
            if start is not None:
                out[int(gid)] = start
    return out


def _snaps_1h_by_game(session, game_ids: Sequence[int], book: Optional[str] = None):
    by_game: Dict[int, List] = {}
    ids = [int(g) for g in game_ids]
    for i in range(0, len(ids), 1000):
        q = session.query(OddsSnapshot).filter(
            OddsSnapshot.market == "1H_total", OddsSnapshot.game_id.in_(ids[i : i + 1000])
        )
        if book is not None:
            q = q.filter(OddsSnapshot.book == book)
        for snap in q.all():
            by_game.setdefault(snap.game_id, []).append(snap)
    return by_game


def hr_close_prices(
    session, game_ids: Sequence[int], kickoffs: Dict[int, datetime]
) -> Dict[int, int]:
    """game_id -> Hard Rock's closing UNDER price (American), strict centring,
    latest priced pre-kick snapshot (lines.book_closing_price_before_kickoff).
    Absent when Hard Rock has no priced centred pre-kick row -- never -110."""
    if not game_ids:
        return {}
    out: Dict[int, int] = {}
    # Every book: the Hard Rock rule needs the field (lines.hr_rung_flags).
    for gid, snaps in _snaps_1h_by_game(session, game_ids).items():
        price = book_closing_price_before_kickoff(snaps, kickoffs.get(gid), HR_BOOK_KEY)
        if price is not None:
            out[gid] = int(price)
    return out


# ---------------------------------------------------------------- decision lines

# The candidate CLV clock (owner's decision, 2026-09-23): a candidate's bet line
# on a game is the consensus 1H line as it stood when that week's Friday
# `fri_pm` build window OPENED (beatvegas/ci.py::SLOT_GATE_ET, 3:45pm ET), the
# look Tate takes before the weekend. The rule string names the slot so a
# report can say which clock it used; any slot in SLOT_GATE_ET is accepted, the
# default is Friday.
DEFAULT_DECISION_RULE = "consensus_as_of(fri_pm)"
_RULE = re.compile(r"^consensus_as_of\((?P<slot>[a-z_]+)\)$")


def parse_decision_rule(rule: str) -> str:
    """The slot named by a `consensus_as_of(<slot>)` rule string; ValueError on
    anything else, so a typo cannot silently become a different clock."""
    m = _RULE.match(rule.strip())
    if not m or m.group("slot") not in SLOT_GATE_ET:
        raise ValueError(
            f"unknown decision rule {rule!r}; expected consensus_as_of(<slot>) with slot in "
            f"{sorted(SLOT_GATE_ET)}"
        )
    return m.group("slot")


def decision_instant(kickoff: datetime, slot: str = "fri_pm") -> Optional[datetime]:
    """The naive-UTC instant a `slot` build window opened in the game's week: the
    most recent occurrence of the slot's weekday on or before the kickoff's ET
    date, at the window's ET open (SLOT_GATE_ET[slot][0]). None when that
    instant is not strictly before kickoff (a Thursday game against the Friday
    clock, a Friday noon kickoff) -- there was no such decision to grade."""
    if kickoff is None:
        return None
    iso_weekday, _build_time = SLOT_BUILD_ET[slot]
    open_et: time = SLOT_GATE_ET[slot][0]
    kick_utc = kickoff.replace(tzinfo=timezone.utc) if kickoff.tzinfo is None else kickoff
    kick_et = kick_utc.astimezone(ET)
    back = (kick_et.isoweekday() - iso_weekday) % 7
    day = kick_et.date() - timedelta(days=back)
    instant_et = datetime.combine(day, open_et, tzinfo=ET)
    instant = instant_et.astimezone(timezone.utc).replace(tzinfo=None)
    kick_naive = kick_utc.replace(tzinfo=None)
    return instant if instant < kick_naive else None


def decision_lines(
    session,
    game_ids: Sequence[int],
    kickoffs: Dict[int, datetime],
    rule: str = DEFAULT_DECISION_RULE,
) -> Dict[int, float]:
    """game_id -> the consensus 1H line as of the build-window instant `rule`
    names (lines.consensus_as_of over every 1H snapshot: last centred quote per
    book at or before the instant, median across books). Absent when the market
    had not posted by then or the instant does not precede kickoff. This is the
    CANDIDATE's bet line for CLV; it exists only where the snapshots do (2026+)."""
    slot = parse_decision_rule(rule)
    if not game_ids:
        return {}
    out: Dict[int, float] = {}
    for gid, snaps in _snaps_1h_by_game(session, game_ids).items():
        t = decision_instant(kickoffs.get(gid), slot)
        if t is None:
            continue
        line, _spread = consensus_as_of(snaps, t)
        if line is not None:
            out[gid] = float(line)
    return out


def _payload(card: Card) -> Optional[Dict[str, Any]]:
    try:
        p = json.loads(card.payload)
    except (TypeError, ValueError):
        return None
    return p if isinstance(p, dict) else None


def _hours(kick: Optional[datetime], built_at: Optional[datetime]) -> Optional[float]:
    if kick is None or built_at is None:
        return None
    return round((kick - built_at).total_seconds() / 3600.0, 2)


def build_rows(session, season: int, cards: Optional[Iterable[Card]] = None) -> pd.DataFrame:
    """One row per (card build, game) for every card of `season`, every item kept
    (all tiers, priced or not), plus the game's realized first half (trusted,
    else None) and the two closes. Empty frame with the right columns when the
    season has no cards."""
    if cards is None:
        cards = (
            session.query(Card).filter(Card.season == season).order_by(Card.built_at.asc()).all()
        )
    cards = list(cards)
    rows: List[Dict[str, Any]] = []
    for c in cards:
        p = _payload(c)
        if not p:
            continue
        slot = p.get("slot")
        for it in p.get("items") or []:
            if it.get("game_id") is None:
                continue
            row: Dict[str, Any] = {
                "card_id": c.id,
                "built_at": c.built_at,
                "slot": slot,
                "status": p.get("status"),
                "schedule": schedule_of(slot),
                "week": p.get("week", c.week),
                "game_id": int(it["game_id"]),
            }
            for k in ITEM_FIELDS:
                row[k] = it.get(k)
            rows.append(row)
    cols = [
        "card_id",
        "built_at",
        "slot",
        "status",
        "schedule",
        "week",
        "game_id",
        *ITEM_FIELDS,
        "kickoff",
        "hours_to_kick",
        "game_week",
        "fh",
        "close_line",
        "hr_close",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    ids = sorted(df["game_id"].unique().tolist())
    kickoffs: Dict[int, datetime] = {}
    ginfo: Dict[int, Dict[str, Any]] = {}
    for i in range(0, len(ids), 1000):
        for g in session.query(Game).filter(Game.id.in_(ids[i : i + 1000])).all():
            if g.start_date is not None:
                kickoffs[g.id] = g.start_date
            ginfo[g.id] = {
                "game_week": g.week,
                "fh": trusted_first_half_total(
                    g.first_half_total, g.home_points, g.away_points, g.first_half_source
                ),
            }
    closes = consensus_closes(session, ids, kickoffs)
    hrc = hr_closes(session, ids, kickoffs)
    df["kickoff"] = df["game_id"].map(kickoffs)
    df["hours_to_kick"] = [_hours(k, b) for k, b in zip(df["kickoff"], df["built_at"])]
    df["game_week"] = df["game_id"].map(lambda g: ginfo.get(g, {}).get("game_week"))
    df["fh"] = df["game_id"].map(lambda g: ginfo.get(g, {}).get("fh"))
    df["close_line"] = df["game_id"].map(closes)
    df["hr_close"] = df["game_id"].map(hrc)
    for col in (
        "hr_line",
        "hr_price",
        "market_line",
        "bv_line",
        "gap",
        "ev",
        "fh",
        "close_line",
        "hr_close",
        "hours_to_kick",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[cols]


HIST_SCOPE = "hist_2023_25"


def postmortem_hist_rows(session, seasons: Sequence[int]) -> pd.DataFrame:
    """FBS rows of the latest hist_2023_25 post-mortem run with a real close, a graded
    first half and the stored walk-forward bv_line -- the 1,902-game cut every
    2023-25 study reads. Columns: game_id, season, week, spread_abs, line_real, fh,
    bv_line, kickoff. `df.attrs["run_id"]` names the run."""
    run_id = session.execute(
        text(
            "select run_id from postmortem_runs where scope = :s order by computed_at desc limit 1"
        ),
        {"s": HIST_SCOPE},
    ).scalar()
    rows = (
        session.execute(
            text(
                """
            select g.game_id, g.season, g.week, g.spread_abs, g.line_real, g.fh, g.bv_line,
                   gm.start_date as kickoff
            from postmortem_games g left join games gm on gm.id = g.game_id
            where g.run_id = :r and g.scope = :s and g.division = 'fbs'
              and g.line_real is not null and g.fh is not null and g.bv_line is not null
            """
            ),
            {"r": run_id, "s": HIST_SCOPE},
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    df.attrs["run_id"] = run_id
    if len(df):
        df = df[df["season"].isin([int(x) for x in seasons])].reset_index(drop=True)
        df.attrs["run_id"] = run_id
    return df
