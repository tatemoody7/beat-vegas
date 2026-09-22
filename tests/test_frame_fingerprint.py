"""beatvegas/etl/frame_fingerprint.py -- what a gate run pins its inputs with.
One frozen gate gave two verdicts on 2026-09-22 because two frames were built
from different snapshots of CFBD's reference tables; the fingerprint is how a
registered result names the inputs it was judged on, and how two frames are
diffed without shipping either."""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from beatvegas.etl import frame_fingerprint as F

ROOT = Path(__file__).resolve().parent.parent


def _frame(shift=0.0):
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "season": [2024, 2024, 2025, 2025],
            "x": [1.0, 2.0, np.nan, 4.0 + shift],
            "flag": [True, False, True, False],
            "team": ["a", "b", "c", "d"],
        }
    )


def test_fingerprint_counts_means_and_platform():
    fp = F.fingerprint(_frame())
    assert fp["rows"] == 4 and fp["by_season"] == {2024: 2, 2025: 2}
    assert fp["columns"]["x"]["non_null"] == 3
    assert fp["columns"]["x"]["mean"] == 7.0 / 3
    assert "mean" not in fp["columns"]["flag"], "booleans and strings carry counts only"
    assert "mean" not in fp["columns"]["team"]
    assert fp["sklearn"] and fp["python"] and fp["platform"]


def test_write_and_diff(tmp_path):
    a = F.write_fingerprint(_frame(), tmp_path / "r_frame.json")
    b = F.write_fingerprint(_frame(shift=0.5), tmp_path / "s_frame.json")
    assert json.loads((tmp_path / "r_frame.json").read_text())["rows"] == 4
    d = F.diff_columns(a, b)
    assert set(d) == {"x"}, "only the column whose values moved is reported"
    assert "mean" in d["x"] and "std" in d["x"] and "non_null" not in d["x"]
    assert F.diff_columns(a, a) == {}


def test_every_gate_that_builds_a_frame_writes_its_fingerprint():
    """The registry now requires a run to name its inputs (docs/MODEL_LEVEL_2026.md,
    Reconciliation). Source-level: the two gates that produced the disagreeing
    verdicts call write_fingerprint right after building their frame."""
    for name in ("intercept_gate", "inseason_gate"):
        src = (ROOT / "scripts" / f"{name}.py").read_text()
        build = src.index("build_feature_frame(")
        assert "write_fingerprint(frame" in src[build : build + 900], name
        assert re.search(r"_frame\.json", src), name
