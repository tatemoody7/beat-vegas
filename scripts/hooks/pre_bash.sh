#!/usr/bin/env bash
# PreToolUse hook (Bash) for Claude Code -- .claude/settings.json. The hard block
# Tate chose on 2026-10-13 (the usage report: masked test runs and pushes on red):
#
#   git push        allowed only when the full suite is green on this exact tree:
#                   the on_stop stamp matches, or the suite runs now and passes
#   gh pr merge N   allowed only when `gh pr checks N` shows web, python and e2e,
#                   every check passing (the local tree is not that PR's tree)
#                   and only when the branch adds no skip/xfail/only to a test
#   masked tests    a test run piped into tail/head/grep without pipefail, or
#                   followed by `|| true`, is refused outright
#
# Exit 2 refuses the call and hands the reason to the model. There is no bypass.
# Every other command passes in ~50 ms (classify_bash.py decides). The checkout is
# the one the command runs in (.cwd); a command that cd's elsewhere is judged
# against the session's cwd.
set -u
IN=$(cat 2>/dev/null || true)
cmd=$(printf '%s' "$IN" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
[ -n "$cmd" ] || exit 0
cwd=$(printf '%s' "$IN" | jq -r '.cwd // empty' 2>/dev/null || true)
[ -n "$cwd" ] && [ -d "$cwd" ] || cwd=$PWD

HERE=$(cd "$(dirname "$0")" && pwd -P)
verdict=$(printf '%s' "$cmd" | python3 "$HERE/classify_bash.py" 2>/dev/null) || exit 0

case "$verdict" in
  none|"") exit 0 ;;
  masked*)
    echo "[pre_bash] refused, ${verdict#masked: }. Run the test command bare, or add 'set -o pipefail;' in front." >&2
    exit 2
    ;;
  merge*)
    pr=${verdict#merge}; pr=${pr# }
    # shellcheck disable=SC2086
    checks=$(cd "$cwd" && gh pr checks $pr --json name,bucket 2>&1) || true
    bad=$(printf '%s' "$checks" | python3 "$HERE/classify_bash.py" --checks)
    if [ -n "$bad" ]; then
      echo "[pre_bash] refused gh pr merge ${pr:-(current branch)}: $bad. Wait for every check to pass." >&2
      printf '%s\n' "$checks" | head -20 >&2
      exit 2
    fi
    exit 0
    ;;
  push)
    ROOT=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || exit 0
    [ -f "$ROOT/pyproject.toml" ] && [ -d "$ROOT/beatvegas" ] || exit 0
    # shellcheck source=_suite.sh
    . "$HERE/_suite.sh"
    base=$(git -C "$ROOT" merge-base origin/main HEAD 2>/dev/null || true)
    if [ -n "$base" ]; then
      skips=$(git -C "$ROOT" diff "$base" HEAD | python3 "$HERE/classify_bash.py" --skips)
      if [ -n "$skips" ]; then
        echo "[pre_bash] refused git push: this branch adds a skip/xfail/only to a test (Tate's call, not a way to green):" >&2
        printf '%s\n' "$skips" >&2
        exit 2
      fi
    fi
    fp=$(bv_fingerprint)
    if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$fp" ]; then exit 0; fi
    LOG=$(mktemp); trap 'rm -f "$LOG"' EXIT
    if ! red=$(bv_suite "$LOG"); then
      echo "[pre_bash] refused git push: $red is red in $ROOT:" >&2
      tail -n 40 "$LOG" >&2
      exit 2
    fi
    printf '%s' "$fp" >"$STAMP"
    exit 0
    ;;
esac
exit 0
