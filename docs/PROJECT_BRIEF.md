# Beat Vegas — Project Brief (Claude Project knowledge)

> Upload this file (plus `README.md`) as **knowledge** in a claude.ai Project.
> Use the Project to brainstorm features, strategy, and priorities; do the actual
> building in Claude Code against the repo (https://github.com/tatemoody7/beat-vegas).
> This is a research / decision-support tool — it never places bets.

## The idea
I have a multi-year hunch that **college-football first-half (1H) unders** are a
soft market. Beat Vegas is a system to test that honestly and, if there's an edge,
surface the best 1H-under opportunities each week — while I stay the decision-maker.

## What it does
- Pulls **free** data: CollegeFootballData (games, play-by-play, advanced stats,
  SP+, returning production, venues), TeamRankings (tempo), Open-Meteo (weather),
  The Odds API (live 1H totals).
- Derives **actual 1H points** for every game, builds **leak-free** pre-kickoff
  features, and a **market-blind** model projects each game's 1H total; the board
  ranks games by the **gap** between that number and Hard Rock's line.
- Tracks **line movement** and learns when 1H totals post.
- Grades **market vs model vs my own picks** with units + CLV, and a "Line Study"
  ranks which opening line numbers cash unders most.

## Honest findings so far (important — keep us grounded)
- No free source has *historical* 1H betting lines, so the backtest grades against
  a **proxy** (a step share of the full-game total, `data/multiplier.json`). Directional, not proof.
- **Blanket** 1H unders ≈ breakeven (no edge). The edge, if any, is in **selection**.
- After backfilling history, **pace** lifted the top-20% classifier picks (the
  53.7% / +2.45% read was graded at the flat 0.52 proxy and is retired with it); the
  gbm_v2 **gap ranking** replaced the classifier as the ranking rule. The "weather
  helped" read was measured on mis-timed values and is withdrawn (`WEATHER.md`).
  Rest/travel/returning-production were flat.
- Against a fair step proxy (0.4975 of the total, 0.5375 at 21+ spreads, FBS-only)
  the proxy-graded backtest shows **no confirmed edge**; earlier 54–59% reads were a
  flat-0.52 proxy artefact.
- Verdict: a genuinely useful *research* tool; **not** a proven money-maker. Real
  first-half lines collected this season are the only true test.
- **Update — "soft market" thesis refuted:** deeper research found no evidence that
  1H totals are systematically soft. So we stopped assuming it and instead **make our
  own number** — the **BV line** (an independent, calibrated 1H projection) — and rank
  games by the **gap** to the real Vegas line, validating with CLV. Live now. See
  `BV_LINE.md`. Since Phase 3 the gap is the **only ranking**; the classifier's
  Under Score gates nothing (the 2026-09-06 post-mortem found it does not separate
  outcomes) and is slated for removal after week 3. The Board (`/`) turns the gap
  into a plain-English Bet / Watch / Pass word per game under the rules in
  `BETTING_POLICY.md`; the game page (`/game/[id]`) carries the decision and logs
  the pick.

## Architecture (plain English)
- The **engine** (Python) runs in **GitHub Actions** on a weekly rhythm: Sunday
  opener capture + pace/weather + scoring, Friday/Saturday first-half line sweeps,
  Monday grading, Tue/Fri news + injuries. Nothing runs on the Mac on a schedule;
  the campus network cannot reach the database anyway. Failed runs are reported by
  GitHub's email, and the board carries stale-results and missed-build banners — the
  only failure signal since every scheduled routine was retired on 2026-09-13.
- Data lives in **Neon Postgres** (SQLite only for local dev/backtests).
- The product is the **Next.js web app on Vercel** (writable, password-protected,
  viewable from any device). Nothing texts Tate; he looks at the board when he
  chooses (best single look: Friday after ~5:30pm ET, when ~78% of Hard Rock's 1H
  lines are up and the Friday card has built).

## Status & roadmap (as of 2026-09-15, week 3 of the 2026 season)
- **Done:** data pipeline, backtest, line tracking, free enrichments, private GitHub
  repo, Neon Postgres, GitHub Actions running the engine, a Vercel cron as the primary
  trigger (GitHub cron is the backup).
- **Done:** Next.js app live on Vercel backed by Neon Postgres, password gate. Three
  tabs — Board / Results / Track record — plus a page per game. The board shows a rank
  and Bet / Watch / Pass with the gap bar; there is **no** 0–100 score, confidence meter
  or prediction band on the page (cut 2026-09-10: "if it isn't obvious I don't want it").
- **Done:** the **BV line** + gap vs Hard Rock (live). Market-blind by rule; gates are
  in **points** (≥ 1.75, from the validated top-20%-by-gap rule), never σ; a real-money
  bet needs Hard Rock's own line and a live price, enforced server-side and failing
  closed. A forward-only **QB-out flag** (Rotowire) blocks paper picks.
- **Done (Sep 2026):** every historical weather row was wrong (UTC kickoff indexed into
  a local-time series) and was repaired into `weather_obs` with decision-safe leads;
  activation is **deferred** on blast radius. The hypothesis registry
  (`docs/HYPOTHESES.md`) lists every test with its pre-registered criterion; the
  1,902-game 2023-25 real-close set is **spent** for exploration. A pre-registered
  **stopping rule** (SPRT, two clocks) runs on the paper ledger from week 3, with a
  real-money pause switch. The **share engine** — a market-conditioned challenger that
  predicts the first-half split — is spec'd and registered (`H-SHARE`), not built; a
  pass of its gate earns a prospective paper arm, not promotion.
- **Always:** the verdict is whether the rule's paper picks earn positive line value
  against Hard Rock's close and profit at actual prices — hit rate stops nothing.

## Good things to brainstorm in this Project
- Which *new free signals* might move the model. Pace helped; situational/returning did
  not; decision-time weather × offensive style is **null after the price control** (R09).
  Still open and unregistered: coordinator/scheme changes, 1Q-only splits,
  opponent-adjusted pace, garbage-time-free 1H efficiency, travel **against market
  error**, QB news vs cluster injuries — see the unregistered list in
  `docs/EXTERNAL_REVIEW.md`. Any new test gets a row in `docs/HYPOTHESES.md` first.
- ~~How to present "confidence"~~ — decided 2026-09-10: nothing on the page but rank,
  Bet / Watch / Pass and the gap bar. A chart that needs a paragraph has failed.
- ~~Bankroll/staking views~~ — decided 2026-09-01: flat units, see `BETTING_POLICY.md`
  (Kelly stays an advisory chip only).
- ~~What "good" looks like for the live tracking~~ — answered by the stopping rule:
  profit per unit at actual prices and favourable line value vs Hard Rock's strict
  close, SPRT at 5% total false-stop; see `STOPPING_RULE.md`.
- ~~Whether/when a paid 1H-line history feed would be worth it~~ — bought 2026-09-06/08
  (Odds API history, 2023-25 first-half closes). It validated the fair proxy and is now
  the spent exploratory set.
- When the share engine's gate report exists: what its prospective paper arm's stopping
  clock should be, and how a challenger and a champion share one board.

## Pointers
- Repo: https://github.com/tatemoody7/beat-vegas (private)
- Every test and its result: `docs/HYPOTHESES.md` (the index) and the study docs it points at.
- Session continuity for Claude Code: `CLAUDE.md` at the repo root.
