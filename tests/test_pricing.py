"""H-PRICE-HR, rule pv1 (beatvegas/pricing.py): the reference must be confirmed at
the capture minute, Hard Rock's rung is skipped, EV reads at Hard Rock's exact
terms (point and lower bound), one opportunity per game-side, evidence tiers from
the feed never exceed 1, spreads are refused, and the registry row is runnable."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from beatvegas import pricing as P
from beatvegas.registry import find_row, parse_registry, require_runnable_row

ROOT = Path(__file__).resolve().parent.parent
KICK = datetime(2026, 10, 10, 19, 30)
T = datetime(2026, 10, 9, 20, 17)


def _snap(
    book, line, over, under, captured, market="1H_total", seen=None, feed=None, home=None, away=None
):
    return P.Snap(1, book, market, line, over, under, home, away, captured, seen, feed, None)


def _game(home_pts=None, away_pts=None, fh=None):
    return {1: P.GameRow(1, 6, "Home", "Away", KICK, home_pts, away_pts, fh)}


def _table():
    return P.MassTable.load()


def test_reference_requires_confirmation_at_the_capture_minute():
    hr = _snap("hardrockbet", 28.5, -110, -110, T)
    refs = [
        _snap(
            "draftkings", 27.5, -110, -110, T - timedelta(hours=5), seen=T + timedelta(minutes=1)
        ),  # re-seen after t
        _snap("fanduel", 27.5, -110, -110, T),  # same minute
        _snap(
            "betmgm", 27.5, -110, -110, T - timedelta(hours=5), seen=T - timedelta(hours=4)
        ),  # stale: not confirmed
        _snap("fliff", 27.5, -110, -110, T),  # excluded book
        _snap("bovada", 27.5, -175, +140, T),  # not centred
    ]
    got = {r.book for r in P.reference_quotes([hr] + refs, "1H_total", T)}
    assert got == {"draftkings", "fanduel"}
    assert {r.book for r in P.reference_quotes([hr] + refs, "1H_total", T, grace_min=600)} == {
        "draftkings",
        "fanduel",
        "betmgm",
    }


def test_ev_totals_hand_worked_and_lower_bound_is_lower():
    table = _table()
    hr = _snap("hardrockbet", 28.5, -110, -110, T)
    refs = [_snap(b, 27.5, -110, -110, T) for b in ("draftkings", "fanduel", "betmgm")]
    point = P.ev_totals(hr, refs, table, conservative=False)
    lower = P.ev_totals(hr, refs, table, conservative=True)
    # The under at 28.5 wins everything the under at 27.5 wins plus a landing on 28:
    # fair under at 27.5 is 0.5, so P(under 28.5) = 0.5 + P(28) and the EV at -110 is positive.
    mass = table.mass("1H_total", 27.5, False)
    assert point["ev_under"] == pytest.approx(
        (0.5 + mass[28]) * (100 / 110) - (1 - 0.5 - mass[28]), abs=1e-6
    )
    assert point["ev_under"] > 0 > point["ev_over"]
    assert lower["ev_under"] < point["ev_under"]  # sampling error only ever lowers the edge
    assert point["books"] == 3 and point["ref_line"] == 27.5
    assert P.ev_totals(hr, refs[:2], table, False) is None  # fewer than MIN_BOOKS
    far = [_snap(b, 31.5, -110, -110, T) for b in ("a", "b", "c")]
    assert P.ev_totals(hr, far, table, False) is None  # beyond MAX_CONVERT_PTS


def test_ev_moneyline_needs_no_conversion():
    hr = _snap("hardrockbet", None, None, None, T, market="full_game_ml", home=-150, away=+140)
    refs = [
        _snap(b, None, None, None, T, market="full_game_ml", home=-180, away=+160)
        for b in ("a", "b", "c")
    ]
    ev = P.ev_moneyline(hr, refs)
    assert (
        ev["ev_home"] > 0 > ev["ev_away"]
    )  # the field has the home side shorter than Hard Rock does


def test_price_states_skips_rungs_flags_on_lower_bound_and_tiers_from_the_feed():
    table = _table()
    # The references stay confirmed through the later states (re-seen at T + 4 h).
    refs = [
        _snap(b, 27.5, -110, -110, T, seen=T + timedelta(hours=4))
        for b in ("draftkings", "fanduel", "betmgm")
    ]
    main = _snap(
        "hardrockbet",
        28.5,
        -110,
        -110,
        T,
        seen=T + timedelta(hours=2),
        feed=T - timedelta(seconds=50),
    )
    rung = _snap(
        "hardrockbet", 30.5, -105, -150, T + timedelta(hours=1)
    )  # -150 under: an alternate rung
    stale_feed = _snap(
        "hardrockbet", 28.5, -110, -110, T + timedelta(hours=3), feed=T - timedelta(hours=2)
    )
    states, drops = P.price_states(
        _game(fh=20), {1: refs + [main, rung, stale_feed]}, "1H_total", table
    )
    assert drops["rung"] == 1 and drops["hr_states"] == 3
    assert [s["tier"] for s in states] == [1, 0]  # fresh + re-seen -> 1; a two-hour-old stamp -> 0
    assert all(s["evidence"].startswith("unverified") for s in states)
    assert states[0]["side"] == "under" and states[0]["result"] == "win"  # 20 under 28.5
    assert states[0]["flag"] == (states[0]["ev_ref_lower"] >= P.EV_FLAG)
    assert states[0]["market_moved"] in {"unchanged", "toward_hr", "away_from_hr", "unknown"}
    opps = P.first_per_game_side(states, flagged_only=False)
    assert len(opps) == 1 and opps[0]["captured_at"] == T  # one per game-side, the first in time


def test_lopsided_moneylines_are_dropped_not_compared():
    hr = _snap("hardrockbet", None, None, None, T, market="full_game_ml", home=-750, away=+500)
    even = _snap("hardrockbet", None, None, None, T, market="full_game_ml", home=-130, away=+110)
    refs = [
        _snap(
            b,
            None,
            None,
            None,
            T,
            market="full_game_ml",
            home=-150,
            away=+130,
            seen=T + timedelta(hours=1),
        )
        for b in ("a", "b", "c")
    ]
    states, drops = P.price_states(
        _game(home_pts=30, away_pts=10), {1: refs + [hr, even]}, "full_game_ml", _table()
    )
    assert drops["lopsided"] == 1 and len(states) == 1
    assert (
        states[0]["hr_home"] == -130 and states[0]["result"] == "win"
    )  # home chosen (field shorter), home won


def test_spreads_are_refused_and_markets_are_fixed():
    with pytest.raises(ValueError):
        P.price_states({}, {}, "full_game_spread", _table())
    assert P.MARKETS == ("1H_total", "full_game_total", "full_game_ml")
    assert P.RULE_VERSION == "pv1" and P.EV_FLAG == 0.02


def test_registry_row_is_exploratory_and_runnable():
    row = find_row(parse_registry(), P.ROW_ID)
    assert row.status == "exploratory"
    assert row.criterion.startswith("None")
    assert require_runnable_row(P.ROW_ID).id == P.ROW_ID


def test_script_refuses_spreads_before_touching_the_database(capsys):
    spec = importlib.util.spec_from_file_location(
        "pricing_check", ROOT / "scripts" / "pricing_check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--markets", "full_game_spread", "--no-init"]) == 2
    assert "REFUSED market" in capsys.readouterr().err
    assert mod.main(["--markets", "nonsense", "--no-init"]) == 2
