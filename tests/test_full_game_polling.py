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


def _row(gid, book, line, spread, over=-110, under=-110, event_id=None, last_update=None):
    return {
        "game_id": gid,
        "book": book,
        "line": line,
        "spread": spread,
        "over_price": over,
        "under_price": under,
        "commence_time": None,
        "event_id": event_id,
        "last_update": last_update,
    }


def _run_poll(mod, monkeypatch, eng, fg_rows, now, source="oddsapi", extra_args=None):
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
    calls = []

    def fetch(src, season, regions, credit_floor=60, markets=mod.DEFAULT_MARKETS):
        calls.append({"regions": regions, "credit_floor": credit_floor, "markets": markets})
        return fg_rows, [], source, 1

    monkeypatch.setattr(mod, "_fetch", fetch)
    monkeypatch.setattr(sys, "argv", ["poll_full_game.py", "--season", "2026", "--source", source])
    mod.main(list(extra_args) if extra_args else None)
    return calls


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


def test_oddsapi_normalize_keeps_the_most_balanced_of_several_pairs(capsys):
    """A book sending its main line AND an alternate in one market: the line is
    the balanced pair, never whichever came last (the old last-outcome-wins
    parse would have kept 30.5 here), and the run log says so."""
    from beatvegas.sources.odds import normalize_first_half

    events = [
        {
            "id": "evt10",
            "commence_time": "2026-09-26T16:00:00Z",
            "home_team": "Tennessee",
            "away_team": "Texas",
            "bookmakers": [
                {
                    "key": "hardrockbet",
                    "markets": [
                        {
                            "key": "totals_h1",
                            "outcomes": [
                                {"name": "Over", "price": -115, "point": 27.5},
                                {"name": "Under", "price": -105, "point": 27.5},
                                {"name": "Over", "price": 125, "point": 30.5},
                                {"name": "Under", "price": -160, "point": 30.5},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    (row,) = normalize_first_half(events)
    assert row["line"] == 27.5 and row["over_price"] == -115 and row["under_price"] == -105
    assert "::warning::odds: hardrockbet sent 2 totals_h1 point pairs" in capsys.readouterr().out


def _row_at(gid, book, line, commence):
    r = _row(gid, book, line, None)
    r["commence_time"] = commence
    return r


def test_close_tick_passes_markets_and_keeps_only_events_inside_the_window(monkeypatch):
    """The Saturday full-game close step: `--markets totals` reaches the client
    (half the credits) and `--kickoff-within-min 180` keeps only events that
    kick off inside REAL_FG_CLOSE_WINDOW_H from now; the rest of the slate is
    not written."""
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=6, home_team="LSU", away_team="Clemson"))
        s.add(Game(id=2, season=2026, week=6, home_team="Ohio State", away_team="Oregon"))
        s.commit()
    now = datetime(2026, 10, 10, 16, 0)
    rows = [
        _row_at(1, "draftkings", 55.5, "2026-10-10T18:00:00Z"),  # 2 h out: in
        _row_at(2, "draftkings", 48.5, "2026-10-10T23:30:00Z"),  # 7.5 h out: not yet
    ]
    calls = _run_poll(
        mod,
        monkeypatch,
        eng,
        rows,
        now,
        extra_args=["--markets", "totals", "--kickoff-within-min", "180", "--allow-empty"],
    )
    assert calls and calls[0]["markets"] == "totals"
    with Session(eng) as s:
        snaps = s.query(OddsSnapshot).filter_by(market="full_game_total").all()
        assert [sn.game_id for sn in snaps] == [1]


def test_full_game_rows_carry_the_feed_event_id_and_stamps(monkeypatch):
    """Capture provenance (2026-10-11): the first capture keeps the provider's stamp;
    a re-sighting under a newer stamp records it in feed_reseen_at and leaves the
    first one alone; a row without a stamp stores NULL."""
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=6, home_team="LSU", away_team="Clemson"))
        s.add(Game(id=2, season=2026, week=6, home_team="Iowa", away_team="Ohio State"))
        s.commit()
    t0, t1 = datetime(2026, 10, 4, 18, 0), datetime(2026, 10, 10, 16, 0)
    first = [
        _row(1, "draftkings", 55.5, -7.0, event_id="ev1", last_update="2026-10-04T17:58:00Z"),
        _row(2, "fanduel", 44.5, 3.0),  # no stamp from this source
    ]
    _run_poll(mod, monkeypatch, eng, first, t0)
    again = [_row(1, "draftkings", 55.5, -7.0, event_id="ev1", last_update="2026-10-10T15:30:00Z")]
    _run_poll(mod, monkeypatch, eng, again, t1)
    with Session(eng) as s:
        by = {r.game_id: r for r in s.query(OddsSnapshot).filter_by(market="full_game_total").all()}
        assert by[1].event_id == "ev1"
        assert by[1].feed_updated_at == datetime(2026, 10, 4, 17, 58)
        assert by[1].feed_reseen_at == datetime(2026, 10, 10, 15, 30)
        assert (by[1].captured_at, by[1].last_seen_at) == (t0, t1)
        assert by[2].event_id is None and by[2].feed_updated_at is None


def test_unchanged_full_game_line_is_re_seen_not_rewritten(monkeypatch):
    """A tick that finds the number standing stamps last_seen_at on the existing
    row (as poll_lines does) instead of writing a duplicate; that stamp is what
    lets an unmoved Sunday line grade as a 3 h close."""
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=6, home_team="LSU", away_team="Clemson"))
        s.commit()
    rows = [_row(1, "draftkings", 55.5, -7.0)]
    _run_poll(mod, monkeypatch, eng, rows, datetime(2026, 10, 4, 18, 0))
    _run_poll(mod, monkeypatch, eng, rows, datetime(2026, 10, 10, 16, 0))
    with Session(eng) as s:
        snaps = s.query(OddsSnapshot).filter_by(market="full_game_total").all()
        assert len(snaps) == 1
        assert snaps[0].captured_at == datetime(2026, 10, 4, 18, 0)
        assert snaps[0].last_seen_at == datetime(2026, 10, 10, 16, 0)


def test_allow_empty_exits_zero_when_nothing_is_due(monkeypatch):
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=6, home_team="LSU", away_team="Clemson"))
        s.commit()
    # no rows at all -> without --allow-empty this is a SystemExit(1)
    import pytest

    with pytest.raises(SystemExit):
        _run_poll(mod, monkeypatch, eng, [], datetime(2026, 10, 10, 16, 0))
    _run_poll(
        mod, monkeypatch, eng, [], datetime(2026, 10, 10, 16, 0), extra_args=["--allow-empty"]
    )


def _side(gid, book, market, line, home, away):
    return {
        "game_id": gid,
        "book": book,
        "market": market,
        "line": line,
        "home_price": home,
        "away_price": away,
        "commence_time": None,
    }


def test_side_markets_are_written_as_their_own_rows_beside_the_total(monkeypatch):
    """Roadmap step 4 (2026-10-07): one pull writes the total, the spread and
    the moneyline per book. The side rows carry both prices and never touch
    the full_game_total row's own `spread` column or Game.spread."""
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=7, home_team="LSU", away_team="Clemson"))
        s.commit()
    rows = [
        _row(1, "draftkings", 55.5, -7.0),
        _side(1, "draftkings", "full_game_spread", -7.0, -110, -110),
        _side(1, "draftkings", "full_game_ml", None, -300, 240),
        _side(1, "draftkings", "full_game_ml", None, -310, 250),  # duplicate: skipped
    ]
    _run_poll(mod, monkeypatch, eng, rows, datetime(2026, 10, 8, 20, 0))
    with Session(eng) as s:
        by_market = {sn.market: sn for sn in s.query(OddsSnapshot).all()}
        assert set(by_market) == {"full_game_total", "full_game_spread", "full_game_ml"}
        assert len(s.query(OddsSnapshot).all()) == 3
        sp, ml = by_market["full_game_spread"], by_market["full_game_ml"]
        assert (sp.line, sp.home_price, sp.away_price) == (-7.0, -110, -110)
        assert sp.over_price is None and sp.spread is None
        assert (ml.line, ml.home_price, ml.away_price) == (None, -300, 240)
        tot = by_market["full_game_total"]
        assert tot.spread == -7.0 and tot.home_price is None
        assert s.get(Game, 1).spread == -7.0


def test_a_moneyline_price_move_writes_a_new_row_and_an_unchanged_one_is_re_seen(monkeypatch):
    """A side row has no line or over/under to move: a change in either team's
    price alone must write a new snapshot, and a standing quote must stamp
    last_seen_at so it can grade as the close."""
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=7, home_team="LSU", away_team="Clemson"))
        s.commit()
    t1, t2, t3 = (
        datetime(2026, 10, 8, 20, 0),
        datetime(2026, 10, 9, 20, 0),
        datetime(2026, 10, 10, 15, 0),
    )
    tot = _row(1, "fanduel", 55.5, -7.0)
    _run_poll(
        mod, monkeypatch, eng, [tot, _side(1, "fanduel", "full_game_ml", None, -300, 240)], t1
    )
    _run_poll(
        mod, monkeypatch, eng, [tot, _side(1, "fanduel", "full_game_ml", None, -300, 250)], t2
    )
    _run_poll(
        mod, monkeypatch, eng, [tot, _side(1, "fanduel", "full_game_ml", None, -300, 250)], t3
    )
    with Session(eng) as s:
        ml = (
            s.query(OddsSnapshot)
            .filter_by(market="full_game_ml")
            .order_by(OddsSnapshot.captured_at)
            .all()
        )
        assert [(m.captured_at, m.away_price) for m in ml] == [(t1, 240), (t2, 250)]
        assert ml[1].last_seen_at == t3


def test_change_detection_sees_side_prices():
    _changed = _load("poll_full_game")._changed

    class Snap:
        line, spread, over_price, under_price = -7.0, None, None, None
        home_price, away_price = -110, -110

    assert not _changed(Snap(), -7.0, None, None, None, home=-110, away=-110)
    assert _changed(Snap(), -7.0, None, None, None, home=-115, away=-110)
    assert _changed(Snap(), -7.5, None, None, None, home=-110, away=-110)


def test_odds_snapshot_side_price_columns_are_migrated():
    from beatvegas.db.store import _MIGRATIONS

    for name in ("home_price", "away_price"):
        assert name in OddsSnapshot.__table__.columns
        assert _MIGRATIONS["odds_snapshots"][name] == "INTEGER"


def _status(path):
    import json

    return json.loads(Path(path).read_text())


def test_status_file_reports_the_window_the_rows_and_the_reseen_stamps(monkeypatch, tmp_path):
    """--status-file (final-2026 PR-05): lines_watch's `fg_close_polled` check reads
    events_in_window / events_polled / rows_written / rows_reseen / complete. A
    first pull writes, the next one that finds the number standing re-sees."""
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=6, home_team="LSU", away_team="Clemson"))
        s.add(Game(id=2, season=2026, week=6, home_team="Ohio State", away_team="Oregon"))
        s.commit()
    rows = [
        _row_at(1, "draftkings", 55.5, "2026-10-10T18:00:00Z"),  # 2 h out: in
        _row_at(2, "draftkings", 48.5, "2026-10-10T23:30:00Z"),  # 7.5 h out: not yet
    ]
    path = str(tmp_path / "fg.json")
    args = ["--kickoff-within-min", "180", "--allow-empty", "--status-file", path]
    _run_poll(mod, monkeypatch, eng, rows, datetime(2026, 10, 10, 16, 0), extra_args=args)
    assert _status(path) == {
        "complete": True,
        "reason": None,
        "events_in_window": 1,
        "events_polled": 1,
        "events_unmatched": 0,
        "rows_written": 1,
        "rows_reseen": 0,
    }
    _run_poll(mod, monkeypatch, eng, rows, datetime(2026, 10, 10, 16, 30), extra_args=args)
    st = _status(path)
    assert st["complete"] is True and st["rows_written"] == 0 and st["rows_reseen"] == 1


def test_status_file_counts_side_market_rows(monkeypatch, tmp_path):
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=6, home_team="LSU", away_team="Clemson"))
        s.commit()
    rows = [
        _row(1, "draftkings", 55.5, -7.0),
        _side(1, "draftkings", "full_game_spread", -7.0, -110, -110),
    ]
    path = str(tmp_path / "fg.json")
    _run_poll(
        mod,
        monkeypatch,
        eng,
        rows,
        datetime(2026, 10, 10, 16, 0),
        extra_args=["--status-file", path],
    )
    st = _status(path)
    assert st["rows_written"] == 2 and st["events_in_window"] == 1 and st["events_polled"] == 1


def test_empty_window_is_complete_and_a_credit_floor_skip_is_not(monkeypatch, tmp_path):
    """No event due is a normal, complete state; the credit-floor guard exits 0 with
    no rows too, and only the status file tells the two apart."""
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    path = str(tmp_path / "fg.json")
    args = ["--allow-empty", "--status-file", path]
    _run_poll(mod, monkeypatch, eng, [], datetime(2026, 10, 10, 16, 0), extra_args=args)
    st = _status(path)
    assert st["complete"] is True and st["events_in_window"] == 0 and st["reason"] is None

    def floor_fetch(*a, **k):
        mod._FETCH_STATE["skip"] = "credit_floor"
        return [], [], "oddsapi", 0

    monkeypatch.setattr(mod, "_fetch", floor_fetch)
    mod.main(args)
    st = _status(path)
    assert st["complete"] is False and st["reason"] == "credit_floor"
    # The next run starts clean: the skip reason does not outlive its run.
    _run_poll(mod, monkeypatch, eng, [], datetime(2026, 10, 10, 16, 0), extra_args=args)
    assert _status(path)["complete"] is True


def test_events_that_match_no_game_are_incomplete_and_the_database_down_is_too(
    monkeypatch, tmp_path
):
    mod = _load("poll_full_game")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)  # no games: every event is unmatched
    path = str(tmp_path / "fg.json")
    row = _row(99, "draftkings", 55.5, -7.0)
    row.update(game_id=None, home_team="Nowhere St", away_team="Elsewhere", commence_time=None)
    _run_poll(
        mod,
        monkeypatch,
        eng,
        [row],
        datetime(2026, 10, 10, 16, 0),
        extra_args=["--allow-empty", "--status-file", path],
    )
    st = _status(path)
    assert st["complete"] is False and st["reason"] == "no_match" and st["events_polled"] == 0

    monkeypatch.setattr(mod, "try_init_db", lambda: False)
    mod.main(["--status-file", path])
    st = _status(path)
    assert st["complete"] is False and st["reason"] == "db_unreachable"
