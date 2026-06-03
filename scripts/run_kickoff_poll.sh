#!/bin/bash
# Light near-kickoff poll: capture a fresh 1H line for games starting soon so the
# closing line (and therefore CLV) is trustworthy. Wired to launchd every ~30 min
# during the season (see deploy/com.beatvegas.kickoff.plist).
#
# Only runs while the Mac is awake/online — a known limitation of the local
# engine. Offseason / no near-kickoff games => exits cheaply (no odds calls).
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
# shellcheck disable=SC1091
source .venv/bin/activate

# Same DB the daily chain + Vercel app use (DATABASE_URL -> Neon; else SQLite).
set -a
# shellcheck disable=SC1091
[ -f "$REPO/.env" ] && . "$REPO/.env"
set +a

LOG="$REPO/data/kickoff_poll.log"
echo "[$(date "+%Y-%m-%d %H:%M:%S")] kickoff poll" >>"$LOG"
python scripts/poll_kickoff_lines.py "$@" >>"$LOG" 2>&1
