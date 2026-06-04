# Decision-quality ledger — design (Phase 4b)

## Context

Beat Vegas grades the user's own `manual_picks` for result / units / CLV and shows a
three-way market/model/you Ledger. What it does **not** answer is whether the user's
*discretion* adds value: do their calls beat their own model's number, beat the closing
line, lean on the right factors, and get good entry timing? This spec adds a
**decision-quality (DQ)** lens to the existing Ledger view.

This is Phase 4b of the green/red factor-board plan
(`~/.claude/plans/i-want-to-brainstorming-zazzy-clover.md`). Phase 4a (bv_line
recalibration from `GameRecord`s) is deferred: 0 graded `GameRecord`s exist yet
(forward-only, off-season) and `retrain.py` already trains on the full 2015–2025 game
table, so the increment has nothing to consume today.

**Builds on** the factor-board / `FactorLedger` work in PR #3 (branch
`factor-board-trend-engine`) — this branch is cut from that tip.

## Goal

Answer four questions in the Ledger view, computed from immutable pick-time snapshots:

1. **Did I beat my own model?** Edge realized vs `bv_gap` at pick time.
2. **Did I beat the close? (CLV)** Avg CLV, % positive, hit% by CLV sign.
3. **Which factors do I over/under-weight?** Per-factor hit% on my picks vs the
   factor's own cumulative `FactorLedger` rate.
4. **Bet-timing quality.** Line taken vs opening vs closing.

## Decisions locked

- **Approach A — snapshot at pick time** (immutable), not a post-hoc join to the
  mutable/superseded `predictions.factors_json`. Consistent with the existing
  `model_score_at_pick` / `model_line_at_pick` pattern and the `GameRecord` philosophy.
- **Render in the existing Ledger view** (`web/app/ledger/page.tsx`), a new "Decision
  quality" section below the current market/model/you cards — not a new route.
- **Forward-only per-factor attribution is acceptable.** `factors_json_at_pick` only
  populates for picks logged after ship; with ~0 existing real picks this loses nothing.

## Components

### 1. Data model — `beatvegas/db/models.py::ManualPick`

Two additive columns:

- `factors_json_at_pick = Column(String)` — frozen `prediction.factors_json` (the factor
  board, incl. each factor's `live` credibility) at log time.
- `opening_line = Column(Float)` — consensus opening 1H total, filled at grading.

Migration via the existing idempotent ALTER mechanism in `beatvegas/db/store.py`
`_MIGRATIONS`: add `"manual_picks": {"factors_json_at_pick": "TEXT", "opening_line":
"FLOAT"}`. Same path that already adds `games.spread`. **Not stored:** `bv_gap_at_pick`
is derived at render time as `line − model_line_at_pick` (both already snapshotted);
`under_score` is the existing `model_score_at_pick`.

### 2. Snapshot at pick time — `web/lib/picks.ts::createPick`

The query that already selects `under_score, line_used FROM predictions ... ORDER BY
created_at DESC LIMIT 1` also selects `factors_json`, written to
`factors_json_at_pick`. `model_score_at_pick` / `model_line_at_pick` unchanged.

### 3. Grading enrichment — `scripts/pick.py grade`

Already computes `consensus_open_close(snaps) → (opening, closing)` and persists only
`closing_line` / `clv`. Add persistence of `opening_line = opening`. No new computation
or query.

### 4. Web data layer — `web/lib/ledger.ts`

New pure function `getDecisionQuality(season)` reading graded `manual_picks` with the new
columns, returning a typed DQ summary. Metric helpers (pure, unit-testable in isolation):

- **Beat my model:** `edge = line − model_line_at_pick` per pick (positive = the market
  1H total sat above our model's line, i.e. our model agreed the under was favorable).
  Bucket on `edge > 0` (model-agreed picks) vs `edge ≤ 0` (discretionary picks against
  the model) and report hit% + units per bucket. No magic constant — the split is the
  sign of the edge. Hit% = under wins / (n − pushes).
- **CLV:** avg `clv`, % positive `clv`, hit% conditioned on CLV sign.
- **Per-factor:** parse `factors_json_at_pick`; for each factor **green** at pick time
  (reuse `BoardFactor.color === 'green'` semantics from `web/lib/score.ts`), accumulate
  `(n, hits)` across the user's picks. Compare the user's per-factor hit% to that
  factor's cumulative `FactorLedger.post_mean` (query `factor_ledger`) → over-weight
  (user hit% < ledger rate) / under-weight (user hit% > ledger rate).
- **Timing:** `line` vs `opening_line` vs `closing_line` — % picked at/better than open,
  % beating close.

Green-state classification and any score thresholds must stay in sync with `score.py` /
`board.py` (CLAUDE.md invariant: `web/lib/score.ts` mirrors `model/score.py`).

### 5. Ledger UI — `web/app/ledger/page.tsx`

A "Decision quality" section under the existing cards:

- A stat row (reusing `.bv-stat`): **Beat my model** (high-edge hit% vs low),
  **Beat the close** (avg CLV, % positive), **Timing** (% ≥ close).
- A per-factor table (`.bv-table`): factor | your n | your hit% | ledger hit% |
  over/under-weight chip. Factor tier dots reused; **green/red reserved for under/over
  outcomes only** — over/under-weight chips use the cyan/neutral palette.

### 6. Testing (TDD)

- **Python:** `pick.py grade` persists `opening_line` from snapshots (extend the pick
  grading test).
- **TS:** unit-test each metric helper with synthetic pick rows — edge bucketing, CLV
  rollup, per-factor accumulation + over/under classification, timing buckets. End-to-end
  sanity against `demo.db` (5 graded picks).

## Validation reality

Beat-my-model / CLV / timing render on existing graded picks (incl. `demo.db`'s 5). The
**per-factor** section stays empty until picks are logged *after* ship
(`factors_json_at_pick` is forward-only) — inherent to Approach A, acceptable at ~0
existing picks.

## Out of scope

- Phase 4a bv_line recalibration (deferred — no data yet).
- Retroactive per-factor attribution for pre-existing picks.
- New nav routes / dedicated DQ page.

## Critical files

- `beatvegas/db/models.py` — `ManualPick` columns.
- `beatvegas/db/store.py` — `_MIGRATIONS` entry.
- `web/lib/picks.ts` — `createPick` snapshot.
- `scripts/pick.py` — grade enrichment (`opening_line`).
- `web/lib/ledger.ts` — `getDecisionQuality` + metric helpers.
- `web/app/ledger/page.tsx` — DQ section render.
- `web/lib/score.ts` — green-state semantics (reuse, keep synced).
