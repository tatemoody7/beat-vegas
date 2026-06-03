# The 2026 Pivot: 1H-Under Mispricing System

Beat Vegas was reframed from **"prove first-half unders win"** to **"find the specific
games where the sportsbook mispriced the 1H under."** Blind 1H unders do not beat the
vig (~51.7% over 2015–25). The edge, if any, comes from *selection*.

## The engine (what's now PRIMARY)

A **market-blind gradient-boosted regressor** predicts each game's actual first-half
total from the full feature set (it never sees a Vegas number:
`BV_FEATURE_COLS = FEATURE_COLS − MARKET_COLS`). The board is ranked by the **gap**:

```
gap = line − predicted_1H_total      (+gap = line ABOVE our number = under lean)
```

An **opportunity** is flagged when the gap exceeds half a residual-sigma
(`bv_gap_z >= 0.5`) — noise-aware, so a small gap on a noisy line isn't oversold.
`score_slate` (`beatvegas/model/score.py`) sorts by `bv_gap` and stores the gap-ranked
predictions; the old classifier `under_score` survives as a secondary lean on the card.

**Validation gate** (`scripts/validate_engine.py`, proxy-graded, 2018+ OOS, top 20%):

| Engine | Under% | ROI |
|---|---|---|
| gbm_v1 classifier (old) | 53.1% | +1.4% |
| **gbm_v2 BV-gap (new)** | **54.0%** | **+3.0%** |

Profitable in 6 of 8 OOS seasons.

## The factor framework

`beatvegas/factors/` is a factor-testing harness: a **registry** (117 factors, each
tagged leak-free / market / forward-only) and a walk-forward **evaluator**
(single-feature GBM, permutation importance, 2–3 way combination scan).
`scripts/rank_factors.py` ranks everything by OOS top-fraction ROI and writes
`factor_scores`. Diagnostics (per-season stability, sample size, `corr_1h`) travel
alongside as *reporting, not filters* — breadth is the goal; the human judges fragility.

Factor families: 1H/full scoring history, prior-season efficiency (SP+/PPA/success),
returning production, talent, roster experience, situational (rest/travel/tz/kickoff,
revenge/rivalry/conference/night), venue (elevation/grass/capacity), pace, weather, and
**1H-specific play-by-play factors** (EPA, success, explosive, early-down, 3rd-down,
red-zone TD, 4th-down go-rate, havoc, turnovers, opening-drive, pace) plus matchup
interactions — all season-to-date and leak-free.

## The honest findings (don't oversell)

1. **The proxy-under ROI is partly a PROXY ARTIFACT.** Historical grading uses a
   0.52×full-total proxy (no free historical 1H lines). The proxy-under "leaders"
   (away 1H explosive + turnovers) actually correlate with *more* 1H scoring
   (`corr_1h > 0`) — they win the under by exploiting the flat-0.52 proxy over-pricing
   games whose real 1H share is below 52%, **not** by genuinely low scoring. Against a
   correctly-priced real line, that half of the edge disappears (the proxy-stress test
   halves the edge at −1 pt). See `scripts/explain_pbp.py`.
2. **The genuine 1H-scoring signal is pace + efficiency/scoring levels.** The `corr_1h`
   diagnostic (correlation of each factor to the *actual* 1H total, proxy-immune) ranks
   pace (`combined_sec_play`, −0.17) and scoring/efficiency aggregates at the top.
3. **The PBP backfill did NOT improve 1H-total prediction** (MAE ablation: 9.22 with the
   PBP/matchup family vs 9.18 without). The base features already capture the predictable
   variance. The PBP work's payoff was confirming the thesis and exposing the artifact;
   those factors stay as display chips and could be trimmed from the predictor.
4. **The edge is real but small and unconfirmed.** The honest test is forward CLV vs real
   DraftKings 1H lines during 2026, not the proxy ROI.

## Data sources (all free)

- **Play-by-play**: bulk parquet from the sportsdataverse/cfbfastR data repo (2015–21,
  no API rate limit), CFBD `/plays` for 2022–25. Normalized to one schema in
  `sources/cfbpbp.py`; 1H aggregates in `etl/fh_factors.py` → `fh_team_game` (23k rows).
- CFBD `/venues` (elevation/grass/capacity), `/talent`, `/roster`, `/teams/matchup`.
- Open-Meteo weather, TeamRankings tempo, The Odds API (forward 1H lines).
- **Confirmed NOT free** (documented gaps, not faked): real historical 1H lines
  (→ proxy), OC/DC coordinator names (→ PBP-derived behavior), public/sharp splits
  (→ free open→close movement only).

## What's deployed

- **Neon (prod DB)**: `fh_team_game`, venue columns, fuller weather pushed additively
  (`deploy_neon.py`, chunked); 2025 re-scored natively → gap-ranked predictions. Live
  data (picks/odds/results) preserved.
- **Vercel board** (https://beat-vegas.vercel.app, password-gated): reads Neon, orders by
  `rank` (= gap), shows the BV line/gap/band + a "1H eff" chip.

## Where to pick up next

1. Extend `poll_lines.py` to capture real DraftKings 1H **open & close** → start the true
   forward CLV test for 2026 (the only real validation of the edge).
2. Optionally **trim the PBP factors from the predictor** (keep as display chips) — the
   MAE ablation says they don't aid prediction; a leaner model is cleaner.
3. Build a **Factor Lab** page in `web/` reading `factor_scores` (table + top combos +
   stability/`corr_1h` diagnostics). `factor_scores` is not yet pushed to Neon.
4. Re-run `rank_factors.py` / `validate_engine.py` as real lines accumulate; re-grade the
   gap tiers against real 1H lines instead of the proxy.
