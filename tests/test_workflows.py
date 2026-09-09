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


def _card_steps_by_id():
    job = _load(WF_DIR / "card.yml")["jobs"]["card"]
    return {s["id"]: s for s in job["steps"] if s.get("id")}


def test_card_yml_wires_the_status_files_through_to_the_build():
    """PR-7: the two steps that can degrade write a status file, and the build
    reads both plus the resolved slot — otherwise a card built on a half-swept
    slate or a blank injury feed ships as the Saturday final."""
    steps = _card_steps_by_id()
    sweep, preview, build = (
        steps["sweep"],
        steps["preview"],
        _load(WF_DIR / "card.yml")["jobs"]["card"]["steps"][-1],
    )
    assert '--status-file "$RUNNER_TEMP/sweep_status.json"' in sweep["run"]
    assert '--status-file "$RUNNER_TEMP/preview_status.json"' in preview["run"]
    assert "--slot" in build["run"] and "steps.slot.outputs.slot" in build["run"]
    assert '--sweep-status "$RUNNER_TEMP/sweep_status.json"' in build["run"]
    assert '--preview-status "$PREVIEW_STATUS"' in build["run"]
    # A preview step that died before writing its own file still reaches the
    # card as a failure.
    assert '{"ok": false, "reason": "step_failed"}' in build["run"]
    assert build["env"]["PREVIEW_OUTCOME"] == "${{ steps.preview.outcome }}"


def test_card_yml_can_rehearse_a_degraded_card_on_demand():
    data = _load(WF_DIR / "card.yml")
    inputs = _on(data)["workflow_dispatch"]["inputs"]
    assert "max_credits" in inputs
    sweep = _card_steps_by_id()["sweep"]
    assert sweep["env"]["MAX_CREDITS"] == "${{ inputs.max_credits }}"
    assert "--max-credits-per-run $MAX_CREDITS" in sweep["run"]


def test_card_yml_installs_before_resolving_the_slot():
    """The resolve step probes the `cards` table (beatvegas.ci.slots_built_today),
    so python + the package must be installed BEFORE it runs, and the old
    `gh run list --status success` retry check — which counted a gate-skip run as
    a success and blocked the EST build — must be gone."""
    steps = _card_steps()
    setup = next(
        i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/setup-python@")
    )
    install = next(i for i, s in enumerate(steps) if s.get("name") == "Install")
    resolve = next(i for i, s in enumerate(steps) if s.get("id") == "slot")
    assert setup < resolve and install < resolve
    assert "if" not in steps[setup] and "if" not in steps[install]
    run = steps[resolve]["run"]
    assert "beatvegas.ci" in run
    assert "gh run list" not in run and "retry_since" not in run
    assert "GH_TOKEN" not in (steps[resolve].get("env") or {})
    # Every step after the resolve is gated on it (directly or via a derived output).
    for s in steps[resolve + 1 :]:
        assert s.get("if"), f"step {s.get('name')!r} is not gated on the slot"
    assert steps[-1]["if"] == "steps.slot.outputs.slot != 'skip'"
    inputs = _on(_load(WF_DIR / "card.yml"))["workflow_dispatch"]["inputs"]
    assert inputs["slot"]["description"].startswith("morning | afternoon | manual")
