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
  set (5 tabs + records + login): `/` (This Week), `/board`, `/results`,
  `/research`, `/research/records`, `/glossary`, `/login`. The retired pages
  `/preview`, `/line-check`, `/line-study`, `/movement`, `/ledger`,
  `/weekly-review`, `/picks` are `redirect()` stubs — check each returns a 307
  to its new home (`/`, `/`, `/research`, `/board`, `/results`, `/results`,
  `/results`) and nothing else. If you cap the list, say so.
- `web/app/api/**/route.ts` for context: `POST /api/picks`,
  `DELETE /api/picks/[id]`, `GET /api/records?season=` (CSV), `GET /api/health`
  (public), `POST /api/login`, `POST /api/logout`. There are no GET data APIs
  any more — pages read the `lib/*` loaders directly, so data is checked via the
  pages plus the network panel.

## 2. Auth

`web/middleware.ts` locks the app when `APP_PASSWORD` is set: pages redirect to
`/login`, APIs return 401. Exempt: `/login`, `/api/login`, `/api/health`, static assets.

- Detect: load `/` on the live URL. If redirected to `/login`, the gate is **on**.
- Log in: read `APP_PASSWORD` from local `web/.env`. With the `Claude_in_Chrome`
  MCP, open `/login`, fill the password field, submit (or POST `/api/login`).
  Confirm the auth cookie is set and `/` now renders. Then sweep gated routes.
- If `APP_PASSWORD` is unset, routes are public — skip login.
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

| Page                | lib                                                                               | Cross-check against Neon                                                                                                                                                                                                                                                          |
| ------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/` (This Week)     | `lib/thisWeek.ts` → `board.ts`, `lineCheck.ts`, `preview.ts`, `picks.ts`          | card count = `predictions` rows for the default week (latest week with a game still to kick off); Hard Rock line/price per card matches the latest `odds_snapshots` row for `hardrockbet*` + `1H_total`; bankroll strip = `manual_picks` where `is_paper=false` and `market='1H'` |
| `/board`            | `lib/board.ts`, `lib/movement.ts`                                                 | row count for the selected week matches `predictions` × `games`; a card's movement row matches that game's `odds_snapshots` (`1H_total`) history                                                                                                                                  |
| `/results`          | `lib/ledger.ts`, `lib/weeklyReview.ts`, `lib/decision-quality.ts`, `lib/picks.ts` | Market/Model cards = `results` rows by `model_version` ('market', 'market_fg', `lib/model.ts::MODEL_VERSION`); You = graded `manual_picks` (real 1H vs paper); week-by-week + by-reason totals sum to the pick count                                                              |
| `/research`         | `lib/research.ts`, `lib/lineStudy.ts`, `lib/trends.ts`                            | games analyzed = FBS-vs-FBS `games` with `first_half_total` for the season; gap-vs-CLV n = `results` ('market') joined to `predictions` with CLV                                                                                                                                  |
| `/research/records` | `lib/records.ts` (`GET /api/records` CSV)                                         | row count = `games` for the season; CSV downloads and row count matches the grid                                                                                                                                                                                                  |
| `/glossary`         | static                                                                            | renders; copy carries no "54%" / "+3.0% ROI" / "52% of the total" claims                                                                                                                                                                                                          |

Tables (from `web/prisma/schema.prisma`): `games`, `predictions`, `results`,
`manual_picks` (incl. the tracking columns `verdict_at_pick`, `reason`,
`gap_at_pick`, `ev_at_pick`, `hr_line_at_pick` — the pages degrade to
"untagged" if the migration has not run), `bv_adjustments`, `odds_snapshots`,
`model_runs`, `teams`, `team_tempo`, `team_week_features`, `venues`, `weather`.
Not in the schema but read defensively: `game_previews`, `factor_scores`,
`factor_ledger` (absent table → empty state, never a 500).

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
