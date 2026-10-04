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

2. **CFBD → Tier 2, $5/month, 30,000 calls** (collegefootballdata.com/api-tiers). The
   free Academic 3,000 is the quota that killed grading for two days on 2026-09-12 and
   the reason the `cfbd-cache` composite actions exist. At $5 they become optional.
   **Decision 2026-10-04 (Tate): buy it now.** The week-6 shadow engines read SP+ special
   teams and strength of schedule from the same `/ratings/sp` call already made, so the
   tier buys headroom and the later coach / drive / box-score pulls, not new calls today.

## On 2026-10-06 (the Odds API renewal)

3. **The Odds API → the 20K plan, $30/month.** Dashboard read 2026-10-04
   (dash.the-odds-api.com/api-subscriptions): the 100K plan started Sep 6, **next invoice
   Oct 6**, 326 of 100,000 credits used this period; credits reset on the 1st of each month
   (the Oct 1 counter reset was that, not a bill). Downgrade before Oct 6 through "Manage
   Subscription" (a Stripe page). If the only path is "New Subscription", the 20K plan gets a
   NEW key: update the `ODDS_API_KEY` repository secret and local `config.yaml` before the
   next card build, and cancel the 100K one. Live use is ~1,000-1,500 credits a month
   against the 100K ($59) plan. There is **no tier between the free 500 and 20K** (checked
   2026-09-22: Starter 500 free, 20K $30, 100K $59, 5M $119, 15M $249), so 20K is the
   smallest paid plan. The 2023-25 history purchase was the only reason 100K was ever
   needed.

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
