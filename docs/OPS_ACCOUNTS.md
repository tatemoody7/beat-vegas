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

1. **GitHub → Settings → Billing and licensing.** (Only needed now to be able to return the repo to private.) On 2026-09-22 at ~17:29Z GitHub
   stopped starting jobs on this private repo: *"The job was not started because recent
   account payments have failed or your spending limit needs to be increased."* Every
   scheduled job — the card builds, daily grading, Sunday's refit, the close polls — is
   blocked until this is fixed. Either raise the Actions spending limit (a few dollars a
   month covers the overage: the 2026-09-16 audit measured ~2,830 billed minutes a month
   against the 2,000 free on a private repo, and review days like this one add hundreds
   more), fix the payment method, or **make the repository public** (public repos have
   unlimited Actions minutes; the site is already public read-only, and the three secrets
   are repository secrets, not files — but read `config.example.yaml` and `docs/` once
   with a stranger's eyes before flipping it).
2. **CFBD → Tier 2, $5/month, 30,000 calls** (collegefootballdata.com/api-tiers). The
   free Academic 3,000 is the quota that killed grading for two days on 2026-09-12 and
   the reason the `cfbd-cache` composite actions exist. At $5 they become optional.

## On 2026-10-06 (the Odds API renewal)

3. **The Odds API → the 20K plan, $30/month.** Live use is ~1,000-1,500 credits a month
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
