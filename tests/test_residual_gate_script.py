"""scripts/residual_gate.py imports without a database and its parser accepts
the documented flags (the workflow builds exactly these)."""

import json
from types import SimpleNamespace

import pytest


class _FakeQuery:
    """Stands in for the SQLAlchemy Query chain load_stored_bv drives —
    .filter()/.order_by() are no-ops here; the rows are pre-selected by the
    test, so this only needs to hand them back through .all()."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def query(self, model):
        return _FakeQuery(self._rows)


def _row(game_id, bv_line, engine=None, created_at=0):
    factors = json.dumps({"engine": engine}) if engine is not None else None
    return SimpleNamespace(
        game_id=game_id, bv_line=bv_line, factors_json=factors, created_at=created_at
    )


def test_parser_defaults(load_script):
    mod = load_script("residual_gate")
    args = mod.parse_args([])
    assert args.train_seasons == [2023, 2024]
    assert args.test_season == 2025
    assert args.out == "reports/residual_gate"
    assert args.write_model_run is False
    assert args.bv_train_seasons == "all"


def test_parser_accepts_the_documented_flags(load_script):
    mod = load_script("residual_gate")
    args = mod.parse_args(
        [
            "--train-seasons",
            "2022",
            "2023",
            "2024",
            "--test-season",
            "2025",
            "--out",
            "reports/x",
            "--write-model-run",
            "--bv-train-seasons",
            "match",
        ]
    )
    assert args.train_seasons == [2022, 2023, 2024]
    assert args.out == "reports/x" and args.write_model_run is True
    assert args.bv_train_seasons == "match"


def test_parser_rejects_an_unknown_bv_mode(load_script):
    mod = load_script("residual_gate")
    with pytest.raises(SystemExit):
        mod.parse_args(["--bv-train-seasons", "some"])


def test_step_summary_appends_when_the_variable_is_set(load_script, tmp_path, monkeypatch):
    mod = load_script("residual_gate")
    path = tmp_path / "summary.md"
    path.write_text("# before\n")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path))
    mod.append_step_summary("## gate\nbody\n")
    assert path.read_text() == "# before\n## gate\nbody\n"
    monkeypatch.delenv("GITHUB_STEP_SUMMARY")
    mod.append_step_summary("ignored")  # no variable: no-op, no error
    assert "ignored" not in path.read_text()


def test_load_stored_bv_excludes_rows_tagged_residual_engine(load_script):
    """The 'stored' column stands in for the incumbent; a row the residual
    engine itself wrote (factors_json.engine == 'residual') must not leak in,
    or a future engine flip would contaminate the gate's own baseline."""
    mod = load_script("residual_gate")
    rows = [
        _row(1, 20.5, engine="bv_line"),
        _row(2, 21.0, engine="residual"),
        _row(3, 22.0, engine=None),  # legacy row, written before the field existed
    ]
    out = mod.load_stored_bv(_FakeSession(rows), [1, 2, 3])
    assert out == {1: 20.5, 3: 22.0}
    assert 2 not in out


def test_load_stored_bv_falls_back_to_an_older_non_residual_row(load_script):
    """Newest-row-wins, but only among non-residual rows: if the latest row
    for a game is the residual's own, the last incumbent row still counts."""
    mod = load_script("residual_gate")
    rows = [
        _row(1, 20.5, engine="bv_line", created_at=1),
        _row(1, 25.0, engine="residual", created_at=2),
    ]
    out = mod.load_stored_bv(_FakeSession(rows), [1])
    assert out == {1: 20.5}


def test_load_stored_bv_treats_a_null_created_at_as_the_oldest_row(load_script):
    """Postgres sorts NULL last under ORDER BY ASC, so a legacy untagged row
    would win 'newest' by accident; the loader must sort NULL as oldest."""
    mod = load_script("residual_gate")
    rows = [
        _row(1, 24.0, engine="bv_line", created_at=5),
        _row(1, 20.5, engine=None, created_at=None),  # legacy row, no timestamp
    ]
    out = mod.load_stored_bv(_FakeSession(rows), [1])
    assert out == {1: 24.0}


def test_report_paths_include_the_per_game_csv(load_script, tmp_path):
    mod = load_script("residual_gate")
    md, js, csv = mod.report_paths(str(tmp_path / "residual_gate"), stamp="20260908T120000Z")
    assert md.name == "residual_gate_20260908T120000Z.md"
    assert js.name == "residual_gate_20260908T120000Z.json"
    assert csv.name == "residual_gate_20260908T120000Z.csv"


def test_only_not_evaluable_errors_are_reported_as_a_soft_failure(load_script):
    """Any other exception (a NaN season, a length mismatch) must propagate:
    a green run that blames data coverage hides the real defect."""
    mod = load_script("residual_gate")
    from beatvegas.backtest.residual_gate import GateNotEvaluable
    from beatvegas.model.residual import ResidualFitError

    assert mod.SOFT_FAILURES == (ResidualFitError, GateNotEvaluable)
    assert ValueError not in mod.SOFT_FAILURES
