"""The factor ledger is a 1H-under record. results rows now also carry the
full-game market (model_version='market_fg', market='full'), and an unfiltered
read let the full-game outcome overwrite the 1H one for the same game."""

from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Result


def test_real_1h_outcomes_ignore_full_game_rows():
    gfl = _load_script("grade_factor_ledger")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all(
            [
                Result(
                    game_id=1, model_version="market", market="1H", line_kind="real", under_hit=True
                ),
                Result(
                    game_id=1,
                    model_version="market_fg",
                    market="full",
                    line_kind="real",
                    under_hit=False,
                ),
                # proxy-graded rows never count
                Result(
                    game_id=2,
                    model_version="gbm_v1",
                    market="1H",
                    line_kind="proxy",
                    under_hit=True,
                ),
                # legacy 1H row from before the market column existed
                Result(
                    game_id=3,
                    model_version="market",
                    market=None,
                    line_kind="real",
                    under_hit=False,
                ),
            ]
        )
        s.commit()
        out = gfl.real_1h_outcomes(s)
    assert out == {1: 1, 3: 0}
