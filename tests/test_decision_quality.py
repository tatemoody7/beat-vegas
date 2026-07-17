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


def test_graded_pick_fields_includes_opening_line():
    from pick import graded_pick_fields  # scripts/ is on sys.path (conftest)

    fields = graded_pick_fields(
        actual_first_half=20,
        line=24.5,
        price=-110,
        stake=1.0,
        opening=26.0,
        closing=25.0,
    )
    assert fields["result"] == "under"  # 20 < 24.5
    assert fields["opening_line"] == 26.0
    assert fields["closing_line"] == 25.0
    assert fields["clv"] == 25.0 - 24.5  # clv_under(line, closing)
    assert fields["actual_first_half_total"] == 20
    assert fields["units"] != 0


def test_graded_pick_fields_no_snapshots():
    from pick import graded_pick_fields

    fields = graded_pick_fields(
        actual_first_half=30,
        line=24.5,
        price=-110,
        stake=1.0,
        opening=None,
        closing=None,
    )
    assert fields["result"] == "over"  # 30 > 24.5
    assert fields["opening_line"] is None
    assert fields["closing_line"] is None
    assert fields["clv"] is None
