"""card.yml slot resolver (beatvegas/ci.py): one source of truth for the card
schedule. Since 2026-09-08 the card is ONE rolling week built every morning
Tue-Sat: the `morning` slot must land 8:05-8:45am ET in EDT and EST without
touching a cron string. Since 2026-09-09 an `afternoon` slot (Thu+Fri ~4pm ET)
builds tonight's kickoffs off the first-half lines Hard Rock posts during the
day. An unmapped cron fails loudly; the legacy weeknight / friday / saturday
inputs are gone; a slot already built today (a `cards` row for today's ET
date) skips on cron but never on dispatch."""

from datetime import datetime, timezone

import pytest

from beatvegas.ci import CRON_SLOTS, SLOT_GATE_ET, et_midnight_as_naive_utc, resolve_slot


def utc(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_morning_is_scheduled_tue_through_sat_and_afternoon_thu_fri():
    by_slot = {}
    for cron, slot in CRON_SLOTS.items():
        by_slot.setdefault(slot, []).append(cron)
    assert set(by_slot) == {"morning", "afternoon"}
    assert all(cron.endswith("* * 2-6") for cron in by_slot["morning"])
    assert all(cron.endswith("* * 4,5") for cron in by_slot["afternoon"])
    assert len(CRON_SLOTS) == 6
    assert set(SLOT_GATE_ET) == {"morning", "afternoon"}


def test_morning_slot_sweeps_the_whole_week_and_forces_the_preview():
    # Tue Sep 8 2026, 12:09Z = 8:09am EDT
    r = resolve_slot("5 12 * * 2-6", utc(2026, 9, 8, 12, 9))
    assert r["slot"] == "morning"
    assert r["force_sweep"] is True and r["force_preview"] is True
    assert r["paper_window"] == "24"
    assert "--days-ahead 6" in r["sweep_args"] and "--hr-universe" in r["sweep_args"]
    assert "retry_since" not in r
    # EST (Nov 17 2026, a Tuesday): 13:05Z = 8:05am ET
    r = resolve_slot("5 13 * * 2-6", utc(2026, 11, 17, 13, 9))
    assert r["slot"] == "morning"


@pytest.mark.parametrize(
    "cron, run_at, expect",
    [
        # EDT (Thu Sep 10): 12:05Z = 8:05am ET runs; 13:35Z = 9:35am ET is too late
        ("5 12 * * 2-6", utc(2026, 9, 10, 12, 9), "morning"),
        ("35 12 * * 2-6", utc(2026, 9, 10, 12, 41), "morning"),
        ("5 13 * * 2-6", utc(2026, 9, 10, 13, 8), "morning"),
        ("35 13 * * 2-6", utc(2026, 9, 10, 13, 37), "skip"),
        # EST (Fri Nov 20): 12:05Z = 7:05am ET too early; 13:05Z = 8:05am runs
        ("5 12 * * 2-6", utc(2026, 11, 20, 12, 7), "skip"),
        ("35 12 * * 2-6", utc(2026, 11, 20, 12, 40), "skip"),
        ("5 13 * * 2-6", utc(2026, 11, 20, 13, 9), "morning"),
        ("35 13 * * 2-6", utc(2026, 11, 20, 13, 38), "morning"),
        # Saturday is still a morning build like any other day
        ("5 12 * * 2-6", utc(2026, 9, 12, 12, 6), "morning"),
    ],
)
def test_morning_build_is_gated_on_the_eastern_clock(cron, run_at, expect):
    r = resolve_slot(cron, run_at)
    assert r["slot"] == expect, r["reason"]


@pytest.mark.parametrize(
    "cron, run_at, expect",
    [
        # EDT (Thu Sep 10): 20:05Z = 4:05pm ET builds; 21:05Z = 5:05pm ET still inside
        ("0 20 * * 4,5", utc(2026, 9, 10, 20, 5), "afternoon"),
        ("0 21 * * 4,5", utc(2026, 9, 10, 21, 5), "afternoon"),
        # EST (Fri Nov 20): 20:05Z = 3:05pm ET too early; 21:05Z = 4:05pm builds
        ("0 20 * * 4,5", utc(2026, 11, 20, 20, 5), "skip"),
        ("0 21 * * 4,5", utc(2026, 11, 20, 21, 5), "afternoon"),
    ],
)
def test_afternoon_build_is_gated_on_the_eastern_clock(cron, run_at, expect):
    r = resolve_slot(cron, run_at)
    assert r["slot"] == expect, r["reason"]
    if expect == "afternoon":
        assert r["paper_window"] == "10"
        assert "--kickoff-within-min 600" in r["sweep_args"]
        assert "--days-ahead" not in r["sweep_args"]
        assert r["force_sweep"] is True and r["force_preview"] is True


def test_a_slot_already_built_today_skips_on_cron_but_not_on_dispatch():
    # The EST bug the probe fixes: Tue Nov 17 2026. 12:35Z = 7:35am ET is a
    # gate-skip (writes no card row) ...
    r = resolve_slot("35 12 * * 2-6", utc(2026, 11, 17, 12, 35))
    assert r["slot"] == "skip" and "outside" in r["reason"]
    # ... so 13:05Z sees an empty probe and BUILDS (the old `gh run list
    # --status success` check counted the skip as a success and blocked it).
    r = resolve_slot("5 13 * * 2-6", utc(2026, 11, 17, 13, 5), built_today=set())
    assert r["slot"] == "morning"
    # 13:35Z: the 13:05Z build is on record for today -> skip.
    r = resolve_slot("35 13 * * 2-6", utc(2026, 11, 17, 13, 35), built_today={"morning"})
    assert r["slot"] == "skip" and "already built today" in r["reason"]
    # The afternoon slot is not blocked by this morning's build (Thu Sep 10 EDT).
    r = resolve_slot("0 20 * * 4,5", utc(2026, 9, 10, 20, 5), built_today={"morning"})
    assert r["slot"] == "afternoon"
    r = resolve_slot("0 21 * * 4,5", utc(2026, 9, 10, 21, 5), built_today={"morning", "afternoon"})
    assert r["slot"] == "skip"
    # A dispatch never self-skips, whatever is on record.
    r = resolve_slot("", utc(2026, 11, 17, 14, 0), input_slot="morning", built_today={"morning"})
    assert r["slot"] == "morning"
    r = resolve_slot("", utc(2026, 11, 17, 14, 0), built_today={"morning", "afternoon"})
    assert r["slot"] == "manual"


def test_et_midnight_as_naive_utc_follows_dst():
    # EDT: midnight ET = 04:00Z; EST: 05:00Z. Built_at is naive UTC.
    assert et_midnight_as_naive_utc(utc(2026, 9, 10, 12, 9)) == datetime(2026, 9, 10, 4, 0)
    assert et_midnight_as_naive_utc(utc(2026, 11, 17, 13, 9)) == datetime(2026, 11, 17, 5, 0)
    # 02:00Z on Sep 11 is still Sep 10 in ET -> Sep 10's midnight.
    assert et_midnight_as_naive_utc(utc(2026, 9, 11, 2, 0)) == datetime(2026, 9, 10, 4, 0)


def test_legacy_slot_inputs_are_rejected():
    for legacy in ("weeknight", "friday", "saturday"):
        with pytest.raises(ValueError):
            resolve_slot("", utc(2026, 9, 17, 15, 0), input_slot=legacy)
    r = resolve_slot("", utc(2026, 9, 9, 14, 0), input_slot="morning")
    assert r["slot"] == "morning"
    r = resolve_slot("", utc(2026, 9, 10, 19, 0), input_slot="afternoon")
    assert r["slot"] == "afternoon" and r["paper_window"] == "10"
    with pytest.raises(ValueError):
        resolve_slot("5 20 * * 2,3,4", utc(2026, 9, 8, 20, 9))  # the retired weeknight cron
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
    assert set(SWEEP_ARGS) == {"morning", "afternoon", "manual"}
    assert CARD_STATUS_BY_SLOT["morning"] == "final"
    assert CARD_STATUS_BY_SLOT["afternoon"] == "final"
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
    assert "--regions" not in resolve_slot("5 12 * * 2-6", utc(2026, 9, 10, 12, 9))["sweep_args"]


def test_slots_built_today_reads_todays_card_rows(monkeypatch):
    """The probe: cards rows for the active week since today's ET midnight,
    by payload slot. Exercised on an in-memory SQLite so no network."""
    import json
    from contextlib import contextmanager

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from beatvegas import ci
    from beatvegas.db import store
    from beatvegas.db.models import Base, Card

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

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
