"""Classify a Bash command for the PreToolUse hook (scripts/hooks/pre_bash.sh).

Prints one line:
  none                 nothing to gate
  push                 a `git push` somewhere in the command
  merge <pr-or-empty>  a `gh pr merge`; the PR argument as given (empty = current branch)
  masked <reason>      a test run whose exit code cannot reach the caller

Masking is what let a red suite push once (CLAUDE.md, "Check the exit code of every
test run yourself"): a test command piped into tail/head/grep without `pipefail`,
or a test command followed by `|| true` / `|| :`.

With --checks it reads `gh pr checks --json name,bucket` instead and prints what
blocks a merge (empty = nothing); with --skips it reads a unified diff and prints
every added line that skips, xfails or narrows a test. Stdlib only; runs on py3.9.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

OPERATORS = {";", "&&", "||", "|", "&", "\n", "(", ")"}
FILTERS = {"tail", "head", "grep"}


def _tokens(cmd: str) -> list[str] | None:
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()")
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:
        return None


def _words(cmd: list[str]) -> list[str]:
    """Drop leading VAR=value assignments and `env`/`time`/`exec` wrappers."""
    i = 0
    while i < len(cmd) and (
        re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", cmd[i]) or cmd[i] in {"env", "time", "exec"}
    ):
        i += 1
    return cmd[i:]


def _is_test(cmd: list[str]) -> bool:
    w = _words(cmd)
    if not w:
        return False
    head = w[0].rsplit("/", 1)[-1]
    if head in {"pytest", "vitest", "tsc"}:
        return True
    if head.startswith("python") and "-m" in w:
        i = w.index("-m")
        return i + 1 < len(w) and w[i + 1] == "pytest"
    if head == "npx" and len(w) > 1:
        return w[1] in {"vitest", "tsc", "playwright"}
    if head == "npm" and len(w) > 1:
        return w[1] == "test" or (w[1] == "run" and len(w) > 2 and w[2].startswith("test"))
    return False


def _git_sub(w: list[str]) -> str | None:
    """The git subcommand, skipping -C <path> / -c <k=v> and other global flags."""
    i = 1
    while i < len(w):
        if w[i] in {"-C", "-c", "--git-dir", "--work-tree"}:
            i += 2
            continue
        if w[i].startswith("-"):
            i += 1
            continue
        return w[i]
    return None


def _after(cmds: list[tuple[list[str], str]], i: int) -> tuple[str, list[str]]:
    """The operator that really follows command i, stepping out of `( ... )`
    groups, and the words of the next command."""
    op = cmds[i][1]
    j = i
    while op == ")" and j + 1 < len(cmds) and not cmds[j + 1][0]:
        j += 1
        op = cmds[j][1]
    nxt = _words(cmds[j + 1][0]) if j + 1 < len(cmds) else []
    return op, nxt


def classify(cmd: str) -> str:
    # Redirections like 2>&1 and &> are not command separators.
    cmd = re.sub(r"\d*[<>]&\d*-?|&>>?", " ", cmd)
    # A newline ends a command too. Inside quotes it stays text; in a heredoc body it
    # turns data into "commands" -- a false push only costs a suite check.
    cmd = cmd.replace("\n", " ; ")
    toks = _tokens(cmd)
    if toks is None:
        # Unparseable (an unquoted heredoc, say): still never let a push slip by.
        if re.search(r"(^|[\s;&|(])git\s+(?:-C\s+\S+\s+)?push(\s|$)", cmd):
            return "push"
        return "none"

    # Split into simple commands, remembering the operator that ended each one.
    cmds: list[tuple[list[str], str]] = []
    cur: list[str] = []
    for t in toks:
        if t in OPERATORS or (t and set(t) <= set(";&|()")):
            cmds.append((cur, t))
            cur = []
        else:
            cur.append(t)
    cmds.append((cur, ""))

    pipefail = "pipefail" in cmd
    result = "none"
    for i, (c, _op) in enumerate(cmds):
        w = _words(c)
        if not w:
            continue
        head = w[0].rsplit("/", 1)[-1]
        if head == "git" and _git_sub(w) == "push":
            result = "push"
        if head == "gh" and w[1:3] == ["pr", "merge"]:
            args = [a for a in w[3:] if not a.startswith("-")]
            return f"merge {args[0] if args else ''}".rstrip()
        if _is_test(c):
            op, nxt = _after(cmds, i)
            if op == "|" and not pipefail and nxt and nxt[0] in FILTERS:
                return f"masked: {w[0]} piped into {nxt[0]} without set -o pipefail"
            if op == "||":
                if nxt in (["true"], [":"]):
                    return f"masked: {w[0]} || {nxt[0]} throws the exit code away"
    return result


REQUIRED_CHECKS = ("web", "python", "e2e")


def check_problems(raw: str) -> str:
    """`gh pr checks --json name,bucket` -> "" when web, python and e2e are all
    present and every check is in the pass bucket, else what is wrong."""
    try:
        rows = json.loads(raw)
    except ValueError:
        return "could not read gh pr checks"
    if not isinstance(rows, list):
        return "could not read gh pr checks"
    names = {r.get("name") for r in rows}
    missing = [n for n in REQUIRED_CHECKS if n not in names]
    out = ["missing: " + ", ".join(missing)] if missing else []
    out += [f"{r.get('name')}={r.get('bucket')}" for r in rows if r.get("bucket") != "pass"]
    return "; ".join(out)


TEST_FILE = re.compile(r"(^|/)(tests/.*\.py|[^/]+\.(test|spec)\.tsx?)$")
SKIP_MARK = re.compile(
    r"pytest\.mark\.(skip|skipif|xfail)|pytest\.(skip|xfail)\(|"
    r"\b(it|test|describe)\.(skip|only|todo|fails)\b|\bx(it|describe)\("
)


def added_skips(diff: str) -> list[str]:
    """Lines a unified diff ADDS to a test file that skip, xfail or narrow a test
    run. Tate's call each time; never a way to get a suite green."""
    hits: list[str] = []
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            path = path[2:] if path.startswith("b/") else path
            continue
        if line.startswith("+") and TEST_FILE.search(path) and SKIP_MARK.search(line):
            hits.append(f"{path}: {line[1:].strip()}")
    return hits


if __name__ == "__main__":
    data = sys.stdin.read()
    mode = sys.argv[1:]
    if mode == ["--checks"]:
        print(check_problems(data))
    elif mode == ["--skips"]:
        print("\n".join(added_skips(data)))
    else:
        print(classify(data))
