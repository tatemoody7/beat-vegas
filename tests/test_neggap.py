"""H-NEGGAP-P: the paper OVER arms (beatvegas/neggap.py, 2026-09-28).

The rule: three nested arms on the card item's gap in H-PCT-U's universe, one
paper OVER per game per arm at Hard Rock's over price, into challenger_picks and
never manual_picks; graded by the champion's grader made side-aware."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from beatvegas import neggap
from beatvegas.challenger_picks import grade_challenger_picks
from beatvegas.db.models import ChallengerPick, Game, ManualPick, OddsSnapshot
from beatvegas.picks import graded_pick_fields
from tests.conftest import _sqlite_scope

NOW = datetime(2026, 9, 25, 20, 16)
KICK = datetime(2026, 9, 26, 23, 30)


def _item(gid, gap, **over):
    it = {
        "game_id": gid,
        "away": f"A{gid}",
        "home": f"H{gid}",
        "kick": KICK.isoformat() + "Z",
        "hr_line": 23.5,
        "hr_price": -115,
        "hr_over_price": -105,
        "bv_line": round(23.5 - gap, 2),
        "gap": gap,
        "gap_basis": "hardrock",
        "hr_centred": True,
        "hr_live": True,
    }
    it.update(over)
    return it


def _card(items, slot="fri_pm"):
    return {"season": 2026, "week": 4, "slot": slot, "items": items}


def test_arms_are_nested_and_stop_at_zero():
    assert neggap.arm_hits(-4.0) == ["neggap_lt0", "neggap_le175", "neggap_le3"]
    assert neggap.arm_hits(-3.0) == ["neggap_lt0", "neggap_le175", "neggap_le3"]
    assert neggap.arm_hits(-2.0) == ["neggap_lt0", "neggap_le175"]
    assert neggap.arm_hits(-1.75) == ["neggap_lt0", "neggap_le175"]
    assert neggap.arm_hits(-0.5) == ["neggap_lt0"]
    assert neggap.arm_hits(0.0) == [] and neggap.arm_hits(2.5) == [] and neggap.arm_hits(None) == []


def test_the_universe_is_hard_rocks_main_line_with_an_over_price():
    assert neggap.in_universe(_item(1, -2.0))
    assert not neggap.in_universe(_item(1, -2.0, hr_live=False))  # an alternate held over
    assert not neggap.in_universe(_item(1, -2.0, hr_centred=False))
    assert not neggap.in_universe(_item(1, -2.0, hr_over_price=None))
    assert not neggap.in_universe(_item(1, -2.0, bv_line=None))
    assert not neggap.in_universe(_item(1, -2.0, gap_basis="market"))


def test_collection_is_off_unless_switched_on(monkeypatch):
    monkeypatch.delenv("NEGGAP_COLLECT", raising=False)
    assert neggap.collection_enabled() is False
    monkeypatch.setenv("NEGGAP_COLLECT", "1")
    assert neggap.collection_enabled() is True
    assert "off" in neggap.summary_line({}, False)
    assert "neggap_le3 +1" in neggap.summary_line({"neggap_le3": 1, "neggap_lt0": 2}, True)


def test_log_writes_one_over_per_game_per_arm_and_never_a_manual_pick():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        for gid in (1, 2, 3, 4):
            s.add(
                Game(
                    id=gid,
                    season=2026,
                    week=4,
                    home_team=f"H{gid}",
                    away_team=f"A{gid}",
                    start_date=KICK,
                )
            )
        s.commit()
    card = _card(
        [
            _item(1, -4.0),  # all three arms
            _item(2, -1.0),  # lt0 only
            _item(3, 2.5),  # positive gap: the champion's side, never ours
            _item(4, -3.5, hr_live=False),  # an alternate held over: out of the universe
        ]
    )
    with scope() as s:
        added = neggap.log_neggap_picks(s, card, NOW)
        again = neggap.log_neggap_picks(s, card, NOW)  # dedupe per arm
    assert added == {"neggap_lt0": 2, "neggap_le175": 1, "neggap_le3": 1}
    assert again == {}
    with Session(eng) as s:
        rows = s.query(ChallengerPick).order_by(ChallengerPick.id).all()
        assert len(rows) == 4 and all(r.side == "over" and r.book == "hardrockbet" for r in rows)
        assert {(r.game_id, r.arm) for r in rows} == {
            (1, "neggap_lt0"),
            (1, "neggap_le175"),
            (1, "neggap_le3"),
            (2, "neggap_lt0"),
        }
        r = rows[0]
        assert r.line == 23.5 and r.price == -105 and r.slot == "fri_pm" and r.placed_at == NOW
        assert r.gap_at_pick == -4.0 and r.arm_line_at_pick == 27.5 and r.stake == 1.0
        assert s.query(ManualPick).count() == 0


def test_the_paper_window_holds_a_game_for_the_next_build():
    eng, scope = _sqlite_scope()
    far = _item(9, -2.0, kick=(NOW + timedelta(hours=60)).isoformat() + "Z")
    with scope() as s:
        assert neggap.log_neggap_picks(s, _card([far]), NOW, window_hours=48) == {}
        assert neggap.log_neggap_picks(s, _card([far]), NOW, window_hours=None) == {
            "neggap_lt0": 1,
            "neggap_le175": 1,
        }


def test_graded_pick_fields_pays_the_over_and_flips_the_price_clv():
    # JMU @ ODU, week 4: over 21.5 at -325, 47 points; the consensus rose 21.5 -> 21.5.
    won = graded_pick_fields(47, 21.5, -325, 1.0, 23.5, 21.5, 0.52, 0.55, side="over")
    assert won["result"] == "over" and round(won["units"], 4) == 0.3077
    assert (
        won["clv"] == 0.0 and round(won["clv_prob"], 4) == -0.03
    )  # the under's fair rose: bad for an over
    lost = graded_pick_fields(14, 23.5, -125, 1.0, 23.5, 24.5, None, None, side="over")
    assert lost["result"] == "under" and lost["units"] == -1.0 and lost["clv"] == 1.0
    # The under caller is byte-identical.
    assert graded_pick_fields(20, 24.5, -110, 1.0, 24.5, 24.0) == graded_pick_fields(
        20, 24.5, -110, 1.0, 24.5, 24.0, side="under"
    )


def test_grade_challenger_picks_settles_an_over_row_at_hard_rocks_over_close():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=4,
                home_team="ODU",
                away_team="JMU",
                start_date=KICK,
                home_points=30,
                away_points=31,
                first_half_total=47,
                first_half_source="pbp",
            )
        )
        # pre-kick consensus 21.5 (two books), Hard Rock's over -325 at the close
        for book, over, under, at in (
            ("draftkings", -110, -110, KICK - timedelta(hours=3)),
            ("fanduel", -108, -112, KICK - timedelta(hours=3)),
            ("hardrockbet", -325, 230, KICK - timedelta(hours=1)),
        ):
            s.add(
                OddsSnapshot(
                    game_id=1,
                    book=book,
                    market="1H_total",
                    line=21.5,
                    over_price=over,
                    under_price=under,
                    captured_at=at,
                )
            )
        s.add(
            ChallengerPick(
                arm="neggap_le3",
                game_id=1,
                season=2026,
                week=4,
                home_team="ODU",
                away_team="JMU",
                side="over",
                market="1H",
                line=21.5,
                price=-325,
                stake=1.0,
                book="hardrockbet",
                placed_at=NOW,
                graded=False,
            )
        )
        s.commit()
    with scope() as s:
        assert grade_challenger_picks(s, 2026) == 1
    with Session(eng) as s:
        p = s.query(ChallengerPick).one()
        assert p.graded and p.result == "over" and round(p.units, 4) == 0.3077
        assert p.closing_line == 21.5 and p.clv == 0.0
        assert p.closing_captured_at is not None
