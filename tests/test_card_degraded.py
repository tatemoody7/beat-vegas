"""Degraded card status: which inputs failed, which games they touched, and
what that does to the card (paper only, no weekly-cap slot, status "degraded").

The pure half of PR-7. The status files those signals come from are covered by
tests/test_poll_lines.py + tests/test_research_preview_status.py; the wiring and
the CARD STATUS: summary line by tests/test_build_card.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from beatvegas.card import (
    DEGRADED_INPUTS,
    apply_degraded,
    apply_weekly_cap,
    build_card,
    card_games,
    degraded_inputs,
)
from beatvegas.ci import CARD_STATUS_BY_SLOT, SWEEP_ARGS

NOW = datetime(2026, 9, 19, 12, 40)  # Saturday 8:40am ET, in UTC
KICK = NOW + timedelta(hours=8)

# The stored factors chips as model/score.py::_factors writes them (no "dome" key
# exists there — _weather_str folds a dome into the weather string).
FACTORS_OK = {"pace": "27.5s/play · 142 plays", "weather": "78°F · wind 6mph"}


def game(gid=1, away="Kansas", home="Missouri", kick=KICK, **extra):
    return {"game_id": gid, "away": away, "home": home, "kick": kick, **extra}


def snap(gid, book, line, over=-110, under=-110, hours_ago=1.0):
    return {
        "game_id": gid,
        "book": book,
        "line": line,
        "over_price": over,
        "under_price": under,
        "captured_at": NOW - timedelta(hours=hours_ago),
    }


def market(gid, line, books=("draftkings", "fanduel", "betmgm")):
    return [snap(gid, b, line, 100, -120) for b in books]


def model(gid, bv_line, factors=None):
    """A gbm_v1 prediction row with its stored factors (the card reads pace off
    these)."""
    return {
        "game_id": gid,
        "model_version": "gbm_v1",
        "bv_line": bv_line,
        "line_used": 24.0,
        "factors": dict(FACTORS_OK if factors is None else factors),
    }


def preview_row(gid, updated_at=NOW):
    return {"game_id": gid, "qb_out": False, "qb_out_detail": "", "updated_at": updated_at}


def bet_snaps(gid, line=24.5):
    """Hard Rock at `line` -110 against a market shaded to the under: a BET."""
    return [snap(gid, "hardrockbet", line, -110, -110)] + market(gid, line)


# --- card_games -----------------------------------------------------------------


def test_card_games_keeps_only_kickoffs_after_now():
    games = [game(1), game(2, kick=NOW - timedelta(hours=1)), game(3, kick=None)]
    assert [g["game_id"] for g in card_games(games, NOW)] == [1]


# --- one signal at a time --------------------------------------------------------


def test_no_status_files_and_healthy_inputs_report_nothing():
    """The signal that matters most: a normal run must be silent. The sweep and
    preview steps may not have run at all (need_sweep false), which is NOT a
    failure."""
    items = [game(1), game(2)]
    assert (
        degraded_inputs(
            items,
            sweep_status=None,
            preview_status=None,
            previews=[preview_row(1), preview_row(2)],
            predictions=[model(1, 22.4), model(2, 22.4)],
            tempo_rows=260,
            now=NOW,
        )
        == []
    )
    # ...and a status file that says everything worked is equally silent.
    assert (
        degraded_inputs(
            items,
            sweep_status={"complete": True, "reason": None, "unpolled_game_ids": []},
            preview_status={"ok": True, "reason": None},
            previews=[preview_row(1), preview_row(2)],
            predictions=[model(1, 22.4), model(2, 22.4)],
            tempo_rows=260,
            now=NOW,
        )
        == []
    )


def test_incomplete_sweep_names_the_games_it_never_reached():
    d = degraded_inputs(
        [game(1), game(2), game(3)],
        sweep_status={
            "complete": False,
            "reason": "credit_cap",
            "events_in_window": 3,
            "events_polled": 1,
            # 99 is not on this card and must not leak into the entry.
            "unpolled_game_ids": [2, 3, 99],
        },
        previews=[preview_row(i) for i in (1, 2, 3)],
        predictions=[model(i, 22.4) for i in (1, 2, 3)],
        tempo_rows=260,
        now=NOW,
    )
    assert len(d) == 1
    assert d[0]["input"] == "sweep" and d[0]["game_ids"] == [2, 3]
    assert d[0]["detail"] == "stopped early (credit_cap) after 1 of 3 events"


def test_incomplete_sweep_that_never_recorded_its_coverage_degrades_every_game():
    """The `unpolled_game_ids` KEY is absent (an old status file, or a stop
    before the ids were known): we cannot say which games are stale, so every
    game on the card is."""
    d = degraded_inputs(
        [game(1), game(2)],
        sweep_status={"complete": False, "reason": "fetch_error"},
        previews=[preview_row(1), preview_row(2)],
        predictions=[model(1, 22.4), model(2, 22.4)],
        tempo_rows=260,
        now=NOW,
    )
    assert [e["input"] for e in d] == ["sweep"] and d[0]["game_ids"] == [1, 2]
    assert d[0]["detail"] == "stopped early (fetch_error); coverage unknown"


@pytest.mark.parametrize("unpolled", [[], [98, 99]])
def test_incomplete_sweep_whose_unreached_games_are_all_off_card_degrades_nothing(unpolled):
    """The key is PRESENT and none of the ids are on this card (a truncated
    sweep whose unreached events all fall outside the card's week): no game is
    held, but the truncation still shows in the card's status detail as a
    build-wide entry (game_ids [])."""
    d = degraded_inputs(
        [game(1), game(2)],
        sweep_status={
            "complete": False,
            "reason": "credit_cap",
            "events_in_window": 9,
            "events_polled": 7,
            "unpolled_game_ids": unpolled,
        },
        previews=[preview_row(1), preview_row(2)],
        predictions=[model(1, 22.4), model(2, 22.4)],
        tempo_rows=260,
        now=NOW,
    )
    assert d == [
        {
            "input": "sweep",
            "detail": "stopped early (credit_cap) after 7 of 9 events; "
            "no game on this card was among the unreached",
            "game_ids": [],
        }
    ]
    c = build_card(
        [game(1), game(2)],
        bet_snaps(1) + bet_snaps(2),
        [model(1, 22.4), model(2, 22.4)],
        [],
        season=2026,
        week=3,
        now=NOW,
        slot="saturday",
        degraded=d,
    )
    assert c["status"] == "degraded" and c["counts"]["degraded"] == 0
    assert [it["blocker"] for it in c["items"]] == [None, None]
    assert c["counts"]["bet"] == 2


def test_failed_preview_holds_every_game_on_the_card():
    """Owner decision (2026-09-08): an empty injury feed means the QB-out gate
    could not run on ANY game, so every game is held — including game 1, whose
    row was refreshed this morning (by a run that had no injuries to write)."""
    d = degraded_inputs(
        [game(1), game(2), game(3)],
        preview_status={"ok": False, "reason": "rotowire_empty"},
        previews=[preview_row(1), preview_row(2, updated_at=NOW - timedelta(days=1))],
        predictions=[model(i, 22.4) for i in (1, 2, 3)],
        tempo_rows=260,
        now=NOW,
    )
    assert d == [
        {
            "input": "preview",
            "detail": "rotowire_empty: the injury read failed, so the quarterback gate "
            "could not run on any of the 3 games",
            "game_ids": [1, 2, 3],
        }
    ]


def test_an_empty_injury_feed_makes_every_bet_paper_only():
    """The case that defeated the purpose before: Rotowire empty but ESPN up,
    so the preview run still upserted a row per game dated TODAY with blank
    injuries. No row looked stale, the entry came back with no game ids and no
    bet was held. Now every bet on the card is paper only and the header
    count agrees."""
    d = degraded_inputs(
        [game(1), game(2)],
        preview_status={"ok": False, "reason": "rotowire_empty"},
        previews=[preview_row(1, updated_at=NOW), preview_row(2, updated_at=NOW)],
        predictions=[model(1, 22.4), model(2, 22.4)],
        tempo_rows=260,
        now=NOW,
    )
    assert [e["game_ids"] for e in d] == [[1, 2]]
    c = build_card(
        [game(1), game(2)],
        bet_snaps(1) + bet_snaps(2),
        [model(1, 22.4), model(2, 22.4)],
        [preview_row(1), preview_row(2)],
        season=2026,
        week=3,
        now=NOW,
        slot="saturday",
        degraded=d,
    )
    assert c["status"] == "degraded"
    assert c["counts"]["degraded"] == 2 and c["counts"]["bet"] == 0
    for it in c["items"]:
        assert it["tier"] == "BET" and it["blocker"] == "degraded"
        assert it["paper_blocker"] == "degraded" and it["cap_rank"] is None


def test_a_healthy_feed_still_holds_a_game_whose_preview_is_missing_or_old():
    """The narrower trigger survives: the feed was fine (ok True) but game 2's
    row is yesterday's and game 3 has none — those two carry no QB read for
    today; game 1 does."""
    d = degraded_inputs(
        [game(1), game(2), game(3)],
        preview_status={"ok": True, "reason": None},
        previews=[preview_row(1), preview_row(2, updated_at=NOW - timedelta(days=1))],
        predictions=[model(i, 22.4) for i in (1, 2, 3)],
        tempo_rows=260,
        now=NOW,
    )
    assert d == [
        {"input": "preview", "detail": "2 games with no QB read from today", "game_ids": [2, 3]}
    ]


def test_no_preview_status_means_the_step_did_not_run_and_is_not_a_failure():
    """The weeknight slots skip the preview when today's rows exist; a missing
    file must not hold games whose rows happen to be older."""
    d = degraded_inputs(
        [game(1), game(2)],
        preview_status=None,
        previews=[preview_row(2, updated_at=NOW - timedelta(days=2))],
        predictions=[model(1, 22.4), model(2, 22.4)],
        tempo_rows=260,
        now=NOW,
    )
    assert d == []


def test_missing_pace_is_a_per_game_signal():
    d = degraded_inputs(
        [game(1), game(2), game(3)],
        predictions=[
            model(1, 22.4),
            model(2, 22.4, {"pace": None, "weather": "60°F"}),
            model(3, 22.4, {"pace": "27.5s/play", "weather": None}),
        ],
        previews=[preview_row(i) for i in (1, 2, 3)],
        tempo_rows=260,
        now=NOW,
    )
    assert [(e["input"], e["game_ids"]) for e in d] == [("pace", [2])]
    assert d[0]["detail"] == "1 model games have no pace read"


def test_missing_weather_on_a_healthy_build_is_not_degraded():
    """Weather is structurally sparse (live Neon: 27 of 303 week-2 games have
    a forecast, zero in weeks 3-6; historically 394 of 637 games with a 1H
    line carry none). The model treats it as missing. A card must NOT go
    paper-only over it, whatever else the game carries."""
    d = degraded_inputs(
        [game(1), game(2)],
        predictions=[
            model(1, 22.4, {"pace": "27.5s/play", "weather": None}),
            model(2, 22.4, {"pace": "27.5s/play", "weather": ""}),
        ],
        previews=[preview_row(1), preview_row(2)],
        tempo_rows=260,
        now=NOW,
    )
    assert d == []
    assert "weather" not in DEGRADED_INPUTS


def test_a_prediction_with_no_stored_factors_is_not_degraded():
    """ "Cannot tell" is not "missing": a caller that never loaded factors_json
    must not make every game on the card read as degraded."""
    pred = {"game_id": 1, "model_version": "gbm_v1", "bv_line": 22.4}
    assert degraded_inputs([game(1)], predictions=[pred], tempo_rows=260, now=NOW) == []


def test_empty_tempo_table_degrades_every_model_game():
    d = degraded_inputs(
        [game(1), game(2)],
        # game 2 has no model read, so it is not a "model game"
        predictions=[model(1, 22.4)],
        previews=[preview_row(1), preview_row(2)],
        tempo_rows=0,
        now=NOW,
    )
    assert [(e["input"], e["game_ids"]) for e in d] == [("tempo", [1])]
    assert d[0]["detail"] == "the tempo table stored 0 rows"


def test_tempo_not_checked_is_not_a_failure():
    d = degraded_inputs([game(1)], predictions=[model(1, 22.4)], tempo_rows=None, now=NOW)
    assert d == []


def test_several_signals_at_once_come_back_in_declared_order():
    d = degraded_inputs(
        [game(1), game(2)],
        sweep_status={
            "complete": False,
            "reason": "credit_floor",
            "events_in_window": 2,
            "events_polled": 1,
            "unpolled_game_ids": [2],
        },
        preview_status={"ok": False, "reason": "both_empty"},
        previews=[],
        predictions=[model(1, 22.4, {"pace": None, "weather": None}), model(2, 22.4)],
        tempo_rows=0,
        now=NOW,
    )
    names = [e["input"] for e in d]
    assert names == ["sweep", "preview", "pace", "tempo"]
    assert list(DEGRADED_INPUTS) == names
    assert {e["input"]: e["game_ids"] for e in d}["sweep"] == [2]


# --- apply_degraded ---------------------------------------------------------------


def test_apply_degraded_keeps_the_tier_and_writes_a_paper_only_action():
    c = build_card([game(1)], bet_snaps(1), [model(1, 22.4)], [], season=2026, week=3, now=NOW)
    (it,) = c["items"]
    assert it["tier"] == "BET" and it["degraded_inputs"] == []

    items = [dict(it)]
    apply_degraded(items, [{"input": "sweep", "detail": "x", "game_ids": [1]}])
    (out,) = items
    assert out["tier"] == "BET"  # the read is unchanged
    assert out["blocker"] == "degraded" and out["degraded_inputs"] == ["sweep"]
    assert out["gate_blocker"] == "none"  # every gate had passed
    assert out["paper_blocker"] == "degraded"  # it qualifies, so the ledger tags it
    assert out["action"] == (
        "Degraded inputs (sweep): paper only — re-check Hard Rock’s number and the "
        "QB report yourself before betting."
    )


def test_apply_degraded_lists_every_input_that_touched_the_game():
    items = [{"game_id": 1, "tier": "BET", "blocker": None, "qualifies": False, "action": ""}]
    apply_degraded(
        items,
        [
            {"input": "tempo", "detail": "", "game_ids": [1]},
            {"input": "sweep", "detail": "", "game_ids": [1, 2]},
        ],
    )
    assert items[0]["degraded_inputs"] == ["sweep", "tempo"]  # DEGRADED_INPUTS order
    assert items[0]["action"].startswith("Degraded inputs (sweep, tempo): paper only")


def test_apply_degraded_preserves_the_gate_that_had_blocked_a_real_bet():
    """A qualifying game blocked on price must not become "just degraded":
    the gate survives as gate_blocker, and a second pass over an already
    degraded item does not overwrite it with "degraded"."""
    items = [
        {"game_id": 1, "tier": "EDGE", "blocker": "price", "qualifies": True, "action": ""},
        {"game_id": 2, "tier": "EDGE", "blocker": "no_hr_line", "qualifies": False, "action": ""},
    ]
    apply_degraded(items, [{"input": "sweep", "detail": "", "game_ids": [1, 2]}])
    assert items[0]["blocker"] == "degraded" and items[0]["gate_blocker"] == "price"
    assert items[1]["blocker"] == "degraded" and items[1]["gate_blocker"] == "no_hr_line"
    apply_degraded(items, [{"input": "tempo", "detail": "", "game_ids": [1]}])
    assert items[0]["blocker"] == "degraded" and items[0]["gate_blocker"] == "price"


def test_apply_degraded_leaves_untouched_games_alone():
    items = [
        {"game_id": 1, "tier": "BET", "blocker": None, "qualifies": True, "action": "Bet now"},
        {"game_id": 2, "tier": "BET", "blocker": None, "qualifies": True, "action": "Bet now"},
    ]
    apply_degraded(items, [{"input": "sweep", "detail": "", "game_ids": [2]}])
    assert items[0]["blocker"] is None and items[0]["action"] == "Bet now"
    assert items[0].get("gate_blocker") is None
    assert items[1]["blocker"] == "degraded"


# --- the weekly cap ----------------------------------------------------------------


def _bet(gid, gap):
    return {
        "game_id": gid,
        "tier": "BET",
        "blocker": None,
        "gap": gap,
        "ev": 0.01,
        "kick": "2026-09-19T20:40:00Z",
        "away": f"A{gid}",
        "cap_rank": None,
        "over_cap": False,
        "qualifies": True,
        "action": "Bet now",
    }


def test_a_degraded_bet_takes_no_cap_slot_and_the_rest_rank_one_to_five():
    """The biggest gap on the board is degraded: it must not eat slot #1 and
    push a clean bet over the cap."""
    items = [_bet(i, gap=5.0 - i * 0.1) for i in range(1, 7)]
    apply_degraded(items, [{"input": "sweep", "detail": "", "game_ids": [1]}])
    apply_weekly_cap(items)
    by_id = {it["game_id"]: it for it in items}
    assert by_id[1]["tier"] == "BET" and by_id[1]["blocker"] == "degraded"
    assert by_id[1]["cap_rank"] is None and by_id[1]["over_cap"] is False
    assert [by_id[i]["cap_rank"] for i in range(2, 7)] == [1, 2, 3, 4, 5]
    assert all(by_id[i]["over_cap"] is False for i in range(2, 7))


# --- the payload ---------------------------------------------------------------------


def _degraded_card(**kw):
    deg = [{"input": "sweep", "detail": "stopped early (credit_cap)", "game_ids": [1]}]
    return build_card(
        [game(1)],
        bet_snaps(1),
        [model(1, 22.4)],
        [],
        season=2026,
        week=3,
        now=NOW,
        degraded=deg,
        **kw,
    )


@pytest.mark.parametrize(
    "slot,expected",
    [("saturday", "final"), ("friday", "preview"), ("manual", "preview"), ("weeknight", "final")],
)
def test_status_comes_from_the_slot_on_a_clean_build(slot, expected):
    c = build_card(
        [game(1)], bet_snaps(1), [model(1, 22.4)], [], season=2026, week=3, now=NOW, slot=slot
    )
    assert (c["slot"], c["status"]) == (slot, expected)
    assert c["degraded"] == [] and c["counts"]["degraded"] == 0
    assert c["items"][0]["degraded_inputs"] == []


def test_status_is_degraded_whatever_the_slot_says():
    c = _degraded_card(slot="saturday")
    assert c["status"] == "degraded" and c["slot"] == "saturday"
    assert c["counts"]["degraded"] == 1
    assert c["degraded"] == [
        {"input": "sweep", "detail": "stopped early (credit_cap)", "game_ids": [1]}
    ]
    (it,) = c["items"]
    assert it["blocker"] == "degraded" and it["degraded_inputs"] == ["sweep"]
    assert it["gate_blocker"] == "none" and it["cap_rank"] is None


def test_counts_bet_excludes_a_degraded_bet():
    """Owner decision (2026-09-08): a degraded BET is tallied in counts.degraded
    only, so the header agrees with the "  BET #" lines beneath it and the
    site's "N bets this week"."""
    deg = [{"input": "sweep", "detail": "stopped early (credit_cap)", "game_ids": [2]}]
    c = build_card(
        [game(1), game(2)],
        bet_snaps(1) + bet_snaps(2),
        [model(1, 22.4), model(2, 22.4)],
        [],
        season=2026,
        week=3,
        now=NOW,
        degraded=deg,
    )
    by_id = {it["game_id"]: it for it in c["items"]}
    assert by_id[1]["tier"] == by_id[2]["tier"] == "BET"
    assert by_id[1]["blocker"] is None and by_id[2]["blocker"] == "degraded"
    assert c["counts"] == {"bet": 1, "edge": 0, "pass": 0, "over_cap": 0, "degraded": 1}


def test_a_build_with_no_slot_still_reads_final():
    c = build_card([game(1)], bet_snaps(1), [model(1, 22.4)], [], season=2026, week=3, now=NOW)
    assert c["slot"] is None and c["status"] == "final"
    assert c["items"][0]["gate_blocker"] is None  # not degraded: no gate to preserve


def test_payload_keys_match_the_web_contract():
    """web/lib/card.ts parseCard reads exactly these names."""
    c = _degraded_card(slot="saturday")
    assert set(c) == {
        "season",
        "week",
        "built_at",
        "model_read",
        "slot",
        "status",
        "degraded",
        "counts",
        "paper",
        "items",
        "notes",
    }
    assert set(c["counts"]) == {"bet", "edge", "pass", "over_cap", "degraded"}
    assert set(c["degraded"][0]) == {"input", "detail", "game_ids"}
    assert "degraded_inputs" in c["items"][0] and "gate_blocker" in c["items"][0]
    # strict JSON, as the cards row is written
    assert json.loads(json.dumps(c, allow_nan=False)) == c


# --- the slot table ---------------------------------------------------------------


def test_every_sweep_slot_has_a_card_status():
    assert set(SWEEP_ARGS) <= set(CARD_STATUS_BY_SLOT)
    assert set(CARD_STATUS_BY_SLOT.values()) <= {"final", "preview"}
