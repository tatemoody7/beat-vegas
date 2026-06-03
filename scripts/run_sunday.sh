#!/bin/bash
# Sunday LOCAL job — notify only. The capture + scoring (which writes Neon) now
# runs in GitHub Actions (.github/workflows/sunday.yml), because the Mac's usual
# network can't reach Neon. All this does is text the "board updated" heads-up,
# which must stay local (iMessage needs a macOS Messages session). Wired to
# launchd via deploy/com.beatvegas.sunday-notify.plist.
#
#   bash scripts/run_sunday.sh             # send the iMessage
#   bash scripts/run_sunday.sh --dry-run   # print it instead
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
# shellcheck disable=SC1091
source .venv/bin/activate

ARGS=()
[ "${1:-}" = "--dry-run" ] && ARGS+=(--dry-run)

LOG="$REPO/data/run_sunday.log"
echo "[$(date "+%Y-%m-%d %H:%M:%S")] sunday notify" >>"$LOG"
python scripts/notify_sunday.py "${ARGS[@]}" >>"$LOG" 2>&1
