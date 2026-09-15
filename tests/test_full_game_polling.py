"""Full-game capture: schema carries spread, change-detection, derived opener."""

import importlib.util
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, OddsSnapshot

_ROOT = Path(__file__).resolve().parent.parent


def _load(script_name: str):
    """Import a scripts/*.py module by path (scripts/ is not a package)."""
    path = _ROOT / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(script_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_schema_has_spread_columns():
    assert "spread" in OddsSnapshot.__table__.columns
    assert "spread" in Game.__table__.columns


def test_change_detection():
    _changed = _load("poll_full_game")._changed

    class Snap:
        def __init__(self, line, spread, over, under):
            self.line, self.spread = line, spread
            self.over_price, self.under_price = over, under

    assert _changed(None, 55.5, -7.0, -110, -110) is True  # first ever
    prev = Snap(55.5, -7.0, -110, -110)
    assert _changed(prev, 55.5, -7.0, -110, -110) is False  # unchanged
    assert _changed(prev, 56.0, -7.0, -110, -110) is True  # total moved
    assert _changed(prev, 55.5, -7.5, -110, -110) is True  # spread moved
    assert _changed(prev, 55.5, -7.0, -115, -110) is True  # price moved
    # A source with no spread (Odds API totals rows) is "unknown", not "moved":
    # a DK->oddsapi switch must not write a redundant snapshot.
    assert _changed(prev, 55.5, None, -110, -110) is False


def test_snapshot_duplicate_capture_rejected():
    import pytest
    from sqlalchemy.exc import IntegrityError

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)

    def snap():
        return OddsSnapshot(
            game_id=1,
            book="draftkings",
            market="full_game_total",
            line=55.5,
            captured_at=datetime(2026, 9, 1, 12, 0),
        )

    with Session(eng) as s:
        s.add(snap())
        s.commit()
        s.add(snap())
        with pytest.raises(IntegrityError):
            s.commit()


def test_book_rank_precedence():
    mod = _load("poll_full_game")
    _book_rank = mod._book_rank
    assert _book_rank("draftkings") < _book_rank("consensus") < _book_rank("hardrockbet")
    assert _book_rank("DraftKings") == _book_rank("draftkings")  # CFBD spelling
    assert _book_rank(None) == _book_rank("some-random-book")


def test_auto_fallback_keeps_dk_1h_rows(monkeypatch):
    mod = _load("poll_full_game")

    class _DK:
        def fetch_ncaaf(self):
            return {"events": [{"id": 1}]}

    h1_row = {"event_id": "1", "book": "draftkings", "line": 27.5}
    monkeypatch.setattr(mod, "DraftKingsClient", _DK)
    monkeypatch.setattr(mod, "normalize_full_game", lambda p: [])  # DK FG empty
    monkeypatch.setattr(mod, "normalize_first_half", lambda p: [h1_row])
    monkeypatch.setattr(mod, "CFBDClient", lambda: None)
    monkeypatch.setattr(mod, "cfbd_full_game_rows", lambda c, season: [{"game_id": 5}])

    fg, h1, source, _ = mod._fetch("auto", 2026)
    assert source == "cfbd" and fg == [{"game_id": 5}]
    assert h1 == [h1_row]  # DK 1H rows survive the CFBD fallback


def test_full_game_snapshot_roundtrips_spread():
    eng = create_engine("sqlite:///:memory:")  # isolated, not the global
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            OddsSnapshot(
                game_id=1,
                book="draftkings",
                market="full_game_total",
                line=55.5,
                spread=-17.0,
                over_price=-110,
                under_price=-110,
                captured_at=datetime(2026, 9, 1),
            )
        )
        s.commit()
        got = s.query(OddsSnapshot).filter_by(market="full_game_total").one()
        assert got.line == 55.5 and got.spread == -17.0


def test_oddsapi_normalize_full_game_multibook_incl_hardrock():
    from beatvegas.sources.odds import normalize_full_game

    events = [
        {
            "id": "evt1",
            "commence_time": "2026-08-30T16:00:00Z",
            "home_team": "LSU",
            "away_team": "Clemson",
            "bookmakers": [
                {
                    "key": "hardrockbet_fl",
                    "markets": [
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "price": -110, "point": 56.5},
                                {"name": "Under", "price": -110, "point": 56.5},
                            ],
                        }
                    ],
                },
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "price": -108, "point": 57.0},
                                {"name": "Under", "price": -112, "point": 57.0},
                            ],
                        }
                    ],
                },
                {"key": "fanduel", "markets": [{"key": "spreads", "outcomes": []}]},  # ignored
            ],
        }
    ]
    rows = normalize_full_game(events)
    by_book = {r["book"]: r for r in rows}
    # fanduel has no totals market (no row); hardrockbet_fl folds onto hardrockbet
    assert set(by_book) == {"hardrockbet", "draftkings"}
    assert by_book["hardrockbet"]["line"] == 56.5
    # no spreads market in this fixture for hardrock -> spread unknown, not 0
    assert by_book["hardrockbet"]["spread"] is None
    assert all(r["event_id"] == "evt1" for r in rows)


def test_oddsapi_normalize_dedupes_book_listed_twice():
    """Requesting several regions (us,us2,us_ex) can list one bookmaker key twice
    for an event; two rows sharing (game, book, market, captured_at) violate
    uq_odds_snapshot on insert (live Sunday failure 2026-09-02). Keep the
    freshest quote."""
    from beatvegas.sources.odds import normalize_full_game

    def bm(key, point, last_update):
        return {
            "key": key,
            "markets": [
                {
                    "key": "totals",
                    "last_update": last_update,
                    "outcomes": [
                        {"name": "Over", "price": -110, "point": point},
                        {"name": "Under", "price": -110, "point": point},
                    ],
                }
            ],
        }

    events = [
        {
            "id": "evt1",
            "commence_time": "2026-09-05T20:00:00Z",
            "home_team": "Ohio State",
            "away_team": "Ball State",
            "bookmakers": [
                bm("fanduel", 61.5, "2026-09-02T01:30:00Z"),
                bm("kalshi", 61.5, "2026-09-02T01:35:00Z"),
                bm("fanduel", 62.0, "2026-09-02T01:35:00Z"),  # same key again, fresher
            ],
        }
    ]
    rows = normalize_full_game(events)
    books = [r["book"] for r in rows]
    assert sorted(books) == ["fanduel", "kalshi"]
    assert next(r for r in rows if r["book"] == "fanduel")["line"] == 62.0


def test_full_game_opener_consensus_with_spread():
    _full_game_opener = _load("weekly_update")._full_game_opener

    class Snap:
        def __init__(self, book, line, spread, cap):
            self.book, self.line, self.spread, self.captured_at = book, line, spread, cap

    snaps = [
        Snap("dk", 56.0, -7.0, datetime(2026, 9, 1, 12)),  # dk opener
        Snap("dk", 57.0, -7.5, datetime(2026, 9, 3, 12)),  # later move (ignored)
        Snap("fd", 58.0, -8.0, datetime(2026, 9, 1, 12)),  # fd opener
    ]
    total, spread = _full_game_opener(snaps)
    assert total == 57.0  # median(56.0, 58.0)
    assert spread == -7.5  # median(-7.0, -8.0)


def test_consensus_spread_is_the_median_of_known_spreads():
    _consensus_spread = _load("poll_full_game")._consensus_spread
    rows = [{"spread": -7.0}, {"spread": None}, {"spread": -8.0}, {"spread": -6.5}]
    assert _consensus_spread(rows) == -7.0
    assert _consensus_spread([{"spread": -7.0}, {"spread": -8.0}]) == -7.5
    assert _consensus_spread([{"spread": None}, {}]) is None
    assert _consensus_spread([]) is None


def _row(gid, book, line, spread, over=-110, under=-110):
    return {
        "game_id": gid,
        "book": book,
        "line": line,
        "spread": spread,
        "over_price": over,
        "under_price": under,
        "commence_time": None,
    }


def _run_poll(mod, monkeypatch, eng, fg_rows, now, source="oddsapi"):
    import sys
    from contextlib import contextmanager

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    class _Now(datetime):
        @classmethod
        def utcnow(cls):
            return now

    monkeypatch.setattr(mod, "session_scope", scope)
    monkeypatch.setattr(mod, "try_init_db", lambda: True)
    monkeypatch.setattr(mod, "datetime", _Now)
    monkeypatch.setattr(
        mod, "_fetch", lambda src, season, regions, credit_floor=60: (fg_rows, [], source, 1)
    )
    monkeypatch.setattr(sys, "argv", ["poll_full_game.py", "--season", "2026", "--source", source])
    mod.main()


def test_two_runs_move_spread_but_fill_total_only_when_null(monkeypatch):
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=3, home_team="LSU", away_team="Clemson"))
        s.commit()

    run1 = [_row(1, "draftkings", 55.5, -7.0), _row(1, "fanduel", 56.0, -8.0)]
    _run_poll(mod, monkeypatch, eng, run1, datetime(2026, 9, 6, 12, 0))
    with Session(eng) as s:
        g = s.get(Game, 1)
        assert g.spread == -7.5  # median across the run's books
        assert g.spread_source == "oddsapi"
        assert g.full_game_total == 55.5  # DK outranks FanDuel for the opener
        assert g.full_game_total_book == "draftkings"
        assert g.full_game_total_source == "oddsapi"

    run2 = [_row(1, "draftkings", 57.0, -8.0), _row(1, "fanduel", 58.0, -9.0)]
    _run_poll(mod, monkeypatch, eng, run2, datetime(2026, 9, 7, 12, 0))
    with Session(eng) as s:
        g = s.get(Game, 1)
        assert g.spread == -8.5  # spread tracks the market
        assert g.full_game_total == 55.5  # opener total is NOT overwritten
        assert g.full_game_total_source == "oddsapi"
        snaps = s.query(OddsSnapshot).filter_by(market="full_game_total").all()
        assert len(snaps) == 4  # both books moved both runs
        assert {sn.spread for sn in snaps if sn.book == "draftkings"} == {-7.0, -8.0}


def test_spread_none_for_every_book_leaves_game_spread_alone(monkeypatch):
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=3, home_team="LSU", away_team="Clemson", spread=-3.0))
        s.commit()
    _run_poll(mod, monkeypatch, eng, [_row(1, "consensus", 50.0, None)], datetime(2026, 9, 6))
    with Session(eng) as s:
        g = s.get(Game, 1)
        assert g.spread == -3.0 and g.spread_source is None
        assert g.full_game_total == 50.0 and g.full_game_total_source == "oddsapi"


def test_oddsapi_normalize_is_over_first_and_skips_split_rungs():
    """One line per book, over-first (sources/draftkings.py's tie-break). A
    market whose Over and Under sit at DIFFERENT points is alternate rungs:
    pairing the prices would invent a line, so the book is skipped."""
    from beatvegas.sources.odds import normalize_full_game

    def bm(key, outcomes):
        return {"key": key, "markets": [{"key": "totals", "outcomes": outcomes}]}

    events = [
        {
            "id": "evt9",
            "commence_time": "2026-09-19T20:00:00Z",
            "home_team": "Kansas",
            "away_team": "Arizona State",
            "bookmakers": [
                # under listed first: the line must still be 55.5, not whichever came last
                bm(
                    "fanduel",
                    [
                        {"name": "Under", "price": -112, "point": 55.5},
                        {"name": "Over", "price": -108, "point": 55.5},
                    ],
                ),
                # split rungs: over 54.5 / under 56.5 -> not a centred line, skipped
                bm(
                    "betmgm",
                    [
                        {"name": "Over", "price": 195, "point": 54.5},
                        {"name": "Under", "price": -275, "point": 56.5},
                    ],
                ),
                # one-sided market still yields its point
                bm("kalshi", [{"name": "Under", "price": -102, "point": 55.5}]),
            ],
        }
    ]
    rows = {r["book"]: r for r in normalize_full_game(events)}
    assert set(rows) == {"fanduel", "kalshi"}
    assert rows["fanduel"]["line"] == 55.5
    assert rows["fanduel"]["over_price"] == -108 and rows["fanduel"]["under_price"] == -112
    assert rows["kalshi"]["line"] == 55.5 and rows["kalshi"]["over_price"] is None
