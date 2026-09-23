"""beatvegas/backtest/reporting.py: the stamped report triple and the step
summary, and the residual_gate script's re-export of both."""

from __future__ import annotations

from datetime import datetime, timezone

from beatvegas.backtest import reporting as REP


def test_utc_stamp_format():
    assert (
        REP.utc_stamp(datetime(2026, 9, 23, 14, 15, 0, tzinfo=timezone.utc)) == "20260923T141500Z"
    )
    assert len(REP.utc_stamp()) == 16 and REP.utc_stamp().endswith("Z")


def test_report_paths_share_one_stamp_and_resolve_relative_to_the_repo(tmp_path):
    md, js, csv = REP.report_paths(str(tmp_path / "harness_X"), stamp="20260923T000000Z")
    assert md.name == "harness_X_20260923T000000Z.md"
    assert js.name == "harness_X_20260923T000000Z.json"
    assert csv.name == "harness_X_20260923T000000Z.csv"
    rel_md, _, _ = REP.report_paths("reports/harness_X", stamp="20260923T000000Z")
    assert rel_md.is_absolute() and rel_md.parts[-2] == "reports"


def test_append_step_summary_appends_when_set_and_is_a_noop_otherwise(tmp_path, monkeypatch):
    path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path))
    REP.append_step_summary("## one")
    REP.append_step_summary("## two\n")
    assert path.read_text() == "## one\n## two\n"
    monkeypatch.delenv("GITHUB_STEP_SUMMARY")
    REP.append_step_summary("ignored")
    assert path.read_text() == "## one\n## two\n"


def test_residual_gate_script_re_exports_the_same_functions(load_script):
    mod = load_script("residual_gate")
    assert mod.report_paths is REP.report_paths
    assert mod.append_step_summary is REP.append_step_summary
