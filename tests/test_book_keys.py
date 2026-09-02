"""odds_snapshots.book must hold ONE spelling per book. CFBD provider strings
("DraftKings", "Bovada", "William Hill (US)") and Odds API keys ("draftkings",
"bovada") were both landing in the table, so per-book medians and fair prices
double-counted the same book. normalize_book is applied by every source
normalizer and at every snapshot write; a data migration lowercases legacy rows."""

from datetime import datetime

from conftest import _load_script
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, OddsSnapshot
from beatvegas.db.store import _apply_migrations
from beatvegas.hardrock import HR_BOOK_KEYS, normalize_book


def test_normalize_book_canonical_forms():
    assert normalize_book("DraftKings") == "draftkings"
    assert normalize_book("draftkings") == "draftkings"
    assert normalize_book("  Bovada ") == "bovada"
    assert normalize_book("William Hill (US)") == "william_hill_us"
    assert normalize_book("ESPN Bet") == "espn_bet"
    assert normalize_book("consensus") == "consensus"
    assert normalize_book("hardrockbet_fl") == "hardrockbet"  # the HR alias collapses
    assert normalize_book("hardrockbet") == "hardrockbet"
    assert normalize_book(None) == ""
    assert normalize_book("hardrockbet") in HR_BOOK_KEYS


def test_normalize_book_is_idempotent():
    for raw in ("DraftKings", "William Hill (US)", "hardrockbet_fl"):
        once = normalize_book(raw)
        assert normalize_book(once) == once


def test_oddsapi_rows_carry_normalized_book_keys():
    from beatvegas.sources.odds import normalize_first_half

    def bm(key, point):
        return {
            "key": key,
            "markets": [
                {
                    "key": "totals_h1",
                    "outcomes": [
                        {"name": "Over", "price": -110, "point": point},
                        {"name": "Under", "price": -110, "point": point},
                    ],
                }
            ],
        }

    events = [
        {
            "id": "e1",
            "commence_time": "2026-09-05T20:00:00Z",
            "home_team": "LSU",
            "away_team": "Clemson",
            "bookmakers": [bm("hardrockbet_fl", 27.5), bm("DraftKings", 28.0)],
        }
    ]
    books = sorted(r["book"] for r in normalize_first_half(events))
    assert books == ["draftkings", "hardrockbet"]


def test_cfbd_rows_carry_normalized_book_keys():
    from beatvegas.sources.cfbd_lines import full_game_rows

    class _C:
        def lines(self, year, season_type="regular"):
            if season_type != "regular":
                return []
            return [
                {
                    "id": 7,
                    "startDate": "2026-09-05T20:00:00Z",
                    "homeTeam": "LSU",
                    "awayTeam": "Clemson",
                    "lines": [{"provider": "William Hill (US)", "overUnder": 55.5, "spread": -3}],
                }
            ]

    (row,) = full_game_rows(_C(), 2026)
    assert row["book"] == "william_hill_us"


def test_poll_full_game_fetch_normalizes_every_source(monkeypatch):
    mod = _load_script("poll_full_game")
    monkeypatch.setattr(mod, "CFBDClient", lambda: None)
    monkeypatch.setattr(
        mod,
        "cfbd_full_game_rows",
        lambda c, season: [{"game_id": 5, "book": "DraftKings", "line": 50.0}],
    )
    fg, _h1, source, _ = mod._fetch("cfbd", 2026)
    assert source == "cfbd" and fg[0]["book"] == "draftkings"

    class _DK:
        def fetch_ncaaf(self):
            return {"events": [{"id": 1}]}

    monkeypatch.setattr(mod, "DraftKingsClient", _DK)
    monkeypatch.setattr(mod, "normalize_full_game", lambda p: [{"book": "DraftKings"}])
    monkeypatch.setattr(mod, "normalize_first_half", lambda p: [{"book": "Draft Kings"}])
    fg, h1, source, _ = mod._fetch("dk", 2026)
    assert source == "dk" and fg[0]["book"] == "draftkings" and h1[0]["book"] == "draft_kings"


def test_migration_lowercases_legacy_book_rows():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(
            [
                OddsSnapshot(
                    game_id=1,
                    book="DraftKings",
                    market="full_game_total",
                    line=55.5,
                    captured_at=datetime(2026, 9, 1, 12),
                ),
                OddsSnapshot(
                    game_id=1,
                    book="draftkings",
                    market="full_game_total",
                    line=56.0,
                    captured_at=datetime(2026, 9, 2, 12),
                ),
                OddsSnapshot(
                    game_id=1,
                    book="Bovada",
                    market="1H_total",
                    line=27.5,
                    captured_at=datetime(2026, 9, 2, 12),
                ),
            ]
        )
        s.commit()
    _apply_migrations(eng)
    with eng.connect() as c:
        books = sorted(c.execute(text("SELECT DISTINCT book FROM odds_snapshots")).scalars())
    assert books == ["bovada", "draftkings"]
