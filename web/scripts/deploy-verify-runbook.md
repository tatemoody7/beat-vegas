# Beat Vegas — Deploy-and-Verify Runbook

Canonical, project-specific checklist for the autonomous deploy-and-verify sweep.
The scheduled poller (and any manual run) follows this exactly. It parameterizes
the global **`deploy-and-verify`** skill for beat-vegas — invoke that skill for
the gate logic; this file supplies the project specifics. **Do not duplicate the
skill's logic here.**

## Identity

- Vercel project: `beat-vegas` — projectId `prj_1GLKfBYu0fVMrbBfI2wRPC9ske5Y`,
  teamId `team_5tX9HE0NhPKHJErSm8o6QUBk`.
- Repo / working dir: `/Users/tatemoody/Desktop/Beat Vegas` (Vercel root is `web/`).
- Stack: Next.js 16 App Router, Prisma → Neon Postgres (`DATABASE_URL`).
- State file: `.deploy-verify/last-verified.json` (gitignored).

## Local verification (before the deploy, from a worktree)

- `bash web/scripts/dev-worktree.sh start` runs THIS checkout's dev server on
  its own port (3100-3199, written to `web/.next-dev.port`) with a clean
  `.next`; it refuses a Neon `DATABASE_URL` without `--allow-neon`, and proves
  via `ps` that the server was launched from the worktree. `stop` when done.
  The Browser pane's preview always serves the main checkout, so never verify a
  worktree through it.
- `cd web && node scripts/shots.mjs --base http://localhost:<port> --label
<before|after>` captures every route at 1440 and 390; `--diff before after`
  compares the metrics (height, overflow, header, tap targets) and
  `--pixdiff before after` compares the pixels, writing
  `shots/<after>/diff_<page>_<width>.png` only where something changed.

## 0. Should we even run?

1. `list_deployments` (projectId/teamId above) → newest **production** deploy with
   `state: READY` and `target: production`. Capture its `uid` and commit `sha`.
2. Read `.deploy-verify/last-verified.json`. If `deploymentUid` equals the newest
   READY uid → **log "no new deploy" and exit.** Otherwise continue.
3. `get_deployment_build_logs` + `get_runtime_logs` for that uid — note any
   errors/warnings even if pages render (they go in the report).

## 1. Discover routes (re-discover every run — never hardcode)

- Browser pages: list `web/app/**/page.tsx`; map dir → URL path
  (`web/app/results/page.tsx` → `/results`, `web/app/page.tsx` → `/`). Current
  set (3 tabs + a game page + records + login): `/` (Board), `/results`,
  `/proof`, `/proof/records`, `/game/[id]`, `/login`. The eleven retired pages
  are `next.config.ts` redirects with `permanent: true` (`movedRoutes`), so
  each returns a **308** — not the 307 a `redirect()` stub sent — to its new
  home: `/board`, `/preview`, `/line-check`, `/movement` → `/`; `/ledger`,
  `/picks`, `/weekly-review` → `/results`; `/line-study`, `/research` →
  `/proof`; `/research/records` → `/proof/records`; `/glossary` →
  `/proof#glossary`. The query string is forwarded. Check the status code and
  the `location` header and nothing else. If you cap the list, say so.
- `web/app/api/**/route.ts` for context: `POST /api/picks`,
  `PATCH`/`DELETE /api/picks/[id]`, `GET /api/records?season=` (CSV),
  `GET /api/health` (public), `POST /api/login`, `POST /api/logout`,
  `GET /api/cron/[job]` (Vercel cron, `CRON_SECRET`). There are no GET data APIs
  any more — pages read the `lib/*` loaders directly, so data is checked via the
  pages plus the network panel.

## 2. Auth

Since 2026-09-16 every page and every GET is public; `APP_PASSWORD` guards
WRITES only (`lib/gate.ts::gateDecision` in `web/middleware.ts`, plus
`requireAuth` inside every pick route): an unsigned `POST /api/picks` or
`PATCH`/`DELETE /api/picks/[id]` returns 401, a form POST elsewhere redirects
to `/login`. Vercel without `APP_PASSWORD` set 503s everything.

- Detect: load `/` on the live URL — it must render signed out, with **Unlock**
  in the header. If it redirects to `/login`, something is wrong (report it).
- Log in only to check the signed-in state: read `APP_PASSWORD` from local
  `web/.env`. With the `Claude_in_Chrome` MCP, open `/login`, fill the password
  field, submit (or POST `/api/login`). Confirm the cookie is set, the header
  shows **Lock**, and a game page shows the log button instead of the unlock
  link. `POST /api/login` is throttled (10 per IP per 15 min).
- If Vercel **deployment protection** (not the app gate) returns 401/403, mint
  access with `get_access_to_vercel_url` and retry.

## 3. Per-route sweep (live production URL)

For every discovered page, with `Claude_in_Chrome`: `navigate` → `read_console_messages`
→ `read_network_requests` → `screenshot`. Per route check:

- **Renders** — no uncaught console errors; no failed requests (no 401/403/404/500
  in the network panel).
- **Copy intact** — no concatenation/template artifacts: `2026yet`, `undefined`,
  `NaN`, `null`, `[object Object]`, `$NaN`, empty headings, doubled tokens.
- **Contrast/visual** — no same-color-on-same-color text, no invisible text, no
  white-blob logo, no mid-animation frozen/faded state. Screenshot is the evidence.

## 4. DB correctness (cross-check live numbers vs Neon)

All data is season-scoped (`?season=YYYY`); use the **active season** the board
shows. Each data page renders what its API returns; each API wraps a Prisma lib.
At run time, read the lib to get the exact query, then verify the displayed
number against Neon via the **`postgres`** MCP (HTTPS — per memory). Map:

| Page             | lib                                                                                                                                                                   | Cross-check against Neon                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/` (Board)      | `lib/homeBoard.ts` → `board.ts`, `lineCheck.ts`, `preview.ts`, `picks.ts`, `movement.ts`; `lib/card.ts`, `lib/answerBar.ts`, `lib/boardHealth.ts`, `lib/rulePause.ts` | row count = `predictions` rows for the default week (`lib/week.ts::defaultWeek`, the latest week with a game still to kick off) inside `boardUniverse`; Hard Rock line/price per row matches the latest `odds_snapshots` row for `hardrockbet` + `1H_total`; "This week's bar" sentence = the latest `cards.payload.slate`; the answer bar's live bets = `manual_picks` where `is_paper=false` and `market='1H'`; no OpsBanner / missed-build / stale-results banner unless `/api/health` says so |
| `/game/[id]`     | `lib/homeBoard.ts::getHomeGame` (same chain), `lib/session.ts`                                                                                                        | the three decision tiles (Hard Rock's number, our number, gap) match the board row; the per-book lines list matches that game's latest `odds_snapshots` (`1H_total`) per book; signed out shows "Unlock to log a pick", signed in shows the log button                                                                                                                                                                                                                                            |
| `/results`       | `lib/ledger.ts`, `lib/weeklyReview.ts`, `lib/decision-quality.ts`, `lib/picks.ts`, `lib/homeBoard.ts` (bankroll)                                                      | Scoreboard band / record table = `results` rows by `model_version` ('market', 'market_fg', `lib/model.ts::MODEL_VERSION`); "Your decisions" = graded REAL `manual_picks` (paper in its own labelled section); breakdown toggles (by week / reason / blocker) each sum to the pick count; line value shown with the favourable sign (+ means the market came toward us)                                                                                                                            |
| `/proof`         | `lib/postmortem.ts`, `lib/proof.ts`, `lib/lineStudy.ts`, `lib/glossary.ts`, `lib/records.ts`                                                                          | headline = `postmortem_buckets` (`hist_2023_25`/`fbs_only`/`real`/`cap5`) with its Wilson interval; the gap ladder draws BARS with games and units under each; **no green or red number anywhere below the "estimated line" heading**; the folds (`<details>`) open                                                                                                                                                                                                                               |
| `/proof/records` | `lib/records.ts` (`GET /api/records` CSV)                                                                                                                             | opens on the latest week with a graded outcome (`latestGradedWeek`); the week's row count = `games` rows for that season-week (LEFT JOIN `predictions` on `MODEL_VERSION`, so a game with no model row still lists); CSV downloads and its row count matches the season's `games` count                                                                                                                                                                                                           |

Tables (from `web/prisma/schema.prisma`): `games`, `predictions`, `results`,
`manual_picks` (incl. the tracking columns `verdict_at_pick`, `reason`,
`gap_at_pick`, `ev_at_pick`, `hr_line_at_pick` — the pages degrade to
"untagged" if the migration has not run), `bv_adjustments`, `odds_snapshots`,
`model_runs`, `teams`, `team_tempo`, `team_week_features`, `venues`, `weather`.
Not in the schema but read defensively (raw SQL): `cards`, `app_settings`,
`game_records`, `game_previews`, `postmortem_runs`/`postmortem_buckets`,
`factor_scores`, `factor_ledger` (absent table → empty state, never a 500).

Flag mismatches, empty-when-should-have-data, stale (last `model_runs` timestamp
far behind today), and wrong-season data.

## 5. Report (always)

Emit the pass/fail table from the `deploy-and-verify` skill:

| Route | Renders | Console/Network | Copy | Contrast | DB data | Verdict |
| ----- | ------- | --------------- | ---- | -------- | ------- | ------- |

Overall verdict = **HEALTHY only if every route PASSes.** Any FAIL → deploy is
NOT healthy.

## 6. On failure — propose, don't push

Fix autonomy is **propose-then-ask**:

1. Diagnose root cause (use the `systematic-debugging` skill if non-obvious).
2. Write the fix on a new branch `verify-fix/<short-sha>` — **do not** commit to
   `main`, push, redeploy, or roll back.
3. Notify with the report + the proposed diff and **STOP for approval.** Mention
   the rollback option (promote the previous READY deploy via `list_deployments`)
   as an alternative.

## 7. Persist state

Write `.deploy-verify/last-verified.json`:
`{ "deploymentUid": "...", "sha": "...", "verifiedAt": "<ISO>", "verdict": "HEALTHY|FAIL", "failingRoutes": [...] }`
so the next poll skips an already-verified deploy.
