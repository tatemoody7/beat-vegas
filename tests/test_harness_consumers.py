"""The first consumers of the harness (P4b): the two `load_closes` wrappers, the
two gates' frame loading, the snapshot's declared build, and the docs."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest
from conftest import _sqlite_scope
from test_harness import _seed_snapshots

from beatvegas import snapshots as SN
from beatvegas.backtest import harness as H
from beatvegas.backtest import neggap_level as NL
from beatvegas.backtest import stats as S

ROOT = Path(__file__).resolve().parent.parent


# --- 18. load_closes wrappers -----------------------------------------------------------


def test_level_anchor_load_closes_is_consensus_closes(load_script, monkeypatch):
    eng, scope = _sqlite_scope()
    kick = _seed_snapshots(eng)
    mod = load_script("level_anchor_gate")
    monkeypatch.setattr(mod, "session_scope", scope)
    got = mod.load_closes([1, 2, 3])
    with scope() as s:
        expect = SN.consensus_closes(s, [1, 2, 3], SN.kickoffs_for(s, [1, 2, 3]))
    assert got == expect == {1: 28.75}
    assert 2 not in got  # its only snapshot is 40 h out -- outside the 2 h window
    assert mod.load_closes([]) == {}
    assert kick.year == 2026


def test_residual_gate_load_closes_is_consensus_closes(load_script):
    eng, scope = _sqlite_scope()
    _seed_snapshots(eng)
    mod = load_script("residual_gate")
    with scope() as s:
        got = mod.load_closes(s, [1, 2, 3])
        expect = SN.consensus_closes(s, [1, 2, 3], SN.kickoffs_for(s, [1, 2, 3]))
    assert got == expect == {1: 28.75}
    assert 2 not in got


# --- 19. frame_snapshot declares its build ---------------------------------------------------


def test_frame_snapshot_writes_the_build_attrs(load_script, monkeypatch, tmp_path):
    mod = load_script("frame_snapshot")
    df = pd.DataFrame({"id": [1, 2], "season": [2025, 2025], "x": [1.0, 2.0]})
    monkeypatch.setattr(mod, "build_feature_frame", lambda min_games: df.copy())
    assert mod.main(["--out", str(tmp_path / "frame_snapshot"), "--min-games", "0"]) == 0
    pkls = list(tmp_path.glob("frame_snapshot_*.pkl"))
    assert len(pkls) == 1
    back = pd.read_pickle(pkls[0])
    assert back.attrs["build"] == {
        "fbs_only": True,
        "min_games": 0,
        "prior_weight": mod.PRIOR_SEASON_WEIGHT,
        "weather_lead": mod.WEATHER_OBS_LEAD_HOURS,
    }
    # and the harness accepts exactly this pickle
    spec = H.HarnessSpec(row_id="x", arms=(H.incumbent_arm(),), test_seasons=(2025,))
    got, fp = H.load_frame(pkls[0], spec, tmp_path / "x_frame.json")
    assert len(got) == 2 and fp["source"]["build"]["min_games"] == 0


# --- the two gates load through the harness -----------------------------------------------------


@pytest.mark.parametrize("name", ["intercept_gate", "inseason_gate"])
def test_gate_scripts_take_a_frame_snapshot_and_refuse_an_undeclared_one(
    load_script, name, tmp_path, monkeypatch
):
    mod = load_script(name)
    args = mod.parse_args(["--frame", "x.pkl"])
    assert args.frame == "x.pkl" and args.min_games == 0
    # an undeclared pickle is refused with exit 2 before any evaluation
    df = pd.DataFrame({"id": [1], "season": [2025]})
    pkl = tmp_path / "bare.pkl"
    df.to_pickle(pkl)
    monkeypatch.setattr(mod, "try_init_db", lambda: True)
    monkeypatch.setattr(mod, "evaluate", lambda *a, **k: pytest.fail("evaluate must not run"))
    rc = mod.main(["--frame", str(pkl), "--out", str(tmp_path / "r"), "--no-closes"])
    assert rc == 2


# --- neggap_level uses the one Wilson, and is not a harness consumer ------------------------------


def test_neggap_level_imports_the_shared_wilson():
    assert NL.wilson is S.wilson
    src = (ROOT / "beatvegas" / "backtest" / "neggap_level.py").read_text()
    assert "harness" not in src


# --- docs ----------------------------------------------------------------------------------------------


def test_harness_doc_states_the_rules_the_code_enforces():
    doc = (ROOT / "docs" / "HARNESS.md").read_text()
    for needle in (
        "exit 2",
        "REAL_1H_CLOSE_WINDOW_H",
        "min-games-train",
        "consensus_as_of(fri_pm)",
        "zero `hardrockbet` rows",
        "gh workflow run study.yml",
        "study-harness_report",
        "diff_columns",
        "No unattended iteration",
        "EXHAUSTED",
        "not a harness consumer",
    ):
        assert needle in doc, needle
    # every fixed caveat's key phrase is in the doc's caveat list
    assert re.search(r"^8\. \*\*2023-25 EXHAUSTED", doc, re.M)
    assert len(H.FIXED_CAVEATS) == 8
