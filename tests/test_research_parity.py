"""web/lib/research.ts carries the protocol's numbers for the Research page; this
pins them to the Python that actually decides an arm (beatvegas/protocol.py) and the
pricing study (beatvegas/pricing.py), the way test_gate_parity pins verdict.ts."""

import re
from pathlib import Path

import pytest

from beatvegas import pricing as X
from beatvegas import protocol as P

TS = Path(__file__).resolve().parent.parent / "web" / "lib" / "research.ts"


def _ts(name: str) -> float:
    m = re.search(rf"\b{name}:\s*(-?[0-9.]+)\s*,", TS.read_text())
    assert m, f"{name} not found in research.ts"
    return float(m.group(1))


@pytest.mark.parametrize(
    "name, value",
    [
        ("NEEDED_READINGS", P.MIN_OBS),
        ("MIN_WEEKS", P.MIN_WEEKS),
        ("MAX_READINGS", P.MAX_OBS),
        ("PROMOTE_LLR", P.UPPER),
        ("STOP_LLR", P.LOWER),
        ("TARGET_EV", P.MU_1 if hasattr(P, "MU_1") else 0.03),
        ("PRICING_NEEDED", X.VERDICT_MIN_OPPS),
    ],
)
def test_the_research_page_numbers_match_the_protocol(name, value):
    assert _ts(name) == pytest.approx(float(value), abs=0.001)


def test_the_page_lists_every_registered_arm_and_the_pricing_study():
    src = TS.read_text()
    for arm in P.ARMS:
        assert f'id: "{arm}"' in src, arm
    assert 'id: "H-PRICE-HR"' in src
