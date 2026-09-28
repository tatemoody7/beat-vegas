"""manual_picks.bet_at (2026-09-28): when the ticket was written, when that is
not the log time. Two week-4 tickets bet Friday and logged Saturday read as
WATCH overrides because the server judged the live Saturday read."""

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from beatvegas.db.models import Game, ManualPick
from beatvegas.picks import add_pick, bet_at_from_et
from tests.conftest import _sqlite_scope


def test_bet_at_from_et_converts_the_eastern_wall_clock_to_naive_utc():
    assert bet_at_from_et("2026-09-25T16:10") == datetime(2026, 9, 25, 20, 10)  # EDT
    assert bet_at_from_et("2026-12-04T16:10") == datetime(2026, 12, 4, 21, 10)  # EST
    assert bet_at_from_et(None) is None and bet_at_from_et("  ") is None
    with pytest.raises(ValueError):
        bet_at_from_et("Friday afternoon")


def test_add_pick_stores_bet_at_and_leaves_placed_at_as_the_log_time():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=4,
                home_team="LSU",
                away_team="Texas A&M",
                start_date=datetime(2026, 9, 26, 23, 30),
            )
        )
        s.commit()
    logged = datetime(2026, 9, 26, 14, 31)
    with scope() as s:
        p = add_pick(
            s,
            game_id=1,
            season=2026,
            week=4,
            home_team="LSU",
            away_team="Texas A&M",
            line=26.5,
            price=100,
            placed_at=logged,
            bet_at=datetime(2026, 9, 25, 20, 16),
        )
        assert p.placed_at == logged and p.bet_at == datetime(2026, 9, 25, 20, 16)
        q = add_pick(
            s,
            game_id=None,
            season=2026,
            week=4,
            home_team="X",
            away_team="Y",
            line=20.5,
            is_paper=True,
        )
        assert q.bet_at is None  # logged at bet time is the default
    with Session(eng) as s:
        assert s.query(ManualPick).filter(ManualPick.bet_at.isnot(None)).count() == 1
