#!/usr/bin/env bash
# Stop hook for Claude Code -- .claude/settings.json.
#
# Runs the FULL suites once when the model finishes a turn: pytest (not
# integration), vitest, tsc. A red suite blocks the first stop (exit 2 hands the
# failure tail back to the model); when Claude Code reports `stop_hook_active`
# the hook only reports and exits 0, so it can never block twice in a row.
# A fingerprint of HEAD + the working tree is stamped after a green run, so a
# turn that changed nothing costs under a second instead of ~2.5 minutes; the
# push gate (pre_bash.sh) reads the same stamp. Runs against the checkout the
# session is rooted in (cwd); python comes from the main checkout's .venv so a
# worktree session still works. Fingerprint and suite live in _suite.sh.
set -u
IN=$(cat 2>/dev/null || true)
active=$(printf '%s' "$IN" | jq -r '.stop_hook_active // false' 2>/dev/null || echo false)

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -f "$ROOT/pyproject.toml" ] || exit 0
# shellcheck source=_suite.sh
. "$(dirname "$0")/_suite.sh"

fp=$(bv_fingerprint)
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$fp" ]; then exit 0; fi

LOG=$(mktemp); trap 'rm -f "$LOG"' EXIT
if ! red=$(bv_suite "$LOG"); then
  echo "[on_stop] $red failed in $ROOT:" >&2
  tail -n 40 "$LOG" >&2
  if [ "$active" = "true" ]; then echo "[on_stop] already blocked once this turn; not blocking again" >&2; exit 0; fi
  exit 2
fi
printf '%s' "$fp" >"$STAMP"
exit 0
