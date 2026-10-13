# Shared by on_stop.sh and pre_bash.sh -- sourced, never run. Needs $ROOT (a
# checkout or worktree with pyproject.toml). Defines GITDIR, MAIN, PY, STAMP and:
#   bv_fingerprint   HEAD + the working tree, the key a green run is stamped under
#   bv_suite LOG     full pytest (not integration), vitest, tsc into LOG; on red it
#                    prints the failing suite's name and returns 1
GITDIR=$(git -C "$ROOT" rev-parse --git-dir); case "$GITDIR" in /*) ;; *) GITDIR="$ROOT/$GITDIR" ;; esac
COMMON=$(git -C "$ROOT" rev-parse --git-common-dir); case "$COMMON" in /*) ;; *) COMMON="$ROOT/$COMMON" ;; esac
MAIN=$(cd "$COMMON/.." && pwd -P)
PY="$MAIN/.venv/bin/python"; [ -x "$PY" ] || PY=python3
STAMP="$GITDIR/claude-stop-hook.stamp"

bv_fingerprint() {
  { git -C "$ROOT" rev-parse HEAD
    git -C "$ROOT" diff HEAD --
    git -C "$ROOT" ls-files --others --exclude-standard -z | (cd "$ROOT" && xargs -0 shasum 2>/dev/null)
  } | shasum | cut -d' ' -f1
}

bv_suite() {
  local log=$1
  (cd "$ROOT" && PYTHONPATH="$ROOT" "$PY" -m pytest -q -x -m "not integration" -p no:cacheprovider) >"$log" 2>&1 || { echo pytest; return 1; }
  if [ -d "$ROOT/web/node_modules" ]; then
    (cd "$ROOT/web" && npx vitest run --reporter=dot) >"$log" 2>&1 || { echo vitest; return 1; }
    (cd "$ROOT/web" && npx tsc --noEmit) >"$log" 2>&1 || { echo "tsc --noEmit"; return 1; }
  else
    echo "[hooks] $ROOT/web/node_modules is missing; vitest/tsc skipped (CI's web job still gates the merge)" >&2
  fi
  return 0
}
