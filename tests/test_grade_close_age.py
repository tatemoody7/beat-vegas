"""grade_pick stores WHEN the consensus close was last confirmed pre-kick
(`closing_captured_at`), so a stale "close" -- Friday's sweep quote standing in
for a dropped pre-kick poll -- can be told from one inside the window. H-STOP-2's
line-value clock cuts on it; the clv value itself is stored whatever the age."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from beatvegas.db.models import Game, ManualPick, OddsSnapshot
from beatvegas.picks import grade_pick
from tests.conftest import _sqlite_scope

KICK = datetime(2026, 9, 26, 19, 30)


def _seed(eng, last_capture):
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=5,
                start_date=KICK,
                home_team="H",
                away_team="A",
                home_points=20,
                away_points=17,
                first_half_total=17,
            )
        )
        for book in ("draftkings", "fanduel", "hardrockbet"):
            s.add(
                OddsSnapshot(
                    game_id=1,
                    book=book,
                    market="1H_total",
                    line=24.0,
                    over_price=-110,
                    under_price=-110,
                    captured_at=KICK - timedelta(days=2),
                )
            )
            s.add(
                OddsSnapshot(
                    game_id=1,
                    book=book,
                    market="1H_total",
                    line=23.5,
                    over_price=-110,
                    under_price=-110,
                    captured_at=last_capture,
                )
            )
        s.add(
            ManualPick(
                id=1,
                game_id=1,
                season=2026,
                week=5,
                is_paper=True,
                market="1H",
                side="under",
                line=24.5,
                price=-110,
                stake=1.0,
                placed_at=KICK - timedelta(days=2),
            )
        )
        s.commit()


def test_closing_captured_at_is_the_freshest_prekick_confirmation():
    eng, scope = _sqlite_scope()
    fresh = KICK - timedelta(minutes=40)
    _seed(eng, fresh)
    with scope() as s:
        pick = s.get(ManualPick, 1)
        game = s.get(Game, 1)
        assert grade_pick(s, pick, game) is True
        assert pick.graded is True
        assert pick.closing_line == 23.5
        assert pick.closing_captured_at == fresh


def test_a_stale_close_is_still_graded_but_carries_its_age():
    eng, scope = _sqlite_scope()
    stale = KICK - timedelta(hours=30)
    _seed(eng, stale)
    with scope() as s:
        pick = s.get(ManualPick, 1)
        game = s.get(Game, 1)
        grade_pick(s, pick, game)
        assert pick.closing_line == 23.5 and pick.clv == -1.0
        assert pick.closing_captured_at == stale
        assert KICK - pick.closing_captured_at > timedelta(hours=2), (
            "outside the 2 h window: Clock 2 excludes it"
        )
