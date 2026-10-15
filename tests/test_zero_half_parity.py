"""The writer and the grader judge a scoreless first half by ONE standard (2026-10-15).

Until 2026-10-15 the writer (`etl.first_half.attach_first_half`) stored a 0-0 half
in a game that scored when the full box reconciled with the final, and the grader
(`grading.trusted_first_half_total`) rejected every line-score 0 regardless. App
State-Old Dominion (2026-10-10; quarters 0-0-3-0 and 0-0-2-8, final 3-10 on both CFBD
and ESPN) sat ungraded with no way out. The writer now records its proof in the
label, and the grader trusts a scoreless half under a proving label and no other.

The core property: whatever the writer persists, the grader grades -- and a stored 0
with no recorded proof (every row written before the fix) is still refused.
"""

import pytest

from beatvegas.etl.first_half import attach_first_half
from beatvegas.grading import (
    SOURCE_LINESCORES,
    SOURCE_LINESCORES_VERIFIED,
    SOURCE_PBP,
    ZERO_PROVEN_SOURCES,
    trusted_first_half_total,
    under_result,
)

APP_STATE_ODU = {
    "id": 401869843,
    "homePoints": 3,
    "awayPoints": 10,
    "homeLineScores": [0, 0, 3, 0],
    "awayLineScores": [0, 0, 2, 8],
}

# (name, game, pbp_lookup, pbp_final, expected total, expected label)
CASES = [
    (
        "app state: full reconciled box, 0-0 half",
        APP_STATE_ODU,
        None,
        None,
        0,
        SOURCE_LINESCORES_VERIFIED,
    ),
    (
        "overtime box (five periods) reconciles, 0-0 half",
        {
            "id": 2,
            "homePoints": 13,
            "awayPoints": 7,
            "homeLineScores": [0, 0, 0, 7, 6],
            "awayLineScores": [0, 0, 7, 0, 0],
        },
        None,
        None,
        0,
        SOURCE_LINESCORES_VERIFIED,
    ),
    (
        "shutout side: all-zero box for a side that scored 0",
        {
            "id": 3,
            "homePoints": 0,
            "awayPoints": 17,
            "homeLineScores": [0, 0, 0, 0],
            "awayLineScores": [0, 0, 7, 10],
        },
        None,
        None,
        0,
        SOURCE_LINESCORES_VERIFIED,
    ),
    (
        "ordinary half with points",
        {
            "id": 4,
            "homePoints": 31,
            "awayPoints": 17,
            "homeLineScores": [7, 10, 7, 7],
            "awayLineScores": [3, 0, 7, 7],
        },
        None,
        None,
        20,
        SOURCE_LINESCORES,
    ),
    (
        "0-0 final",
        {
            "id": 5,
            "homePoints": 0,
            "awayPoints": 0,
            "homeLineScores": [0, 0, 0, 0],
            "awayLineScores": [0, 0, 0, 0],
        },
        None,
        None,
        0,
        SOURCE_LINESCORES,
    ),
    (
        "placeholder all-zero box in a game that scored: refused, nothing stored",
        {
            "id": 6,
            "homePoints": 24,
            "awayPoints": 17,
            "homeLineScores": [0, 0, 0, 0],
            "awayLineScores": [0, 0, 0, 0],
        },
        None,
        None,
        None,
        None,
    ),
    (
        "partial box (two quarters) with a 0-0 half: refused, nothing stored",
        {
            "id": 7,
            "homePoints": 10,
            "awayPoints": 3,
            "homeLineScores": [0, 0],
            "awayLineScores": [0, 0],
        },
        None,
        None,
        None,
        None,
    ),
    (
        "partial box, PBP reaches the final: the PBP zero is stored",
        {
            "id": 8,
            "homePoints": 10,
            "awayPoints": 3,
            "homeLineScores": [0, 0],
            "awayLineScores": [0, 0],
        },
        {8: (0, 0)},
        {8: (10, 3)},
        0,
        SOURCE_PBP,
    ),
    (
        "partial box, PBP stops short: nothing stored",
        {
            "id": 9,
            "homePoints": 10,
            "awayPoints": 3,
            "homeLineScores": [0, 0],
            "awayLineScores": [0, 0],
        },
        {9: (0, 0)},
        {9: (0, 0)},
        None,
        None,
    ),
]


@pytest.mark.parametrize(
    "name, game, pbp, pbp_final, total, label", CASES, ids=[c[0] for c in CASES]
)
def test_the_writer_labels_its_evidence(name, game, pbp, pbp_final, total, label):
    out = attach_first_half(game, pbp, pbp_final)
    assert out["first_half_total"] == total
    assert out["first_half_source"] == label


@pytest.mark.parametrize(
    "name, game, pbp, pbp_final, total, label", CASES, ids=[c[0] for c in CASES]
)
def test_whatever_the_writer_stores_the_grader_grades(name, game, pbp, pbp_final, total, label):
    out = attach_first_half(game, pbp, pbp_final)
    if out["first_half_total"] is None:
        return  # nothing stored, nothing to grade
    graded = trusted_first_half_total(
        out["first_half_total"],
        game.get("homePoints"),
        game.get("awayPoints"),
        out["first_half_source"],
    )
    assert graded == out["first_half_total"], name


def test_app_state_old_dominion_grades_as_a_scoreless_half():
    out = attach_first_half(APP_STATE_ODU)
    fh = trusted_first_half_total(out["first_half_total"], 3, 10, out["first_half_source"])
    assert fh == 0
    assert under_result(fh, 24.5) == "under"


def test_a_stored_zero_without_recorded_proof_is_still_refused():
    """Rows written before 2026-10-15 carry plain `linescores`: the grader cannot
    tell a proven zero from the placeholder corruption, so it keeps refusing them
    until the writer re-derives them (the nightly season load does, for 2026)."""
    assert trusted_first_half_total(0, 3, 10, SOURCE_LINESCORES) is None
    assert trusted_first_half_total(0, 3, 10, None) is None
    assert trusted_first_half_total(0, 3, 10, "something_else") is None


def test_only_the_proving_labels_carry_a_scoreless_half():
    assert ZERO_PROVEN_SOURCES == {SOURCE_LINESCORES_VERIFIED, SOURCE_PBP}
    assert SOURCE_LINESCORES not in ZERO_PROVEN_SOURCES


def test_the_writer_never_labels_a_half_with_points_as_verified():
    for name, game, pbp, pbp_final, _total, _label in CASES:
        out = attach_first_half(game, pbp, pbp_final)
        if out["first_half_source"] == SOURCE_LINESCORES_VERIFIED:
            assert out["first_half_total"] == 0, name
            assert (game["homePoints"] + game["awayPoints"]) > 0, name
