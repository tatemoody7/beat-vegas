"""Guards on the GitHub Actions workflows (pure YAML checks, no network).

1. Every Neon-writing workflow shares ONE concurrency group so two writers never
   run at once (id-sequence race, see tests/test_store_sequences.py).
2. Every cron string in a workflow with a "resolve" step is mapped in that step's
   `case "$SCHEDULE"` block — an unmapped cron fails the run loudly, so this test
   catches the edit before it ships.
"""

from pathlib import Path

import yaml

WF_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
NEON_GROUP = "neon-writers"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _workflows():
    return sorted(p for p in WF_DIR.glob("*.yml"))


def _on(data: dict) -> dict:
    # PyYAML parses the bare `on:` key as boolean True.
    return data.get("on") or data.get(True) or {}


def _writes_neon(data: dict) -> bool:
    text = yaml.safe_dump(data)
    return "secrets.DATABASE_URL" in text


def _cron_strings(data: dict):
    sched = _on(data).get("schedule") or []
    return [s["cron"] for s in sched]


def _run_blocks(data: dict):
    for job in (data.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if isinstance(step.get("run"), str):
                yield step["run"]


def test_every_neon_writer_shares_the_concurrency_group():
    writers = [p for p in _workflows() if _writes_neon(_load(p))]
    assert writers, "expected at least one Neon-writing workflow"
    for p in writers:
        conc = _load(p).get("concurrency") or {}
        assert conc.get("group") == NEON_GROUP, f"{p.name}: concurrency.group must be {NEON_GROUP}"
        assert conc.get("cancel-in-progress") is False, (
            f"{p.name}: cancel-in-progress must be false"
        )


def test_ci_keeps_its_own_group():
    conc = _load(WF_DIR / "ci.yml").get("concurrency") or {}
    assert conc.get("group") != NEON_GROUP


def test_every_cron_is_mapped_in_its_resolve_step():
    checked = 0
    for p in _workflows():
        data = _load(p)
        crons = _cron_strings(data)
        resolve = [r for r in _run_blocks(data) if 'case "$SCHEDULE"' in r]
        if not crons or not resolve:
            continue
        block = "\n".join(resolve)
        for cron in crons:
            assert f"'{cron}'" in block, (
                f"{p.name}: cron '{cron}' is not mapped in the resolve step"
            )
            checked += 1
    assert checked > 0


def test_card_yml_crons_match_ci_slots_exactly():
    """card.yml resolves its schedule through beatvegas.ci.CRON_SLOTS (no shell
    case block): the two must name exactly the same cron strings."""
    from beatvegas.ci import CRON_SLOTS

    data = _load(WF_DIR / "card.yml")
    assert any("beatvegas.ci" in r for r in _run_blocks(data))
    assert set(_cron_strings(data)) == set(CRON_SLOTS), "card.yml and CRON_SLOTS drifted"
