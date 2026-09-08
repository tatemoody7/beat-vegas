"""card.yml slot resolver (beatvegas/ci.py): one source of truth for the card
schedule. The Saturday final must land 8:05-8:45am ET in EDT and EST without
touching a cron string; an unmapped cron fails loudly."""

from datetime import datetime, timezone

import pytest

from beatvegas.ci import CRON_SLOTS, resolve_slot


def utc(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_weeknight_and_friday_slots_and_their_retry_windows():
    r = resolve_slot("5 20 * * 2,3,4", utc(2026, 9, 24, 20, 12))
    assert r["slot"] == "weeknight" and r["retry_since"] == ""
    assert r["force_sweep"] is False and r["force_preview"] is False
    assert r["paper_window"] == "10" and "--kickoff-within-min 600" in r["sweep_args"]
    r = resolve_slot("50 20 * * 2,3,4", utc(2026, 9, 24, 20, 55))
    assert r["slot"] == "weeknight" and r["retry_since"] == "2026-09-24T19:45:00+00:00"
    r = resolve_slot("5 22 * * 5", utc(2026, 9, 25, 22, 9))
    assert r["slot"] == "friday" and r["force_sweep"] is True and r["paper_window"] == "6"
    assert "--days-ahead 3" in r["sweep_args"]
    r = resolve_slot("0 23 * * 5", utc(2026, 9, 25, 23, 4))
    assert r["retry_since"] == "2026-09-25T21:45:00+00:00"


@pytest.mark.parametrize(
    "cron, run_at, expect",
    [
        # EDT (September): 12:05Z = 8:05am ET runs; 13:35Z = 9:35am ET is too late
        ("5 12 * * 6", utc(2026, 9, 19, 12, 9), "saturday"),
        ("35 12 * * 6", utc(2026, 9, 19, 12, 41), "saturday"),
        ("5 13 * * 6", utc(2026, 9, 19, 13, 8), "saturday"),
        ("35 13 * * 6", utc(2026, 9, 19, 13, 37), "skip"),
        # EST (November 14): 12:05Z = 7:05am ET too early; 13:05Z = 8:05am runs
        ("5 12 * * 6", utc(2026, 11, 14, 12, 7), "skip"),
        ("35 12 * * 6", utc(2026, 11, 14, 12, 40), "skip"),
        ("5 13 * * 6", utc(2026, 11, 14, 13, 9), "saturday"),
        ("35 13 * * 6", utc(2026, 11, 14, 13, 38), "saturday"),
    ],
)
def test_saturday_final_is_gated_on_the_eastern_clock(cron, run_at, expect):
    r = resolve_slot(cron, run_at)
    assert r["slot"] == expect, r["reason"]


def test_saturday_final_forces_the_sweep_and_the_preview_and_skips_after_a_success():
    r = resolve_slot("5 12 * * 6", utc(2026, 9, 19, 12, 9))
    assert r["force_sweep"] is True and r["force_preview"] is True
    assert r["paper_window"] == "20" and "--days-ahead 2" in r["sweep_args"]
    # retry check: a scheduled success since 7:30am ET today -> skip (EDT: 11:30Z)
    assert r["retry_since"] == "2026-09-19T11:30:00+00:00"
    r = resolve_slot("5 13 * * 6", utc(2026, 11, 14, 13, 9))  # EST: 12:30Z
    assert r["retry_since"] == "2026-11-14T12:30:00+00:00"


def test_dispatch_inputs_and_unknowns():
    r = resolve_slot("", utc(2026, 9, 17, 15, 0))
    assert r["slot"] == "manual" and r["force_sweep"] is True and r["paper_window"] == ""
    r = resolve_slot("", utc(2026, 9, 19, 14, 0), input_slot="saturday")
    assert r["slot"] == "saturday" and r["retry_since"] == ""  # a manual final never self-skips
    with pytest.raises(ValueError):
        resolve_slot("", utc(2026, 9, 19, 14, 0), input_slot="sunday")
    with pytest.raises(ValueError):
        resolve_slot("0 15 * * 6", utc(2026, 9, 19, 15, 0))  # the retired Sat 11am refresh


def test_every_cron_slot_has_sweep_args_and_a_paper_window():
    from beatvegas.ci import PAPER_WINDOW_HOURS, SWEEP_ARGS

    for slot, _ in CRON_SLOTS.values():
        assert slot in SWEEP_ARGS and slot in PAPER_WINDOW_HOURS


def test_no_sweep_pays_for_the_exchange_region():
    """us_ex buys nothing on this market: probed against the live Odds API on
    2026-09-07, the region returned ZERO first-half-total bookmakers across
    three upcoming NCAAF games, at ~50% more credits per event. Every slot
    stays on the config regions (us,us2) — the sweeps never pass --regions."""
    from beatvegas.ci import SWEEP_ARGS

    for slot in SWEEP_ARGS:
        assert "--regions" not in SWEEP_ARGS[slot], slot
        assert "us_ex" not in SWEEP_ARGS[slot], slot
    for cron in ("5 22 * * 5", "5 12 * * 6"):
        now = utc(2026, 9, 25, 22, 9) if cron.endswith("5") else utc(2026, 9, 19, 12, 9)
        assert "--regions" not in resolve_slot(cron, now)["sweep_args"]
