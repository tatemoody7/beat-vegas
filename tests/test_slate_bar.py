"""H-PCT: the per-slate bar, pinned to the vectors web/lib/slateBar.test.ts reads."""

import json
from pathlib import Path

from beatvegas.model.score import BET_GAP_PTS, PCT_SHARE, slate_bar

VECTORS = Path(__file__).resolve().parent / "fixtures" / "slate_bar_vectors.json"


def test_share_is_the_validated_top_20_percent():
    assert PCT_SHARE == 0.20
    assert BET_GAP_PTS == 1.75, "the constant stays only as the empty-slate fallback"


def test_golden_vectors():
    v = json.loads(VECTORS.read_text())
    assert v["share"] == PCT_SHARE
    for case in v["cases"]:
        assert slate_bar(case["gaps"]) == case["bar"], case


def test_k_is_at_least_one_and_ties_at_the_bar_all_qualify():
    assert slate_bar([0.3, 0.2]) == 0.3  # N=2 -> k=1
    gaps = [3.0, 3.0, 3.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    bar = slate_bar(gaps)
    assert sum(1 for g in gaps if g >= bar) == 3, "three games tie at the bar; all qualify"
