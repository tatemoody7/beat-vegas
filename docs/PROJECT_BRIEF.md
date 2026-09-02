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
  features, and a model scores each upcoming game **0–100** for under value.
- Tracks **line movement** and learns when 1H totals post.
- Grades **market vs model vs my own picks** with units + CLV, and a "Line Study"
  ranks which opening line numbers cash unders most.

## Honest findings so far (important — keep us grounded)
- No free source has *historical* 1H betting lines, so the backtest grades against
  a **proxy** (0.52 × full-game total). Directional, not proof.
- **Blanket** 1H unders ≈ breakeven (no edge). The edge, if any, is in **selection**.
- After backfilling history, **pace + weather** lifted the top-20% classifier picks to
  ~53.7% / +2.45% ROI; the gbm_v2 **gap ranking** now grades **54.0% / +3.0% ROI**
  (2018–25 OOS, proxy-graded). Rest/travel/returning-production were flat.
- Against a fair step proxy (0.4975 of the total, 0.5375 at 21+ spreads, FBS-only)
  the proxy-graded backtest shows **no confirmed edge**; earlier 54–59% reads were a
  flat-0.52 proxy artefact.
- Verdict: a genuinely useful *research* tool; **not** a proven money-maker. Real
  first-half lines collected this season are the only true test.
- **Update — "soft market" thesis refuted:** deeper research found no evidence that
  1H totals are systematically soft. So we stopped assuming it and instead **make our
  own number** — the **BV line** (an independent, calibrated 1H projection) — and rank
  games by the **gap** to the real Vegas line, validating with CLV. Live now. See
  `BV_LINE.md`. Since Phase 3 the gap is the **primary ranking**; the classifier's
  Under Score is a secondary lean. The 2026 landing page (`/`, "This Week") turns
  this into a plain-English BET / WATCH / PASS verdict per game under the rules in
  `BETTING_POLICY.md`; the ranked research board lives at `/board`.

## Architecture (plain English)
- The **engine** (Python) runs in **GitHub Actions** on a weekly rhythm: Sunday
  opener capture + pace/weather + scoring, Friday/Saturday first-half line sweeps,
  Monday grading, Tue/Fri news + injuries. Nothing runs on the Mac on a schedule;
  the campus network cannot reach the database anyway. Failed runs are reported by
  GitHub's email and re-checked by the Claude routines.
- Data lives in **Neon Postgres** (SQLite only for local dev/backtests).
- The product is the **Next.js web app on Vercel** (writable, password-protected,
  viewable from any device). Two Claude routines text Tate: the Friday bet card and
  the Sunday ops/recap.

## Status & roadmap
- **Done:** data pipeline, backtest, 0–100 scoring, line tracking, free
  enrichments, historical pace/weather backfill, private GitHub repo,
  Neon Postgres, GitHub Actions running the weekly engine.
- **Done:** Next.js app live on Vercel backed by Neon Postgres, password gate
  (the old Streamlit dashboard was removed).
- **Done:** the **BV line** + gap vs Vegas + gap-vs-CLV tracker (live). Now
  **market-blind** (no Vegas number feeds it, by rule), with an **80% prediction
  band** so gaps are read in units of noise (the line's σ ≈ 12 pts — most single-game
  gaps are noise, and the UI says so), a **near-kickoff line poll** so CLV is
  trustworthy, and a forward-only **QB-out flag**. See `BV_LINE.md`.
- **Always:** collect real 1H lines this season and re-measure the edge for real —
  the verdict is whether the biggest (noise-adjusted) BV-vs-Vegas gaps earn positive CLV.

## Good things to brainstorm in this Project
- Which *new free signals* might actually move the model (we've seen pace/weather
  help, situational/returning not). Ideas: specific coordinator/scheme changes,
  1Q-only splits, opponent-adjusted pace, garbage-time-free 1H efficiency.
- How to present "confidence" honestly when the edge is marginal or unconfirmed.
- ~~Bankroll/staking views~~ — decided 2026-09-01: flat units, see `BETTING_POLICY.md`
  (Kelly stays an advisory chip only).
- What "good" looks like for the live tracking after N weeks of real lines.
- Whether/when a paid 1H-line history feed would be worth it to validate the proxy.

## Pointers
- Repo: https://github.com/tatemoody7/beat-vegas (private)
- Full technical plan & history: the plan file (ADDENDUMs 1–5) in Claude Code.
- Session continuity for Claude Code: `CLAUDE.md` at the repo root.
