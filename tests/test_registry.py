"""beatvegas/registry.py reads docs/HYPOTHESES.md the way the registry test does,
and refuses every row the harness may not run."""

from __future__ import annotations

import pytest

from beatvegas import registry as R

HEADER = (
    "| id | question | status | family | data (seasons, cut) | n | comparisons run | "
    "pass criterion (pre-registered) | result doc |\n|---|---|---|---|---|---|---|---|---|\n"
)


def _row(rid, status, criterion="paired gain with a 95% CI excluding zero, both seasons"):
    return f"| {rid} | q? | {status} | fam | 2024-25 | 100 | 1 | {criterion} | `docs/X.md` |\n"


@pytest.fixture
def registry_file(tmp_path):
    text = (
        "# Registry\n\nprose | with a pipe that is not a table row\n\n"
        + HEADER
        + _row("PRE", "pre-registered")
        + _row("EXP", "exploratory", "None. Counts and intervals only.")
        + _row("NULL", "tested-null")
        + _row("POS", "tested-positive")
        + _row("LIVE", "live-tracking")
        + _row("REJ", "rejected")
        + _row("ADOPT", "adopted")
        + _row("EMPTY", "pre-registered", "")
        + "| ESC | \\|mean bias\\| smaller | pre-registered | fam | d | n | 1 | crit \\| more | doc |\n"
    )
    p = tmp_path / "HYPOTHESES.md"
    p.write_text(text)
    return p


def test_parser_agrees_with_the_registry_test_on_every_real_row():
    """Same ids, same statuses, same count as tests/test_hypotheses_registry.py."""
    import test_hypotheses_registry as T

    theirs = {r["id"]: r["status"] for r in T._rows()}
    ours = {r.id: r.status for r in R.parse_registry()}
    assert ours == theirs
    assert len(R.parse_registry()) == len(T._rows())
    assert R.STATUSES == frozenset(T.STATUSES)


def test_parser_keeps_escaped_pipes_inside_a_cell(registry_file):
    rows = {r.id: r for r in R.parse_registry(registry_file)}
    assert rows["ESC"].question == "\\|mean bias\\| smaller"
    assert rows["ESC"].criterion == "crit \\| more"
    assert len(rows) == 9


@pytest.mark.parametrize(
    "rid, needle",
    [
        ("NOPE", "not found"),
        ("NULL", "'tested-null'"),
        ("POS", "'tested-positive'"),
        ("LIVE", "'live-tracking'"),
        ("REJ", "'rejected'"),
        ("ADOPT", "'adopted'"),
        ("EMPTY", "empty pass-criterion"),
    ],
)
def test_refusal_matrix(registry_file, rid, needle):
    with pytest.raises(R.HarnessRefusal) as e:
        R.require_runnable_row(rid, registry_file)
    assert needle in str(e.value)


@pytest.mark.parametrize("rid", ["PRE", "EXP", "ESC"])
def test_runnable_statuses_are_accepted(registry_file, rid):
    row = R.require_runnable_row(rid, registry_file)
    assert row.id == rid and row.runnable


def test_runnable_statuses_are_exactly_the_two_open_ones():
    assert R.RUNNABLE_STATUSES == frozenset({"pre-registered", "exploratory"})
    assert R.RUNNABLE_STATUSES < R.STATUSES


def test_find_row_is_exact_and_case_sensitive(registry_file):
    rows = R.parse_registry(registry_file)
    assert R.find_row(rows, "PRE") is not None
    assert R.find_row(rows, "pre") is None


def test_the_real_registry_has_a_runnable_row_for_the_planned_smoke_run():
    """H-STOP-2 is the planned first dispatch; if its status ever leaves the
    runnable set this names the change."""
    row = R.require_runnable_row("H-STOP-2")
    assert row.status == "pre-registered"
    assert len(row.criterion) > 40
