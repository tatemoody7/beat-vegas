"""The registered protocol arms (docs/HYPOTHESES.md H-ARM-1HU / 1HO / FGU,
Tate's calls of 2026-10-08): arm 2's bottom-20% overs mirror, arm 3's uncapped
full-game rule, the position script that reads them, and the `no_price`
exclusion that keeps an unpriced paper pick counted rather than silent."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy.orm import Session

from beatvegas import arm_paper, fg_paper
from beatvegas import protocol as P
from beatvegas.consensus import EX_NO_PRICE, fields_for_pick
from beatvegas.db.models import ChallengerPick, Game, ManualPick
from beatvegas.db.store import _MIGRATIONS
from tests.conftest import _sqlite_scope

NOW = datetime(2026, 10, 9, 20, 16)
KICK = datetime(2026, 10, 10, 19, 30)


def _item(gid, gap, **over):
    it = {
        "game_id": gid,
        "away": f"A{gid}",
        "home": f"H{gid}",
        "kick": KICK.isoformat() + "Z",
        "hr_line": 27.5,
        "hr_price": -110,
        "hr_over_price": -110,
        "bv_line": round(27.5 - gap, 2),
        "gap": gap,
        "hr_centred": True,
        "hr_live": True,
    }
    it.update(over)
    return it


def _card(items):
    return {"season": 2026, "week": 6, "slot": "fri_pm", "items": items}


def test_the_arms_are_registered_with_their_slots():
    assert P.ARMS[P.ARM_1H_UNDER] == {
        "table": "manual_picks",
        "market": "1H",
        "side": "under",
        "slot": 1,
    }
    assert P.ARMS[P.ARM_1H_OVER]["side"] == "over" and P.ARMS[P.ARM_1H_OVER]["slot"] == 2
    assert P.ARMS[P.ARM_FG_UNDER]["market"] == "full" and P.ARMS[P.ARM_FG_UNDER]["slot"] == 3
    assert P.ARMS_TAGGED_FROM == "2026-10-09T00:00:00"
    # p1.1 (roadmap v1.5, 2026-10-09): paused before any completed week, until the
    # first card built on the leak-fixed model -- the 2026-10-13 tue_pm card
    # (Tate's approval 2026-10-13). The 2026-10-09 rows sit before it.
    assert P.ARMS_START == "2026-10-13T20:51:39.533351" and P.PROTOCOL_VERSION == "p1.2"
    assert P.ARMS_START > P.ARMS_TAGGED_FROM
    for arm in (P.ARM_1H_UNDER, P.ARM_1H_OVER, P.ARM_FG_UNDER):
        assert P.arm_start(arm) == P.ARMS_START


def test_a_paused_arm_reports_no_reading_and_says_so(load_script):
    pos = load_script("protocol_position")
    line = pos.paused_arm(7)
    assert line["state"] == P.PAUSED and line["readings"] == 0 and line["logged"] == 7
    assert line["label"].startswith("PAUSED")
    md = pos.render({"generated_at": "now", "arms": {P.ARM_1H_UNDER: {**line, "slot": 1}}})
    assert "**Clocks paused**" in md and "| H-ARM-1HU | 1 | PAUSED" in md


def test_a_running_read_carries_no_pause_note(load_script):
    pos = load_script("protocol_position")
    line = pos.read_arm([_row(2026, 7, True, 0.01)])
    md = pos.render({"generated_at": "now", "arms": {P.ARM_1H_UNDER: {**line, "slot": 1}}})
    assert "Clocks paused" not in md and "IN FORWARD TEST" in md


def test_slate_floor_mirrors_the_bar():
    # 10 gaps -> k = 2: the 2nd smallest
    gaps = [3.0, 2.0, 1.0, 0.5, 0.0, -0.5, -1.0, -2.0, -2.0, -3.0]
    assert arm_paper.slate_floor(gaps) == -2.0
    assert arm_paper.slate_floor([1.5]) == 1.5
    assert arm_paper.slate_floor([]) is None


def test_select_takes_the_bottom_20_percent_below_zero_with_ties():
    items = [
        _item(i, g) for i, g in enumerate([3.0, 2.0, 1.0, 0.5, 0.0, -0.5, -1.0, -2.0, -2.0], 1)
    ]
    items.append(_item(10, -3.0))
    items.append(_item(11, -9.0, hr_centred=False))  # an alternate line: out of the slate
    no_read = _item(12, -4.0)
    no_read.update(bv_line=None, gap=None)  # no model read: out
    items.append(no_read)
    sel = arm_paper.select(items)
    assert sel["n"] == 10 and sel["floor"] == -2.0
    assert sorted(it["game_id"] for it in sel["qualifying"]) == [8, 9, 10]  # tie at -2 qualifies


def test_select_never_takes_a_gap_at_or_above_zero_and_needs_an_over_price():
    # 5 games -> k = 1; the smallest gap is +0.5: no qualifier (the mirror needs gap < 0)
    items = [_item(i, g) for i, g in enumerate([2.0, 1.5, 1.0, 0.8, 0.5], 1)]
    assert arm_paper.select(items)["qualifying"] == []
    items = [_item(1, 1.0), _item(2, 0.5), _item(3, -1.0, hr_over_price=None), _item(4, 2.0)]
    assert arm_paper.select(items)["qualifying"] == []  # the floor game has no over price


def test_log_writes_one_over_per_game_into_challenger_picks_only():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        for gid in range(1, 6):
            s.add(Game(id=gid, season=2026, week=6, home_team=f"H{gid}", away_team=f"A{gid}"))
        s.commit()
    card = _card([_item(1, 2.0), _item(2, 1.0), _item(3, -1.5), _item(4, 0.5), _item(5, 0.2)])
    with scope() as s:
        first = arm_paper.log_overs_mirror(s, card, NOW)
        again = arm_paper.log_overs_mirror(s, card, NOW)
    assert first["added"] == 1 and first["floor"] == -1.5 and first["universe"] == 5
    assert again["added"] == 0
    with Session(eng) as s:
        (r,) = s.query(ChallengerPick).all()
        assert (r.arm, r.side, r.market, r.game_id) == ("H-ARM-1HO", "over", "1H", 3)
        assert r.line == 27.5 and r.price == -110 and r.book == "hardrockbet"
        assert r.gap_at_pick == -1.5 and r.placed_at == NOW
        assert s.query(ManualPick).count() == 0


def test_the_overs_window_holds_a_far_game_for_a_later_build():
    eng, scope = _sqlite_scope()
    far = _item(9, -2.0, kick=(NOW + timedelta(hours=60)).isoformat() + "Z")
    with scope() as s:
        assert arm_paper.log_overs_mirror(s, _card([far]), NOW, window_hours=24)["added"] == 0
        assert arm_paper.log_overs_mirror(s, _card([far]), NOW, window_hours=None)["added"] == 1


def _fg(gid, gap):
    return {"game_id": gid, "gap": gap, "kick": KICK, "away": f"A{gid}"}


def test_fg_arm_is_uncapped_and_needs_a_positive_gap():
    # 10 games -> k = 2, bar = 3.0; six tie at 3.0: capped H-FG-P takes 5,
    # the registered arm takes all six.
    items = [_fg(i, 3.0) for i in range(1, 7)] + [_fg(i, -1.0) for i in range(7, 11)]
    capped = fg_paper.select([dict(it) for it in items], [])
    arm = fg_paper.select([dict(it) for it in items], [], cap=None, require_positive=True)
    assert len(capped["selected"]) == 5 and len(arm["selected"]) == 6
    # A slate whose bar falls at or below zero: the arm takes nothing below it.
    low = [_fg(1, 0.0), _fg(2, -0.5), _fg(3, -1.0), _fg(4, -2.0), _fg(5, -3.0)]
    sel = fg_paper.select(low, [], cap=None, require_positive=True)
    assert sel["bar"] == 0.0 and sel["selected"] == [] and sel["qualifying"] == 0


def _row(season, week, graded, ev, excluded=None):
    return SimpleNamespace(
        season=season, week=week, graded=graded, ev_cons=ev, cons_excluded=excluded
    )


def test_position_reads_only_completed_weeks_and_counts_exclusions(load_script):
    pos = load_script("protocol_position")
    rows = [
        _row(2026, 6, True, 0.02),
        _row(2026, 6, True, None, "stale_close"),
        _row(2026, 6, True, None, "no_price"),
        _row(2026, 7, True, 0.10),
        _row(2026, 7, False, None),  # week 7 not finished: none of it enters
    ]
    r = pos.read_arm(rows)
    assert r["completed_weeks"] == ["2026-w6"] and r["pending"] == 2
    assert r["readings"] == 1 and r["excluded"] == 2
    assert r["excluded_by_reason"] == {"stale_close": 1, "no_price": 1}
    assert r["state"] == P.RUNNING and r["mean_ev"] == 0.02


def test_an_unpriced_pick_is_excluded_by_name(monkeypatch):
    """The consensus reads a close but EV needs a price: a paper pick logged
    before Hard Rock priced its line is counted as `no_price`, never silent."""
    import beatvegas.consensus as C

    read = C.Reading(books=4, center_line=27.5, p_win=0.52, p_push=0.0, ev=None)
    monkeypatch.setattr(C, "consensus_reading", lambda *a, **k: read)
    monkeypatch.setattr(C, "hr_reading", lambda *a, **k: C.Reading(ev=None))
    unpriced = SimpleNamespace(market="1H", side="under", line=27.5, price=None)
    fields = fields_for_pick([], datetime(2026, 10, 10, 19, 30), unpriced, table=object())
    assert fields["cons_excluded"] == EX_NO_PRICE == "no_price"
    assert fields["ev_cons"] is None and fields["cons_books"] == 4
    priced = SimpleNamespace(market="1H", side="under", line=27.5, price=-110)
    assert fields_for_pick([], None, priced, table=object())["cons_excluded"] is None


def test_manual_picks_carries_the_arm_column():
    assert "arm" in ManualPick.__table__.columns
    assert _MIGRATIONS["manual_picks"]["arm"] == "VARCHAR(16)"


# --- p1.2 (Tate, 2026-10-14): the reading unit and the Monday rule ------------------
from datetime import datetime as _dt  # noqa: E402


def _prow(week, kick, graded=True, ev=0.01, season_type="regular", excluded=None, books=5):
    return SimpleNamespace(
        season=2026,
        week=week,
        graded=graded,
        ev_cons=ev,
        cons_excluded=excluded,
        cons_books=books,
        kickoff=kick,
        season_type=season_type,
    )


def test_a_week_closes_at_the_monday_noon_utc_after_its_last_kickoff(load_script):
    pos = load_script("protocol_position")
    assert pos.week_closes_at(_dt(2026, 10, 17, 23, 30)) == _dt(
        2026, 10, 19, 12, 0
    )  # Saturday night
    assert pos.week_closes_at(_dt(2026, 10, 19, 0, 30)) == _dt(
        2026, 10, 19, 12, 0
    )  # Sunday night ET
    assert pos.week_closes_at(_dt(2026, 10, 19, 12, 30)) == _dt(
        2026, 10, 26, 12, 0
    )  # a Monday game


def test_a_mid_week_read_counts_no_partial_week(load_script):
    """R2: every row logged so far graded is not enough; the week must be over."""
    pos = load_script("protocol_position")
    rows = [_prow(7, _dt(2026, 10, 14, 0, 0)), _prow(7, _dt(2026, 10, 17, 19, 30))]
    wednesday = pos.read_arm(rows, now=_dt(2026, 10, 15, 12, 0))
    assert (
        wednesday["readings"] == 0
        and wednesday["pending"] == 2
        and wednesday["completed_weeks"] == []
    )
    just_before = pos.read_arm(rows, now=_dt(2026, 10, 19, 11, 59))
    assert just_before["readings"] == 0
    monday = pos.read_arm(rows, now=_dt(2026, 10, 19, 12, 0))
    assert monday["readings"] == 2 and monday["completed_weeks"] == ["2026-w7"]
    # An ungraded row still holds its week, whatever the clock says.
    held = pos.read_arm(
        rows + [_prow(7, _dt(2026, 10, 17, 19, 30), graded=False, ev=None)],
        now=_dt(2026, 10, 26, 12, 0),
    )
    assert held["readings"] == 0 and held["pending"] == 3


def test_bowls_read_by_iso_week_across_new_year_after_the_regular_season(load_script):
    """R1: CFBD files every bowl as week 1; the reading unit is the ISO week of kickoff."""
    pos = load_script("protocol_position")
    rows = [
        _prow(1, _dt(2026, 12, 30, 1, 0), season_type="postseason", ev=0.02),
        _prow(
            1, _dt(2027, 1, 2, 20, 0), season_type="postseason", ev=0.04
        ),  # same ISO week 2026-W53
        _prow(1, _dt(2027, 1, 12, 0, 30), season_type="postseason", ev=-0.01),  # 2027-W02
        _prow(14, _dt(2026, 11, 28, 19, 0), ev=0.0),  # the last regular week
    ]
    r = pos.read_arm(rows, now=_dt(2027, 1, 19, 12, 0))
    assert r["completed_weeks"] == ["2026-w14", "2026-post-2026W53", "2026-post-2027W02"]
    assert r["readings"] == 4 and r["weeks"] == 3
    assert [pos.key_label(pos.reading_key(x)) for x in rows[:2]] == ["2026-post-2026W53"] * 2


def test_exclusions_are_reported_by_the_close_book_count(load_script):
    """Programme 4.2: a report line beside each arm, never a gate."""
    pos = load_script("protocol_position")
    rows = [
        _prow(6, _dt(2026, 10, 10, 19, 0), ev=None, excluded="stale_close", books=0),
        _prow(6, _dt(2026, 10, 10, 19, 0), ev=None, excluded="few_books", books=2),
        _prow(6, _dt(2026, 10, 10, 19, 0), ev=0.01, books=6),
    ]
    r = pos.read_arm(rows, now=_dt(2026, 10, 12, 12, 0))
    assert r["excluded_by_books"] == {"0": 1, "2": 1} and r["excluded"] == 2
    md = pos.render({"generated_at": "now", "arms": {P.ARM_1H_UNDER: {**r, "slot": 1}}})
    assert "exclusions by close book count (the judge needs 3+): 0 books 1, 2 books 1" in md


def test_r3_prime_a_judged_pick_counts_whatever_its_result_and_stays_marked_unverified(load_script):
    """p1.2 R3' (Tate, 2026-10-14): the reading is the close, never the score. A
    pick the judge has read completes its week even while its result is unproven;
    the result is reported unverified, not hidden and not discarded."""
    pos = load_script("protocol_position")
    kick = _dt(2026, 10, 17, 19, 30)
    proven = _prow(7, kick, graded=True, ev=0.02)
    unproven = _prow(7, kick, graded=False, ev=0.04)  # read from the close, 0-0 half unproven
    unproven.cons_version = "cv1"
    r = pos.read_arm([proven, unproven], now=_dt(2026, 10, 19, 12, 0))
    assert r["readings"] == 2 and r["completed_weeks"] == ["2026-w7"]
    assert r["results_unverified"] == 1 and r["pending"] == 0
    md = pos.render({"generated_at": "now", "arms": {P.ARM_1H_UNDER: {**r, "slot": 1}}})
    assert "1 judged pick(s) whose result is not verified yet" in md


def test_r3_prime_an_unjudged_pick_still_holds_its_week(load_script):
    pos = load_script("protocol_position")
    kick = _dt(2026, 10, 17, 19, 30)
    not_read = _prow(7, kick, graded=False, ev=None)
    r = pos.read_arm([_prow(7, kick), not_read], now=_dt(2026, 10, 26, 12, 0))
    assert r["readings"] == 0 and r["pending"] == 2


def test_r3_prime_the_judge_reads_a_pick_an_hour_after_kickoff(load_script):
    cb = load_script("consensus_backfill")
    kick = _dt(2026, 10, 17, 19, 30)
    assert cb.READ_AFTER_KICKOFF_H == 1.0
    assert cb.needs_reading(True, None, kick) is True  # graded rows, as before
    assert cb.needs_reading(False, kick, _dt(2026, 10, 17, 20, 29)) is False
    assert cb.needs_reading(False, kick, _dt(2026, 10, 17, 20, 30)) is True
    assert cb.needs_reading(False, None, _dt(2026, 10, 30, 0, 0)) is False  # no kickoff: never read


# --- H-ARM-EVP, exploratory (Tate's option A, 2026-10-14) ---------------------------


def _xrow(gid, week, kick, ev=0.01, excluded=None):
    return SimpleNamespace(
        game_id=gid,
        season=2026,
        week=week,
        graded=True,
        cons_version="cv1",
        ev_cons=ev,
        cons_excluded=excluded,
        cons_books=5,
        kickoff=kick,
        season_type="regular",
    )


def test_the_exploratory_read_compares_with_the_gap_rule_over_the_same_weeks(load_script):
    pos = load_script("protocol_position")
    sat7, sat8 = _dt(2026, 10, 17, 19), _dt(2026, 10, 24, 19)
    evp = [
        _xrow(1, 8, sat7, 0.04),
        _xrow(2, 8, sat7, None, "far_lines"),
        _xrow(3, 9, sat8, 0.02),  # week 9 not closed at this read: pending
    ]
    gap = [
        _xrow(1, 8, sat7, 0.04),  # the same game, both rules
        _xrow(4, 8, sat7, -0.06),
        _xrow(5, 7, _dt(2026, 10, 10, 19), 0.5),  # a week EVP has no pick in: left out
    ]
    now = _dt(2026, 10, 19, 12, 30)
    x = pos.exploratory_read(evp, gap, now)
    assert (x["logged"], x["readings"], x["excluded"], x["pending"], x["weeks"]) == (3, 1, 1, 1, 1)
    assert x["excluded_by_reason"] == {"far_lines": 1}
    assert x["picks_per_week"] == {"2026-w8": 2, "2026-w9": 1}
    assert x["mean_ev"] == 0.04 and x["ev_lo"] is None  # one reading: no interval
    c = x["comparison"]
    assert c["against"] == "H-ARM-1HU" and c["weeks"] == ["2026-w8"]
    assert c["gap_rule"]["n"] == 2 and c["gap_rule"]["mean_ev"] == -0.01
    assert c["gap_rule"]["excluded"] == 0
    assert (c["both"], c["evp_only"], c["gap_only"]) == (1, 1, 1)
    assert x["state"] == "exploratory" and x["label"] == "EXPLORATORY"


def test_the_exploratory_row_has_no_llr_and_no_readings_target():
    from beatvegas import positions as X

    line = {
        "logged": 3,
        "readings": 1,
        "weeks": 1,
        "excluded": 1,
        "pending": 1,
        "mean_ev": 0.04,
        "ev_lo": None,
        "ev_hi": None,
        "state": "exploratory",
        "label": "EXPLORATORY",
        "comparison": {"both": 1},
    }
    row = X.exploratory_position("H-ARM-EVP", line, _dt(2026, 10, 19, 12, 30), "123")
    assert row["standard"] == X.STANDARD_EXPLORATORY == "exploratory"
    assert row["llr"] is None and row["needed"] is None
    assert row["read_date"] == "2026-10-19" and row["next_read"] == "2026-10-26"
    assert "H-ARM-EVP" in X.EXPLORATORY_IDS and "H-ARM-EVP" not in P.ARMS
