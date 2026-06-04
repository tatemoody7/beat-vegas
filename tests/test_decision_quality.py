from beatvegas.db import models, store


def test_manual_pick_has_dq_columns(tmp_path):
    """New ManualPick columns exist and round-trip through a fresh SQLite DB."""
    store._engine = None
    store._Session = None
    db = tmp_path / "dq.db"
    store.init_db(path=db)
    with store.session_scope() as s:
        s.add(
            models.ManualPick(
                game_id=1,
                season=2025,
                week=1,
                line=24.5,
                factors_json_at_pick='{"factor_board": []}',
                opening_line=25.0,
            )
        )
    with store.session_scope() as s:
        p = s.query(models.ManualPick).first()
        assert p.factors_json_at_pick == '{"factor_board": []}'
        assert p.opening_line == 25.0
    store._engine = None
    store._Session = None
