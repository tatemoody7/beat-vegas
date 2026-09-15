# Beat Vegas — Glossary & Key Numbers

## Core terms
- **1H under** — a bet that the combined first-half points stay *under* the
  sportsbook's first-half total. The project's whole focus.
- **Breakeven (52.4%)** — at standard −110 juice you must win >52.4% of bets to
  profit. The line every result is measured against.
- **Historical 1H proxy** — because no *free* source has historical first-half
  betting lines, we synthesise one where a real close is missing. The current
  proxy is the **spread-conditioned step** in `data/multiplier.json`: **0.4975**
  of the full-game total below a 21-point spread, **0.5375** at 21+. The old flat
  **0.52** is retired, and is worth naming as a retired source of a false
  positive — it sits ~1 pt above fair, which flattered every under and produced
  the 54% / +3% reads the project used to quote. Proxy-graded results are
  **diagnostic only**, never evidence of profitability. Always split on
  `line_real` before concluding anything.
- **Under Score (0–100)** — a legacy display index, **not a probability and not
  EV**. It must never be converted into an expected value or a stake. The
  classifier behind it is uncalibrated, the 2026-09-06 post-mortem found it
  carries no information about the outcome, and it no longer gates anything: the
  board ranks on `bv_gap` and the 0–100 colour is a deterministic transform of
  the gap. "50 = breakeven" was also plain wrong — breakeven at −110 is
  **52.38%**, so a 50 on a 0–100 display scale cannot mean it. A genuinely
  calibrated `p_under` does not exist yet; when it does it gets its own name.
- **CLV (closing line value)** — did the market move in your favour after you
  bet? Stored as `closing − bet` in points, so for an under **negative is the
  good direction** (`decision-quality.ts::favourable`, pinned by
  `clvDirection.test.ts`). Consistently favourable CLV is **strong evidence that
  we are seeing information before the market fully prices it — an early
  diagnostic, not proof of profitability**; prospective results and calibration
  still decide. Note the points channel is only half of it: many 1H totals never
  move in points at all (48 of 71 in week 2) while the PRICE moves, which
  `clv_prob` captures and the record cards do not yet show.
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
- **Gap selection threshold** — the frozen 2026 policy threshold `bv_gap ≥ 1.75`,
  approximately the historical top 20% of games by model–market disagreement
  (≥ 3.0 pts ≈ top 10%). It decides which disagreements get **tracked**; it is
  **not a proven profitable threshold** — the profitability that first motivated
  it did not survive replacing the flat proxy with the fair step proxy. Frozen on
  purpose and parity-tested (`tests/test_gate_parity.py`): moving it as 2026
  results arrive would quietly turn a prospective test back into an adaptive
  backtest. A change becomes a new versioned policy and a new cohort. See
  `BETTING_POLICY.md`.
- **BET / WATCH / PASS** — the This Week page's verdict per game. BET = bettable
  gap + live 1H line + Hard Rock price not worse than market. WATCH = a smaller
  lean, a good price alone ("price edge only"), or a bettable gap against an
  *estimated* line. PASS = nothing to act on.
- **Paper pick** — a pick logged at a flat 1 unit (`manual_picks.is_paper`,
  `picks.py::PAPER_STAKE`) so its record reads in the same units as the real
  one. Graded for record and CLV, but kept out of the bankroll.
- **Unit** — one standard bet. 2026: **$10 flat**, every bet, on a $100 roll (see
  `BETTING_POLICY.md` for the acknowledged risk).
- **Prediction market / exchange** — a CFTC-regulated venue (Kalshi, Polymarket,
  FanDuel Predicts, Novig, ProphetX) where you trade event contracts against
  other people instead of taking a fixed sportsbook quote. They avoid the
  conventional sportsbook overround, but **"no vig" is wrong**: bid/ask spreads,
  taker fees, maker rebates, liquidity and price impact are all real transaction
  costs. Availability and the state/federal legal position are **changing
  rapidly** — verify before relying on any of it; we do not execute there. Their
  prices reach us only through the Sunday **full-game** capture (Odds API region
  `us_ex`); `us_ex` returns **zero** first-half bookmakers, so they do not touch
  the 1H fair price we actually bet against.
- **Market-blind (rule)** — the BV regressor is forbidden from training on any Vegas
  number (full-game total, 1H line). Enforced by a guard test; keeps the gap from
  being circular. (The 0–100 classifier is allowed to be market-relative — different job.)
- **BV mean calibration** — *calibration-in-the-large*, i.e. unbiasedness:
  `mean(actual − BV) ≈ 0` overall, with segment residuals (era/tempo/dome)
  reported separately to catch conditional bias. Achieved by a global intercept.
  Measured OOF residual ≈ −0.18, all segments within ±0.5. This is
  **mean-unbiasedness only** — it does not imply every segment, or the prediction
  band, is calibrated. A model can average to zero error while running several
  points low on big spreads and high in domes.
- **2023 era flag** — feature marking the Division I/II clock-rule regime from
  2023, when the game clock stopped pausing after most first downs. Preseason
  estimates expected roughly **7–8 fewer plays per game**; that is an *estimate*,
  not our measurement, and Beat Vegas should report its own measured FBS effect
  separately rather than let a projection harden into a fact.
- **QB-out flag** — a forward-only, unofficial "QB listed Out/Doubtful" banner from
  Rotowire's college injury report (which aggregates the SEC/ACC/Big Ten
  availability reports). Display only — never a model feature (no historical injury
  data exists to train on). ESPN publishes no college injuries, so ESPN is news-only.
- **Closing-line freshness** — CLV is only trustworthy if the closing line was
  captured near kickoff. A near-kickoff poll keeps it fresh; grading stores when the
  closing snapshot landed.

## Data sources and operating costs
- **CollegeFootballData (CFBD)** — games, play-by-play (→ actual 1H points),
  advanced stats, SP+, returning production, venues, full-game lines.
- **TeamRankings** — tempo (seconds/play, plays/game), as-of-date historical.
- **Open-Meteo** — weather (temp/wind/precip) by venue, archive + forecast.
- **The Odds API** — live first-half totals (`totals_h1`). **PAID**: the free tier
  is 500 credits/month and the project spends ~567 a *week*, so it runs on the
  **100K/month** tier (since 2026-09-06). This is the one source with a real bill.
- **ESPN hidden API** — team news for card context (display only, unofficial; use the
  `site.web.api.espn.com` host — `site.api.espn.com` is Akamai-blocked).
- **Rotowire injury report** — the college injury/availability table behind
  rotowire.com's injury-report page (unofficial JSON). The only free source that
  actually carries CFB injuries. Display only.

## What moved the model (and what didn't)
- **Helped:** pace (tempo). **Weather is no longer claimed** — every historical
  weather value was mis-timed (a UTC kickoff hour indexed into a local-time
  array), so any earlier ablation, factor ranking or "weather helped" read was
  computed on values several hours from kickoff. It is an **open hypothesis
  pending remeasurement** from the corrected, decision-time data
  (`docs/WEATHER.md`). Proxy-graded selection stats (the old 54% / +3% ROI reads) were
  a flat-0.52 artefact and are no longer quoted as an edge; against the fair step
  proxy the backtest shows no confirmed edge. Only real-line CLV can.
- **Flat:** rest/travel/time-zone/kickoff (situational) and returning production —
  kept as on-card *context*, not model inputs.
- **Status, stated plainly:** *Beat Vegas does not currently have a confirmed
  betting edge.* It has a market-blind ranking hypothesis under prospective test
  against real Hard Rock prices. Against the corrected proxy **no historical edge
  is confirmed**; prospective results on real captured lines are the deciding
  evidence. "Real but small" was never a defensible phrase — something cannot be
  both real and unconfirmed.

## Key facts / decisions
- Free data only. Research/decision-support only — never auto-bets.
- DB: SQLite locally, **Neon Postgres** in the cloud (`DATABASE_URL`).
- Product: the **Next.js app on Vercel** (Neon-backed, password-gated).
- Engine: the Python scripts run in **GitHub Actions** (`.github/workflows/`) — Sunday
  capture + score, per-game 1H closes, a morning card Tue–Sat (~8:05am ET) plus an
  afternoon card Thu/Fri (~4pm ET), daily grading, Tue/Fri research preview. GitHub emails
  failed runs. **There are no scheduled Claude routines and no scheduled texts**
  (retired 2026-09-13 — they were local sessions that only fired when the laptop
  was awake). The board is the failure signal: `web/lib/boardHealth.ts`.
- Repo (private): https://github.com/tatemoody7/beat-vegas
- The real test of the edge = **real first-half lines collected this season**,
  graded vs the model and my own picks.
