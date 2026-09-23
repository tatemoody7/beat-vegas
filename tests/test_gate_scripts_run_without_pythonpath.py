"""The gate workflows run `python scripts/<gate>.py`, which puts scripts/ on
sys.path and NOT the repo root -- so a bare `from scripts.x import y` raises
ModuleNotFoundError on the runner while passing every local run that sets
PYTHONPATH=. (intercept_gate.yml, 2026-09-22: the study had only ever run on a
laptop). Each gate script must import cleanly with an EMPTY PYTHONPATH."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# health_check is not a gate but runs the same way: `python scripts/health_check.py`
# as the last step of every scheduled workflow, with scripts/ on sys.path.
GATES = [
    "harness_report",
    "intercept_gate",
    "inseason_gate",
    "level_anchor_gate",
    "residual_gate",
    "health_check",
]


@pytest.mark.parametrize("name", GATES)
def test_gate_script_help_runs_with_empty_pythonpath(name):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    r = subprocess.run(
        [sys.executable, f"scripts/{name}.py", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, f"{name}: {r.stderr[-800:]}"
    assert "ModuleNotFoundError" not in r.stderr
