"""scripts/residual_gate.py imports without a database and its parser accepts
the documented flags (the workflow builds exactly these)."""

import pytest


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


def test_report_paths_carry_a_utc_stamp(load_script, tmp_path):
    mod = load_script("residual_gate")
    md, js = mod.report_paths(str(tmp_path / "residual_gate"), stamp="20260908T120000Z")
    assert md.name == "residual_gate_20260908T120000Z.md"
    assert js.name == "residual_gate_20260908T120000Z.json"


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
