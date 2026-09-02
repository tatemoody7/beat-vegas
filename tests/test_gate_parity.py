"""The verdict gates live twice — model/score.py (Python) and web/lib/verdict.ts
(the This Week page). They are POINT gates from the validated top-20%-by-gap
rule, never sigma thresholds. This test reads the TypeScript constants by regex
and fails the moment the two drift apart."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from beatvegas.model import score

_TS = Path(__file__).resolve().parent.parent / "web" / "lib" / "verdict.ts"

PARITY = {
    "BET_GAP_PTS": score.BET_GAP_PTS,
    "STRONG_GAP_PTS": score.STRONG_GAP_PTS,
    "WATCH_GAP_PTS": score.WATCH_GAP_PTS,
    "MODEL_BET_THRESHOLD": score.MODEL_BET_THRESHOLD,
    "WEEKLY_BET_CAP": score.WEEKLY_BET_CAP,
}


def _ts_const(src: str, name: str) -> float:
    m = re.search(rf"export\s+const\s+{name}\s*=\s*([0-9.]+)\s*;", src)
    assert m, f"{name} not exported from {_TS}"
    return float(m.group(1))


@pytest.mark.parametrize("name", sorted(PARITY))
def test_python_gate_matches_verdict_ts(name):
    if not _TS.exists():
        pytest.skip(f"{_TS} not present in this checkout")
    src = _TS.read_text()
    assert _ts_const(src, name) == pytest.approx(PARITY[name]), name


def test_gates_are_ordered_points_not_sigmas():
    assert score.WATCH_GAP_PTS < score.BET_GAP_PTS < score.STRONG_GAP_PTS
    assert not hasattr(score, "OPPORTUNITY_Z")  # the sigma gate is gone for good
