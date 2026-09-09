"""card.yml slot resolver (beatvegas/ci.py): one source of truth for the card
schedule. Since 2026-09-09 there are FOUR decision builds a week, each a
whole-week sweep and each `final`: tue_pm / thu_pm / fri_pm (4:05pm ET) and
sat_am (8:05am ET), timed to when Hard Rock actually posts first-half lines.
Each must land inside its ET gate in EDT and EST without touching a cron
string. Each paper window is exactly the gap to the next build, so every
qualifying game is logged once, by the last build before its kickoff.

An unmapped cron fails loudly, and so does every retired slot name. A slot
already built today (a `cards` row for today's ET date) skips on cron AND on a
dispatch that names it — the Vercel cron and the GitHub backup cron would
otherwise both build, each spending a whole sweep. `force=true` overrides;
`manual` never self-skips."""

from datetime import datetime, timezone

import pytest
from conftest import _sqlite_scope

from beatvegas.ci import (
    CRON_SLOTS,
    PAPER_WINDOW_HOURS,
    SLOT_BUILD_ET,
    SLOT_GATE_ET,
    et_midnight_as_naive_utc,
    resolve_for_cli,
    resolve_slot,
)

SCHEDULED = ("tue_pm", "thu_pm", "fri_pm", "sat_am")


def utc(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_four_slots_each_with_four_crons_on_its_own_weekday():
    by_slot = {}
    for cron, slot in CRON_SLOTS.items():
        by_slot.setdefault(slot, []).append(cron)
    assert set(by_slot) == set(SCHEDULED)
    for slot, day in (("tue_pm", "2"), ("thu_pm", "4"), ("fri_pm", "5"), ("sat_am", "6")):
        assert all(c.endswith(f"* * {day}") for c in by_slot[slot]), slot
        # Four crons so TWO land inside the gate in each DST regime.
        assert len(by_slot[slot]) == 4, slot
    assert len(CRON_SLOTS) == 16
    assert set(SLOT_GATE_ET) == set(SCHEDULED)
    # Never the top of the hour, where GitHub's scheduler drops the most runs.
    assert all(c.split()[0] in {"5", "35"} for c in CRON_SLOTS), sorted(CRON_SLOTS)


def test_each_paper_window_is_the_gap_to_the_next_build():
    """The window controls WHICH build freezes a game's line, not whether it is
    logged (picks.py::existing_pick guards on game_id). Too wide and an earlier
    build claims a game a fresher one should price; too narrow and nobody logs
    it — the old flat 24 h morning window logged no Sunday or Monday game at
    all. So each window must equal the gap to the next build, exactly."""
    for i, slot in enumerate(SCHEDULED):
        nxt = SCHEDULED[(i + 1) % len(SCHEDULED)]
        d1, t1 = SLOT_BUILD_ET[slot]
        d2, t2 = SLOT_BUILD_ET[nxt]
        days = (d2 - d1) % 7 or 7
        gap = days * 24 + ((t2.hour * 60 + t2.minute) - (t1.hour * 60 + t1.minute)) / 60
        assert PAPER_WINDOW_HOURS[slot] == gap, f"{slot} -> {nxt}"


def test_every_slot_sweeps_the_whole_week_and_forces_the_preview():
    # Tue Sep 8 2026, 20:09Z = 4:09pm EDT
    r = resolve_slot("5 20 * * 2", utc(2026, 9, 8, 20, 9))
    assert r["slot"] == "tue_pm"
    assert r["force_sweep"] is True and r["force_preview"] is True
    assert r["paper_window"] == "48"
    assert "--days-ahead 6" in r["sweep_args"] and "--hr-universe" in r["sweep_args"]
    # No slot sweeps "tonight only" any more: every build prices the week.
    assert "--kickoff-within-min" not in r["sweep_args"]
    assert "retry_since" not in r
    # EST (Nov 17 2026, a Tuesday): 21:05Z = 4:05pm ET
    r = resolve_slot("5 21 * * 2", utc(2026, 11, 17, 21, 9))
    assert r["slot"] == "tue_pm"
    # Saturday morning is the same whole-week sweep, with the window that
    # reaches Tuesday so Sunday and Monday games are logged by somebody.
    r = resolve_slot("5 12 * * 6", utc(2026, 9, 12, 12, 6))
    assert r["slot"] == "sat_am" and r["paper_window"] == "80"
    assert "--days-ahead 6" in r["sweep_args"]


@pytest.mark.parametrize(
    "cron, run_at, expect",
    [
        # Afternoon slots, gate 15:45-17:15 ET.
        # EDT (Tue Sep 15): 20:05Z=16:05 in, 20:35Z=16:35 in, 21:05Z=17:05 in,
        # 21:35Z=17:35 out.
        ("5 20 * * 2", utc(2026, 9, 15, 20, 5), "tue_pm"),
        ("35 20 * * 2", utc(2026, 9, 15, 20, 35), "tue_pm"),
        ("5 21 * * 2", utc(2026, 9, 15, 21, 5), "tue_pm"),
        ("35 21 * * 2", utc(2026, 9, 15, 21, 35), "skip"),
        # EST (Tue Nov 17): 20:05Z=15:05 out, 20:35Z=15:35 out (both before the
        # gate), 21:05Z=16:05 in, 21:35Z=16:35 in.
        ("5 20 * * 2", utc(2026, 11, 17, 20, 5), "skip"),
        ("35 20 * * 2", utc(2026, 11, 17, 20, 35), "skip"),
        ("5 21 * * 2", utc(2026, 11, 17, 21, 5), "tue_pm"),
        ("35 21 * * 2", utc(2026, 11, 17, 21, 35), "tue_pm"),
        # Thursday and Friday behave identically on their own weekdays.
        ("5 20 * * 4", utc(2026, 9, 17, 20, 5), "thu_pm"),
        ("5 21 * * 4", utc(2026, 11, 19, 21, 5), "thu_pm"),
        ("5 20 * * 5", utc(2026, 9, 18, 20, 5), "fri_pm"),
        ("5 21 * * 5", utc(2026, 11, 20, 21, 5), "fri_pm"),
        # Saturday morning, gate 07:45-09:15 ET.
        # EDT (Sep 12): 12:05Z=08:05 in ... 13:35Z=09:35 out.
        ("5 12 * * 6", utc(2026, 9, 12, 12, 5), "sat_am"),
        ("35 12 * * 6", utc(2026, 9, 12, 12, 35), "sat_am"),
        ("5 13 * * 6", utc(2026, 9, 12, 13, 5), "sat_am"),
        ("35 13 * * 6", utc(2026, 9, 12, 13, 35), "skip"),
        # EST (Nov 14): 12:05Z=07:05 out, 13:05Z=08:05 in, 13:35Z=08:35 in.
        ("5 12 * * 6", utc(2026, 11, 14, 12, 5), "skip"),
        ("35 12 * * 6", utc(2026, 11, 14, 12, 35), "skip"),
        ("5 13 * * 6", utc(2026, 11, 14, 13, 5), "sat_am"),
        ("35 13 * * 6", utc(2026, 11, 14, 13, 35), "sat_am"),
    ],
)
def test_every_build_is_gated_on_the_eastern_clock(cron, run_at, expect):
    """Two of each slot's four crons land inside the gate in either regime, so
    a DST change needs no cron edit and a dropped run still has a retry."""
    r = resolve_slot(cron, run_at)
    assert r["slot"] == expect, r["reason"]


def test_each_regime_leaves_at_least_two_usable_crons_per_slot():
    """The property the table above spot-checks: never zero (that regime gets
    no build at all that day) and never all four (one of them is always outside
    the gate, so a cron that could never build is dead weight). Two is the
    minimum that survives GitHub dropping a run."""
    edt = {
        "tue_pm": (2026, 9, 15),
        "thu_pm": (2026, 9, 17),
        "fri_pm": (2026, 9, 18),
        "sat_am": (2026, 9, 12),
    }
    est = {
        "tue_pm": (2026, 11, 17),
        "thu_pm": (2026, 11, 19),
        "fri_pm": (2026, 11, 20),
        "sat_am": (2026, 11, 14),
    }
    for regime in (edt, est):
        for slot, (y, m, d) in regime.items():
            usable = 0
            for cron, cron_slot in CRON_SLOTS.items():
                if cron_slot != slot:
                    continue
                mm, hh = int(cron.split()[0]), int(cron.split()[1])
                if resolve_slot(cron, utc(y, m, d, hh, mm))["slot"] == slot:
                    usable += 1
            assert 2 <= usable <= 3, f"{slot} has {usable} usable crons in {y}-{m}"


def test_a_slot_already_built_today_skips_on_cron_and_on_a_named_dispatch():
    # The EST bug the probe fixes, on a Saturday: Nov 14 2026. 12:35Z = 7:35am
    # ET is a gate-skip (writes no card row) ...
    r = resolve_slot("35 12 * * 6", utc(2026, 11, 14, 12, 35))
    assert r["slot"] == "skip" and "outside" in r["reason"]
    # ... so 13:05Z sees an empty probe and BUILDS (the old `gh run list
    # --status success` check counted the skip as a success and blocked it).
    r = resolve_slot("5 13 * * 6", utc(2026, 11, 14, 13, 5), built_today=set())
    assert r["slot"] == "sat_am"
    # 13:35Z: the 13:05Z build is on record for today -> skip.
    r = resolve_slot("35 13 * * 6", utc(2026, 11, 14, 13, 35), built_today={"sat_am"})
    assert r["slot"] == "skip" and "already built today" in r["reason"]
    # One slot's build never blocks another's (Thu, with Tuesday on record).
    r = resolve_slot("5 20 * * 4", utc(2026, 9, 17, 20, 5), built_today={"tue_pm"})
    assert r["slot"] == "thu_pm"


def test_a_named_dispatch_respects_the_probe_unless_forced():
    """Vercel cron dispatches the slot by name and GitHub cron is the backup,
    so a dispatch that ignored the probe would double every build — ~82 Odds
    credits and a duplicate card row, four times a week."""
    at = utc(2026, 9, 15, 20, 5)
    r = resolve_slot("", at, input_slot="tue_pm", built_today=set())
    assert r["slot"] == "tue_pm"
    r = resolve_slot("", at, input_slot="tue_pm", built_today={"tue_pm"})
    assert r["slot"] == "skip" and "force=true" in r["reason"]
    r = resolve_slot("", at, input_slot="tue_pm", built_today={"tue_pm"}, force=True)
    assert r["slot"] == "tue_pm"
    # `manual` is not a scheduled slot and never self-skips.
    r = resolve_slot("", at, built_today={"tue_pm", "manual"})
    assert r["slot"] == "manual"


def test_et_midnight_as_naive_utc_follows_dst():
    # EDT: midnight ET = 04:00Z; EST: 05:00Z. Built_at is naive UTC.
    assert et_midnight_as_naive_utc(utc(2026, 9, 10, 12, 9)) == datetime(2026, 9, 10, 4, 0)
    assert et_midnight_as_naive_utc(utc(2026, 11, 17, 13, 9)) == datetime(2026, 11, 17, 5, 0)
    # 02:00Z on Sep 11 is still Sep 10 in ET -> Sep 10's midnight.
    assert et_midnight_as_naive_utc(utc(2026, 9, 11, 2, 0)) == datetime(2026, 9, 10, 4, 0)


def test_legacy_slot_inputs_are_rejected():
    """Every retired name must FAIL, not build the wrong card. `morning` and
    `afternoon` are in here because the Mac routine and old run logs still say
    them: a silent re-map would freeze the wrong paper window on real games."""
    for legacy in ("weeknight", "friday", "saturday", "morning", "afternoon"):
        with pytest.raises(ValueError):
            resolve_slot("", utc(2026, 9, 17, 15, 0), input_slot=legacy)
    for slot, window in (("tue_pm", "48"), ("thu_pm", "24"), ("fri_pm", "16"), ("sat_am", "80")):
        r = resolve_slot("", utc(2026, 9, 15, 20, 5), input_slot=slot)
        assert r["slot"] == slot and r["paper_window"] == window
    for retired in ("5 20 * * 2,3,4", "5 12 * * 2-6", "0 20 * * 4,5"):
        with pytest.raises(ValueError):
            resolve_slot(retired, utc(2026, 9, 8, 20, 9))
    with pytest.raises(ValueError):
        resolve_slot("5 12 * * 1", utc(2026, 9, 14, 12, 9))  # Monday never builds


def test_dispatch_inputs_and_unknowns():
    r = resolve_slot("", utc(2026, 9, 17, 15, 0))
    assert r["slot"] == "manual" and r["force_sweep"] is True and r["paper_window"] == ""
    assert r["force_preview"] is False
    with pytest.raises(ValueError):
        resolve_slot("", utc(2026, 9, 19, 14, 0), input_slot="sunday")
    with pytest.raises(ValueError):
        resolve_slot("0 15 * * 6", utc(2026, 9, 19, 15, 0))  # the retired Sat 11am refresh


def test_every_slot_has_sweep_args_a_status_and_a_paper_window():
    from beatvegas.ci import CARD_STATUS_BY_SLOT, PAPER_WINDOW_HOURS, SWEEP_ARGS

    for slot in CRON_SLOTS.values():
        assert slot in SWEEP_ARGS and slot in PAPER_WINDOW_HOURS
    assert set(SWEEP_ARGS) == set(CARD_STATUS_BY_SLOT) == set(PAPER_WINDOW_HOURS)
    assert set(SWEEP_ARGS) == set(SCHEDULED) | {"manual"}
    for slot in SCHEDULED:
        assert CARD_STATUS_BY_SLOT[slot] == "final", slot
    assert CARD_STATUS_BY_SLOT["manual"] == "preview"


def test_no_sweep_pays_for_the_exchange_region():
    """us_ex buys nothing on this market: probed against the live Odds API on
    2026-09-07, the region returned ZERO first-half-total bookmakers across
    three upcoming NCAAF games, at ~50% more credits per event. Every slot
    stays on the config regions (us,us2) — the sweeps never pass --regions."""
    from beatvegas.ci import SWEEP_ARGS

    for slot in SWEEP_ARGS:
        assert "--regions" not in SWEEP_ARGS[slot], slot
        assert "us_ex" not in SWEEP_ARGS[slot], slot
    assert "--regions" not in resolve_slot("5 20 * * 4", utc(2026, 9, 17, 20, 9))["sweep_args"]


def test_slots_built_today_reads_todays_card_rows(monkeypatch):
    """The probe: cards rows for the active week since today's ET midnight,
    by payload slot. Exercised on an in-memory SQLite so no network."""
    import json

    from sqlalchemy.orm import Session

    from beatvegas import ci
    from beatvegas.db import store
    from beatvegas.db.models import Card

    eng, scope = _sqlite_scope()
    monkeypatch.setattr(store, "try_init_db", lambda: True)
    monkeypatch.setattr(store, "session_scope", scope)
    monkeypatch.setattr("beatvegas.season.active", lambda: (2026, 3))

    def row(built_at, slot, week=3):
        return Card(season=2026, week=week, built_at=built_at, payload=json.dumps({"slot": slot}))

    with Session(eng) as s:
        s.add_all(
            [
                row(datetime(2026, 9, 10, 12, 10), "morning"),  # today 8:10am EDT
                row(datetime(2026, 9, 9, 20, 5), "afternoon"),  # yesterday
                row(datetime(2026, 9, 10, 12, 30), "morning", week=2),  # another week
                Card(season=2026, week=3, built_at=datetime(2026, 9, 10, 12, 20), payload="{}"),
            ]
        )
        s.commit()

    assert ci.slots_built_today(utc(2026, 9, 10, 20, 5)) == {"morning"}
    # 02:00Z Sep 11 is still Sep 10 in ET; Sep 11 8am ET has nothing on record.
    assert ci.slots_built_today(utc(2026, 9, 11, 2, 0)) == {"morning"}
    assert ci.slots_built_today(utc(2026, 9, 11, 12, 5)) == set()
    # An unreachable DB (outside GHA) and no active week both yield empty.
    monkeypatch.setattr(store, "try_init_db", lambda: False)
    assert ci.slots_built_today(utc(2026, 9, 10, 20, 5)) == set()
    monkeypatch.setattr(store, "try_init_db", lambda: True)
    monkeypatch.setattr("beatvegas.season.active", lambda: (2026, None))
    assert ci.slots_built_today(utc(2026, 9, 10, 20, 5)) == set()


def test_the_probe_runs_only_for_an_in_gate_scheduled_tick(monkeypatch):
    """Gate BEFORE probe: two of the four morning crons are gate-skips every
    day, and they used to open Neon (try_init_db runs DDL and, inside GHA,
    re-raises) just to learn what the ET clock already said. The probe is paid
    for only by a tick that is going to build unless a card is on record."""
    from beatvegas import ci

    calls = []

    def probe(now):
        calls.append(now)
        return set()

    monkeypatch.setattr(ci, "slots_built_today", probe)
    # EST Sat Nov 14: 12:35Z = 7:35am ET is a gate-skip -> no probe.
    r = resolve_for_cli("35 12 * * 6", utc(2026, 11, 14, 12, 35))
    assert r["slot"] == "skip" and "outside" in r["reason"]
    assert calls == []
    # 13:05Z = 8:05am ET is inside the gate -> exactly one probe, then a build.
    r = resolve_for_cli("5 13 * * 6", utc(2026, 11, 14, 13, 5))
    assert r["slot"] == "sat_am"
    assert calls == [utc(2026, 11, 14, 13, 5)]
    # The probe's answer is what decides the second in-gate cron.
    r = resolve_for_cli("35 13 * * 6", utc(2026, 11, 14, 13, 35), probe=lambda now: {"sat_am"})
    assert r["slot"] == "skip" and "already built today" in r["reason"]
    assert len(calls) == 1  # the explicit probe was used, not the module one
    # A NAMED dispatch now probes too: Vercel and GitHub cron would otherwise
    # both build the same slot.
    r = resolve_for_cli("", utc(2026, 11, 14, 14, 0), input_slot="sat_am")
    assert r["slot"] == "sat_am"
    assert calls == [utc(2026, 11, 14, 13, 5), utc(2026, 11, 14, 14, 0)]
    # ... but a forced one has nothing to learn from it, and neither has manual.
    r = resolve_for_cli("", utc(2026, 11, 14, 14, 0), input_slot="sat_am", force=True)
    assert r["slot"] == "sat_am"
    r = resolve_for_cli("", utc(2026, 11, 14, 14, 0))
    assert r["slot"] == "manual"
    assert len(calls) == 2
    # An afternoon gate-skip (EST 20:05Z = 3:05pm ET) is just as silent.
    assert resolve_for_cli("5 20 * * 5", utc(2026, 11, 20, 20, 5))["slot"] == "skip"
    assert len(calls) == 2


def test_resolve_slot_cli_gate_skips_without_touching_the_db(monkeypatch, capsys):
    """The card.yml entry point end to end: SCHEDULE/INPUT_SLOT from the env,
    the wall clock frozen, JSON on stdout (no $GITHUB_OUTPUT locally)."""
    import json

    from beatvegas import ci

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return utc(2026, 11, 14, 12, 35)

    monkeypatch.setattr(ci, "datetime", FrozenDatetime)
    monkeypatch.setenv("SCHEDULE", "35 12 * * 6")
    monkeypatch.setenv("INPUT_SLOT", "")
    monkeypatch.delenv("INPUT_FORCE", raising=False)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    def boom(now):
        raise AssertionError("slots_built_today must not run for a gate-skip tick")

    monkeypatch.setattr(ci, "slots_built_today", boom)
    ci.resolve_slot_cli()
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["slot"] == "skip" and "outside" in out["reason"]

    # The same entry point, one cron later (13:05Z = 8:05am ET): the probe runs.
    FrozenDatetime.now = classmethod(lambda cls, tz=None: utc(2026, 11, 14, 13, 5))
    seen = []
    monkeypatch.setattr(ci, "slots_built_today", lambda now: seen.append(now) or set())
    monkeypatch.setenv("SCHEDULE", "5 13 * * 6")
    ci.resolve_slot_cli()
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["slot"] == "sat_am" and seen == [utc(2026, 11, 14, 13, 5)]
