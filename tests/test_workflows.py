"""Guards on the GitHub Actions workflows (pure YAML checks, no network).

1. Every Neon-writing workflow shares ONE concurrency group so two writers never
   run at once (id-sequence race, see tests/test_store_sequences.py).
2. Every cron string in a workflow with a "resolve" step is mapped in that step's
   `case "$SCHEDULE"` block — an unmapped cron fails the run loudly, so this test
   catches the edit before it ships.
"""

import re
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
    slate or a blank injury feed ships as the morning card."""
    steps = _card_steps_by_id()
    sweep, preview, build = steps["sweep"], steps["preview"], steps["build"]
    assert '--status-file "$RUNNER_TEMP/sweep_status.json"' in sweep["run"]
    assert '--status-file "$RUNNER_TEMP/preview_status.json"' in preview["run"]
    assert "--slot" in build["run"] and "steps.slot.outputs.slot" in build["run"]
    assert '--sweep-status "$SWEEP_STATUS"' in build["run"]
    assert '--preview-status "$PREVIEW_STATUS"' in build["run"]
    # Either step dying before it wrote its own file still reaches the card as
    # a failure, rather than as "the step did not run".
    assert '{"ok": false, "reason": "step_failed"}' in build["run"]
    assert '"complete": false, "reason": "step_failed"' in build["run"]
    assert build["env"]["PREVIEW_OUTCOME"] == "${{ steps.preview.outcome }}"
    assert build["env"]["SWEEP_OUTCOME"] == "${{ steps.sweep.outcome }}"


def test_a_failed_sweep_still_publishes_a_card_and_still_reddens_the_run():
    """A mid-sweep Odds API error used to kill the job before build_card ran, so
    the most likely degraded-card trigger produced NO card at all. The sweep now
    continues on error and a final step fails the run, so both signals survive:
    the card ships degraded AND GitHub sends the failed-run email."""
    steps = _card_steps_by_id()
    assert steps["sweep"]["continue-on-error"] is True
    # The build is NOT gated on the sweep succeeding.
    assert "sweep" not in steps["build"]["if"]
    guard = _card_steps()[-1]
    assert guard["if"] == "always() && steps.sweep.outcome == 'failure'"
    assert "exit 1" in guard["run"] and "::error::" in guard["run"]


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
    # The build is the last SLOT-GATED step; only the sweep-failure guard, which
    # runs on always(), may follow it.
    assert _card_steps_by_id()["build"]["if"] == "steps.slot.outputs.slot != 'skip'"
    assert steps[-1]["if"].startswith("always()")
    inputs = _on(_load(WF_DIR / "card.yml"))["workflow_dispatch"]["inputs"]
    assert inputs["slot"]["description"].startswith("tue_pm | thu_pm | fri_pm | sat_am | manual")
    # `force` is what lets a deliberate rebuild past the built-today probe that
    # now applies to a named dispatch; the resolve step must actually read it.
    assert "force" in inputs
    assert (steps[resolve].get("env") or {}).get("INPUT_FORCE")


def test_grade_yml_backfills_pbp_only_missing_and_scopes_post_mortem():
    """grade.yml runs twice a day with no skip gate, so each run must be cheap:
    the PBP step fetches only the weeks still missing rows, and the post-mortem
    regrades only the live season except on Monday ET / a manual dispatch."""
    data = _load(WF_DIR / "grade.yml")
    steps = data["jobs"]["grade"]["steps"]
    runs = [s["run"] for s in steps if isinstance(s.get("run"), str)]
    pbp = next(r for r in runs if "scripts/backfill_pbp.py" in r)
    assert "--only-missing" in pbp
    resolve = next(s for s in steps if s.get("id") == "season")
    assert "et_dow=$(TZ=America/New_York date +%u)" in resolve["run"]
    pm = next(s for s in steps if "scripts/post_mortem.py" in (s.get("run") or ""))
    assert pm["env"]["ET_DOW"] == "${{ steps.season.outputs.et_dow }}"
    assert "scope=live" in pm["run"]
    assert '"$ET_DOW" = "1"' in pm["run"]
    assert '"$GITHUB_EVENT_NAME" = "workflow_dispatch"' in pm["run"]
    assert '--scope "$scope"' in pm["run"]
    # Both crons stay; no case-block gate.
    assert len(_cron_strings(data)) == 2
    assert not any('case "$SCHEDULE"' in r for r in runs)


def test_rescore_yml_is_dispatch_only_and_writes_through_env():
    """rescore.yml: re-score one past week (2026 week 1 was never scored).
    Dispatch-only with required season/week inputs that reach bash only via
    env:, no GameRecord snapshot after kickoff, then the two graders."""
    data = _load(WF_DIR / "rescore.yml")
    on = _on(data)
    assert set(on) == {"workflow_dispatch"}
    inputs = on["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"season", "week"}
    assert inputs["season"]["required"] is True and inputs["week"]["required"] is True
    assert (data.get("concurrency") or {}).get("group") == NEON_GROUP
    steps = data["jobs"]["rescore"]["steps"]
    run_steps = [s for s in steps if isinstance(s.get("run"), str)]
    for s in run_steps:
        assert "inputs." not in s["run"], "an input is inlined into a run: block"
    score = next(s for s in run_steps if "scripts/weekly_update.py" in s["run"])
    assert "--no-snapshot" in score["run"]
    assert '--season "$IN_SEASON"' in score["run"] and '--week "$IN_WEEK"' in score["run"]
    assert score["env"] == {"IN_SEASON": "${{ inputs.season }}", "IN_WEEK": "${{ inputs.week }}"}
    order = [
        i
        for i, s in enumerate(run_steps)
        if any(k in s["run"] for k in ("weekly_update.py", "scripts/grade.py", "pick.py grade"))
    ]
    assert len(order) == 3 and order == sorted(order)
    assert "scripts/grade.py" in run_steps[order[1]]["run"]
    assert "pick.py grade" in run_steps[order[2]]["run"]


def test_sunday_capture_is_gated_so_three_crons_spend_one_slates_credits():
    """Three Sunday crons each spent 6 credits (2 markets x 3 regions), so a
    week where all three fired paid 18 to capture one slate. The expensive step
    is now gated on a positive fact -- a full_game_total snapshot written today
    (ET) -- the same shape as card.yml's built-today probe, with `force` for a
    deliberate re-capture. Only the capture is gated: the rest of the job costs
    nothing and re-running it is what you want if the first run half-failed."""
    data = _load(WF_DIR / "sunday.yml")
    steps = data["jobs"]["capture-and-score"]["steps"]
    by_name = {s.get("name"): s for s in steps}

    gate = next(s for s in steps if s.get("id") == "captured")
    assert "full_game_total" in gate["run"]
    assert "America/New_York" in gate["run"], "the guard must key on the ET day"
    assert gate["env"]["FORCE"] == "${{ inputs.force }}"
    assert "force" in _on(data)["workflow_dispatch"]["inputs"]

    capture = next(s for s in steps if s.get("name", "").startswith("Capture full-game openers"))
    assert capture["if"] == "steps.captured.outputs.need_capture == 'true'"
    assert "poll_full_game.py" in capture["run"]

    # The free, idempotent work stays ungated.
    assert by_name["Score + rank the board"].get("if") is None


def test_card_yml_crons_and_ci_CRON_SLOTS_are_the_same_set():
    """The gap this closes: NOTHING asserted these two agreed.

    test_workflows only validated workflows whose run block contains a
    `case "$SCHEDULE"` ladder, and card.yml resolves through
    `python -m beatvegas.ci` instead — so it was skipped entirely here.
    test_ci_slots checks CRON_SLOTS on its own and never opens the YAML. Adding
    a cron to card.yml without adding it to ci.py therefore passed CI in full
    and then failed at 4:05pm ET with `::error:: unmapped cron`, on a day the
    card is what Tate bets off.

    Both directions matter: an unmapped cron fails the run loudly, and a mapping
    with no cron behind it is a slot that silently never fires.
    """
    from beatvegas.ci import CRON_SLOTS

    yml = _on(_load(WF_DIR / "card.yml"))["schedule"]
    in_yaml = {c["cron"] for c in yml}
    in_py = set(CRON_SLOTS)

    assert in_yaml - in_py == set(), (
        f"card.yml crons with no beatvegas.ci mapping (these would fail the run "
        f"at fire time): {sorted(in_yaml - in_py)}"
    )
    assert in_py - in_yaml == set(), (
        f"beatvegas.ci mappings with no cron in card.yml (these slots never "
        f"fire): {sorted(in_py - in_yaml)}"
    )
    # Four crons per slot is the DST design: two land inside the ET gate in each
    # regime. Fewer than four means a regime lost its retry.
    from collections import Counter

    per_slot = Counter(CRON_SLOTS.values())
    assert set(per_slot.values()) == {4}, f"expected 4 crons per slot, got {dict(per_slot)}"


def test_lines_watch_has_no_mapping_for_a_cron_it_no_longer_runs():
    """The reverse of the check above, for the workflow that DOES use a case
    ladder. test_workflows only ever checked crons -> mappings, so the retired
    `1h_open` branches sat in the script as dead code long after their crons
    were removed, and nothing said so."""
    data = _load(WF_DIR / "lines_watch.yml")
    crons = {c["cron"] for c in _on(data)["schedule"]}
    run = next(
        s["run"]
        for s in data["jobs"][next(iter(data["jobs"]))]["steps"]
        if 'case "$SCHEDULE"' in str(s.get("run", ""))
    )
    # Every cron string the case ladder names must still be scheduled.
    mapped = set(re.findall(r"^\s*'([-\d,* /]+)'\)", run, re.M))
    orphans = mapped - crons
    assert not orphans, f"case branches for crons that no longer exist: {sorted(orphans)}"
