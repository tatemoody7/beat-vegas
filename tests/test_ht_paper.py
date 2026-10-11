"""The high-total arm H-ARM-HT1H (docs/HYPOTHESES.md; roadmap v1.8, Tate's calls of
2026-10-10): the consensus full-game total on the judge's books, the 60.0 line, and
paper first-half unders at Hard Rock's price into challenger_picks only."""

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from beatvegas import ht_paper as HT
from beatvegas import protocol as P
from beatvegas.db.models import ChallengerPick, Game, ManualPick, OddsSnapshot
from tests.conftest import _sqlite_scope

NOW = datetime(2026, 10, 13, 20, 10)  # a Tuesday build
KICK = datetime(2026, 10, 17, 19, 30)  # Saturday


def _seed(eng, game_ids, quotes):
    """quotes: [(game_id, book, line, over, under, hours_before_now)]."""
    with Session(eng) as s:
        for gid in game_ids:
            s.add(
                Game(
                    id=gid,
                    season=2026,
                    week=8,
                    home_team=f"H{gid}",
                    away_team=f"A{gid}",
                    start_date=KICK,
                )
            )
        for gid, book, line, over, under, hours in quotes:
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book=book,
                    market="full_game_total",
                    line=line,
                    over_price=over,
                    under_price=under,
                    captured_at=NOW - timedelta(hours=hours),
                )
            )
        s.commit()


def _books(gid, lines, hours=10):
    """One centred quote per book, for the books needed."""
    names = ["draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers"]
    return [(gid, b, ln, -110, -110, hours) for b, ln in zip(names, lines)]


def test_the_consensus_is_the_median_of_each_counted_books_newest_centred_quote():
    eng, scope = _sqlite_scope()
    quotes = [
        (1, "draftkings", 60.5, -110, -110, 30),
        (1, "draftkings", 61.5, -110, -110, 5),  # newer: counts
        (1, "fanduel", 59.5, -110, -110, 8),
        (1, "betmgm", 60.0, -110, -110, 8),
        (1, "williamhill_us", 58.5, -110, -110, 20),  # its last centred quote
        (1, "williamhill_us", 75.5, -170, 135, 2),  # an off-centre rung: never counts
        (1, "hardrockbet", 70.0, -110, -110, 3),  # the book we bet into: never counts
        (1, "fliff", 70.0, -110, -110, 3),
        (1, "consensus", 70.0, -110, -110, 3),
        (1, "draftkings", 90.5, -110, -110, -1),  # after the build: never read
    ]
    _seed(eng, [1], quotes)
    with scope() as s:
        got = HT.consensus_totals(s, [1], NOW)[1]
    assert got["books"] == 4
    assert got["total"] == 59.75  # median of 58.5, 59.5, 60.0, 61.5
    assert [q["book"] for q in got["quotes"]] == [
        "betmgm",
        "draftkings",
        "fanduel",
        "williamhill_us",
    ]
    assert {q["book"]: q["line"] for q in got["quotes"]}["draftkings"] == 61.5


def test_fewer_than_three_counted_books_is_no_consensus():
    eng, scope = _sqlite_scope()
    quotes = _books(1, [62.5, 63.5]) + [(1, "hardrockbet", 63.0, -110, -110, 1)]
    quotes += _books(2, [62.5, 63.5, 64.5])
    _seed(eng, [1, 2], quotes)
    with scope() as s:
        got = HT.consensus_totals(s, [1, 2], NOW)
    assert 1 not in got and got[2]["total"] == 63.5 and got[2]["books"] == 3


def test_sixty_is_the_line():
    assert HT.HT_TOTAL_MIN == 60.0
    assert HT.qualifies({"total": 60.0}) is True
    assert HT.qualifies({"total": 59.5}) is False
    assert HT.qualifies(None) is False


def _item(gid, **over):
    it = {
        "game_id": gid,
        "home": f"H{gid}",
        "away": f"A{gid}",
        "kick": KICK.isoformat() + "Z",
        "hr_line": 31.5,
        "hr_price": -112,
        "hr_centred": True,
    }
    it.update(over)
    return it


def test_logs_each_high_total_game_once_at_hard_rocks_main_line():
    eng, scope = _sqlite_scope()
    quotes = _books(1, [60.5, 61.0, 61.5]) + _books(2, [59.0, 59.5, 60.0])
    quotes += _books(3, [64.5, 65.0, 65.5])
    _seed(eng, [1, 2, 3, 4], quotes)
    card = {
        "season": 2026,
        "week": 8,
        "slot": "tue_pm",
        # 1 qualifies (61.0); 2 does not (59.5); 3 qualifies but Hard Rock's line is
        # off-centre; 4 has no full-game quote at all.
        "items": [_item(1), _item(2), _item(3, hr_centred=False), _item(4)],
    }
    with scope() as s:
        first = HT.log_first_half(s, card, NOW)
        again = HT.log_first_half(s, card, NOW)
    assert first == {"priced": 3, "with_consensus": 2, "high": 1, "added": 1}
    assert again["added"] == 0
    with Session(eng) as s:
        (r,) = s.query(ChallengerPick).all()
        assert (r.arm, r.side, r.market, r.game_id) == ("H-ARM-HT1H", "under", "1H", 1)
        assert r.line == 31.5 and r.price == -112 and r.book == "hardrockbet"
        assert r.slot == "tue_pm" and r.placed_at == NOW
        frozen = json.loads(r.factors_json_at_pick)
        assert frozen["consensus_fg_total"] == 61.0 and frozen["books"] == 3
        assert frozen["total_min"] == 60.0 and frozen["min_books"] == 3
        assert s.query(ManualPick).count() == 0


def test_respects_the_paper_window():
    eng, scope = _sqlite_scope()
    _seed(eng, [1], _books(1, [62.0, 62.5, 63.0]))
    card = {"season": 2026, "week": 8, "slot": "tue_pm", "items": [_item(1)]}
    with scope() as s:
        assert HT.log_first_half(s, card, NOW, window_hours=48)["added"] == 0  # 95 h out
        assert HT.log_first_half(s, card, NOW, window_hours=None)["added"] == 1


def test_the_arm_holds_ledger_slot_8_on_its_own_clock():
    assert P.ARMS[P.ARM_HT_1H] == {
        "table": "challenger_picks",
        "market": "1H",
        "side": "under",
        "slot": 8,
    }
    assert P.arm_start(P.ARM_HT_1H) == P.HT_ARM_START == "2026-10-10T00:00:00"
    slots = [a["slot"] for a in P.ARMS.values()]
    assert len(slots) == len(set(slots)) and len(slots) <= P.K_TESTS


def test_the_summary_line():
    assert HT.summary_lines(None)[0].endswith(": not run")
    line = HT.summary_lines({"priced": 52, "with_consensus": 50, "high": 4, "added": 3})[0]
    assert "4 of 52 Hard Rock-priced games (50 with a 3+ book consensus), +3 logged" in line
