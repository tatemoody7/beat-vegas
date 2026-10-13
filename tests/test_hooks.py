"""Behaviour of the push/merge gate (scripts/hooks/pre_bash.sh, 2026-10-13).

The classifier is tested directly; the hook runs against a throwaway git repo
whose `.venv/bin/python` is a stub, so no test here ever runs the real suite,
and `gh` is a PATH stub. test_hooks_settings.py pins the wiring.

Skip markers are spelled by concatenation below: post_edit.sh refuses an edit
that ADDS one to a test file, and fixture strings would count.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "scripts" / "hooks"
sys.path.insert(0, str(HOOKS))
from classify_bash import added_skips, check_problems, classify  # noqa: E402

SKIP = "pytest.mark." + "skip"
XFAIL = "pytest.mark." + "xfail"
ONLY = "it." + "only"


@pytest.mark.parametrize(
    "cmd, want",
    [
        ("ls -la", "none"),
        ("git status && git log --oneline -3", "none"),
        ("git push -u origin ship-guards", "push"),
        ('cd "a b" && git -C /x push', "push"),
        ('git add -A\ngit commit -m "a\nb"\ngit push', "push"),
        ('git commit -m "push it"', "none"),
        ('echo "git push" > notes.txt', "none"),
        ("gh pr merge 370 --squash --delete-branch", "merge 370"),
        ("gh pr merge --squash", "merge"),
        ("gh pr view 370", "none"),
        ("set -o pipefail; pytest -q | tail -1", "none"),
        ("grep -rn pytest tests | head", "none"),
        ("PYTHONPATH=. python -m pytest -q", "none"),
        ("npx vitest run lib/x.test.ts", "none"),
    ],
)
def test_classify(cmd, want):
    assert classify(cmd) == want


@pytest.mark.parametrize(
    "cmd",
    [
        "PYTHONPATH=. python -m pytest -q | tail -1",
        "pytest -q 2>&1 | tail -3",
        "(cd web && npx vitest run) | tail -5",
        "npx tsc --noEmit || true",
        "pytest -q || :",
        "npm test | grep -c passed",
        ".venv/bin/python -m pytest tests/test_x.py | head -20",
    ],
)
def test_masked_test_runs_are_flagged(cmd):
    assert classify(cmd).startswith("masked:")


def test_check_problems_wants_web_python_e2e_all_passing():
    ok = [{"name": n, "bucket": "pass"} for n in ("web", "python", "e2e")]
    assert check_problems(json.dumps(ok)) == ""
    pending = ok[:2] + [{"name": "e2e", "bucket": "pending"}]
    assert check_problems(json.dumps(pending)) == "e2e=pending"
    assert check_problems(json.dumps(ok[:2])) == "missing: e2e"
    assert check_problems("no checks reported on the 'x' branch") == "could not read gh pr checks"


def test_added_skips_only_counts_added_lines_in_test_files():
    diff = "\n".join(
        [
            "+++ b/tests/test_a.py",
            f"+@{SKIP}(reason='flaky')",
            f"-@{XFAIL}",
            f" @{XFAIL}",
            "+++ b/beatvegas/x.py",
            f"+# {SKIP} in a comment outside tests",
            "+++ b/web/lib/y.test.ts",
            f"+  {ONLY}('narrows the run', () => {{}});",
        ]
    )
    hits = added_skips(diff)
    assert len(hits) == 2
    assert hits[0].startswith("tests/test_a.py:") and hits[1].startswith("web/lib/y.test.ts:")


# --- the hook end to end -------------------------------------------------------


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _suite_stub(repo, code):
    py = repo / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text(f"#!/bin/sh\necho 'FAILED tests/test_stub.py::test_x'\nexit {code}\n")
    py.chmod(0o755)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "beatvegas").mkdir(parents=True)
    (r / "pyproject.toml").write_text("[project]\nname='x'\n")
    (r / ".gitignore").write_text(".venv/\n")
    (r / "beatvegas" / "__init__.py").write_text("")
    _git(r, "init", "-q", "-b", "main")
    _git(r, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    _git(r, "update-ref", "refs/remotes/origin/main", "HEAD")
    return r


def _hook(cmd, cwd, path_prefix=None):
    env = dict(os.environ)
    if path_prefix:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
    stdin = json.dumps({"tool_input": {"command": cmd}, "cwd": str(cwd)})
    return subprocess.run(
        [str(HOOKS / "pre_bash.sh")], input=stdin, text=True, capture_output=True, env=env
    )


def test_push_on_a_red_suite_is_refused(repo):
    _suite_stub(repo, 1)
    r = _hook("git push -u origin x", repo)
    assert r.returncode == 2
    assert "pytest is red" in r.stderr and "FAILED" in r.stderr


def test_push_on_green_stamps_and_the_next_push_skips_the_suite(repo):
    _suite_stub(repo, 0)
    assert _hook("git push", repo).returncode == 0
    stamp = repo / ".git" / "claude-stop-hook.stamp"
    assert stamp.exists()
    _suite_stub(repo, 1)  # .venv is ignored, so the tree (and its stamp) is unchanged
    assert _hook("git push", repo).returncode == 0
    (repo / "beatvegas" / "new.py").write_text("x = 1\n")  # the tree moved: re-run, now red
    assert _hook("git push", repo).returncode == 2


def test_push_of_a_branch_adding_a_skip_is_refused(repo):
    _suite_stub(repo, 0)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_a.py").write_text(
        f"import pytest\n\n@{SKIP}\ndef test_a():\n    pass\n"
    )
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "skip")
    r = _hook("git push", repo)
    assert r.returncode == 2 and "tests/test_a.py" in r.stderr


def test_masked_test_run_is_refused(repo):
    r = _hook("pytest -q | tail -1", repo)
    assert r.returncode == 2 and "pipefail" in r.stderr


def test_merge_waits_for_every_check(repo, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"

    def checks(rows):
        gh.write_text(f"#!/bin/sh\necho '{json.dumps(rows)}'\n")
        gh.chmod(0o755)

    passing = [{"name": n, "bucket": "pass"} for n in ("web", "python", "e2e")]
    checks(passing[:2] + [{"name": "e2e", "bucket": "pending"}])
    r = _hook("gh pr merge 370 --squash", repo, bin_dir)
    assert r.returncode == 2 and "e2e=pending" in r.stderr
    checks(passing)
    assert _hook("gh pr merge 370 --squash", repo, bin_dir).returncode == 0


def test_ordinary_commands_pass_untouched(repo):
    for cmd in ("ls", "git status", "gh pr view 1", 'git commit -m "x"'):
        assert _hook(cmd, repo).returncode == 0, cmd
