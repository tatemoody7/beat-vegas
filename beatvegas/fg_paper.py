"""H-FG-P: paper FULL-GAME UNDERS from the full-game shadow engine, logged beside
the champion.

Registry row H-FG-P; design in docs/FG_MARKET.md; constants in
beatvegas/backtest/stopping.py::FG. One arm, `fg_under`: the champion's rule
unchanged on the full-game gap (Hard Rock's full-game line minus `bv_fg_v1`,
scripts/fg_shadow.py) -- the slate bar (top 20% by gap, `score.slate_bar`),
then the weekly cap of 5 by gap with the week's earlier rows holding their
slots. One paper UNDER per selected game at Hard Rock's UNDER price as captured
at the build, written to `challenger_picks` (market='full', side='under') and
NEVER to `manual_picks`, so nothing that feeds the bankroll, the cap, Results or
H-STOP-2 can see a row.

Every row here is PAPER. There is no real-money path through this file, no flag
that could create one, and `docs/BETTING_POLICY.md` (first-half unders) is not
amended by anything in it. Collection is OFF unless FG_COLLECT=1 is set in the
environment (card.yml sets it for the decision builds).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func

from .backtest.stopping import FG
from .challenger_picks import add_challenger_pick
from .db.models import ChallengerPick, Game, OddsSnapshot, Prediction
from .devig import is_centred_quote
from .hardrock import HR_BOOK_KEY
from .model.score import MODEL_VERSION, WEEKLY_BET_CAP, slate_bar
from .picks import freeze_factors

ARM = FG["arms"][0]  # "fg_under"
MARKET = FG["market"]  # "full"
FG_MODEL_VERSION = "bv_fg_v1"  # scripts/fg_shadow.py::FG_MODEL_VERSION
FG_SNAPSHOT_MARKET = "full_game_total"


def collection_enabled() -> bool:
    """FG_COLLECT=1 switches the arm on; unset is off (the default)."""
    return os.environ.get("FG_COLLECT") == "1"


def _hr_quotes(session, game_ids: List[int], now: datetime) -> Dict[int, Any]:
    """Each game's NEWEST Hard Rock full-game total captured at or before `now`."""
    rows = (
        session.query(OddsSnapshot)
        .filter(
            OddsSnapshot.game_id.in_(game_ids),
            OddsSnapshot.market == FG_SNAPSHOT_MARKET,
            func.lower(OddsSnapshot.book) == HR_BOOK_KEY,
            OddsSnapshot.captured_at <= now,
        )
        .order_by(OddsSnapshot.captured_at.asc(), OddsSnapshot.id.asc())
        .all()
    )
    out: Dict[int, Any] = {}
    for s in rows:  # ascending, so the newest wins
        out[int(s.game_id)] = s
    return out


def _predictions(session, game_ids: List[int], version: str) -> Dict[int, Prediction]:
    rows = (
        session.query(Prediction)
        .filter(Prediction.game_id.in_(game_ids), Prediction.model_version == version)
        .order_by(Prediction.created_at.asc(), Prediction.id.asc())
        .all()
    )
    return {int(p.game_id): p for p in rows}


def _logged_this_week(session, season: int, week: int, arm: str = ARM) -> List[int]:
    """Game ids the arm already logged this week, in placed order. Each holds
    its cap slot: a decision made Thursday is not undone Saturday."""
    rows = (
        session.query(ChallengerPick.game_id)
        .filter(
            ChallengerPick.arm == arm,
            ChallengerPick.market == MARKET,
            ChallengerPick.season == int(season),
            ChallengerPick.week == int(week),
        )
        .order_by(ChallengerPick.placed_at, ChallengerPick.id)
        .all()
    )
    return [int(g) for (g,) in rows]


def universe(session, season: int, week: int, now: datetime) -> List[Dict[str, Any]]:
    """H-FG-P's universe at this build: the week's games not yet kicked off whose
    newest Hard Rock full-game quote is centred and carries a line and an UNDER
    price, with a `bv_fg_v1` read. One dict per game with its gap."""
    games = (
        session.query(Game)
        .filter(Game.season == int(season), Game.week == int(week), Game.start_date > now)
        .all()
    )
    ids = [int(g.id) for g in games]
    if not ids:
        return []
    quotes = _hr_quotes(session, ids, now)
    fg = _predictions(session, ids, FG_MODEL_VERSION)
    champ = _predictions(session, ids, MODEL_VERSION)
    out = []
    for g in games:
        gid = int(g.id)
        q, p = quotes.get(gid), fg.get(gid)
        if q is None or p is None or p.bv_line is None:
            continue
        if q.line is None or q.under_price is None:
            continue
        if not is_centred_quote(q.over_price, q.under_price):
            continue
        out.append(
            {
                "game_id": gid,
                "home": g.home_team,
                "away": g.away_team,
                "kick": g.start_date,
                "hr_line": float(q.line),
                "hr_under_price": int(q.under_price),
                "hr_over_price": None if q.over_price is None else int(q.over_price),
                "hr_captured_at": q.captured_at,
                "bv_fg": float(p.bv_line),
                "gap": round(float(q.line) - float(p.bv_line), 4),
                "pred": p,
                "champion_bv_line": None
                if champ.get(gid) is None or champ[gid].bv_line is None
                else float(champ[gid].bv_line),
            }
        )
    return out


def select(
    items: List[Dict[str, Any]],
    logged: List[int],
    cap: Optional[int] = WEEKLY_BET_CAP,
    require_positive: bool = False,
) -> Dict[str, Any]:
    """The champion's rule on the full-game gap: qualify at or above the slate
    bar (ties qualify), then rank the not-yet-logged qualifiers by gap (desc),
    kickoff, away team behind the slots the week's logged rows already hold.
    Every item gets `qualifies` and, if it qualifies, `cap_rank`; `selected`
    is the cap_rank <= cap set, or every fresh qualifier when `cap` is None
    (H-ARM-FGU, uncapped). `require_positive` adds gap > 0 (H-ARM-FGU, the
    mirror of the first-half unders arm). Pure: no database, no clock."""
    bar = slate_bar([it["gap"] for it in items])
    done = set(logged)
    used = len(done)

    def ok(it: Dict[str, Any]) -> bool:
        return bar is not None and it["gap"] >= bar and (not require_positive or it["gap"] > 0)

    quals = [it for it in items if ok(it)]
    fresh = [it for it in quals if it["game_id"] not in done]
    fresh.sort(key=lambda it: (-it["gap"], it["kick"] or datetime.max, it["away"] or ""))
    for it in items:
        it["qualifies"] = ok(it)
        it["cap_rank"] = None
    for i, it in enumerate(fresh):
        it["cap_rank"] = used + i + 1
    return {
        "bar": bar,
        "n": len(items),
        "qualifying": len(quals),
        "held": used,
        "selected": [it for it in fresh if cap is None or it["cap_rank"] <= cap],
    }


def _frozen(it: Dict[str, Any], sel: Dict[str, Any]) -> str:
    """factors_json_at_pick: the market read at the build, the shadow's factor
    payload, and its input vector (the shadow freezes no GameRecord, so the
    vector rides in its own `factors_json`)."""
    f: Dict[str, Any] = {}
    raw = it["pred"].factors_json
    if raw:
        try:
            f = json.loads(raw) or {}
        except (TypeError, ValueError):
            f = {}
    features = f.pop("features", None) if isinstance(f, dict) else None
    chips = {
        "hr_fg_line": it["hr_line"],
        "hr_fg_under_price": it["hr_under_price"],
        "hr_fg_over_price": it["hr_over_price"],
        "hr_captured_at": None
        if it["hr_captured_at"] is None
        else it["hr_captured_at"].isoformat(),
        "bar": sel["bar"],
        "cap_rank": it["cap_rank"],
        "universe_n": sel["n"],
        "champion_1h_bv_line": it["champion_bv_line"],
    }
    return freeze_factors(chips, {"factors": f}, features)


def log_fg_picks(
    session,
    card: Dict,
    now: datetime,
    window_hours: Optional[float] = None,
    arm: str = ARM,
    cap: Optional[int] = WEEKLY_BET_CAP,
    require_positive: bool = False,
) -> Dict[str, Any]:
    """Insert this build's paper full-game UNDERS. Mirrors
    scripts/build_card.py::log_paper_picks: the same paper window (a selected
    game kicking off beyond `window_hours` waits for the next build, its rank
    unchanged), one row per game (a row already on file is never re-logged).
    Returns {"added", "universe", "bar", "qualifying", "held"}. Never touches
    `manual_picks`. H-ARM-FGU (2026-10-08) calls it with its own `arm`,
    `cap=None` and `require_positive=True`."""
    season, week = int(card["season"]), int(card["week"])
    items = universe(session, season, week, now)
    logged = _logged_this_week(session, season, week, arm)
    sel = select(items, logged, cap=cap, require_positive=require_positive)
    added = 0
    for it in sel["selected"]:
        kick = it["kick"]
        if window_hours is not None and kick is not None:
            if kick - now > timedelta(hours=window_hours):
                continue
        p = it["pred"]
        add_challenger_pick(
            session,
            arm=arm,
            game_id=it["game_id"],
            season=season,
            week=week,
            home_team=it["home"],
            away_team=it["away"],
            side="under",
            market=MARKET,
            line=it["hr_line"],
            price=it["hr_under_price"],
            book=HR_BOOK_KEY,
            slot=card.get("slot"),
            placed_at=now,
            blocker=None,
            arm_line_at_pick=it["bv_fg"],
            # The FIRST-HALF champion's number on the same game (1H scale), for
            # the paired diagnostic the row lists as secondary; never compared
            # to the full-game line.
            champion_line_at_pick=it["champion_bv_line"],
            gap_at_pick=it["gap"],
            factors_json_at_pick=_frozen(it, sel),
            refit_id=p.refit_id,
        )
        added += 1
    return {
        "added": added,
        "universe": sel["n"],
        "bar": sel["bar"],
        "qualifying": sel["qualifying"],
        "held": sel["held"],
    }


def summary_line(stats: Optional[Dict[str, Any]], enabled: bool) -> str:
    """The card summary's one line about the arm."""
    tag = "  FG (H-FG-P, paper full-game unders)"
    if not enabled:
        return f"{tag}: off (FG_COLLECT unset); no row written"
    if not stats:
        return f"{tag}: not run"
    if not stats["universe"]:
        return f"{tag}: no game with a Hard Rock full-game price and a bv_fg_v1 read"
    bar = "—" if stats["bar"] is None else f"{stats['bar']:.2f}"
    return (
        f"{tag}: universe {stats['universe']}, bar {bar}, {stats['qualifying']} qualify, "
        f"{stats['held']} held this week, +{stats['added']} logged"
    )


def arm_summary_line(stats: Optional[Dict[str, Any]]) -> str:
    """The card summary's line about the registered full-game arm H-ARM-FGU."""
    from .protocol import ARM_FG_UNDER

    tag = f"  ARM {ARM_FG_UNDER} (paper full-game unders, uncapped)"
    if not stats:
        return f"{tag}: not run"
    if not stats["universe"]:
        return f"{tag}: no game with a Hard Rock full-game price and a bv_fg_v1 read"
    bar = "—" if stats["bar"] is None else f"{stats['bar']:.2f}"
    return (
        f"{tag}: universe {stats['universe']}, bar {bar}, "
        f"{stats['qualifying']} qualify, +{stats['added']} logged"
    )
