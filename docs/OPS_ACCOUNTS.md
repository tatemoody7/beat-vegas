# Account-side checklist (things only Tate can click)

Written 2026-09-22 from the system review. Each item names the exact plan and the
date; the board cannot see any of these until the change is made.

## Status 2026-09-22 evening

- **The repository was made PUBLIC at ~18:20Z** (Tate), which removes the Actions minute cap
  and unblocked every job. The billing fix below is still worth finishing so the repo can go
  private again if wanted: GitHub's Payment information form timed out on every save (unicorn
  page), so no card could be added; a **Billing support ticket** is filed from help.github.com
  (replies to boomtatermac@gmail.com; "View tickets" on help.github.com).

## Do now

1. **GitHub billing — RESOLVED 2026-10-04.** A card is on file, the repo is private again
   (made private 14:36Z; it had been public since 2026-09-22 with 0 forks and 0 stars), and the
   Actions budget is **$10/month, stop usage at the cap, alerts at 75/90/100%**
   (github.com/settings/billing/budgets). The $0 budget with stop-usage on was what halted
   every job on 2026-09-22; a private repo gets 2,000 free minutes against ~2,830 measured, so
   the overage (~$7) bills to the card inside the budget. Check the budget page in the last
   week of each month.

2. **CFBD — Patreon Tier 3 ($10/month, 75,000 calls) since 2026-10-05.** Tate bought Tier
   3 (Patreon account boomtatermac@gmail.com); CFBD applies the tier by email match, so the key
   issued to that address on 2026-06-02 became Tier 3 automatically (`/info`: patronLevel 3,
   all feature flags true). That key is now in local `config.yaml` and the `CFBD_API_KEY`
   repository secret (14:11Z); the FGCU Academic key (3,000/mo) is retired from the system.
   Everything the review found useful is Tier 1 data (`/wepa/team/season`, weather,
   scoreboard); dropping to Tier 1 ($1) at the Nov 6 renewal is Tate's call
   (`docs/CFBD_TIER3_REVIEW_2026-10-05.md`). Optional: link Discord in Patreon
   (patreon.com/settings/apps) for the patron channel.

3. **GitHub dispatch token — confirm its scope (added 2026-10-07).** `GITHUB_DISPATCH_TOKEN`
   (Vercel env) now also backs the game page's **Refresh price** (`POST /api/price-refresh` →
   `lines_watch.yml` `market=1h_game`, 1 Odds API credit). It should be a **fine-grained** token
   with **Actions: read and write** on **tatemoody7/beat-vegas only**, nothing else
   (github.com/settings/personal-access-tokens). If it is a classic token or covers more repos,
   replace it with one of that shape and paste it into Vercel → Settings → Environment
   Variables → Production, then redeploy.

## Done 2026-10-05

3. **The Odds API — on the 20K plan ($30/month) since 2026-10-05.** Tate cancelled the 100K
   ($59) subscription and created the 20K one; each subscription has its own key, so the
   `ODDS_API_KEY` repository secret was re-set (13:35Z) and local `config.yaml` updated the
   same hour. Verified: the free `/v4/sports` call on the new key reads 20,000 remaining, 0
   used; a zero-credit `lines_watch.yml` `market=1h_close` dispatch (run 37318117401) proved
   the runner's copy. Live use is well under 2,000 credits a month (326 for Oct 1-4, which
   covered three card builds and the 14 Saturday close ticks), so the plan carries ~10x.
   There is **no tier between the free 500 and 20K** (re-read 2026-10-05: Starter 500 free,
   20K $30, 100K $59, 5M $119, 15M $249, hard cap, no overage). The 100K plan existed for the
   one-time 2023-25 history purchase (~44.9K credits, Sep 6-8). Full stack review:
   `docs/DATA_STACK_REVIEW_2026-10-05.md`.

## What the board now shows about these

`beatvegas/ops.py` writes `cfbd_calls_remaining`, `odds_credits_remaining`,
`last_close_capture_at` and `last_grade_completed_at` into `app_settings`; the board's
ops banner and `/api/health` read them (`web/lib/boardHealth.ts::opsWarnings`). The cron
route adds one row per job, `last_dispatch_<job>`: the last time a Vercel tick acted inside
its window (dispatched, or found the build already there). A job whose window closed without
one raises a banner line — the build may still have happened, on GitHub's backup cron or by
hand, but the primary trigger did not fire; check the Vercel cron list, `CRON_SECRET` and
`GITHUB_DISPATCH_TOKEN`. GitHub's own billing state is the one thing none of them can see: if
every gauge stops updating at once, that is what it looks like.

Since 2026-09-28 the Saturday close poll is also Vercel-dispatched (`lines-close`, one entry
per UTC hour 15Z–04Z, 14 entries, every tick dispatching): GitHub's own 30-minute crons fired 3 of 18
Saturday slots in week 4, and only about a third of Hard-Rock-priced games had any 1H snapshot
inside the registered 2-hour close window. `last_dispatch_lines-close` should advance hourly on
a Saturday.
