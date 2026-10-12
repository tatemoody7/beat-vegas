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


# --- pv1 is frozen; development vs forward; the Florida checks; the verdict -----------


def test_pv1_constants_are_pinned_and_a_change_needs_a_new_version():
    """Tate 2026-10-12: a change to any threshold, filter or probability treatment is
    pv2, a new row read beside this one. Changing a value here without bumping the
    version fails CI on purpose."""
    assert P.RULE_VERSION == "pv1"
    assert (P.MIN_BOOKS, P.MAX_CONVERT_PTS, P.DEVIG) == (3, 1.5, "multiplicative")
    assert (P.EV_FLAG, P.CONSERVATIVE_Z, P.GRACE_MIN, P.FRESH_MIN) == (0.02, 1.96, 0, 5)
    assert P.ML_MAX_ABS_PRICE == 200
    assert P.FORWARD_CUTOFF == datetime(2026, 10, 13)
    assert (P.VERDICT_MIN_OPPS, P.TOWARD_HR_NULL, P.TOWARD_HR_ALT, P.VERDICT_EV_CLOSE_MIN) == (
        40,
        0.5,
        0.25,
        0.01,
    )
    assert P.FL_MATCH_WINDOW_MIN == 10


def test_split_dev_forward_on_the_cutoff():
    before = {"captured_at": datetime(2026, 10, 12, 23, 59)}
    at = {"captured_at": datetime(2026, 10, 13, 0, 0)}
    dev, fwd = P.split_dev_forward([before, at])
    assert dev == [before] and fwd == [at]


def _state(
    gid=1,
    market="1H_total",
    captured=T,
    line=28.5,
    over=-110,
    under=-110,
    tier=0,
    moved="unchanged",
    ev_close=0.02,
):
    return {
        "game_id": gid,
        "market": market,
        "captured_at": captured,
        "hr_line": line,
        "hr_over": over,
        "hr_under": under,
        "hr_home": None,
        "hr_away": None,
        "tier": tier,
        "evidence": P.TIER_LABEL[tier],
        "market_moved": moved,
        "ev_close": ev_close,
    }


def test_fl_checks_match_only_the_same_quote_within_ten_minutes(tmp_path):
    csv_path = tmp_path / "fl.csv"
    csv_path.write_text(
        "checked_at_utc,game_id,market,app_line,app_over,app_under,app_home,app_away,note\n"
        f"{(T + timedelta(minutes=4)).isoformat()},1,1H_total,28.5,-110,-110,,,same quote\n"  # match
        f"{(T + timedelta(minutes=6)).isoformat()},99,1H_total,30.5,-110,-110,,,other game\n"  # a game with no state
        f"{(T + timedelta(minutes=30)).isoformat()},3,1H_total,28.5,-110,-110,,,too late\n"  # outside the window
        f"{(T + timedelta(minutes=2)).isoformat()},4,1H_total,27.5,-110,-110,,,app showed 27.5\n"  # mismatch
        f"{(T + timedelta(minutes=1)).isoformat()},5,1H_total,28.5,-110,-110,,,one agrees\n"
        f"{(T + timedelta(minutes=3)).isoformat()},5,1H_total,28.5,-105,-115,,,one disagrees\n"  # -> ambiguous
        "not-a-time,6,1H_total,28.5,-110,-110,,,bad row\n"  # invalid, counted, skipped
        f"{T.isoformat()},7,full_game_spread,3.5,,,,,wrong market\n"  # invalid market
    )
    checks = P.load_fl_checks(csv_path)
    assert sum(1 for c in checks if c["invalid"]) == 2
    states = [_state(gid=g) for g in (1, 2, 3, 4, 5)]
    counts = P.apply_fl_checks(states, checks)
    by = {s["game_id"]: s for s in states}
    assert by[1]["fl_check"] == "match" and by[1]["tier"] == 2
    assert by[2]["fl_check"] == "none" and by[2]["tier"] == 0
    assert by[3]["fl_check"] == "none"
    assert by[4]["fl_check"] == "mismatch" and by[4]["tier"] == 0
    assert by[5]["fl_check"] == "ambiguous" and by[5]["tier"] == 0
    assert (
        counts["match"] == 1
        and counts["mismatch"] == 1
        and counts["ambiguous"] == 1
        and counts["invalid_rows"] == 2
    )
    assert P.load_fl_checks(tmp_path / "missing.csv") == []


def test_verdict_is_insufficient_below_the_minimum_then_reads_the_thresholds():
    few = [_state(gid=i) for i in range(10)]
    v = P.verdict(few)
    assert v["verdict"] == "insufficient" and "10 forward opportunities" in v["why"]
    # 40 forward opportunities, market never toward HR, close EV +2% each: strengthening.
    strong = [_state(gid=i, moved="unchanged", ev_close=0.02 + (i % 3) * 0.001) for i in range(40)]
    assert P.verdict(strong)["verdict"] == "strengthening"
    # Three in five moved toward Hard Rock (the 90% lower bound clears 40%): weakening.
    weak = [
        _state(gid=i, moved="toward_hr" if i % 5 < 3 else "unchanged", ev_close=0.02)
        for i in range(40)
    ]
    assert P.verdict(weak)["verdict"] == "weakening"
    # Close EV at zero: weakening even if the market never moved.
    flat = [_state(gid=i, moved="unchanged", ev_close=0.0) for i in range(40)]
    assert P.verdict(flat)["verdict"] == "weakening"
    # 18 of 40 toward (90% bounds about 33% to 57%): neither bound crossed -> inconclusive.
    mid = [
        _state(gid=i, moved="toward_hr" if i % 20 < 9 else "unchanged", ev_close=0.02)
        for i in range(40)
    ]
    assert P.verdict(mid)["verdict"] == "inconclusive"


def test_wilson_interval_hand_checked():
    lo, hi = P.wilson(10, 40)
    assert 0.15 < lo < 0.17 and 0.36 < hi < 0.38  # 25% on 40 at 90%: about 16% to 37%
    assert P.wilson(0, 0) == (None, None)
