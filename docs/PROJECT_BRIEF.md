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
- Tracks **line movement**, learns when 1H totals post, and **alerts via iMessage**.
- Grades **market vs model vs my own picks** with units + CLV, and a "Line Study"
  ranks which opening line numbers cash unders most.

## Honest findings so far (important — keep us grounded)
- No free source has *historical* 1H betting lines, so the backtest grades against
  a **proxy** (0.52 × full-game total). Directional, not proof.
- **Blanket** 1H unders ≈ breakeven (no edge). The edge, if any, is in **selection**.
- After backfilling history, **pace + weather** lifted the top-20% model picks to
  ~**53.7% / +2.45% ROI** (2018–25). Rest/travel/returning-production were flat.
- The signal is **decaying** recently (≈57–59% in 2018–21 → ≈50% in 2023–25).
- Verdict: a genuinely useful *research* tool; **not** a proven money-maker. Real
  first-half lines collected this season are the only true test.

## Architecture (plain English)
- A **local engine** on my Mac scrapes data, scores games, sends alerts, and runs
  itself daily.
- Data lives in a database (local SQLite now; moving to **Neon Postgres** in the cloud).
- The dashboard is moving from a local Streamlit app to a **Next.js web app on
  Vercel** (writable, password-protected, viewable from any device).

## Status & roadmap
- **Done:** data pipeline, backtest, 0–100 scoring, line tracking + iMessage alerts,
  Streamlit dashboard, weekly auto-run, free enrichments, historical pace/weather
  backfill, private GitHub repo, DB layer made Postgres-ready.
- **Now (Phase B–D):** rebuild the dashboard as a Next.js app on Vercel backed by
  Neon Postgres, with a simple password gate; point the engine at Neon.
- **Always:** collect real 1H lines this season and re-measure the edge for real.

## Good things to brainstorm in this Project
- Which *new free signals* might actually move the model (we've seen pace/weather
  help, situational/returning not). Ideas: specific coordinator/scheme changes,
  1Q-only splits, opponent-adjusted pace, garbage-time-free 1H efficiency.
- How to present "confidence" honestly when the edge is marginal/decaying.
- Bankroll/staking views (Kelly fractions, unit sizing) — research-only.
- What "good" looks like for the live tracking after N weeks of real lines.
- Whether/when a paid 1H-line history feed would be worth it to validate the proxy.

## Pointers
- Repo: https://github.com/tatemoody7/beat-vegas (private)
- Full technical plan & history: the plan file (ADDENDUMs 1–5) in Claude Code.
- Session continuity for Claude Code: `CLAUDE.md` at the repo root.
