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

    assert _changed(None, 55.5, -7.0, -110, -110) is True       # first ever
    prev = Snap(55.5, -7.0, -110, -110)
    assert _changed(prev, 55.5, -7.0, -110, -110) is False      # unchanged
    assert _changed(prev, 56.0, -7.0, -110, -110) is True       # total moved
    assert _changed(prev, 55.5, -7.5, -110, -110) is True       # spread moved
    assert _changed(prev, 55.5, -7.0, -115, -110) is True       # price moved


def test_full_game_snapshot_roundtrips_spread():
    eng = create_engine("sqlite:///:memory:")           # isolated, not the global
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(OddsSnapshot(game_id=1, book="draftkings", market="full_game_total",
                           line=55.5, spread=-17.0, over_price=-110,
                           under_price=-110, captured_at=datetime(2026, 9, 1)))
        s.commit()
        got = s.query(OddsSnapshot).filter_by(market="full_game_total").one()
        assert got.line == 55.5 and got.spread == -17.0


def test_full_game_opener_consensus_with_spread():
    _full_game_opener = _load("weekly_update")._full_game_opener

    class Snap:
        def __init__(self, book, line, spread, cap):
            self.book, self.line, self.spread, self.captured_at = book, line, spread, cap

    snaps = [
        Snap("dk", 56.0, -7.0, datetime(2026, 9, 1, 12)),   # dk opener
        Snap("dk", 57.0, -7.5, datetime(2026, 9, 3, 12)),   # later move (ignored)
        Snap("fd", 58.0, -8.0, datetime(2026, 9, 1, 12)),   # fd opener
    ]
    total, spread = _full_game_opener(snaps)
    assert total == 57.0       # median(56.0, 58.0)
    assert spread == -7.5      # median(-7.0, -8.0)
