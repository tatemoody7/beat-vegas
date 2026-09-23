"""The Claude Code hooks in .claude/settings.json (2026-09-22).

Two scripts under scripts/hooks/: post_edit.sh runs the checks matching an
edited file and feeds a failure back (exit 2); on_stop.sh runs the full suites
once per turn and blocks the first stop on red. These tests pin the wiring, not
the behaviour -- a hook whose script is missing, unreadable or times out is a
hook that silently never ran.
"""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ("post_edit.sh", "on_stop.sh")


def _settings():
    return json.loads((ROOT / ".claude" / "settings.json").read_text())


def test_post_edit_hook_is_wired_to_edits_and_writes():
    post = _settings()["hooks"]["PostToolUse"]
    assert len(post) == 1 and post[0]["matcher"] == "Edit|Write"
    hook = post[0]["hooks"][0]
    assert hook["type"] == "command"
    # The project path has a space; the command must quote it.
    assert hook["command"].startswith('"$CLAUDE_PROJECT_DIR/')
    assert hook["command"].endswith('scripts/hooks/post_edit.sh"')
    assert hook["timeout"] >= 90


def test_stop_hook_runs_the_full_suites_with_time_to_finish():
    stop = _settings()["hooks"]["Stop"]
    hook = stop[0]["hooks"][0]
    assert hook["command"] == '"$CLAUDE_PROJECT_DIR/scripts/hooks/on_stop.sh"'
    # pytest ~150 s + vitest + tsc; a timeout below that is a hook that never finishes.
    assert hook["timeout"] >= 240


def test_hook_scripts_exist_are_executable_and_parse():
    for name in SCRIPTS:
        p = ROOT / "scripts" / "hooks" / name
        assert p.exists(), p
        assert os.access(p, os.X_OK), f"{name} is not executable"
        assert p.read_text().startswith("#!/usr/bin/env bash")
        subprocess.run(["bash", "-n", str(p)], check=True)


def test_hooks_exit_zero_on_empty_or_irrelevant_input():
    """A hook that crashes on odd input blocks every edit; these must be inert."""
    post = ROOT / "scripts" / "hooks" / "post_edit.sh"
    for stdin in ("", "{}", json.dumps({"tool_input": {"file_path": "/nonexistent/x.py"}})):
        r = subprocess.run([str(post)], input=stdin, text=True, capture_output=True)
        assert r.returncode == 0, (stdin, r.stderr)
