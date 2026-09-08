"""card.yml slot resolver (beatvegas/ci.py): one source of truth for the card
schedule. Since 2026-09-08 the card is ONE rolling week built every morning
Tue-Sat: the `morning` slot must land 8:05-8:45am ET in EDT and EST without
touching a cron string; an unmapped cron fails loudly; the legacy weeknight /
friday / saturday slots survive as workflow_dispatch inputs only."""

from datetime import datetime, timezone

import pytest

from beatvegas.ci import CRON_SLOTS, resolve_slot


def utc(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_only_the_morning_slot_is_scheduled_tue_through_sat():
    assert {slot for slot, _ in CRON_SLOTS.values()} == {"morning"}
    assert all(cron.endswith("* * 2-6") for cron in CRON_SLOTS)
    assert len(CRON_SLOTS) == 4


def test_morning_slot_sweeps_the_whole_week_and_forces_the_preview():
    # Tue Sep 8 2026, 12:09Z = 8:09am EDT
    r = resolve_slot("5 12 * * 2-6", utc(2026, 9, 8, 12, 9))
    assert r["slot"] == "morning"
    assert r["force_sweep"] is True and r["force_preview"] is True
    assert r["paper_window"] == "24"
    assert "--days-ahead 6" in r["sweep_args"] and "--hr-universe" in r["sweep_args"]
    # retry check: a scheduled success since 7:30am ET today -> skip (EDT: 11:30Z)
    assert r["retry_since"] == "2026-09-08T11:30:00+00:00"
    # EST (Nov 17 2026, a Tuesday): 13:05Z = 8:05am ET; since 7:30am ET = 12:30Z
    r = resolve_slot("5 13 * * 2-6", utc(2026, 11, 17, 13, 9))
    assert r["slot"] == "morning" and r["retry_since"] == "2026-11-17T12:30:00+00:00"


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


def test_legacy_slots_are_dispatch_only():
    r = resolve_slot("", utc(2026, 9, 17, 15, 0), input_slot="weeknight")
    assert r["slot"] == "weeknight" and r["force_sweep"] is False and r["paper_window"] == "10"
    r = resolve_slot("", utc(2026, 9, 18, 22, 0), input_slot="friday")
    assert r["slot"] == "friday" and r["force_sweep"] is True and r["paper_window"] == "6"
    r = resolve_slot("", utc(2026, 9, 19, 14, 0), input_slot="saturday")
    assert r["slot"] == "saturday" and r["retry_since"] == ""  # a manual final never self-skips
    r = resolve_slot("", utc(2026, 9, 9, 14, 0), input_slot="morning")
    assert r["slot"] == "morning" and r["retry_since"] == ""
    with pytest.raises(ValueError):
        resolve_slot("5 20 * * 2,3,4", utc(2026, 9, 8, 20, 9))  # the retired weeknight cron
    with pytest.raises(ValueError):
        resolve_slot("5 12 * * 1", utc(2026, 9, 14, 12, 9))  # Monday never builds


def test_dispatch_inputs_and_unknowns():
    r = resolve_slot("", utc(2026, 9, 17, 15, 0))
    assert r["slot"] == "manual" and r["force_sweep"] is True and r["paper_window"] == ""
    with pytest.raises(ValueError):
        resolve_slot("", utc(2026, 9, 19, 14, 0), input_slot="sunday")
    with pytest.raises(ValueError):
        resolve_slot("0 15 * * 6", utc(2026, 9, 19, 15, 0))  # the retired Sat 11am refresh


def test_every_slot_has_sweep_args_a_status_and_a_paper_window():
    from beatvegas.ci import CARD_STATUS_BY_SLOT, PAPER_WINDOW_HOURS, SWEEP_ARGS

    for slot, _ in CRON_SLOTS.values():
        assert slot in SWEEP_ARGS and slot in PAPER_WINDOW_HOURS
    assert set(SWEEP_ARGS) == set(CARD_STATUS_BY_SLOT) == set(PAPER_WINDOW_HOURS)
    assert CARD_STATUS_BY_SLOT["morning"] == "final"


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
