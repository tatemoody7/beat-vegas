#!/usr/bin/env bash
# Stop hook for Claude Code -- .claude/settings.json.
#
# Runs the FULL suites once when the model finishes a turn: pytest (not
# integration), vitest, tsc. A red suite blocks the first stop (exit 2 hands the
# failure tail back to the model); when Claude Code reports `stop_hook_active`
# the hook only reports and exits 0, so it can never block twice in a row.
# A fingerprint of HEAD + the working tree is stamped after a green run, so a
# turn that changed nothing costs under a second instead of ~2.5 minutes.
# Runs against the checkout the session is rooted in (cwd); python comes from
# the main checkout's .venv so a worktree session still works.
set -u
IN=$(cat 2>/dev/null || true)
active=$(printf '%s' "$IN" | jq -r '.stop_hook_active // false' 2>/dev/null || echo false)

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -f "$ROOT/pyproject.toml" ] || exit 0
GITDIR=$(git -C "$ROOT" rev-parse --git-dir); case "$GITDIR" in /*) ;; *) GITDIR="$ROOT/$GITDIR" ;; esac
COMMON=$(git -C "$ROOT" rev-parse --git-common-dir); case "$COMMON" in /*) ;; *) COMMON="$ROOT/$COMMON" ;; esac
MAIN=$(cd "$COMMON/.." && pwd -P)
PY="$MAIN/.venv/bin/python"; [ -x "$PY" ] || PY=python3

fp=$( { git -C "$ROOT" rev-parse HEAD
        git -C "$ROOT" diff HEAD --
        git -C "$ROOT" ls-files --others --exclude-standard -z | (cd "$ROOT" && xargs -0 shasum 2>/dev/null)
      } | shasum | cut -d' ' -f1)
STAMP="$GITDIR/claude-stop-hook.stamp"
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$fp" ]; then exit 0; fi

LOG=$(mktemp); trap 'rm -f "$LOG"' EXIT
fail() {
  echo "[on_stop] $1 failed in $ROOT:" >&2
  tail -n 40 "$LOG" >&2
  if [ "$active" = "true" ]; then echo "[on_stop] already blocked once this turn; not blocking again" >&2; exit 0; fi
  exit 2
}

(cd "$ROOT" && PYTHONPATH="$ROOT" "$PY" -m pytest -q -x -m "not integration" -p no:cacheprovider) >"$LOG" 2>&1 || fail "pytest"
if [ -d "$ROOT/web/node_modules" ]; then
  (cd "$ROOT/web" && npx vitest run --reporter=dot) >"$LOG" 2>&1 || fail "vitest"
  (cd "$ROOT/web" && npx tsc --noEmit) >"$LOG" 2>&1 || fail "tsc --noEmit"
else
  echo "[on_stop] $ROOT/web/node_modules is missing; vitest/tsc skipped" >&2
fi
printf '%s' "$fp" >"$STAMP"
exit 0
