# Beat Vegas — Glossary & Key Numbers

## Core terms
- **1H under** — a bet that the combined first-half points stay *under* the
  sportsbook's first-half total. The project's whole focus.
- **Breakeven (52.4%)** — at standard −110 juice you must win >52.4% of bets to
  profit. The line every result is measured against.
- **Proxy 1H line** — because no *free* source has historical first-half betting
  lines, we estimate one as **0.52 × the full-game total**. Backtests use it, so
  they're *directional, not proof*.
- **Under Score (0–100)** — the model's lean per game. 50 = breakeven-neutral;
  higher = stronger under lean. It's a rescaled probability, not a guarantee.
- **CLV (closing line value)** — did the number move in your favor after you bet?
  Positive CLV over many bets is the best sign of a real edge.
- **Leak-free features** — every model input uses only info known *before* kickoff
  (season-to-date stats are lagged). No peeking at the result.
- **Walk-forward backtest** — train on past seasons, test on the next, repeat.
  Honest out-of-sample evaluation.
- **BV line** — our *own* independent projected 1H total, from a regressor over the
  full feature set (pace/efficiency/weather/era). "Make our own number first."
  See `BV_LINE.md`.
- **Gap** — `Vegas 1H line − BV line` (under direction). Positive = Vegas above our
  number = a candidate under. Big gaps can be model *blind spots*, not edges.
- **Calibration (of the line)** — unbiasedness: `mean(actual − BV) ≈ 0` overall and
  per segment (era/tempo/dome). A line biased ~1.5 pt low would falsely scream
  "under" on every game. Achieved by a global bias correction, audited per segment.
- **2023 era flag** — feature marking the post-2023 running-clock regime (~8 fewer
  plays/game); pre-2023 is a different scoring distribution.

## Data sources (all free)
- **CollegeFootballData (CFBD)** — games, play-by-play (→ actual 1H points),
  advanced stats, SP+, returning production, venues, full-game lines.
- **TeamRankings** — tempo (seconds/play, plays/game), as-of-date historical.
- **Open-Meteo** — weather (temp/wind/precip) by venue, archive + forecast.
- **The Odds API** — live first-half totals (`totals_h1`), free tier (500/mo).
- **ESPN hidden API** — news/injuries for card context (display only, unofficial).

## What moved the model (and what didn't)
- **Helped:** pace (tempo) + weather — lifted top-20% model picks to
  ~53.7% under / +2.45% ROI (2018–25, proxy-graded).
- **Flat:** rest/travel/time-zone/kickoff (situational) and returning production —
  kept as on-card *context*, not model inputs.
- **Caveat:** edge is small and **decaying** — ~57–59% (2018–21) → ~50% (2023–25),
  consistent with defenses adapting to tempo.

## Key facts / decisions
- Free data only. Research/decision-support only — never auto-bets.
- DB: SQLite locally, **Neon Postgres** in the cloud (`DATABASE_URL`).
- Dashboard: Streamlit (local) → **Next.js on Vercel** (the product), password-gated.
- Engine runs on the Mac (scrape → score → grade → iMessage alerts), daily via launchd.
- Repo (private): https://github.com/tatemoody7/beat-vegas
- The real test of the edge = **real first-half lines collected this season**,
  graded vs the model and my own picks.
