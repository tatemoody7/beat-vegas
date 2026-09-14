"""The opening spread: the one as-of spread recoverable for 2023-25.

`Game.spread` is mutable (overwritten by every capture that carries one, so it
is effectively a close with no timestamp) and `odds_snapshots.spread` is NULL
before 2026. An opening line never moves, so it is the one honest as-of point
that can be reconstructed after the fact.
"""

from conftest import _load_script, _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.db.models import Game
from beatvegas.sources.cfbd_lines import pick_spread_open

mod = _load_script("backfill_spread_open")

# Shaped like a real CFBD /lines game payload.
LINES = [
    {"provider": "Bovada", "spreadOpen": -6.5, "spread": -7.5, "overUnder": 52.5},
    {"provider": "consensus", "spreadOpen": -7.0, "spread": -8.0, "overUnder": 53.0},
    {"provider": "DraftKings", "spreadOpen": -6.0, "spread": -7.0, "overUnder": 52.0},
]


def test_provider_priority_picks_consensus_first():
    assert pick_spread_open(LINES) == (-7.0, "consensus")


def test_falls_back_to_any_provider_offering_an_opener():
    only_bovada = [{"provider": "Bovada", "spreadOpen": -6.5}]
    assert pick_spread_open(only_bovada) == (-6.5, "Bovada")


def test_snake_case_key_is_accepted():
    assert pick_spread_open([{"provider": "consensus", "spread_open": -3.5}]) == (
        -3.5,
        "consensus",
    )


def test_a_missing_opener_is_none_and_is_NEVER_backfilled_from_the_close():
    """pick_open_close deliberately backfills one side of the total from the
    other. This must NOT: substituting the closing spread for a missing opener
    manufactures exactly the leak the column exists to avoid."""
    closes_only = [{"provider": "consensus", "spread": -8.0, "overUnder": 53.0}]
    assert pick_spread_open(closes_only) == (None, None)
    assert pick_spread_open([]) == (None, None)
    assert pick_spread_open(None) == (None, None)


def test_zero_is_a_real_opening_spread_not_a_missing_one():
    """A pick'em opens at 0. `if opn is None` rather than `if not opn`."""
    assert pick_spread_open([{"provider": "consensus", "spreadOpen": 0}]) == (0.0, "consensus")


# --- the backfill is write-once ---------------------------------------------


class _FakeClient:
    """One CFBD /lines game. `calls_remaining` mirrors the real client so the
    script's budget line does not need a special case."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.calls_remaining = None

    def lines(self, year, season_type=None):
        self.calls += 1
        return self.payload


def _payload(spread_open=None):
    lines = LINES if spread_open is None else [{"provider": "consensus", "spreadOpen": spread_open}]
    return [{"id": 1, "lines": lines}]


def _seed(eng):
    with Session(eng) as s:
        s.add(Game(id=1, season=2024, week=3, home_team="A", away_team="B"))
        s.commit()


def test_backfill_writes_the_opener_and_leaves_the_mutable_spread_alone(monkeypatch):
    eng, scope = _sqlite_scope()
    _seed(eng)
    monkeypatch.setattr(mod, "session_scope", scope)
    written, kept, _ = mod.backfill_season(_FakeClient(_payload()), 2024, "regular")
    assert (written, kept) == (1, 0)
    with Session(eng) as s:
        g = s.get(Game, 1)
        assert g.spread_open == -7.0 and g.spread_open_source == "cfbd"
        assert g.spread is None, "the mutable spread must not be touched"


def test_backfill_is_write_once_and_idempotent(monkeypatch):
    """An opening line does not move, so a re-run must not churn it -- the
    opposite of backfill_spread.py, whose rule protects LIVE sources from CFBD.
    Here CFBD is the only source there is, and the value is a historical fact."""
    eng, scope = _sqlite_scope()
    _seed(eng)
    monkeypatch.setattr(mod, "session_scope", scope)
    mod.backfill_season(_FakeClient(_payload()), 2024, "regular")

    written, kept, _ = mod.backfill_season(_FakeClient(_payload(-99.0)), 2024, "regular")
    assert (written, kept) == (0, 1)
    with Session(eng) as s:
        assert s.get(Game, 1).spread_open == -7.0

    written, kept, _ = mod.backfill_season(
        _FakeClient(_payload(-99.0)), 2024, "regular", force=True
    )
    assert (written, kept) == (1, 0)
    with Session(eng) as s:
        assert s.get(Game, 1).spread_open == -99.0


def test_dry_run_reports_without_writing(monkeypatch):
    eng, scope = _sqlite_scope()
    _seed(eng)
    monkeypatch.setattr(mod, "session_scope", scope)
    written, kept, _ = mod.backfill_season(_FakeClient(_payload()), 2024, "regular", dry_run=True)
    assert (written, kept) == (1, 0)
    with Session(eng) as s:
        assert s.get(Game, 1).spread_open is None


def test_a_game_cfbd_offers_no_opener_for_is_left_null(monkeypatch):
    eng, scope = _sqlite_scope()
    _seed(eng)
    monkeypatch.setattr(mod, "session_scope", scope)
    closes_only = [{"id": 1, "lines": [{"provider": "consensus", "spread": -8.0}]}]
    written, kept, none = mod.backfill_season(_FakeClient(closes_only), 2024, "regular")
    assert (written, kept, none) == (0, 0, 1)
    with Session(eng) as s:
        assert s.get(Game, 1).spread_open is None
