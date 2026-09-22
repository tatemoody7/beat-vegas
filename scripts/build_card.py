#!/usr/bin/env python
"""Build the week's bet card and publish it to the Board (`cards` table).

Runs in GitHub Actions (`.github/workflows/card.yml`: four decision builds a
week — tue_pm/thu_pm/fri_pm ~4:05pm ET and sat_am ~8:05am ET; slots and paper
windows in beatvegas/ci.py). Pure rules live in beatvegas/card.py; this script only loads
the inputs, writes one `cards` row per build (history; the newest row is the
live card) and logs every QUALIFYING game (Hard Rock's 1H line >= BET_GAP_PTS
above ours, any tier) as a PAPER pick tagged with its blocker, through the same
code path as `pick.py add` (beatvegas.picks.add_pick), never twice for one game.

    python scripts/build_card.py                      # active season/week
    python scripts/build_card.py --season 2026 --week 3
    python scripts/build_card.py --dry-run            # print the payload, write nothing
    python scripts/build_card.py --slot fri_pm \
        --sweep-status "$RUNNER_TEMP/sweep_status.json" \
        --preview-status "$RUNNER_TEMP/preview_status.json"

--slot sets the card's clean status (beatvegas.ci.CARD_STATUS_BY_SLOT); the two
status files say whether the sweep and the research preview actually covered the
slate. Any failure marks the games it touched paper only, the card status
"degraded", and prints it as line 2 of the summary ("CARD STATUS: ...").

Exit 1 when the Hard Rock universe has games but the card came out empty (every
game already kicked off, or the inputs are missing) so the run goes red instead
of publishing nothing quietly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from beatvegas.card import REFERENCE_MODEL_VERSION, build_card, card_games, degraded_inputs
from beatvegas.challenger import (
    PAPER_ARMS,
    arm_context,
    arm_label,
    arm_predictions,
)
from beatvegas.challenger_picks import (
    add_challenger_pick,
    current_intercept,
    existing_challenger_pick,
    season_read_as_of,
)
from beatvegas.db.models import (
    Card,
    Game,
    GamePreview,
    ManualPick,
    OddsSnapshot,
    Prediction,
    TeamTempo,
)
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.hardrock import HR_BOOK_KEY, hr_universe_game_ids
from beatvegas.model.score import MODEL_VERSION
from beatvegas.picks import add_pick, existing_pick


def hr_universe(session, season: int, week: int) -> List[Dict]:
    """The week's games Hard Rock has priced a full-game total on, as card rows."""
    ids = hr_universe_game_ids(session, season, week)
    if not ids:
        return []
    rows = session.query(Game).filter(Game.id.in_(ids)).order_by(Game.start_date, Game.id).all()
    return [
        {
            "game_id": g.id,
            "away": g.away_team,
            "home": g.home_team,
            "kick": g.start_date,
            "total": g.full_game_total,
            "spread": g.spread,
        }
        for g in rows
    ]


def bet_slots_this_week(session, season: int, week: int) -> Set[int]:
    """Game ids with a BET-verdict 1H pick already logged this week (paper or
    real; over-cap paper picks excluded). They hold their cap slot."""
    rows = (
        session.query(ManualPick.game_id)
        .filter(
            ManualPick.season == season,
            ManualPick.week == week,
            (ManualPick.market == "1H") | (ManualPick.market.is_(None)),
            ManualPick.verdict_at_pick == "BET",
            (ManualPick.blocker.is_(None)) | (ManualPick.blocker == "none"),
            ManualPick.game_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def real_bets_this_week(session, season: int, week: int) -> Set[int]:
    """Game ids with a REAL, BANKROLL-FUNDED 1H pick this week (is_paper False
    or legacy NULL, and not a bonus bet).
    Passed to build_card as prior_bet_game_ids: a real ticket on a game NOT on
    this card (a Thursday game already played) consumes a weekly-cap slot;
    apply_weekly_cap ignores ids that are on the card (they rank via `held`).

    A BONUS bet is excluded: the cap exists to limit how much of the $100 roll
    is at risk in a week, and the book funded that stake, so a free bet must not
    crowd out a real one."""
    rows = (
        session.query(ManualPick.game_id)
        .filter(
            ManualPick.season == season,
            ManualPick.week == week,
            (ManualPick.is_paper.is_(False)) | (ManualPick.is_paper.is_(None)),
            (ManualPick.is_bonus.is_(False)) | (ManualPick.is_bonus.is_(None)),
            (ManualPick.market == "1H") | (ManualPick.market.is_(None)),
            ManualPick.game_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def load_inputs(session, game_ids: List[int]) -> tuple:
    """(snapshots, predictions, previews) as the plain dicts build_card takes."""
    if not game_ids:
        return [], [], []
    snaps = [
        {
            "game_id": s.game_id,
            "book": s.book,
            "line": s.line,
            "over_price": s.over_price,
            "under_price": s.under_price,
            "captured_at": s.captured_at,
        }
        for s in session.query(OddsSnapshot)
        .filter(OddsSnapshot.game_id.in_(game_ids), OddsSnapshot.market == "1H_total")
        .all()
    ]
    preds = [
        {
            "game_id": p.game_id,
            "model_version": p.model_version,
            "bv_line": p.bv_line,
            "bv_intercept": p.bv_intercept,
            "under_score": p.under_score,
            "line_used": p.line_used,
            # the stored pace chip: degraded_inputs reads it
            "factors_json": p.factors_json,
        }
        for p in session.query(Prediction)
        .filter(
            Prediction.game_id.in_(game_ids),
            Prediction.model_version.in_([MODEL_VERSION, REFERENCE_MODEL_VERSION]),
        )
        .all()
    ]
    previews = [
        {
            "game_id": p.game_id,
            "qb_out": p.qb_out,
            "qb_out_detail": p.qb_out_detail,
            # how fresh the QB read is (a preview written before today is stale)
            "updated_at": p.updated_at,
        }
        for p in session.query(GamePreview).filter(GamePreview.game_id.in_(game_ids)).all()
    ]
    return snaps, preds, previews


def load_status(path: Optional[str]) -> Optional[Dict]:
    """A --status-file written by poll_lines.py / research_preview.py, or None.

    None means "that step did not run" (a dispatch with no forced sweep skips it
    when today's snapshots already exist, and the workflow only writes the
    preview file when the step ran), which is NOT a failure. A file that is missing or
    unreadable is treated the same way rather than degrading a healthy card."""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"[card] WARNING: could not read status file {path}: {e}")
        return None
    return data if isinstance(data, dict) else None


def tempo_row_count(session, season: int, week: int) -> int:
    """How many teams the pace lookup can actually see for THIS card's
    (season, week) — the same filter beatvegas.etl.context.pace_for_games
    reads pace with. 0 means the TeamRankings mapper stored nothing for the
    week and no game on the card has a real pace. Prior seasons and weeks are
    deliberately not counted: they would hide a current-week failure."""
    return (
        session.query(TeamTempo.team)
        .filter(
            TeamTempo.season == season,
            TeamTempo.week == week,
            TeamTempo.seconds_per_play.isnot(None),
        )
        .distinct()
        .count()
    )


PAPER_VERDICT = {"BET": "BET", "EDGE": "WATCH", "PASS": "PASS"}


def log_paper_picks(
    session, card: Dict, now: datetime, window_hours: Optional[float] = None
) -> int:
    """Insert one PAPER pick per QUALIFYING item (Hard Rock's 1H line >=
    BET_GAP_PTS above ours — any tier) that has no paper pick yet, tagged with
    the gate that blocked a real bet (`blocker`: none = BET, price, off_market,
    no_fair_price, qb_out, early_season, cap, degraded). Tate's real ticket on the same game never blocks it and is
    never blocked by it (per-ledger guard). `window_hours` restricts logging to
    games kicking off within that many hours — the games this build is the
    DECISION build for (beatvegas.ci.PAPER_WINDOW_HOURS: the midweek builds take
    the gap to the next look, fri_pm and sat_am take the rest of the week).
    None = every qualifying game still on the card. Freezes OUR number
    (`model_line`/`model_score`) alongside Hard Rock's, marks `paper_logged`, and
    returns the number inserted."""
    inserted = 0
    for it in card["items"]:
        if not it.get("qualifies"):
            continue
        if window_hours is not None and it.get("kick"):
            kick = datetime.fromisoformat(it["kick"].replace("Z", "+00:00")).replace(tzinfo=None)
            if kick - now > timedelta(hours=window_hours):
                continue
        gid = it["game_id"]
        if existing_pick(session, gid, "1H", is_paper=True) is not None:
            it["paper_logged"] = True
            continue
        blocker = "cap" if it.get("over_cap") else (it.get("paper_blocker") or "none")
        # Display chips + the market read frozen at the pick, so the post-mortem
        # can slice by them even after the lines move (never gates).
        chips = {
            k: it.get(k)
            for k in (
                "total_band",
                "hook_side",
                "key_dist",
                "full_game_total",
                "spread",
                "hr_vs_market",
                "fair_source",
                "fair_under",
                "market_line",
            )
        }
        # gate_blocker: on a degraded pick, the gate result the failed input
        # overrode ("none" = every gate passed); null otherwise.
        chips.update(
            {
                "tier": it["tier"],
                "cap_rank": it.get("cap_rank"),
                "gate_blocker": it.get("gate_blocker"),
            }
        )
        add_pick(
            session,
            game_id=gid,
            season=card["season"],
            week=card["week"],
            home_team=it["home"],
            away_team=it["away"],
            market="1H",
            line=it["hr_line"],
            price=it["hr_price"],  # None when Hard Rock has not priced the line yet
            is_paper=True,
            book=HR_BOOK_KEY,
            note=f"card {now:%Y-%m-%d} [{blocker}]: {it['action']}",
            reason="model_gap",
            verdict=PAPER_VERDICT[it["tier"]],
            gap=it["gap"],
            ev=it["ev"],
            hr_line=it["hr_line"],
            placed_at=now,
            blocker=blocker,
            factors_json=json.dumps(chips, ensure_ascii=False, allow_nan=False),
            # OUR number and the model's score, off the same card item the gap
            # was computed from. Until 2026-09-13 nothing in the Python lane
            # wrote these, so the whole paper ledger sat outside
            # decision-quality's agreed/against split.
            model_line=it["bv_line"],
            model_score=it.get("under_score"),
        )
        it["paper_logged"] = True
        inserted += 1
    return inserted


def _kill_text(it: Dict) -> str:
    parts = []
    if it.get("kill_line") is not None:
        parts.append(f"below u{it['kill_line']}")
    if it.get("kill_price") is not None:
        parts.append(f"worse than {it['kill_price']:+d}")
    return f" | kill: {' or '.join(parts)}" if parts else ""


def _status_line(card: Dict) -> str:
    """`CARD STATUS: {status} slot={slot} held={n} (bets {m})` plus the failed
    inputs. n = every game a failed input held (counts.degraded, what the web
    reads); m = how many of those were BETs, so the operator sees at a glance
    how many real bets the failure took off the card. Line 2 of the summary,
    so the Saturday text routine can see whether this card is the one to bet
    off."""
    deg = card.get("degraded") or []
    held_bets = sum(
        1 for it in card["items"] if it["tier"] == "BET" and it.get("blocker") == "degraded"
    )
    line = (
        f"CARD STATUS: {card.get('status')} slot={card.get('slot')} "
        f"held={card['counts'].get('degraded', 0)} (bets {held_bets})"
    )
    if deg:
        line += " [" + "; ".join(f"{d['input']}: {d['detail']}" for d in deg) + "]"
    return line


def challenger_collection_enabled() -> bool:
    """H-INSEASON-P collection is PAUSED (2026-09-22) pending the Mac/runner
    reconciliation of the gate that licensed it. Off unless CHALLENGER_COLLECT=1
    is set; the workflows do not set it. Turning it on is a registry decision,
    not a deploy."""
    return os.environ.get("CHALLENGER_COLLECT") == "1"


def log_challenger_picks(
    session,
    *,
    games,
    snaps,
    preds,
    previews,
    season: int,
    week: int,
    now: datetime,
    slot: Optional[str],
    held,
    real,
    degraded,
    window_hours: Optional[float] = None,
) -> Dict[str, int]:
    """One paper observation per qualifying game per H-INSEASON arm.

    Registry row H-INSEASON-P. Every arm is rebuilt through the SAME `build_card`
    the champion just ran, with only `bv_line` moved to that arm's intercept, so
    the gates, the blockers and `qualifies` are the champion's code rather than a
    parallel implementation that could drift. The snapshot is identical: same
    games, same Hard Rock lines and prices, same previews, same degraded inputs,
    same paper window.

    Writes to `challenger_picks` and NOTHING ELSE. No path here can reach
    `manual_picks`, the bankroll, the 5-bet cap or H-STOP's observations.
    """
    read = season_read_as_of(session, season, now, MODEL_VERSION)
    c_prior = current_intercept(session, season, MODEL_VERSION)
    # The champion's own number at this build, frozen beside the arm's so the
    # paired diagnostic in docs/INSEASON_PAPER.md can be computed later. It
    # decides nothing.
    champion_lines = {
        int(pr["game_id"]): pr.get("bv_line")
        for pr in preds
        if pr.get("model_version") == MODEL_VERSION and pr.get("bv_line") is not None
    }
    added: Dict[str, int] = {}
    for k in PAPER_ARMS:
        label = arm_label(k)
        ctx = arm_context(c_prior, read, k)
        arm_card = build_card(
            games,
            snaps,
            arm_predictions(preds, read, k, model_version=MODEL_VERSION),
            previews,
            season=season,
            week=week,
            now=now,
            held_game_ids=held,
            prior_bet_game_ids=real,
            slot=slot,
            degraded=degraded,
        )
        n = 0
        for it in arm_card["items"]:
            if not it.get("qualifies"):
                continue
            if window_hours is not None and it.get("kick"):
                kick = datetime.fromisoformat(it["kick"].replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
                if kick - now > timedelta(hours=window_hours):
                    continue
            gid = it["game_id"]
            if existing_challenger_pick(session, gid, label) is not None:
                continue
            add_challenger_pick(
                session,
                game_id=gid,
                season=season,
                week=week,
                home_team=it["home"],
                away_team=it["away"],
                line=it["hr_line"],
                price=it.get("hr_price"),
                book="hardrockbet",
                slot=slot,
                placed_at=now,
                blocker="cap" if it.get("over_cap") else (it.get("paper_blocker") or "none"),
                arm_line_at_pick=it.get("bv_line"),
                champion_line_at_pick=champion_lines.get(gid),
                gap_at_pick=it.get("gap"),
                **ctx,
            )
            n += 1
        added[label] = n
    return added


def summary_lines(card: Dict, universe: int, picks_added: int) -> List[str]:
    c = card["counts"]
    paper = card.get("paper", {})
    out = [
        f"Card {card['season']} wk{card['week']} built {card['built_at']}: "
        f"{c['bet']} BET / {c['edge']} EDGE / {c['pass']} PASS "
        f"({len(card['items'])} of {universe} Hard Rock games still to kick off; "
        f"model read: {'yes' if card['model_read'] else 'no'}; "
        f"qualifying: {paper.get('qualifying', 0)}; paper picks added: {picks_added})",
        _status_line(card),
    ]
    for it in card["items"]:
        # A degraded bet is NEVER listed as a bet: the Saturday routine greps
        # "  BET #" for the list it texts.
        if it["tier"] == "BET" and not it.get("over_cap") and it.get("blocker") != "degraded":
            price = f" {it['hr_price']:+d}" if it["hr_price"] is not None else ""
            out.append(
                f"  BET #{it.get('cap_rank')}  {it['away']} @ {it['home']}: 1H under {it['hr_line']}{price} "
                f"(gap {it['gap']:+.2f}, ev {it['ev'] if it['ev'] is not None else 'n/a'})"
                f"{_kill_text(it)}"
            )
    for it in card["items"]:
        if it.get("over_cap"):
            out.append(
                f"  OVER CAP #{it.get('cap_rank')} {it['away']} @ {it['home']}: 1H under "
                f"{it['hr_line']} (gap {it['gap']:+.2f}) — paper only"
            )
    for it in card["items"]:
        if it["tier"] == "EDGE":
            # A degraded EDGE keeps its gate in the bracket: "[price · degraded]".
            tag = (
                f"{it.get('gate_blocker')} · degraded"
                if it.get("blocker") == "degraded"
                else it["blocker"]
            )
            out.append(f"  EDGE {it['away']} @ {it['home']} [{tag}]: {it['action']}")
    for it in card["items"]:
        if it["tier"] == "BET" and it.get("blocker") == "degraded":
            out.append(
                f"  DEGRADED {it['away']} @ {it['home']}: 1H under {it['hr_line']} "
                f"(gap {it['gap']:+.2f}) — paper only [{', '.join(it['degraded_inputs'])}]"
            )
    logged = [it for it in card["items"] if it.get("paper_logged")]
    if logged:
        out.append("  PAPER (qualifying games logged, by blocker):")
        for it in logged:
            b = "cap" if it.get("over_cap") else (it.get("paper_blocker") or "none")
            out.append(
                f"    [{b}] {it['away']} @ {it['home']} u{it['hr_line']} gap {it['gap']:+.2f}"
            )
    for n in card["notes"]:
        out.append(f"  note: {n}")
    return out


def write_step_summary(card: Dict, lines: List[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    c = card["counts"]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"## Bet card {card['season']} wk{card['week']}\n\n")
        fh.write(f"**{c['bet']} BET · {c['edge']} EDGE · {c['pass']} PASS**\n\n")
        for it in card["items"]:
            if it["tier"] == "BET" and not it.get("over_cap"):
                fh.write(f"- {it['action']} ({it['away']} @ {it['home']}){_kill_text(it)}\n")
        if c["bet"] == 0:
            fh.write("- No bets this week.\n")
        over = [it for it in card["items"] if it.get("over_cap")]
        if over:
            fh.write("\nOver the weekly cap (paper only): ")
            fh.write(", ".join(f"{it['away']} @ {it['home']} u{it['hr_line']}" for it in over))
            fh.write("\n")
        for n in card["notes"]:
            fh.write(f"\n_{n}_\n")


def run(
    season: Optional[int],
    week: Optional[int],
    dry_run: bool,
    now: Optional[datetime] = None,
    *,
    paper_window_hours: Optional[float] = None,
    no_paper: bool = False,
    slot: Optional[str] = None,
    sweep_status_path: Optional[str] = None,
    preview_status_path: Optional[str] = None,
) -> int:
    """Build + persist; returns the process exit code."""
    now = now or datetime.utcnow()
    if season is None or week is None:
        from beatvegas.season import active

        s, w = active(now)
        season = season or s
        week = week if week is not None else w
    if week is None:
        print(f"[card] no active week for {season} — nothing to build")
        return 0

    with session_scope() as s:
        games = hr_universe(s, season, week)
        snaps, preds, previews = load_inputs(s, [g["game_id"] for g in games])
        held = bet_slots_this_week(s, season, week)
        real = real_bets_this_week(s, season, week)
        # Which inputs failed on THIS build (PR-7). Every one of them either
        # narrows the slate or makes a gate read clear for the wrong reason, so
        # the games they touch go out paper only instead of looking final.
        degraded = degraded_inputs(
            card_games(games, now),
            sweep_status=load_status(sweep_status_path),
            preview_status=load_status(preview_status_path),
            previews=previews,
            predictions=preds,
            tempo_rows=tempo_row_count(s, season, week),
            now=now,
        )
        card = build_card(
            games,
            snaps,
            preds,
            previews,
            season=season,
            week=week,
            now=now,
            held_game_ids=held,
            prior_bet_game_ids=real,
            slot=slot,
            degraded=degraded,
        )
        picks_added = 0
        challenger_added: Dict[str, int] = {}
        if not dry_run and card["items"]:
            if not no_paper:
                picks_added = log_paper_picks(s, card, now, window_hours=paper_window_hours)
                # H-INSEASON-P: the challenger family logs beside the champion,
                # from the same snapshot, into its own table. A failure here must
                # never cost the real card -- the challenger is a measurement.
                #
                # PAUSED 2026-09-22 before the first pick (Tate): the gate that
                # licensed this family read Holm p 0.004 on the Mac and 0.056 on
                # the runner, and the two must be reconciled before either result
                # is allowed to decide anything. Collection is OFF unless
                # CHALLENGER_COLLECT=1 is set in the environment; card.yml does
                # not set it. docs/INSEASON_PAPER.md carries the status.
                if not challenger_collection_enabled():
                    print(
                        "[card] challenger family: collection PAUSED pending the "
                        "Mac/runner reconciliation (docs/INSEASON_PAPER.md); no row written"
                    )
                else:
                    try:
                        challenger_added = log_challenger_picks(
                            s,
                            games=games,
                            snaps=snaps,
                            preds=preds,
                            previews=previews,
                            season=season,
                            week=week,
                            now=now,
                            slot=slot,
                            held=held,
                            real=real,
                            degraded=degraded,
                            window_hours=paper_window_hours,
                        )
                    except Exception as e:  # noqa: BLE001 - never break the card
                        print(f"[card] WARNING: challenger family not logged: {e}")
            s.add(
                Card(
                    season=season,
                    week=week,
                    built_at=now,
                    payload=json.dumps(card, ensure_ascii=False, allow_nan=False),
                )
            )

    lines = summary_lines(card, len(games), picks_added)
    if challenger_added:
        lines.append(
            "  CHALLENGER (H-INSEASON family, paper only): "
            + ", ".join(f"{a} +{n}" for a, n in sorted(challenger_added.items()))
        )
    print("\n".join(lines))
    if dry_run:
        print(json.dumps(card, indent=2, ensure_ascii=False, allow_nan=False))
    write_step_summary(card, lines)
    if games and not card["items"]:
        print(
            f"[card] ERROR: {len(games)} Hard Rock games this week but zero card items "
            "(all kicked off, or inputs missing) — not publishing an empty card."
        )
        return 1
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, help="default: the current season")
    ap.add_argument("--week", type=int, help="default: beatvegas.season.active()")
    ap.add_argument("--dry-run", action="store_true", help="print the payload; write nothing")
    ap.add_argument(
        "--paper-log-window-hours",
        type=float,
        default=None,
        dest="paper_window_hours",
        help="paper-log only qualifying games kicking off within N hours (the decision "
        "build for those games); default: every upcoming qualifying game",
    )
    ap.add_argument(
        "--no-paper",
        action="store_true",
        dest="no_paper",
        help="publish the card without logging paper picks (preview builds)",
    )
    ap.add_argument(
        "--slot",
        default=None,
        help="which build this is (tue_pm|thu_pm|fri_pm|sat_am|manual, "
        "beatvegas.ci.CARD_STATUS_BY_SLOT); sets the card's clean status",
    )
    ap.add_argument(
        "--sweep-status",
        default=None,
        dest="sweep_status",
        help="path to the --status-file scripts/poll_lines.py wrote this run "
        "(missing = the sweep did not run, which is not a failure)",
    )
    ap.add_argument(
        "--preview-status",
        default=None,
        dest="preview_status",
        help="path to the --status-file scripts/research_preview.py wrote this run",
    )
    args = ap.parse_args()
    if not try_init_db():
        return
    sys.exit(
        run(
            args.season,
            args.week,
            args.dry_run,
            paper_window_hours=args.paper_window_hours,
            no_paper=args.no_paper,
            slot=args.slot,
            sweep_status_path=args.sweep_status,
            preview_status_path=args.preview_status,
        )
    )


if __name__ == "__main__":
    main()
