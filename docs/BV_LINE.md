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
  **actual realized 1H points**, using the full leak-free feature set — pace
  (expected possessions), efficiency (SP+/PPA/success), 1H scoring history, weather,
  situational, and a **2023-era flag**. Walk-forward (train on prior seasons),
  bias-corrected so it's unbiased out of fold. Lives in `beatvegas/model/bv_line.py`.
- **Isn't:** the old `proj_1h_total` "Hist proj" chip — that's a *naive* formula
  from 1H scoring history only (no pace/weather/efficiency/era). It stays on the card
  as a separate, clearly-labeled context chip. Don't conflate the two.
- **Isn't:** an input to the score. The 0–100 **Under Score still comes only from the
  classifier.** The gap is **display + a "Biggest gaps" sort** — nothing more — until
  CLV proves it out (see "Honesty").

## Where it shows up
- **Opportunities cards** (web + Streamlit): each card shows `BV · Vegas · gap` and a
  "BV line" chip. The board has a **Sort** toggle: "Model rank" (default) or
  "Biggest gaps." The card gap is computed against the *live* consensus line when
  available, else the line stored at scoring time.
- **Research tab:** a **Gap vs CLV** bucket table (the verdict — do our biggest gaps
  earn positive CLV?) and a **BV-line calibration** table (out-of-fold mean residual
  per segment; near 0 = unbiased).

## How it works (for builders)
- **Feature:** `era_post2023 = (season >= 2023)` added to `FEATURE_COLS`
  (`beatvegas/etl/features.py`). The 2023 NCAA running-clock rule cut ~8 plays/game —
  a real scoring-regime shift, so pre-2023 is a different distribution.
- **Scoring:** `score_slate` (`beatvegas/model/score.py`) fits the regressor on the
  same walk-forward train slice as the classifier and writes `bv_line` +
  `bv_gap` (= `line_used − bv_line`) to the `predictions` table and into
  `factors_json`.
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
# Local dev (SQLite). Score a slate normally; bv_line populates automatically:
python scripts/weekly_update.py --season 2025 --week 8

# Backfill bv_line onto historical predictions (re-scores walk-forward; no API calls):
python scripts/backfill_bv_line.py --start-season 2018

# Log model_runs + BV calibration residual table (feeds the Research calibration table):
python scripts/retrain.py --notes "..."
```
**Deploying to the live site (Neon + Vercel):**
1. The `bv_line`/`bv_gap` columns auto-add to Neon on the next `init_db()` (via
   `db/store.py::_MIGRATIONS`) — no hand-written migration.
2. **Resync the Postgres id sequence before bulk inserts** (rows seeded from SQLite
   leave the sequence at 1 → pkey collision):
   `SELECT setval(pg_get_serial_sequence('predictions','id'), (SELECT MAX(id) FROM predictions))`
   (same for `model_runs` before `retrain.py`).
3. Run `backfill_bv_line.py` and `retrain.py` with `DATABASE_URL` pointed at Neon.
4. Push to `main` → Vercel auto-deploys the web. (Do the data steps first so the new
   code never queries a column that isn't there yet.)

## Honesty (carry this through every change)
- **Gaps can be blind spots, not edges.** Vegas embeds injuries, late weather, and
  sharp money the model can't see. A huge gap may mean *we're* missing something.
- **CLV, not win rate, is the verdict.** On the biggest-gap bucket: lines moving
  *toward* our number before close = real signal; moving away = noise/blind spots.
- The gap **never feeds the Under Score or rank** until the gap-vs-CLV table earns it.
- Early on, the live CLV sample is tiny (only real 1H lines collected so far) and may
  read flat — that's *insufficient data*, not a verdict. It sharpens through the season.
