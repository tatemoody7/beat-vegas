#!/usr/bin/env bash
# PostToolUse hook (Edit|Write) for Claude Code -- .claude/settings.json.
#
# Runs the checks that MATCH the edited file, so a broken test is seen on the
# edit that broke it rather than at the end of the turn:
#   *.py            ruff --fix, then tests/test_<name>.py and tests/test_<name>_*.py if they exist
#   web/**/*.ts(x)  the sibling lib/<name>.test.ts if it exists, then tsc --noEmit (incremental)
#   any test file   refused (exit 2) when the edit adds a skip/xfail/only
# Quiet on success. On failure it prints the last 40 lines to stderr and exits 2,
# which feeds the failure back to the model (Tate, 2026-09-22: feedback, not a log).
# The repo root is resolved from the FILE, not from cwd, so edits inside a git
# worktree run against that worktree; python/ruff come from the main checkout's
# .venv (a worktree has none). Never fails when the file or the toolchain is missing.
set -u
IN=$(cat 2>/dev/null || true)
f=$(printf '%s' "$IN" | jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null || true)
[ -n "$f" ] && [ -f "$f" ] || exit 0

d=$(cd "$(dirname "$f")" 2>/dev/null && pwd -P) || exit 0
ROOT=""
while [ "$d" != "/" ]; do
  if [ -f "$d/pyproject.toml" ] && [ -e "$d/.git" ]; then ROOT="$d"; break; fi
  d=$(dirname "$d")
done
[ -n "$ROOT" ] || exit 0
COMMON=$(git -C "$ROOT" rev-parse --git-common-dir 2>/dev/null) || exit 0
case "$COMMON" in /*) ;; *) COMMON="$ROOT/$COMMON" ;; esac
MAIN=$(cd "$COMMON/.." && pwd -P)
PY="$MAIN/.venv/bin/python"; [ -x "$PY" ] || PY=python3
RUFF="$MAIN/.venv/bin/ruff"; [ -x "$RUFF" ] || RUFF=ruff
rel=${f#"$ROOT/"}

LOG=$(mktemp); trap 'rm -f "$LOG"' EXIT
fail() { echo "[post_edit] $1 failed for $rel:" >&2; tail -n 40 "$LOG" >&2; exit 2; }

# A skip, xfail or .only added to a test is Tate's call, never a way to green
# (2026-10-13); pre_bash.sh refuses the push for the same lines.
case "$rel" in
  tests/*.py|*.test.ts|*.test.tsx|*.spec.ts)
    if git -C "$ROOT" ls-files --error-unmatch "$rel" >/dev/null 2>&1; then
      diff=$(git -C "$ROOT" diff HEAD -- "$rel")
    else
      diff=$(printf '+++ b/%s\n' "$rel"; sed 's/^/+/' "$f")
    fi
    skips=$(printf '%s\n' "$diff" | "$PY" "$ROOT/scripts/hooks/classify_bash.py" --skips)
    if [ -n "$skips" ]; then
      echo "[post_edit] $rel adds a skip/xfail/only -- take it out, or ask Tate first:" >&2
      printf '%s\n' "$skips" >&2
      exit 2
    fi
    ;;
esac

case "$rel" in
  *.py)
    "$RUFF" check --fix -q "$f" >"$LOG" 2>&1 || fail "ruff"
    name=$(basename "$f" .py)
    tests=()
    case "$rel" in
      tests/test_*.py) tests=("$f") ;;
      *)
        [ -f "$ROOT/tests/test_${name}.py" ] && tests+=("$ROOT/tests/test_${name}.py")
        for t in "$ROOT"/tests/test_"${name}"_*.py; do [ -f "$t" ] && tests+=("$t"); done
        ;;
    esac
    if [ ${#tests[@]} -gt 0 ]; then
      (cd "$ROOT" && PYTHONPATH="$ROOT" "$PY" -m pytest -q -x -p no:cacheprovider "${tests[@]}") >"$LOG" 2>&1 \
        || fail "pytest (${#tests[@]} matching file(s))"
    fi
    ;;
  web/*.ts|web/*.tsx)
    if [ ! -d "$ROOT/web/node_modules" ]; then
      echo "[post_edit] $ROOT/web/node_modules is missing; vitest/tsc skipped" >&2
      exit 0
    fi
    wrel=${rel#web/}
    spec=""
    case "$wrel" in
      *.test.ts) spec="$wrel" ;;
      lib/*.ts) spec="${wrel%.ts}.test.ts" ;;
    esac
    if [ -n "$spec" ] && [ -f "$ROOT/web/$spec" ]; then
      (cd "$ROOT/web" && npx vitest run --reporter=dot "$spec") >"$LOG" 2>&1 || fail "vitest $spec"
    fi
    (cd "$ROOT/web" && npx tsc --noEmit) >"$LOG" 2>&1 || fail "tsc --noEmit"
    ;;
esac
exit 0
