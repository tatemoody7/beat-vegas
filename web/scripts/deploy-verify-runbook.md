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
  (`web/app/picks/page.tsx` → `/picks`, `web/app/page.tsx` → `/`). Current set:
  `/`, `/ledger`, `/line-check`, `/line-study`, `/login`, `/movement`, `/picks`,
  `/preview`, `/research`, `/weekly-review`. If you cap the list, say so.
- Note `web/app/api/**/route.ts` for context (board, ledger, line-study,
  movement, picks, records, research, login, logout). API routes are checked
  indirectly via the pages that call them + the network panel.

## 2. Auth

`web/middleware.ts` locks the app when `APP_PASSWORD` is set: pages redirect to
`/login`, APIs return 401. Exempt: `/login`, `/api/login`, static assets.

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

| Page                         | API / lib                        | Cross-check against Neon                                                    |
| ---------------------------- | -------------------------------- | --------------------------------------------------------------------------- |
| `/` (board)                  | `lib/board.ts` (`/api/board`)    | board row count + active season match `games`/`predictions` for that season |
| `/picks`                     | `lib/picks.ts` (`/api/picks`)    | pick count + running W-L-P record match `manual_picks` joined to `results`  |
| `/ledger`                    | `lib/ledger.ts` (`/api/ledger`)  | running balance/units match sum over `manual_picks`/`bv_adjustments`        |
| `/research`, `/movement`     | `/api/research`, `/api/movement` | row counts match `odds_snapshots`/`predictions` for the season              |
| `/line-study`, `/line-check` | `lib/*`                          | spot-check a displayed line/edge vs `odds_snapshots`/`predictions`          |

Tables (from `web/prisma/schema.prisma`): `games`, `predictions`, `results`,
`manual_picks`, `bv_adjustments`, `odds_snapshots`, `model_runs`, `teams`,
`team_tempo`, `team_week_features`, `venues`, `weather`.

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
