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
- **BV line** — our *own* independent projected 1H total, from a **market-blind**
  regressor (pace/efficiency/weather/era — but no Vegas number, by rule). "Make our
  own number first." See `BV_LINE.md`.
- **Gap** — `Vegas 1H line − BV line` (under direction). Positive = Vegas above our
  number = a candidate under. Big gaps can be model *blind spots*, not edges.
- **Prediction band / gap-in-σ** — the BV line is noisy (σ ≈ 12 pts), so it ships an
  80% band (`bv_lo`–`bv_hi`) and reports each gap in σ (`bv_gap_z`). σ is the
  noise of a single game's outcome — no gap ever reaches 1σ — so it is context
  ("any one game is near a coin flip"), **not** the bet gate.
- **Bettable gap** — the validated selection rule in points: the top 20% of a
  season's games by gap (≈ **≥ 1.75 pts**; ≥ 3.0 pts ≈ top 10%). This is what the
  This Week page calls **BET** when a live line and a fair-or-better Hard Rock
  price are also present. See `BETTING_POLICY.md`.
- **BET / WATCH / PASS** — the This Week page's verdict per game. BET = bettable
  gap + live 1H line + Hard Rock price not worse than market. WATCH = a smaller
  lean, a good price alone ("price edge only"), or a bettable gap against an
  *estimated* line. PASS = nothing to act on.
- **Paper pick** — a pick logged with stake 0 (`manual_picks.is_paper`): graded
  for record and CLV but kept out of the real-money ledger.
- **Unit** — one standard bet. 2026: **$10 flat**, every bet, on a $100 roll (see
  `BETTING_POLICY.md` for the acknowledged risk).
- **Prediction market / exchange** — a CFTC-regulated venue (Kalshi, Polymarket,
  FanDuel Predicts, Novig, ProphetX) where you trade event contracts against
  other people instead of a bookmaker, so prices carry ~no vig. Legal in
  Florida; no first-half totals, so we never bet there — we use their prices
  (Odds API region `us_ex`, Sunday capture) to sharpen the market fair price.
- **Market-blind (rule)** — the BV regressor is forbidden from training on any Vegas
  number (full-game total, 1H line). Enforced by a guard test; keeps the gap from
  being circular. (The 0–100 classifier is allowed to be market-relative — different job.)
- **Calibration (of the line)** — unbiasedness: `mean(actual − BV) ≈ 0` overall and
  per segment (era/tempo/dome). Achieved by a global bias correction, audited per
  segment. Measured OOF residual ≈ −0.18, all segments within ±0.5.
- **2023 era flag** — feature marking the post-2023 running-clock regime (~8 fewer
  plays/game); pre-2023 is a different scoring distribution.
- **QB-out flag** — a forward-only, unofficial "QB listed Out/Doubtful" banner from
  Rotowire's college injury report (which aggregates the SEC/ACC/Big Ten
  availability reports). Display only — never a model feature (no historical injury
  data exists to train on). ESPN publishes no college injuries, so ESPN is news-only.
- **Closing-line freshness** — CLV is only trustworthy if the closing line was
  captured near kickoff. A near-kickoff poll keeps it fresh; grading stores when the
  closing snapshot landed.

## Data sources (all free)
- **CollegeFootballData (CFBD)** — games, play-by-play (→ actual 1H points),
  advanced stats, SP+, returning production, venues, full-game lines.
- **TeamRankings** — tempo (seconds/play, plays/game), as-of-date historical.
- **Open-Meteo** — weather (temp/wind/precip) by venue, archive + forecast.
- **The Odds API** — live first-half totals (`totals_h1`), free tier (500/mo).
- **ESPN hidden API** — team news for card context (display only, unofficial; use the
  `site.web.api.espn.com` host — `site.api.espn.com` is Akamai-blocked).
- **Rotowire injury report** — the college injury/availability table behind
  rotowire.com's injury-report page (unofficial JSON). The only free source that
  actually carries CFB injuries. Display only.

## What moved the model (and what didn't)
- **Helped:** pace (tempo) + weather — the only inputs that moved 1H-total
  prediction error. Proxy-graded selection stats (the old 54% / +3% ROI reads) were
  a flat-0.52 artefact and are no longer quoted as an edge; against the fair step
  proxy the backtest shows no confirmed edge. Only real-line CLV can.
- **Flat:** rest/travel/time-zone/kickoff (situational) and returning production —
  kept as on-card *context*, not model inputs.
- **Caveat:** the edge is small and unconfirmed; the system measures it (CLV on
  real Hard Rock lines), it does not promise it.

## Key facts / decisions
- Free data only. Research/decision-support only — never auto-bets.
- DB: SQLite locally, **Neon Postgres** in the cloud (`DATABASE_URL`).
- Product: the **Next.js app on Vercel** (Neon-backed, password-gated).
- Engine: the Python scripts run in **GitHub Actions** (`.github/workflows/`) — Sunday
  capture + score, Friday/Saturday 1H sweeps with Pushover alerts, Monday grading,
  Tue/Fri research preview. Two Claude routines (Friday card, Sunday ops/recap) text Tate.
- Repo (private): https://github.com/tatemoody7/beat-vegas
- The real test of the edge = **real first-half lines collected this season**,
  graded vs the model and my own picks.
