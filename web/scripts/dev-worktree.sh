#!/usr/bin/env bash
# Run THIS checkout's Next dev server on its own port.
#
#   bash web/scripts/dev-worktree.sh start [--port N] [--allow-neon] [--link-modules]
#   bash web/scripts/dev-worktree.sh stop | status | url
#
# Why this exists: the Browser pane's `preview_start` is pinned to the MAIN
# checkout (it reads .claude/launch.json from the directory the session started
# in and runs with that cwd), so a worktree that "looks fine in the preview" is
# showing unmodified main. Verified three times on 2026-09-09 and again on
# 2026-09-13; see memory `preview-pane-pinned-to-main-checkout`. The fix is a
# server that belongs to the worktree: its own port, its own .next cache, and a
# `ps` check proving the process was launched from this tree.
#
# State files (all gitignored, all under web/):
#   .next-dev.pid   pid of the `next dev` parent process
#   .next-dev.port  the port it listens on
#   .next-dev.log   its stdout/stderr
#
# Exit codes: 0 ok · 1 usage / not running / generic failure · 2 could not start
# or the running server is not this worktree's · 3 refused a Neon DATABASE_URL.
#
# Deliberately `set -u` and not `set -e`: every failure path below is handled
# explicitly with its own message, and -e would abort inside the polling loops.
set -u

usage() {
  echo "usage: $0 start [--port N] [--allow-neon] [--link-modules] | stop | status | url" >&2
  exit 1
}

CMD="${1:-}"
[ -n "$CMD" ] || usage
shift

PORT_OPT=""
ALLOW_NEON=0
LINK_MODULES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --port)
      [ $# -ge 2 ] || usage
      PORT_OPT="$2"
      shift 2
      ;;
    --port=*)
      PORT_OPT="${1#--port=}"
      shift
      ;;
    --allow-neon)
      ALLOW_NEON=1
      shift
      ;;
    --link-modules)
      LINK_MODULES=1
      shift
      ;;
    *)
      echo "unknown option: $1" >&2
      usage
      ;;
  esac
done

# --- where are we -----------------------------------------------------------
# WT is this checkout (main or a worktree). MAIN is the first `worktree ` line
# of the porcelain listing, which git always prints as the main working tree.
WT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "not inside a git checkout" >&2
  exit 1
}
MAIN="$(git -C "$WT" worktree list --porcelain | awk '/^worktree /{print substr($0, 10); exit}')"
[ -n "$MAIN" ] || MAIN="$WT"
WEB="$WT/web"
[ -d "$WEB" ] || {
  echo "no web/ directory under $WT" >&2
  exit 1
}
PID_FILE="$WEB/.next-dev.pid"
PORT_FILE="$WEB/.next-dev.port"
LOG_FILE="$WEB/.next-dev.log"

alive() {
  # $1 = pid. kill -0 tells us the process exists without touching it.
  [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null
}

read_state() {
  # Sets RUN_PID / RUN_PORT when the state files describe a live server, else
  # clears them (and removes stale files so the next start does not trip on
  # a pid that was recycled by some unrelated process).
  RUN_PID=""
  RUN_PORT=""
  if [ -f "$PID_FILE" ] && [ -f "$PORT_FILE" ]; then
    local pid port
    pid="$(cat "$PID_FILE" 2>/dev/null)"
    port="$(cat "$PORT_FILE" 2>/dev/null)"
    if alive "$pid" && ps -o args= -p "$pid" 2>/dev/null | grep -q "next dev"; then
      RUN_PID="$pid"
      RUN_PORT="$port"
    else
      rm -f "$PID_FILE" "$PORT_FILE"
    fi
  fi
}

port_free() {
  # lsof exits 1 when nothing listens; that is the "free" answer we want.
  ! lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

print_followups() {
  local base="http://localhost:$1" branch
  branch="$(git -C "$WT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo worktree)"
  echo "BASE_URL=$base"
  echo "next:"
  echo "  (cd \"$WEB\" && node scripts/shots.mjs --base $base --label $branch)"
  echo "  (cd \"$WEB\" && E2E_BASE_URL=$base npm run e2e)"
}

# --- commands ---------------------------------------------------------------
case "$CMD" in
  status)
    read_state
    if [ -n "$RUN_PID" ]; then
      echo "running: pid $RUN_PID port $RUN_PORT ($WT)"
      exit 0
    fi
    echo "not running ($WT)"
    exit 1
    ;;

  url)
    read_state
    if [ -n "$RUN_PID" ]; then
      echo "http://localhost:$RUN_PORT"
      exit 0
    fi
    echo "not running ($WT) -- start it with: $0 start" >&2
    exit 1
    ;;

  stop)
    read_state
    stopped=0
    if [ -n "$RUN_PID" ]; then
      kill "$RUN_PID" 2>/dev/null && stopped=1
      # Next's dev parent forwards SIGTERM to its next-server child; give it a
      # moment before falling back to a broader match on the port.
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        alive "$RUN_PID" || break
        sleep 0.5
      done
    fi
    port="${RUN_PORT:-$(cat "$PORT_FILE" 2>/dev/null)}"
    if [ -n "${port:-}" ]; then
      pkill -f "next dev -p $port" 2>/dev/null && stopped=1
      # The next-server child does not carry the port in its args; whatever
      # still listens on OUR port after the parent went is ours to kill.
      listeners="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null)"
      if [ -n "$listeners" ]; then
        # shellcheck disable=SC2086
        kill $listeners 2>/dev/null && stopped=1
      fi
    fi
    rm -f "$PID_FILE" "$PORT_FILE"
    if [ "$stopped" = 1 ]; then
      echo "stopped dev server on port ${port:-?} ($WT)"
      exit 0
    fi
    echo "nothing to stop ($WT)"
    exit 0
    ;;

  start) ;;

  *)
    usage
    ;;
esac

# --- start --------------------------------------------------------------------
read_state
if [ -n "$RUN_PID" ]; then
  if [ -n "$PORT_OPT" ] && [ "$PORT_OPT" != "$RUN_PORT" ]; then
    echo "already running on port $RUN_PORT (pid $RUN_PID); --port $PORT_OPT ignored. Run '$0 stop' first to move it." >&2
  fi
  echo "already running: pid $RUN_PID"
  print_followups "$RUN_PORT"
  exit 0
fi

# Port: an explicit --port wins, else the first free one in 3100-3199. Port 3000
# is never chosen: the Browser pane's preview owns it (main checkout, autoPort),
# and from the main checkout this script must still stand apart from that.
if [ -n "$PORT_OPT" ]; then
  case "$PORT_OPT" in
    '' | *[!0-9]*)
      echo "--port must be a number, got '$PORT_OPT'" >&2
      exit 1
      ;;
  esac
  if [ "$PORT_OPT" = 3000 ] && [ "$WT" = "$MAIN" ]; then
    echo "port 3000 belongs to the Browser pane's preview of the main checkout; pick another (default range 3100-3199)" >&2
    exit 1
  fi
  if ! port_free "$PORT_OPT"; then
    echo "port $PORT_OPT is already in use:" >&2
    lsof -nP -iTCP:"$PORT_OPT" -sTCP:LISTEN >&2
    exit 1
  fi
  PORT="$PORT_OPT"
else
  PORT=""
  p=3100
  while [ "$p" -le 3199 ]; do
    if port_free "$p"; then
      PORT="$p"
      break
    fi
    p=$((p + 1))
  done
  if [ -z "$PORT" ]; then
    echo "no free port in 3100-3199; pass --port N" >&2
    exit 1
  fi
fi

# web/.env is gitignored, so a fresh worktree has none. Copy main's rather than
# invent one -- but then LOOK at what was copied: main's .env points at Neon
# most of the time, and a dev server pointed at Neon is what burned the Free
# plan's 5 GB/month of egress on 2026-09-16 (every board render is ~0.5 MB;
# `next dev` + a screenshot pass re-renders on every save).
if [ ! -f "$WEB/.env" ]; then
  if [ -f "$MAIN/web/.env" ]; then
    cp "$MAIN/web/.env" "$WEB/.env"
    echo "copied web/.env from $MAIN (gitignored; never commit it)"
  else
    echo "no web/.env here and none in $MAIN/web/.env to copy; see web/.env.example" >&2
    exit 1
  fi
fi
# Every ACTIVE DATABASE_URL line counts (dotenv lets a later line win, and a
# stray duplicate is exactly how a Neon URL sneaks back in).
active_urls="$(grep -E '^[[:space:]]*(export[[:space:]]+)?DATABASE_URL=' "$WEB/.env" 2>/dev/null || true)"
if printf '%s\n' "$active_urls" | grep -q 'neon\.tech' && [ "$ALLOW_NEON" != 1 ]; then
  cat >&2 <<EOF
REFUSED: $WEB/.env points DATABASE_URL at Neon (neon.tech).

A local dev server against the production database is what exhausted Neon's
5 GB/month egress on 2026-09-16 -- each board render is ~0.5 MB of metered
reads and \`next dev\` re-renders on every save. Use a local database instead:

  cd web && npm run e2e:db        # synthetic week in a local Postgres (Playwright lane)
  python scripts/simulate_week.py # replay a real past week into ~/.cache/beatvegas/pg_sim

then point web/.env at the URL it prints (port 54329) and start again. If you
really mean to read production from this worktree, pass --allow-neon.
EOF
  exit 3
fi

# node_modules: each worktree gets its own install. Two reasons, in order of
# how hard they bite:
#   1. Turbopack (Next 16's dev bundler) REFUSES a node_modules symlink whose
#      target lies outside the project root -- "Symlink [project]/node_modules
#      is invalid, it points out of the filesystem root" -- and `next dev`
#      exits before serving a page. Measured 2026-09-23 with a link to
#      main's tree. So a shared tree does not merely risk something; it does
#      not start.
#   2. Even where it did start: `postinstall` runs `prisma generate`, which
#      writes the generated client INTO node_modules, so a schema.prisma edit
#      in one tree regenerates the OTHER tree's client.
# `--link-modules` is kept as a named flag so the temptation has an answer
# instead of a silent mystery: it explains why and exits 2.
if [ "$LINK_MODULES" = 1 ]; then
  cat >&2 <<EOF
--link-modules is not supported: Turbopack rejects a node_modules symlink that
points outside the project root ("Symlink [project]/node_modules is invalid, it
points out of the filesystem root") and next dev exits before serving a page.
Run without the flag; the script does an npm ci in this worktree (~40 s cached).
EOF
  exit 2
fi
if [ -L "$WEB/node_modules" ]; then
  target="$(readlink "$WEB/node_modules")"
  case "$target" in
    "$WT"/*) ;;
    *)
      cat >&2 <<EOF
$WEB/node_modules is a symlink to $target, outside this worktree.
Turbopack refuses it ("Symlink [project]/node_modules is invalid, it points out
of the filesystem root") and next dev exits before serving a page. Replace it
with a real install:

  rm "$WEB/node_modules" && (cd "$WEB" && npm ci)

(lint and vitest are happy with the link; only next dev is not.)
EOF
      exit 2
      ;;
  esac
fi
if [ ! -e "$WEB/node_modules" ]; then
  echo "installing node_modules in $WEB (npm ci; ~40 s cached) ..."
  if ! (cd "$WEB" && npm ci --no-audit --no-fund >"$WEB/.npm-ci.log" 2>&1); then
    echo "npm ci failed; last lines of $WEB/.npm-ci.log:" >&2
    tail -n 20 "$WEB/.npm-ci.log" >&2
    exit 2
  fi
  rm -f "$WEB/.npm-ci.log"
fi
NEXT_BIN="$WEB/node_modules/.bin/next"
[ -x "$NEXT_BIN" ] || {
  echo "$NEXT_BIN is missing or not executable; is node_modules complete?" >&2
  exit 2
}

# A .next left by another branch is a Turbopack cache keyed on paths that may
# no longer exist; it produces stale chunks and phantom 500s. Always clean.
rm -rf "$WEB/.next"

# Launch the bin by its ABSOLUTE path inside this worktree, not via `npx`: the
# parent process then reads `node $WT/web/node_modules/.bin/next dev -p PORT`
# in `ps`, which is the evidence the check below needs. (Next spawns the actual
# server as a `next-server` child; the parent forwards signals to it.)
: >"$LOG_FILE"
(
  cd "$WEB" || exit 2
  nohup "$NEXT_BIN" dev -p "$PORT" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
)
PID="$(cat "$PID_FILE")"
echo "$PORT" >"$PORT_FILE"
echo "starting next dev on port $PORT (pid $PID, log $LOG_FILE) ..."

# /login is a client component with no database read, so it answers as soon as
# the server is up and compiled -- it proves the server, not the data.
ready=0
for _ in $(seq 1 90); do
  if ! alive "$PID"; then
    echo "dev server exited before it was ready; last lines of $LOG_FILE:" >&2
    tail -n 30 "$LOG_FILE" >&2
    rm -f "$PID_FILE" "$PORT_FILE"
    exit 2
  fi
  if curl -sf -o /dev/null "http://localhost:$PORT/login"; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" != 1 ]; then
  echo "dev server did not answer http://localhost:$PORT/login within 90 s; last lines of $LOG_FILE:" >&2
  tail -n 30 "$LOG_FILE" >&2
  echo "it is still running (pid $PID); '$0 stop' to kill it" >&2
  exit 2
fi

# The check that would have caught 2026-09-09: the process serving this port
# must have been launched from THIS tree.
args="$(ps -o args= -p "$PID" 2>/dev/null)"
case "$args" in
  *"$WT"*)
    echo "ok: pid $PID serves $WT"
    echo "    $args"
    ;;
  *)
    echo "WRONG TREE: pid $PID args do not mention $WT:" >&2
    echo "    $args" >&2
    kill "$PID" 2>/dev/null
    rm -f "$PID_FILE" "$PORT_FILE"
    exit 2
    ;;
esac

print_followups "$PORT"
exit 0
