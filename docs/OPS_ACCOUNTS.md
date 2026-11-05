# Account-side checklist and shutdown runbook (things only Tate can click)

Rewritten 2026-10-18 for the final-2026 plan (`~/.claude/plans/beat-vegas-final-fluffy-hollerith.md`,
B1 decisions D1-D14, B8 the shutdown table, C1/C12 the Odds API cycle and archive queue; final-2026
PR-22). Paid operation ends after **Sat 2026-11-28** (week 13; last kickoff 2026-11-29 04:00 UTC,
`protocol.SEASON_LAST_KICKOFF`); the final read is **Mon 2026-11-30**. The board cannot see any
account-side change until it is made, so each row says who acts and what has to be true first.

## What stop, cancel and retain mean here

- **Stop** a job: the workflow or cron is switched off. It spends nothing further but keeps the
  subscription behind it; nothing is refunded.
- **Cancel a renewal**: the provider is told not to bill again. Access continues until the paid period
  ends (The Odds API says so in its cancellation guide, with no refund of the unused part; re-read the
  wording on the billing page before clicking). Cancelling early therefore saves nothing and can only
  cut access short if the provider's wording turns out different.
- **Retain** paid access: we keep paying because a job still needs it. Every retained plan has a date
  on which it stops being retained.
- **Downgrade**: move to the provider's free tier; only after what the paid tier held is exported.
- **Claude never cancels, downgrades or buys anything. Only Tate does, on the provider's own page.**

## The runbook (all dates 2026; times UTC unless marked)

| Date | Action | Kind | Precondition | Who |
|---|---|---|---|---|
| Sun 10-18 | Real money ended: `rule_paused` on (14:59Z, `app_settings_log` 674); the 30 graded tickets are a frozen ledger. The Mac task `bv-saturday-board-report` deleted (D7); no scheduled text remains | stop | Tate's decision D2/D7 | Tate decided; Claude executed |
| Sun 10-18 | **CFBD Patreon membership cancelled** (Tate, on Patreon). Tier 3 (75,000 calls) stays until **Nov 5**, then the key drops to the free tier: **1,000 calls a month**. This replaces the earlier plan to move to Tier 1 ($1) on Nov 6. **Unverified (2026-11-02):** the key's counter reset to 75,000 at 2026-11-01 (`app_settings_log` cfbd_calls_remaining 72,998 -> 74,999); Patreon bills on the 1st, so Tate checks Patreon for a Nov 1 charge before trusting the Nov 5 drop | cancel renewal | None | Tate |
| Nov 1-4 | Archive queue, first window: items 1-3 of the final queue (reference plan C12), run automatically in the last 4 days of the cycle, never taking the balance under the **1,500** floor. **What happened (2026-11-02):** the cycle had already reset at 2026-11-01 00:00Z (the row below), so 8,285 credits expired unspent on 10-31 and the window opened against the new cycle; the 11-01 and 11-02 runs paid 270 credits for rows Neon refused (`research_snapshots.source` was VARCHAR(8), the value `historical` 10 chars; fixed 2026-11-02, the refused waves are bought again in the final window) | retain | Balance above the floor | automatic |
| Nov 5 onward | CFBD free tier: measured use is ~600-900 calls a month and a hand season reload costs ~500. The daily digest warns under 500 remaining (`cfbd_calls_remaining`, PR-06). **No hand season reload (`backfill.py`, `history_load.yml`, `backfill_1h.yml`) may run after Nov 5 without reading the balance first** | retain (free) | `/info` on the key shows the remaining calls | Claude checks before any run |
| ~~Nov 5 (±1)~~ **Dec 1, 00:00Z** | The Odds API 20K plan ($30) resets for the **last** cycle (credits do not roll over). **Measured 2026-11-02:** the quota resets on the **1st of the month at 00:00Z** (`app_settings_log` odds_credits_remaining 8,285 -> 20,000 at 2026-11-01 00:46Z, the only rise above 1,000 since July); Nov 5 was a guess written on 10-18. The controller setting `odds_cycle_reset_at` moves to `2026-12-01T00:00:00` by the `archive.yml` dispatch `set-reset` (input `reset_at`), which writes `app_settings` + `app_settings_log` from the runner. The quota reset and the **billing** renewal may be different dates (the plan changed on Oct 6): Tate reads both on the dashboard before the cancellation row below | retain paid access | Tate confirms the date on the dashboard; the dispatch runs after that | Tate confirms; Claude dispatches |
| Sat 11-28 | Last capture. The Saturday close ticks end at 04:00 UTC Nov 29 | stop | Week 13 priced | automatic |
| Sun 11-29 | Last grade. The last Sunday job is skipped (no week 14 capture); `sunday.yml` crons are disabled by PR | stop | All week-13 finals in | automatic; Claude disables the crons |
| Mon 11-30 | Final read (`season_over=true`, implied from 12Z), late reads (H6, H-JUDGE, H-VENUE-1, H-ARM-EVP), the final-report generation, and the export | stop | **Gate for every row below:** the week-13 judge readings are present on the graded picks; `data/evidence/2026-w13` is committed; the export (PR-23) is verified by a **restore into the local sandbox** (`scripts/pg_sim.py`) with row counts matching Neon | automatic + Claude |
| ~~Nov 30 - Dec 4~~ **Fri Nov 27 - Mon Nov 30** (the last 4 days before the Dec 1 reset) | Archive queue, final window (every item, including the waves the Nov 1-2 runs paid for and lost; ~15,000 credits available; whatever is unbought is listed in the final report). The window overlaps the last capture (Sat 11-28) and the final read (Mon 11-30): the daily 07Z run spends from the live balance after the recurring need, so the cards and closes are never short. The Vercel cron entries are removed by PR-24 only after this window drains, `grade` last | retain | Floor 1,500 held; export verified | automatic; Claude removes the crons |
| Before the renewal (the billing date on the dashboard; the quota resets Dec 1) | **Tate cancels The Odds API subscription** ("Manage subscription" on the plan). Access runs to the end of the paid period; no refund | cancel renewal | The archive queue has drained (credits left unspent are lost at the reset) **and the Vercel crons are already removed (PR-24)**: a dead key would turn `lines_watch` and `card` red every day | Tate |
| After the export is verified (Dec 1-5) | **Tate moves Neon Launch to the free plan** | downgrade | The export restores cleanly (see Mon 11-30). Size and restore window checked first (below). The database is shared with six `swfl_*` fishing tables, which the downgrade also affects | Tate |
| Ongoing | Vercel Hobby ($0) and the public GitHub repository ($0) stay; the site is read-only and stays up as the public record | retain | None | none |

**CFBD note.** B8 of the plan still reads "Tier 1 on Nov 6, cancel before Dec 6"; the 10-18
cancellation replaced both rows. The CFBD key has no Tier 3-only data in use (only `/games/weather`
is tier-gated and nothing live uses it), so the drop costs the live system nothing; it only removes
headroom for hand reloads.

**Neon check before the downgrade** (read 2026-10-18 from Neon's changelog and plans pages; re-read
on the billing page before clicking, the pages disagreed with each other): the free plan allows
**1 GB per project** since the 2026-10-02 changelog (older pages still say 0.5 GB); the database is
**131 MB** (PostgreSQL 16.15), so either cap fits. The free plan's point-in-time restore window is
**about 6 hours** against up to 7 days on Launch, so after the downgrade the committed export is the
only long-lived copy of the season. Do not downgrade until the restore test has passed.

**Other standing accounts.** `GITHUB_DISPATCH_TOKEN` (Vercel env, fine-grained, Actions read and
write on `tatemoody7/beat-vegas` only) triggers every Vercel-dispatched job; it stops mattering when
PR-24 empties the crons, after which Tate may revoke it. It no longer backs anything on the site: the
owner's Refresh price poll left with the log path (PR-12+13, 2026-10-18). `APP_PASSWORD` (Vercel env) is
read by nothing since the same PR — the login, the cookie and every write route are gone — so Tate can
delete it from Vercel once that deploy is live; `CRON_SECRET` is the one app secret that stays. The GitHub Actions budget is moot while the
repository is public (public since 2026-10-16: no minute cap). Open-Meteo, TeamRankings, Rotowire and
ESPN are free and unmetered. A Kalshi account is opened only for the Mon 11-30 H-VENUE-1 read, if that read needs one.

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

From 2026-11-05 `cfbd_calls_remaining` counts down from the free tier's 1,000 calls a month, not Tier 3's 75,000,
so the board's warning under 200 is the last line of defence; the daily digest (PR-06) warns under 500.
