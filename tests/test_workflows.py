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
    assert '--season "$SEASON"' in run and '--week "$WEEK"' in run
    assert steps[rescore]["env"]["SEASON"] == "${{ steps.active.outputs.season }}"
    assert steps[rescore]["env"]["WEEK"] == "${{ steps.active.outputs.week }}"
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
    assert '--slot "$SLOT"' in build["run"]
    assert build["env"]["SLOT"] == "${{ steps.slot.outputs.slot }}"
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


def test_card_yml_gates_on_the_eastern_clock_before_installing_anything():
    """Two of each slot's four backup crons fall outside the ET window in any
    DST regime (the DST design), and until 2026-09-16 every one of them paid
    setup-python + pip install to learn that (20 of 29 card runs that month
    were skips, ~1 billed minute each). The gate is stdlib-only, so it runs on
    the runner's python3 straight after checkout (GATE_ONLY=true, no DB probe);
    setup, install, the cache restore and the full resolve are all gated on it.
    The full resolve still probes the `cards` table, so python + the package
    must be installed BEFORE it, and the old `gh run list --status success`
    retry check — which counted a gate-skip run as a success and blocked the
    EST build — must stay gone."""
    steps = _card_steps()
    assert str(steps[0].get("uses", "")).startswith("actions/checkout@")
    gate = steps[1]
    assert gate.get("id") == "gate"
    assert gate["env"]["GATE_ONLY"] == "true"
    assert {"SCHEDULE", "INPUT_SLOT", "INPUT_FORCE"} <= set(gate["env"])
    assert "python3 -m beatvegas.ci" in gate["run"]
    assert "if" not in gate, "the gate itself must always run"
    setup = next(
        i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/setup-python@")
    )
    install = next(i for i, s in enumerate(steps) if s.get("name") == "Install")
    restore = next(i for i, s in enumerate(steps) if s.get("id") == "cfbd_cache")
    resolve = next(i for i, s in enumerate(steps) if s.get("id") == "slot")
    assert 1 < setup < install < restore < resolve
    for i in (setup, install, restore, resolve):
        assert steps[i].get("if") == "steps.gate.outputs.slot != 'skip'", steps[i].get("name")
    assert steps[setup]["with"].get("cache") == "pip"
    run = steps[resolve]["run"]
    assert "beatvegas.ci" in run
    assert "GATE_ONLY" not in (steps[resolve].get("env") or {}), "the full resolve must probe"
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
    """grade.yml fires three times a day (Vercel dispatch + two GitHub crons),
    so each run must be cheap even when the probe below lets it through:
    the PBP step fetches only the weeks still missing rows, and the post-mortem
    regrades only the live season except on Monday ET or a dispatch that asks
    for it (hist=true). NOT every dispatch: the Vercel cron that is this
    workflow's primary trigger is a dispatch, and keying on the event ran the
    2023-25 regrade (7 MB read, 3.5 MB rewrite) every single day."""
    data = _load(WF_DIR / "grade.yml")
    steps = data["jobs"]["grade"]["steps"]
    runs = [s["run"] for s in steps if isinstance(s.get("run"), str)]
    pbp = next(r for r in runs if "scripts/backfill_pbp.py" in r)
    assert "--only-missing" in pbp
    espn = next(r for r in runs if "scripts/backfill_scores_espn.py" in r)
    assert "--days-back 4" in espn, "twice a day, four days back covers every late final"
    resolve = next(s for s in steps if s.get("id") == "season")
    assert "et_dow=$(TZ=America/New_York date +%u)" in resolve["run"]
    pm = next(s for s in steps if "scripts/post_mortem.py" in (s.get("run") or ""))
    assert pm["env"]["ET_DOW"] == "${{ steps.season.outputs.et_dow }}"
    assert "scope=live" in pm["run"]
    assert '"$ET_DOW" = "1"' in pm["run"]
    assert pm["env"]["IN_HIST"] == "${{ inputs.hist }}"
    assert '"$IN_HIST" = "true"' in pm["run"]
    assert 'GITHUB_EVENT_NAME" = "workflow_dispatch' not in pm["run"]
    assert '--scope "$scope"' in pm["run"]
    hist = _on(data)["workflow_dispatch"]["inputs"]["hist"]
    assert hist["type"] == "boolean" and hist["default"] is False
    # Both crons stay; no case-block gate.
    assert len(_cron_strings(data)) == 2
    assert not any('case "$SCHEDULE"' in r for r in runs)


def test_grade_yml_skips_when_a_run_completed_in_the_last_four_hours():
    """Three triggers a day (the Vercel dispatch at ~10:52Z and GitHub's 10:30Z
    and 16:00Z crons, which fire 2-4 h late) each ran every step: ~18
    runner-minutes a day for one useful pass, measured 2026-09-20/21. The
    probe reads a POSITIVE fact -- a postmortem_runs row with scope=live inside
    the last four hours; the post-mortem is the job's last step, so the row
    proves a whole run completed -- and gates every work step on it. Four
    hours, not "today": the noon-ET second pass for late finals is deliberate
    and stays. hist=true forces. The cache save stays on always()."""
    data = _load(WF_DIR / "grade.yml")
    steps = data["jobs"]["grade"]["steps"]
    probe = next(s for s in steps if s.get("id") == "probe")
    # The live scope is written as live_<season> (beatvegas/postmortem.py); a probe
    # on scope = 'live' matched nothing and never skipped (caught 2026-09-22).
    # The probe keys on the gauge grade.yml writes after its FATAL steps, not on
    # the post-mortem row (written even when four continue-on-error steps failed).
    assert "app_settings" in probe["run"] and "last_grade_completed_at" in probe["run"]
    assert "postmortem_runs" not in probe["run"]
    marker = next(
        s for s in steps if "record_gauge.py --key last_grade_completed_at" in (s.get("run") or "")
    )
    names = [s.get("name", "") for s in steps]
    assert names.index(marker["name"]) > names.index("Grade frozen game records")
    assert names.index(marker["name"]) < names.index(
        "Post-mortem (rated games vs outcomes -> postmortem_* tables)"
    )
    assert "timedelta(hours=4)" in probe["run"]
    assert probe["env"]["IN_HIST"] == "${{ inputs.hist }}"
    assert 'os.environ.get("IN_HIST") == "true"' in probe["run"]
    assert "need_grade=" in probe["run"]
    idx = steps.index(probe)
    assert steps[idx - 1].get("id") == "season", "the probe runs right after the season resolves"
    gate = "steps.probe.outputs.need_grade == 'true'"
    for s in steps[idx + 1 :]:
        if s.get("uses") == CACHE_SAVE:
            assert (s.get("if") or "").startswith("always()")
            continue
        assert s.get("if") == gate, f"{s.get('name')} is not gated on the probe"
    assert any("scripts/post_mortem.py" in (s.get("run") or "") for s in steps[idx + 1 :])


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
    deliberate re-capture.

    Since 2026-09-16 the REST of the job is gated on a second positive fact,
    `need_score` (no model prediction row for the active week written today
    ET): "free and idempotent" was ~290 Open-Meteo calls, 22 CFBD reference
    calls and two feature-frame builds per tick, and 2026-09-13 ran four ticks
    for one capture. A run that captured but died before scoring leaves no
    prediction row, so the next tick still scores -- the old design's one
    virtue, kept. The scorer also writes the board-tint references once and
    the derived-lines step reads them instead of rebuilding the frame."""
    data = _load(WF_DIR / "sunday.yml")
    steps = data["jobs"]["capture-and-score"]["steps"]
    by_name = {s.get("name"): s for s in steps}

    gate = next(s for s in steps if s.get("id") == "captured")
    assert "full_game_total" in gate["run"]
    assert "America/New_York" in gate["run"], "the guard must key on the ET day"
    assert gate["env"]["FORCE"] == "${{ inputs.force }}"
    assert "force" in _on(data)["workflow_dispatch"]["inputs"]
    assert "need_score=" in gate["run"] and 'model_version != "derived_lines"' in gate["run"]
    assert gate["env"]["SEASON"] == "${{ steps.active.outputs.season }}"
    assert gate["env"]["WEEK"] == "${{ steps.active.outputs.week }}"

    capture = next(s for s in steps if s.get("name", "").startswith("Capture full-game openers"))
    assert capture["if"] == "steps.captured.outputs.need_capture == 'true'"
    assert "poll_full_game.py" in capture["run"]

    score_gate = "steps.captured.outputs.need_score == 'true'"
    for name in (
        "Refresh pace for the active week (TeamRankings, season-to-date as of today)",
        "Refresh weather forecasts for the active week (Open-Meteo)",
        "Score + rank the board",
        "Post derived 1H lines for the active week",
    ):
        assert by_name[name].get("if") == score_gate, name
    assert by_name["Warn when the board scored WITHOUT pace/weather"]["if"].startswith(score_gate)
    score = by_name["Score + rank the board"]["run"]
    derived = by_name["Post derived 1H lines for the active week"]["run"]
    assert '--write-refs "$RUNNER_TEMP/factor_refs.json"' in score
    assert '--refs "$RUNNER_TEMP/factor_refs.json"' in derived
    # Weather is FBS-only by default: no --all-divisions on the scheduled path.
    assert (
        "--all-divisions"
        not in by_name["Refresh weather forecasts for the active week (Open-Meteo)"]["run"]
    )


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


# --- Actions minutes + the CFBD reference cache (2026-09-16). The repo is
# private, so every runner minute is metered against 2,000/month; CI was 58% of
# the bill and the CFBD cache had been saving an EMPTY payload all season.

FEATURE_FRAME_SCRIPTS = (
    # Every script here reaches etl/features.build_feature_frame, which fetches
    # the SP+/talent/roster/returning/adv references (~22 CFBD calls) unless
    # data/cache already holds them.
    "scripts/weekly_update.py",
    "scripts/grade_factor_ledger.py",
    "scripts/post_derived_lines.py",
    "scripts/residual_gate.py",
    "scripts/level_anchor_gate.py",
    "scripts/backfill_bv_intercept.py",
)
CACHE_RESTORE = "./.github/actions/cfbd-cache"
CACHE_SAVE = "./.github/actions/cfbd-cache-save"
ACTIONS_DIR = WF_DIR.parent / "actions"


def _steps(data: dict):
    for job in (data.get("jobs") or {}).values():
        yield from (job.get("steps") or [])


def test_ci_runs_on_pull_requests_only_and_caches_pip():
    """`push: main` re-ran the exact content the PR had just passed (81 of 284
    runs in half a month); Vercel deploys main on its own. The python job also
    reinstalled pandas/sklearn from PyPI every run."""
    data = _load(WF_DIR / "ci.yml")
    assert set(_on(data)) == {"pull_request"}
    setups = [s for s in _steps(data) if str(s.get("uses", "")).startswith("actions/setup-python@")]
    assert setups and all(s["with"].get("cache") == "pip" for s in setups)


def test_every_scheduled_python_workflow_caches_pip():
    """A scheduled job runs dozens of times a month; the ~40 s reinstall is a
    billed minute each time."""
    checked = 0
    for p in _workflows():
        data = _load(p)
        if not _cron_strings(data):
            continue
        for s in _steps(data):
            if str(s.get("uses", "")).startswith("actions/setup-python@"):
                assert (s.get("with") or {}).get("cache") == "pip", (
                    f"{p.name}: setup-python without cache: pip"
                )
                checked += 1
    assert checked >= 4


def test_cfbd_cache_is_restored_where_features_build_and_saved_only_when_populated():
    """The single `actions/cache` step saved in its post-job hook whenever the
    key was missing -- whoever ran first. The first job of every ISO week was
    the Tuesday research preview (zero CFBD calls), so the key held 12 KB of
    espn_teams.json and every later run re-fetched the ~22 reference calls the
    cache exists to share (~1,900 of the 3,000-call month). Now: a restore step
    with id `cfbd_cache` wherever a feature frame is built, and ONE save step,
    after the last such script, that runs on always() and only when this run
    populated the directory (the save action checks the files itself)."""
    checked = 0
    for p in _workflows():
        data = _load(p)
        steps = list(_steps(data))
        runs_features = any(
            isinstance(s.get("run"), str) and any(k in s["run"] for k in FEATURE_FRAME_SCRIPTS)
            for s in steps
        )
        restores = [i for i, s in enumerate(steps) if s.get("uses") == CACHE_RESTORE]
        saves = [i for i, s in enumerate(steps) if s.get("uses") == CACHE_SAVE]
        for s in steps:
            assert not str(s.get("uses", "")).startswith("actions/cache@"), (
                f"{p.name}: use the split restore/save composites, not actions/cache"
            )
        if runs_features:
            assert restores, f"{p.name}: builds a feature frame without restoring the CFBD cache"
        if not restores:
            assert not saves, f"{p.name}: saves a cache it never restored"
            continue
        assert len(restores) == 1 and steps[restores[0]].get("id") == "cfbd_cache", p.name
        assert len(saves) == 1, f"{p.name}: exactly one save step"
        save = steps[saves[0]]
        assert save["with"]["key"] == "${{ steps.cfbd_cache.outputs.key }}", p.name
        cond = save.get("if") or ""
        assert cond.startswith("always()"), f"{p.name}: the save must run on always()"
        assert "steps.cfbd_cache.outputs.hit != 'true'" in cond, p.name
        last_feature = max(
            (
                i
                for i, s in enumerate(steps)
                if isinstance(s.get("run"), str)
                and any(k in s["run"] for k in FEATURE_FRAME_SCRIPTS)
            ),
            default=restores[0],
        )
        assert saves[0] > last_feature > restores[0] or saves[0] > restores[0], p.name
        checked += 1
    assert checked >= 6, (
        f"expected the card, grade, sunday, rescore, study and gate workflows; got {checked}"
    )


def test_cfbd_cache_actions_are_split_and_sha_pinned():
    """Restore and save are two composites so the save can be gated on the
    directory actually holding reference files, and both pin actions/cache's
    sub-actions to a SHA -- the one mutable `@v4` tag PR #98 left behind sat
    inside the jobs carrying DATABASE_URL."""
    sha = re.compile(r"^actions/cache/(restore|save)@[0-9a-f]{40}$")
    restore = _load(ACTIONS_DIR / "cfbd-cache" / "action.yml")
    assert set(restore["outputs"]) == {"key", "hit"}
    r_steps = restore["runs"]["steps"]
    assert r_steps[0]["id"] == "week" and "%G-W%V" in r_steps[0]["run"]
    assert r_steps[1]["id"] == "restore" and sha.match(r_steps[1]["uses"]).group(1) == "restore"
    assert r_steps[1]["with"]["path"] == "data/cache"
    assert not any("restore-keys" in (s.get("with") or {}) for s in r_steps), (
        "no restore-keys: SP+ would freeze"
    )

    save = _load(ACTIONS_DIR / "cfbd-cache-save" / "action.yml")
    assert save["inputs"]["key"]["required"] is True
    s_steps = save["runs"]["steps"]
    check = s_steps[0]
    assert check["id"] == "check" and "populated=" in check["run"]
    for name in ("sp_", "talent_", "roster_", "returning_", "adv_"):
        assert name in check["run"], f"the populated check must look for {name}*.json"
    assert "-size +1k" in check["run"], "2-byte empty payloads must not count"
    assert sha.match(s_steps[1]["uses"]).group(1) == "save"
    assert s_steps[1]["if"] == "steps.check.outputs.populated == 'true'"
    assert s_steps[1]["with"]["path"] == "data/cache"

    # Repo-wide: every remote `uses:` under .github is a 40-hex SHA.
    for path in list(WF_DIR.glob("*.yml")) + list(ACTIONS_DIR.glob("*/action.yml")):
        for m in re.finditer(r"^\s*-?\s*uses:\s*(\S+)", path.read_text(), re.M):
            ref = m.group(1)
            if ref.startswith("./"):
                continue
            assert re.search(r"@[0-9a-f]{40}$", ref), f"{path.name}: {ref} is not pinned to a SHA"


# --- Script-injection hygiene, repo-wide (2026-09-16 security review). A `${{ }}`
# inside a run: block is substituted into the script TEXT before bash parses
# it. Every job here carries secrets, so any value a person can type -- a
# dispatch input, or a step output derived from one -- has to cross into the
# shell as an environment variable. card.yml's season/week were the one
# regression (four run: blocks), and the guard on residual_gate/rescore did
# not cover `steps.*.outputs`, so this is the general rule.

INLINE_EXPR = re.compile(r"\$\{\{\s*(inputs\.|steps\.|github\.event\.)")


def test_no_run_block_inlines_an_expression_in_a_job_that_holds_secrets():
    checked = 0
    for p in _workflows():
        for jname, job in (_load(p).get("jobs") or {}).items():
            if "secrets." not in yaml.safe_dump(job.get("env") or {}):
                continue
            for st in job.get("steps") or []:
                run = st.get("run")
                if not isinstance(run, str):
                    continue
                m = INLINE_EXPR.search(run)
                assert m is None, (
                    f"{p.name}:{jname} step {st.get('name') or st.get('id')!r} inlines "
                    f"`{run[m.start() : m.start() + 40]}...` into bash; pass it through env:"
                )
                checked += 1
    assert checked > 30


def test_card_yml_validates_the_two_typed_inputs_before_using_them():
    steps = _card_steps_by_id()
    resolve = steps["active"]
    assert set(resolve["env"]) == {"INPUT_SEASON", "INPUT_WEEK"}
    run = resolve["run"]
    assert '[[ "$INPUT_SEASON" =~ ^[0-9]{4}$ ]]' in run
    assert '[[ "$INPUT_WEEK" =~ ^[0-9]{1,2}$ ]]' in run
    # The checks run BEFORE the values are used or echoed to $GITHUB_OUTPUT.
    assert run.index("^[0-9]{4}$") < run.index('echo "season=')
    # Downstream, only env carries them.
    for sid in ("sweep", "preview", "build"):
        assert not INLINE_EXPR.search(steps[sid]["run"]), sid
    assert steps["sweep"]["env"]["SWEEP_ARGS"] == "${{ steps.slot.outputs.sweep_args }}"
    assert "$SWEEP_ARGS" in steps["sweep"]["run"]
    assert steps["preview"]["env"]["SEASON"] == "${{ steps.active.outputs.season }}"


# --- Hash-pinned installs (2026-09-16). requirements.txt caps the next major;
# requirements/lock.txt pins the exact release and its sha256 hashes, and every
# runner installs from the lock with --require-hashes, then this repo with
# --no-build-isolation so the build backend (also locked) is never fetched
# unhashed.

LOCK = WF_DIR.parent.parent / "requirements" / "lock.txt"
REQS = WF_DIR.parent.parent / "requirements.txt"


def _pkg_names(text: str):
    out = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("--"):
            continue
        name = re.split(r"[<>=!~\[; \\]", line, maxsplit=1)[0]
        out.add(name.lower().replace("_", "-"))
    return out


def test_every_python_install_is_hash_pinned_and_the_pip_cache_keys_on_the_lock():
    checked = 0
    for p in _workflows():
        data = _load(p)
        for job in (data.get("jobs") or {}).values():
            steps = job.get("steps") or []
            # CI's web job has an "Install" step too (`npm ci`); only pip installs count.
            installs = [
                s for s in steps if s.get("name") == "Install" and "pip" in str(s.get("run"))
            ]
            for s in installs:
                run = s["run"]
                assert "pip install --require-hashes -r requirements/lock.txt" in run, p.name
                assert "pip install --no-deps --no-build-isolation -e ." in run, p.name
                assert "pip install -e .\n" not in run + "\n" or "--no-deps" in run, p.name
                checked += 1
            for s in steps:
                if str(s.get("uses", "")).startswith("actions/setup-python@"):
                    w = s.get("with") or {}
                    if w.get("cache") == "pip":
                        assert w.get("cache-dependency-path") == "requirements/lock.txt", p.name
    assert checked >= 14


def test_the_lock_lives_where_dependabot_can_see_it():
    """Dependabot's Python fetcher only fetches files ending in .txt or .in
    (dependabot-core python/shared_file_fetcher.rb). A `requirements.lock` was
    invisible to it, so it raised every range in requirements.txt instead
    (#171). The lock must be a .txt in its own directory, and the pip entry
    must point at that directory and nowhere else."""
    assert LOCK.suffix == ".txt" and LOCK.parent.name == "requirements"
    assert LOCK.exists()
    bot = yaml.safe_load((WF_DIR.parent / "dependabot.yml").read_text())
    pip = [u for u in bot["updates"] if u["package-ecosystem"] == "pip"]
    assert len(pip) == 1 and pip[0]["directory"] == "/requirements"
    # Nothing else in that directory could be mistaken for a manifest.
    # `.python-version` is the one exception and is not one: Dependabot reads it
    # to pick the interpreter it resolves against (3.11, the runner), which is
    # what stops it proposing wheels that need 3.12 -- contourpy 1.4.0 (#173),
    # numpy 2.5.3 / scipy 1.18.1 (#184), all MINOR bumps the semver-major ignore
    # cannot catch. It lives here rather than at the repo root so a pyenv shim
    # cannot switch this Mac's interpreter (local dev is 3.9).
    assert sorted(f.name for f in LOCK.parent.iterdir()) == [".python-version", "lock.txt"]
    assert (LOCK.parent / ".python-version").read_text().strip() == "3.11"
    # And it must not look like pip-compile output, or Dependabot would go
    # hunting for a lock.in that does not exist.
    assert "--output-file" not in LOCK.read_text()


def test_the_lock_covers_requirements_and_carries_a_hash_for_every_pin():
    lock = LOCK.read_text()
    pins = re.findall(r"^([A-Za-z0-9_.\-]+)==([^\s\\]+)", lock, re.M)
    assert len(pins) >= 30
    names = {n.lower().replace("_", "-") for n, _ in pins}
    for req in _pkg_names(REQS.read_text()):
        assert req in names, f"{req} is in requirements.txt but not in requirements/lock.txt"
    # The build backend rides in the lock so the editable install needs no isolation.
    assert {"setuptools", "wheel"} <= names
    # Every pinned block has at least one --hash line.
    blocks = re.split(r"\n(?=[A-Za-z0-9_.\-]+==)", lock)
    pinned_blocks = [b for b in blocks if re.match(r"[A-Za-z0-9_.\-]+==", b)]
    assert len(pinned_blocks) == len(pins)
    for b in pinned_blocks:
        assert "--hash=sha256:" in b, b.splitlines()[0]
