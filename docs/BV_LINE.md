# Beat Vegas — The "BV line" (independent number vs Vegas, ranked by gap)

> Upload this file as **knowledge** in the claude.ai Project alongside
> `PROJECT_BRIEF.md`, `GLOSSARY.md`, and `README.md`. It documents the BV-line
> feature: what it is, why it's built this way, how to operate it, and how to read
> it honestly. Research / decision-support only — it never places bets.

## The idea
Instead of anchoring to Vegas's 1H line, **make our own number first.** The BV line
is an independent projected first-half total for each game, then we compare it to
the real Vegas 1H line and rank games by the gap:

```
gap = Vegas 1H line − BV line        (under direction: positive = Vegas above us)
```

The biggest positive gaps are the candidate under edges. This replaces the
(refuted) "1H totals are a soft market" framing: we don't assume Vegas is soft — we
make an honest number and let the gaps + closing-line value (CLV) show where, if
anywhere, we genuinely diverge with value.

## What the BV line *is* (and isn't)
- **Is:** a `HistGradientBoostingRegressor` (scikit-learn) trained to predict the
  **actual realized 1H points**, **market-blind** — it sees pace, efficiency
  (SP+/PPA/success), 1H scoring history, weather, situational, and a **2023-era
  flag**, but **none** of Vegas's numbers. Walk-forward, bias-corrected to be
  unbiased out of fold. Lives in `beatvegas/model/bv_line.py`.
- **Is noisy, and says so.** Stripped of the market's number, the BV line's own
  error bar is wide — out-of-fold **σ ≈ 12 points**. So it ships with an **80%
  prediction band** (`bv_lo`–`bv_hi`) and reports each gap in units of that noise
  (`bv_gap_z`). A gap inside ~1σ is **noise, not an edge**, and the card says so.
- **Isn't:** the old `proj_1h_total` "Hist proj" chip — a *naive* 1H-scoring-history
  formula. It stays as a separate, clearly-labeled context chip. Don't conflate them.
- **Isn't:** an input to the score. The 0–100 **Under Score still comes only from the
  classifier.** The gap is **display + a "Biggest gaps" sort** — nothing more — until
  CLV proves it out (see "Honesty").

## Where it shows up
- **Opportunities cards** (web + Streamlit): each card shows `BV (lo–hi) · Vegas ·
  gap (±Nσ)` — the band and the gap in σ, with sub-1σ gaps greyed and labeled
  "noise." A **⚠ QB OUT** banner appears when a starting QB is listed out (live
  ESPN, unofficial). The board **Sort** toggles: "Model rank" (default), "Biggest
  gaps," or "Biggest gaps (noise-adjusted)" = ranked by σ. A manual BV nudge, if
  set, shows as `(adj −N: reason)`.
- **Research tab:** a **Gap vs CLV** bucket table (the verdict — do our biggest gaps
  earn positive CLV?) and a **BV-line calibration** table (out-of-fold mean residual
  per segment; near 0 = unbiased).

## How it works (for builders)
- **The no-Vegas-line rule (enforced):** `MARKET_COLS = {full_game_total,
  proj_1h_ratio}` in `features.py`; the regressor trains on `BV_FEATURE_COLS =
  FEATURE_COLS − MARKET_COLS`. A runtime assert in `fit_bv_regressor` + the guard
  tests in `tests/test_features.py` make it impossible for any betting line to become
  a model input. (The classifier keeps `FEATURE_COLS` — it's the *market-relative*
  model by design.)
- **Prediction interval:** `residual_band()` reuses the walk-forward OOF residuals
  (no extra models) to produce `bv_lo`/`bv_hi` (80%) and `bv_sigma`; `score_slate`
  also stores `bv_gap_z = gap / sigma`.
- **Feature:** `era_post2023 = (season >= 2023)` (the 2023 running-clock rule cut
  ~8 plays/game — a real regime shift).
- **Scoring:** `score_slate` (`beatvegas/model/score.py`) fits the regressor on the
  same walk-forward train slice as the classifier and writes `bv_line`, `bv_gap`,
  `bv_lo`, `bv_hi`, `bv_sigma` to the `predictions` table and into `factors_json`.
- **Calibration = unbiasedness.** For a regression line, "calibrated" means
  `mean(actual − pred) ≈ 0` overall and per segment — NOT `calibration_curve` /
  `CalibratedClassifierCV` (those are for probabilities). We learn a **global**
  intercept correction from out-of-fold residuals on the train slice and shift
  predictions by it. We deliberately do **not** apply a *per-era* correction: with
  `era_post2023` already a feature, a per-era intercept double-counts (pooled OOF
  residuals mix early folds that had no post-2023 training data with the final model
  that does). Per-era residuals are **reported** for auditing instead
  (`bv_line.residual_report` → `model_runs.metrics_json.bv_residual` →
  Research calibration table). Measured: overall OOF residual ≈ **−0.19 pts**, every
  segment within ±0.5 — well calibrated, including post-2023.
  - **Honest limit:** the *first* post-2023 season can't be de-biased from data that
    doesn't exist yet. The calibration table surfaces this rather than hiding it.
- **Gap vs CLV join:** `predictions(gbm_v1).bv_line` joined to
  `results(model_version='market')` on `game_id`. The **market** ledger's
  `clv = closing_line − opening_line` is pure line movement — exactly "did the line
  move toward our number?" — and is what's actually graded. (The `gbm_v1` results
  ledger is often ungraded.) Buckets by gap size report n, mean gap, mean CLV, mean
  units, under %. The headline: **mean CLV rising with the gap bucket ⇒ real signal.**

## Operating it
```bash
# Score a slate normally; bv_line + band populate automatically. weekly_update also
# tags the upcoming slate with live QB-out flags (forward-only, unofficial):
python scripts/weekly_update.py --season 2025 --week 8

# Backfill bv_line/band onto historical predictions (re-scores walk-forward; no API calls):
python scripts/backfill_bv_line.py --start-season 2018

# Log model_runs + BV calibration residual table (feeds the Research calibration table):
python scripts/retrain.py --notes "..."

# Keep the closing line fresh: poll games kicking off in the next ~2h (every ~30 min
# via deploy/com.beatvegas.kickoff.plist; only runs while the Mac is awake):
python scripts/poll_kickoff_lines.py

# Manual BV nudge for a game the model can't see (display-only, clearly labeled):
python scripts/bv_adjust.py set --game 401752875 --delta -3 --reason "starter QB out"
```
**Deploying to the live site (Neon + Vercel):**
1. New columns/tables auto-add to Neon on the next `init_db()` (via
   `db/store.py::_MIGRATIONS` for columns; `create_all` for the `bv_adjustments`
   table) — no hand-written migration.
2. **Resync the Postgres id sequence before bulk inserts** (rows seeded from SQLite
   leave the sequence at 1 → pkey collision):
   `SELECT setval(pg_get_serial_sequence('predictions','id'), (SELECT MAX(id) FROM predictions))`
   (same for `model_runs` before `retrain.py`).
3. Run `backfill_bv_line.py` and `retrain.py` with `DATABASE_URL` pointed at Neon.
4. Push to `main` → Vercel auto-deploys the web. (Do the data steps first so the new
   code never queries a column that isn't there yet.)

## Honesty (carry this through every change)
- **Most gaps are noise.** The market-blind BV line's σ ≈ 12 pts, so a single-game
  gap under ~1σ is statistically indistinguishable from zero. The σ view says this
  out loud — don't read a raw 6-pt gap as an edge on its own.
- **Gaps can be blind spots, not edges.** Vegas embeds injuries, late weather, and
  sharp money the model can't see. A huge gap may mean *we're* missing something.
- **CLV, not win rate, is the verdict.** On the biggest-gap bucket: lines moving
  *toward* our number before close = real signal; moving away = noise/blind spots.
- The gap **never feeds the Under Score or rank** until the gap-vs-CLV table earns it.
- Early on, the live CLV sample is tiny (only real 1H lines collected so far) and may
  read flat — that's *insufficient data*, not a verdict. It sharpens through the season.
