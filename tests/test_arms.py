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
    assert P.ARMS_START == "2026-10-13T20:51:39.533351" and P.PROTOCOL_VERSION == "p1.1"
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
