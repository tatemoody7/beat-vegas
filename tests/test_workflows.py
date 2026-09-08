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


# --- card-day re-score (PR-4): the residual engine conditions on the live 1H line,
# so weekly_update must run again AFTER the sweep refreshes it. Under the
# incumbent `--if-engine residual` makes the step a no-op, so today's card-day
# behaviour is unchanged. (card.yml's crons are asserted against
# beatvegas.ci.CRON_SLOTS above — the single source of truth — not re-listed here.)


def _card_steps():
    data = _load(WF_DIR / "card.yml")
    return data["jobs"]["card"]["steps"]


def _step_index(steps, needle: str) -> int:
    hits = [i for i, st in enumerate(steps) if needle in (st.get("run") or "")]
    assert len(hits) == 1, f"expected exactly one step running {needle!r}, got {hits}"
    return hits[0]


def test_card_rescores_with_the_residual_engine_after_the_sweep():
    steps = _card_steps()
    sweep = _step_index(steps, "scripts/poll_lines.py")
    rescore = _step_index(steps, "scripts/weekly_update.py")
    build = _step_index(steps, "scripts/build_card.py")
    assert sweep < rescore < build
    run = steps[rescore]["run"]
    assert "--if-engine residual" in run
    assert "--season" in run and "--week" in run
    assert "steps.active.outputs.season" in run and "steps.active.outputs.week" in run
    # Gated exactly like the sweep: no sweep, nothing new to condition on.
    assert steps[rescore].get("if") == steps[sweep].get("if")
    assert "need_sweep" in steps[rescore]["if"]


def test_residual_gate_passes_inputs_through_env_and_uploads_the_report():
    """residual_gate.yml: dispatch-only, inputs reach bash only via env:, the
    Neon secret puts it in the shared writers group, and the report files are
    uploaded as an artifact (the repo's first upload-artifact step)."""
    data = _load(WF_DIR / "residual_gate.yml")
    on = _on(data)
    assert set(on) == {"workflow_dispatch"}
    inputs = on["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"train_seasons", "test_season", "write_model_run"}
    assert inputs["train_seasons"]["default"] == "2023 2024"
    assert inputs["test_season"]["default"] == "2025"
    assert inputs["write_model_run"]["type"] == "boolean"
    assert inputs["write_model_run"]["default"] is False
    assert (data.get("concurrency") or {}).get("group") == NEON_GROUP
    steps = data["jobs"]["gate"]["steps"]
    run_steps = [s for s in steps if isinstance(s.get("run"), str)]
    for s in run_steps:
        assert "inputs." not in s["run"], "an input is inlined into a run: block"
    gate = next(s for s in run_steps if "residual_gate.py" in s["run"])
    assert set(gate["env"]) == {"IN_TRAIN_SEASONS", "IN_TEST_SEASON", "IN_WRITE_MODEL_RUN"}
    assert all(v.startswith("${{ inputs.") for v in gate["env"].values())
    upload = next(s for s in steps if str(s.get("uses", "")).startswith("actions/upload-artifact@"))
    assert upload["with"]["path"] == "reports/residual_gate_*"
    assert upload.get("if") == "always()"
