#!/bin/bash
# Unattended daily chain: refresh data -> enrich -> capture lines + alert ->
# score -> grade. Wired to launchd (see deploy/com.beatvegas.daily.plist).
#
#   bash scripts/run_daily.sh             # live (real DB, real alerts)
#   bash scripts/run_daily.sh --dry-run   # demo DB, alerts printed not sent
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
# shellcheck disable=SC1091
source .venv/bin/activate

# Load gitignored secrets (DATABASE_URL -> Neon) so the live chain writes to the
# same DB the Vercel app reads. Absent -> falls back to local SQLite.
set -a
# shellcheck disable=SC1091
[ -f "$REPO/.env" ] && . "$REPO/.env"
set +a

DRY=0
POLL_ARGS=()
if [ "${1:-}" = "--dry-run" ]; then
  DRY=1
  unset DATABASE_URL            # dry-run stays on the local demo DB, never Neon
  export BEATVEGAS_DB=data/demo.db
  POLL_ARGS+=(--dry-run-alerts)
fi

if [ -n "${DATABASE_URL:-}" ]; then DBTARGET="Neon Postgres"; else DBTARGET="sqlite:${BEATVEGAS_DB:-data/beatvegas.db}"; fi

LOG="$REPO/data/run_daily.log"
ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }
step() {  # step "label" cmd...
  local label="$1"; shift
  if "$@" >>"$LOG" 2>&1; then log "$label ok"; else log "$label FAILED"; fi
}

read -r SEASON WEEK < <(python -c "from beatvegas.season import active; s,w=active(); print(s, w if w else '')")
if [ "$DRY" = "1" ]; then SEASON=2025; WEEK=8; fi
log "run_daily start season=$SEASON week=${WEEK:-none} dry=$DRY db=$DBTARGET"

if [ "$DRY" != "1" ]; then
  step "backfill" python scripts/backfill.py --season "$SEASON"
fi
if [ -n "${WEEK:-}" ]; then
  step "tempo"   python scripts/enrich_tempo.py --season "$SEASON" --week "$WEEK" --date "$(date +%F)"
  step "weather" python scripts/enrich_weather.py --season "$SEASON" --week "$WEEK"
fi
step "poll" python scripts/poll_lines.py "${POLL_ARGS[@]}"
if [ -n "${WEEK:-}" ]; then
  step "score" python scripts/weekly_update.py --season "$SEASON" --week "$WEEK"
fi
step "grade"      python scripts/grade.py --season "$SEASON"
step "pick-grade" python scripts/pick.py grade --season "$SEASON"
log "run_daily done"
