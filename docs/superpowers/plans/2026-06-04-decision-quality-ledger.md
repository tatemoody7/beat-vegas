# Decision-Quality Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a decision-quality lens to the existing Ledger view — answering whether the user's picks beat their own model, beat the close, lean on the right factors, and time entries well — from immutable pick-time snapshots.

**Architecture:** Two additive `manual_picks` columns (`factors_json_at_pick`, `opening_line`) snapshotted at log time / grade time. Pure metric helpers compute four rollups: Python for the grade-side field assembly (pytest), TypeScript for the web rollups (Vitest). A new `web/lib/decision-quality.ts` holds the pure helpers + `getDecisionQuality`, rendered as a new section in `web/app/ledger/page.tsx`.

**Tech Stack:** SQLAlchemy + idempotent ALTER migrations (`store.py`), Prisma `$queryRaw` (web), Vitest (new), Tailwind v4 `.bv-*` classes.

**Spec:** `docs/superpowers/specs/2026-06-04-decision-quality-ledger-design.md`
**Branch:** `decision-quality-ledger` (already cut from `factor-board-trend-engine` tip).

---

## File Structure

- **Modify** `beatvegas/db/models.py` — `ManualPick`: 2 new columns (Task 1).
- **Modify** `beatvegas/db/store.py` — `_MIGRATIONS["manual_picks"]` (Task 1).
- **Create** `scripts/pick.py::graded_pick_fields` (pure helper) + rewire `cmd_grade` (Task 2).
- **Modify** `web/lib/picks.ts::createPick` — snapshot `factors_json` (Task 3).
- **Create** `web/vitest.config.ts` + dev dep + `package.json` test script (Task 4).
- **Create** `web/lib/decision-quality.ts` — pure metric helpers + `getDecisionQuality` (Tasks 5–8).
- **Create** `web/lib/decision-quality.test.ts` — Vitest unit tests (Tasks 5–8).
- **Modify** `web/app/ledger/page.tsx` — render the DQ section (Task 9).
- **Modify** `web/app/globals.css` — only if a new class is needed (Task 9; reuse `.bv-*` first).

---

## Task 1: ManualPick columns + migration

**Files:**
- Modify: `beatvegas/db/models.py:246` (after `clv = Column(Float)`)
- Modify: `beatvegas/db/store.py:29`
- Test: `tests/test_decision_quality.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_decision_quality.py`:

```python
from beatvegas.db import models, store


def test_manual_pick_has_dq_columns(tmp_path):
    """New ManualPick columns exist and round-trip through a fresh SQLite DB."""
    store._engine = None
    store._Session = None
    db = tmp_path / "dq.db"
    store.init_db(path=db)
    with store.session_scope() as s:
        s.add(
            models.ManualPick(
                game_id=1,
                season=2025,
                week=1,
                line=24.5,
                factors_json_at_pick='{"factor_board": []}',
                opening_line=25.0,
            )
        )
    with store.session_scope() as s:
        p = s.query(models.ManualPick).first()
        assert p.factors_json_at_pick == '{"factor_board": []}'
        assert p.opening_line == 25.0
    store._engine = None
    store._Session = None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_decision_quality.py -v`
Expected: FAIL — `AttributeError`/`TypeError` on unknown kwarg `factors_json_at_pick` (column does not exist).

> Note: confirm `store.init_db` accepts a `path=` kwarg; if its signature is `init_db()` only, instead set `os.environ["DATABASE_URL"] = f"sqlite:///{db}"`, reset `store._engine/_Session = None`, then `store.init_db()`. Mirror whatever `tests/test_game_records.py` does for its SQLite setup.

- [ ] **Step 3: Add the columns**

In `beatvegas/db/models.py`, immediately after line 246 (`clv = Column(Float)`), inside `class ManualPick`:

```python

    # Decision-quality snapshot (Phase 4b). factors_json_at_pick freezes the
    # factor board at log time (forward-only); opening_line filled at grading.
    factors_json_at_pick = Column(String)
    opening_line = Column(Float)
```

In `beatvegas/db/store.py`, change line 29 to add the two columns to the existing dict:

```python
    "manual_picks": {
        "model_score_at_pick": "INTEGER",
        "model_line_at_pick": "FLOAT",
        "factors_json_at_pick": "TEXT",
        "opening_line": "FLOAT",
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_decision_quality.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add beatvegas/db/models.py beatvegas/db/store.py tests/test_decision_quality.py
git commit -m "feat(dq): ManualPick factors_json_at_pick + opening_line columns

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Grade-side `opening_line` persistence (pure helper)

Extract the per-pick graded-field assembly into a pure, testable helper, then have `cmd_grade` use it. This adds `opening_line` to the persisted fields.

**Files:**
- Modify: `scripts/pick.py` (add `graded_pick_fields`, rewire `cmd_grade:118-123`)
- Test: `tests/test_decision_quality.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_decision_quality.py`:

```python
def test_graded_pick_fields_includes_opening_line():
    from pick import graded_pick_fields  # scripts/ is on sys.path (conftest)

    fields = graded_pick_fields(
        actual_first_half=20, line=24.5, price=-110, stake=1.0,
        opening=26.0, closing=25.0,
    )
    assert fields["result"] == "under"          # 20 < 24.5
    assert fields["opening_line"] == 26.0
    assert fields["closing_line"] == 25.0
    assert fields["clv"] == 25.0 - 24.5          # clv_under(line, closing)
    assert fields["actual_first_half_total"] == 20
    assert fields["units"] != 0


def test_graded_pick_fields_no_snapshots():
    from pick import graded_pick_fields

    fields = graded_pick_fields(
        actual_first_half=30, line=24.5, price=-110, stake=1.0,
        opening=None, closing=None,
    )
    assert fields["result"] == "over"            # 30 > 24.5
    assert fields["opening_line"] is None
    assert fields["closing_line"] is None
    assert fields["clv"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_decision_quality.py -k graded_pick_fields -v`
Expected: FAIL — `ImportError: cannot import name 'graded_pick_fields'`.

- [ ] **Step 3: Add the pure helper and rewire `cmd_grade`**

In `scripts/pick.py`, add a module-level function (near the other helpers, above `cmd_grade`). It reuses the existing pure grading math already imported in this file (`under_result`, `units_won`, `clv_under`):

```python
def graded_pick_fields(actual_first_half, line, price, stake, opening, closing) -> dict:
    """Pure: the graded ManualPick fields for one pick + its line snapshots."""
    return {
        "actual_first_half_total": actual_first_half,
        "result": under_result(actual_first_half, line),
        "units": stake * units_won(actual_first_half, line, price),
        "opening_line": opening,
        "closing_line": closing,
        "clv": clv_under(line, closing) if closing is not None else None,
    }
```

Then replace the assignment block in `cmd_grade` (currently `scripts/pick.py:117-123`,
from `_open, closing = consensus_open_close(snaps)` through `p.graded = True`) with:

```python
            opening, closing = consensus_open_close(snaps)
            for k, v in graded_pick_fields(
                g.first_half_total, p.line, p.price, p.stake, opening, closing
            ).items():
                setattr(p, k, v)
            p.graded = True
```

> Verify `clv_under`, `units_won`, `under_result`, `consensus_open_close` are already imported at the top of `scripts/pick.py` (they are used by the current `cmd_grade`). No new imports needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_decision_quality.py -v`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/pick.py tests/test_decision_quality.py
git commit -m "feat(dq): persist opening_line at grading via pure graded_pick_fields

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Snapshot the factor board at pick time

**Files:**
- Modify: `web/lib/picks.ts:141-166` (`createPick`)

- [ ] **Step 1: Extend the prediction query to pull `factors_json`**

In `web/lib/picks.ts`, change the `$queryRaw` block at line 141 to also select `factors_json`:

```typescript
  const pred = await prisma.$queryRaw<
    {
      under_score: number | bigint | null;
      line_used: number | null;
      factors_json: string | null;
    }[]
  >`
    SELECT under_score, line_used, factors_json FROM predictions
    WHERE game_id = ${input.gameId} ORDER BY created_at DESC LIMIT 1
  `;
  const modelScore =
    pred[0]?.under_score == null ? null : Number(pred[0].under_score);
  const modelLine = pred[0]?.line_used ?? null;
  const factorsAtPick = pred[0]?.factors_json ?? null;
```

- [ ] **Step 2: Write `factors_json_at_pick` in the INSERT**

Change the INSERT column list and VALUES (lines 158-166) to include the new column:

```typescript
  await prisma.$executeRaw`
    INSERT INTO manual_picks
      (game_id, season, week, home_team, away_team, side, line, price, stake,
       placed_at, note, model_score_at_pick, model_line_at_pick,
       factors_json_at_pick, graded)
    VALUES
      (${input.gameId}, ${game.season}, ${game.week}, ${game.home_team},
       ${game.away_team}, 'under', ${input.line}, ${price}, ${stake},
       ${placedAt}::timestamp, ${note}, ${modelScore}, ${modelLine},
       ${factorsAtPick}, false)
  `;
```

- [ ] **Step 3: Verify it compiles**

Run: `cd web && npx tsc --noEmit`
Expected: exit 0, no errors.

- [ ] **Step 4: Commit**

```bash
git add web/lib/picks.ts
git commit -m "feat(dq): snapshot factor board (factors_json) onto picks at log time

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Add Vitest to `web/`

**Files:**
- Create: `web/vitest.config.ts`
- Modify: `web/package.json` (devDependency + `test` script)

- [ ] **Step 1: Install Vitest**

Run: `cd web && npm install -D vitest@^2`
Expected: `vitest` added to `devDependencies`.

- [ ] **Step 2: Add the test script**

In `web/package.json`, add to the `"scripts"` object:

```json
    "test": "vitest run"
```

- [ ] **Step 3: Create the config**

Create `web/vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  test: { environment: "node", include: ["lib/**/*.test.ts"] },
  resolve: {
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
});
```

- [ ] **Step 4: Smoke-test the runner**

Create a throwaway `web/lib/__smoke.test.ts` with `import {expect, test} from "vitest"; test("ok", () => expect(1).toBe(1));`
Run: `cd web && npm test`
Expected: 1 passed. Then delete `web/lib/__smoke.test.ts`.

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/package-lock.json web/vitest.config.ts
git commit -m "chore(web): add Vitest for unit-testing pure lib helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: DQ types + "beat my model" rollup

`web/lib/decision-quality.ts` holds all pure helpers and the data-layer fetch. Tasks 5–8
build it incrementally; each adds a helper + tests. The shared input row type:

```typescript
export type DqPickRow = {
  result: string | null;          // "under" | "over" | "push" | null
  line: number | null;            // 1H total taken
  model_line_at_pick: number | null;
  opening_line: number | null;
  closing_line: number | null;
  clv: number | null;
  factors_json_at_pick: string | null;
};
```

**Files:**
- Create: `web/lib/decision-quality.ts`
- Create: `web/lib/decision-quality.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/lib/decision-quality.test.ts`:

```typescript
import { expect, test } from "vitest";
import { beatMyModel, type DqPickRow } from "@/lib/decision-quality";

const row = (o: Partial<DqPickRow>): DqPickRow => ({
  result: null, line: null, model_line_at_pick: null, opening_line: null,
  closing_line: null, clv: null, factors_json_at_pick: null, ...o,
});

test("beatMyModel splits on edge sign and computes hit% excluding pushes", () => {
  const picks: DqPickRow[] = [
    // edge = line - model_line. Positive edge = model agreed.
    row({ line: 26, model_line_at_pick: 24, result: "under" }), // +2, win
    row({ line: 26, model_line_at_pick: 24, result: "over" }),  // +2, loss
    row({ line: 25, model_line_at_pick: 25, result: "push" }),  // 0 -> agreed bucket, push excluded
    row({ line: 23, model_line_at_pick: 25, result: "under" }), // -2, against, win
  ];
  const r = beatMyModel(picks);
  // agreed: edge > 0 => rows 1 & 2 (n=2); 1 under win, 1 over loss, no push.
  expect(r.agreed).toEqual({ n: 2, wins: 1, decided: 2, hitPct: 50 });
  // against: edge <= 0 => row 3 (push, edge==0) + row 4 (-2, under win) = n 2;
  // push excluded from decided, so 1 decided / 1 win.
  expect(r.against).toEqual({ n: 2, wins: 1, decided: 1, hitPct: 100 });
});
```

> The `against` bucket includes the `edge == 0` push row (edge ≤ 0) and the `-2` win.
> push is excluded from `decided`; `hitPct = 100 * wins / decided`, or `null` when `decided === 0`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — cannot resolve `beatMyModel` (module/export missing).

- [ ] **Step 3: Implement**

Create `web/lib/decision-quality.ts`:

```typescript
export type DqPickRow = {
  result: string | null;
  line: number | null;
  model_line_at_pick: number | null;
  opening_line: number | null;
  closing_line: number | null;
  clv: number | null;
  factors_json_at_pick: string | null;
};

export type Bucket = {
  n: number;
  wins: number;
  decided: number;
  hitPct: number | null;
};

function tally(picks: DqPickRow[]): Bucket {
  const wins = picks.filter((p) => p.result === "under").length;
  const pushes = picks.filter((p) => p.result === "push").length;
  const decided = picks.filter(
    (p) => p.result === "under" || p.result === "over",
  ).length;
  return {
    n: picks.length,
    wins,
    decided,
    hitPct: decided ? (100 * wins) / decided : null,
  };
}

export function beatMyModel(picks: DqPickRow[]): {
  agreed: Bucket;
  against: Bucket;
} {
  const edge = (p: DqPickRow) =>
    p.line != null && p.model_line_at_pick != null
      ? p.line - p.model_line_at_pick
      : null;
  // edge > 0 = market line above our model line = our model agreed under is favorable.
  const agreed = picks.filter((p) => (edge(p) ?? -1) > 0);
  const against = picks.filter((p) => (edge(p) ?? -1) <= 0);
  return { agreed: tally(agreed), against: tally(against) };
}
```

> The test's `against` expectation uses `decided: 1` (the push is excluded from decided
> but counted in `n`). Adjust the literal `hitPct` in the test if your `tally` returns a
> float (e.g. `50`); `(100*1)/2 === 50` and `(100*1)/1 === 100` are exact here.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/lib/decision-quality.ts web/lib/decision-quality.test.ts
git commit -m "feat(dq): beatMyModel edge-sign rollup + types

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: CLV rollup

**Files:**
- Modify: `web/lib/decision-quality.ts`, `web/lib/decision-quality.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `web/lib/decision-quality.test.ts`:

```typescript
import { clvSummary } from "@/lib/decision-quality";

test("clvSummary: avg, positive share, and hit% by clv sign", () => {
  const picks: DqPickRow[] = [
    row({ clv: 1.0, result: "under" }),  // +clv win
    row({ clv: 0.5, result: "over" }),   // +clv loss
    row({ clv: -1.0, result: "under" }), // -clv win
    row({ clv: null, result: "under" }), // ignored for clv stats
  ];
  const r = clvSummary(picks);
  expect(r.n).toBe(3);                       // non-null clv only
  expect(r.avg).toBeCloseTo((1.0 + 0.5 - 1.0) / 3);
  expect(r.pctPositive).toBeCloseTo((100 * 2) / 3);
  expect(r.posClvHitPct).toBe(50);          // 2 decided +clv, 1 win
  expect(r.negClvHitPct).toBe(100);         // 1 decided -clv, 1 win
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — `clvSummary` not exported.

- [ ] **Step 3: Implement**

Append to `web/lib/decision-quality.ts`:

```typescript
export function clvSummary(picks: DqPickRow[]): {
  n: number;
  avg: number | null;
  pctPositive: number | null;
  posClvHitPct: number | null;
  negClvHitPct: number | null;
} {
  const withClv = picks.filter((p) => p.clv != null);
  const n = withClv.length;
  const avg = n
    ? withClv.reduce((a, p) => a + (p.clv as number), 0) / n
    : null;
  const positive = withClv.filter((p) => (p.clv as number) > 0);
  const pos = tally(positive);
  const neg = tally(withClv.filter((p) => (p.clv as number) <= 0));
  return {
    n,
    avg,
    pctPositive: n ? (100 * positive.length) / n : null,
    posClvHitPct: pos.hitPct,
    negClvHitPct: neg.hitPct,
  };
}
```

> `tally` is already defined in Task 5. Do not redefine it.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/lib/decision-quality.ts web/lib/decision-quality.test.ts
git commit -m "feat(dq): CLV rollup (avg, % positive, hit% by clv sign)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Bet-timing rollup

**Files:**
- Modify: `web/lib/decision-quality.ts`, `web/lib/decision-quality.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `web/lib/decision-quality.test.ts`:

```typescript
import { timingSummary } from "@/lib/decision-quality";

test("timingSummary: share at/better than open, share beating close", () => {
  // For an UNDER bettor a HIGHER line taken is better.
  const picks: DqPickRow[] = [
    row({ line: 26, opening_line: 25, closing_line: 25.5 }), // >= open, > close
    row({ line: 24, opening_line: 25, closing_line: 24.5 }), // < open, < close
    row({ line: 25, opening_line: 25, closing_line: 25 }),   // == open (counts), == close (not beating)
    row({ line: 27, opening_line: null, closing_line: 26 }), // no open; > close
  ];
  const r = timingSummary(picks);
  expect(r.nOpen).toBe(3);                  // rows with opening_line
  expect(r.pctAtOrBetterThanOpen).toBeCloseTo((100 * 2) / 3); // rows 1 and 3
  expect(r.nClose).toBe(4);
  expect(r.pctBeatingClose).toBeCloseTo((100 * 2) / 4);       // rows 1 and 4
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — `timingSummary` not exported.

- [ ] **Step 3: Implement**

Append to `web/lib/decision-quality.ts`:

```typescript
export function timingSummary(picks: DqPickRow[]): {
  nOpen: number;
  pctAtOrBetterThanOpen: number | null;
  nClose: number;
  pctBeatingClose: number | null;
} {
  // UNDER bettor: a higher line taken is a better number.
  const withOpen = picks.filter(
    (p) => p.line != null && p.opening_line != null,
  );
  const atOrBetter = withOpen.filter(
    (p) => (p.line as number) >= (p.opening_line as number),
  );
  const withClose = picks.filter(
    (p) => p.line != null && p.closing_line != null,
  );
  const beatClose = withClose.filter(
    (p) => (p.line as number) > (p.closing_line as number),
  );
  return {
    nOpen: withOpen.length,
    pctAtOrBetterThanOpen: withOpen.length
      ? (100 * atOrBetter.length) / withOpen.length
      : null,
    nClose: withClose.length,
    pctBeatingClose: withClose.length
      ? (100 * beatClose.length) / withClose.length
      : null,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/lib/decision-quality.ts web/lib/decision-quality.test.ts
git commit -m "feat(dq): bet-timing rollup (vs opening, beating close)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Per-factor attribution + `getDecisionQuality`

Parse `factors_json_at_pick` (reusing `parseFactors` from `score.ts`), count each
green factor's record across the user's picks, and compare to that factor's cumulative
`FactorLedger.post_mean`.

**Files:**
- Modify: `web/lib/decision-quality.ts`, `web/lib/decision-quality.test.ts`

- [ ] **Step 1: Write the failing test (pure helper)**

Append to `web/lib/decision-quality.test.ts`:

```typescript
import { perFactorAttribution } from "@/lib/decision-quality";

const board = (greens: string[]) =>
  JSON.stringify({
    factor_board: greens.map((key) => ({
      key, label: key, family: "x", tier: 1, direction: 1, hypothesis: false,
      binary: false, value: 1, color: "green", intensity: 0.5, lean: 1,
      sentence: "", live: null,
    })),
  });

test("perFactorAttribution: your hit% per green factor vs ledger rate", () => {
  const picks: DqPickRow[] = [
    row({ result: "under", factors_json_at_pick: board(["pace_estimate"]) }),
    row({ result: "over", factors_json_at_pick: board(["pace_estimate"]) }),
    row({ result: "under", factors_json_at_pick: board(["pace_estimate"]) }),
    row({ result: "push", factors_json_at_pick: board([]) }),
  ];
  const ledger = { pace_estimate: { mean: 0.6, n: 100 } };
  const rows = perFactorAttribution(picks, ledger);
  expect(rows).toHaveLength(1);
  const f = rows[0];
  expect(f.key).toBe("pace_estimate");
  expect(f.n).toBe(3);
  expect(f.decided).toBe(3);          // no pushes among the 3 with this factor green
  expect(f.yourHitPct).toBeCloseTo((100 * 2) / 3);
  expect(f.ledgerHitPct).toBe(60);
  // your 66.7% > ledger 60% => you use it well (under-weight relative to its value)
  expect(f.weight).toBe("under");
});
```

> `weight` is `"under"` when `yourHitPct > ledgerHitPct` (you rely on it less than its
> edge would justify / use it well), `"over"` when `yourHitPct < ledgerHitPct`, `"even"`
> when within 1 percentage point or `ledgerHitPct` is null.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — `perFactorAttribution` not exported.

- [ ] **Step 3: Implement the pure helper**

Append to `web/lib/decision-quality.ts` (note the `parseFactors` import at top of file):

```typescript
import { parseFactors } from "@/lib/score";

export type LedgerRates = Record<string, { mean: number; n: number }>;

export type FactorAttribution = {
  key: string;
  label: string;
  n: number;
  wins: number;
  decided: number;
  yourHitPct: number | null;
  ledgerHitPct: number | null;
  weight: "under" | "over" | "even";
};

export function perFactorAttribution(
  picks: DqPickRow[],
  ledger: LedgerRates,
): FactorAttribution[] {
  // factor key -> {label, picks where it was green}
  const acc = new Map<string, { label: string; rows: DqPickRow[] }>();
  for (const p of picks) {
    const board = parseFactors(p.factors_json_at_pick).factor_board ?? [];
    for (const f of board) {
      if (f.color !== "green") continue;
      const e = acc.get(f.key) ?? { label: f.label, rows: [] };
      e.rows.push(p);
      acc.set(f.key, e);
    }
  }
  const out: FactorAttribution[] = [];
  for (const [key, { label, rows }] of acc) {
    const b = tally(rows);
    const ledgerHitPct = ledger[key] ? 100 * ledger[key].mean : null;
    let weight: "under" | "over" | "even" = "even";
    if (b.hitPct != null && ledgerHitPct != null) {
      if (b.hitPct > ledgerHitPct + 1) weight = "under";
      else if (b.hitPct < ledgerHitPct - 1) weight = "over";
    }
    out.push({
      key, label, n: b.n, wins: b.wins, decided: b.decided,
      yourHitPct: b.hitPct, ledgerHitPct, weight,
    });
  }
  return out.sort((a, b) => b.n - a.n);
}
```

> Move the `import { parseFactors } from "@/lib/score";` line to the TOP of
> `decision-quality.ts` with the other imports (don't leave it mid-file).

- [ ] **Step 4: Run the pure-helper test to verify it passes**

Run: `cd web && npm test`
Expected: PASS.

- [ ] **Step 5: Add `getDecisionQuality` data-layer fetch (not unit-tested — DB I/O)**

Append to `web/lib/decision-quality.ts`:

```typescript
import { prisma } from "@/lib/prisma";

export type DecisionQuality = {
  beatModel: ReturnType<typeof beatMyModel>;
  clv: ReturnType<typeof clvSummary>;
  timing: ReturnType<typeof timingSummary>;
  factors: FactorAttribution[];
  n: number;
};

export async function getDecisionQuality(
  season: number,
): Promise<DecisionQuality> {
  const picks = await prisma.$queryRaw<DqPickRow[]>`
    SELECT result, line, model_line_at_pick, opening_line, closing_line, clv,
           factors_json_at_pick
    FROM manual_picks
    WHERE season = ${season} AND graded = true
  `;
  // factor_ledger may not exist yet (created by the Phase-3 Python jobs on
  // their next Neon write). Degrade to no ledger rather than throwing.
  let ledgerRows: {
    factor: string;
    post_mean: number | null;
    n: number | bigint | null;
  }[] = [];
  try {
    ledgerRows = await prisma.$queryRaw`
      SELECT factor, post_mean, n FROM factor_ledger
    `;
  } catch {
    ledgerRows = [];
  }
  const ledger: LedgerRates = {};
  for (const r of ledgerRows) {
    if (r.post_mean != null)
      ledger[r.factor] = { mean: r.post_mean, n: Number(r.n ?? 0) };
  }
  return {
    beatModel: beatMyModel(picks),
    clv: clvSummary(picks),
    timing: timingSummary(picks),
    factors: perFactorAttribution(picks, ledger),
    n: picks.length,
  };
}
```

> `factor_ledger` may not exist on a DB where the Phase-3 Python jobs have not yet run
> (`create_all` creates it on the next Python write). Guard the ledger query so a missing
> table degrades to empty rather than throwing: wrap it in `try { ... } catch { /* no
> ledger yet */ }` and default `ledgerRows = []`. The per-factor section then renders
> with `ledgerHitPct = null` (weight "even") until the ledger exists.

- [ ] **Step 6: Verify compile + tests**

Run: `cd web && npx tsc --noEmit && npm test`
Expected: tsc exit 0; all DQ tests PASS.

- [ ] **Step 7: Commit**

```bash
git add web/lib/decision-quality.ts web/lib/decision-quality.test.ts
git commit -m "feat(dq): per-factor attribution + getDecisionQuality data layer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Render the Decision-quality section in the Ledger view

**Files:**
- Modify: `web/app/ledger/page.tsx`
- Modify: `web/app/globals.css` (only if a new class is genuinely needed)

- [ ] **Step 1: Fetch DQ in the page loader**

In `web/app/ledger/page.tsx`, add the import and call. After the existing
`const { market, model, you, picks } = await getLedger(season);` (line ~82), add:

```typescript
  const dq = await getDecisionQuality(season);
```

And at the top with the other imports:

```typescript
import { getDecisionQuality } from "@/lib/decision-quality";
```

- [ ] **Step 2: Render the section**

After the existing picks table block (the `<div className="bv-table-wrap">…</div>` that
closes the picks table, near the end of the returned JSX), insert a new section. Use the
existing `.bv-card`, `.bv-stat`, `.bv-stat-label`, `.bv-table`, `.bv-table-wrap` classes.
Format helpers: render `null` hit/avg as `"—"`.

```tsx
      <h2 className="mb-2 mt-7 text-sm font-semibold text-[var(--text)]">
        Decision quality
      </h2>
      {dq.n === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No graded picks yet. Log picks to see whether your calls beat your
          model, beat the close, and which factors you lean on well.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="bv-card p-4">
              <h3 className="mb-2 text-sm font-semibold">Beat my model</h3>
              <dl className="space-y-1">
                <div className="flex justify-between">
                  <dt className="bv-stat-label" title="Hit% when your model agreed (market line above our line).">
                    With model
                  </dt>
                  <dd>{pct(dq.beatModel.agreed.hitPct)} ({dq.beatModel.agreed.n})</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label" title="Hit% when you picked against your model.">
                    Against model
                  </dt>
                  <dd>{pct(dq.beatModel.against.hitPct)} ({dq.beatModel.against.n})</dd>
                </div>
              </dl>
            </div>
            <div className="bv-card p-4">
              <h3 className="mb-2 text-sm font-semibold">Beat the close</h3>
              <dl className="space-y-1">
                <div className="flex justify-between">
                  <dt className="bv-stat-label" title="Average closing line value.">Avg CLV</dt>
                  <dd>{dq.clv.avg == null ? "—" : dq.clv.avg.toFixed(2)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label" title="Share of picks with positive CLV.">% positive</dt>
                  <dd>{pct(dq.clv.pctPositive)}</dd>
                </div>
              </dl>
            </div>
            <div className="bv-card p-4">
              <h3 className="mb-2 text-sm font-semibold">Timing</h3>
              <dl className="space-y-1">
                <div className="flex justify-between">
                  <dt className="bv-stat-label" title="Share of picks taken at or above the opening line.">≥ open</dt>
                  <dd>{pct(dq.timing.pctAtOrBetterThanOpen)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label" title="Share of picks with a better number than the close.">Beat close</dt>
                  <dd>{pct(dq.timing.pctBeatingClose)}</dd>
                </div>
              </dl>
            </div>
          </div>
          {dq.factors.length > 0 && (
            <div className="bv-table-wrap mt-3">
              <table className="bv-table">
                <thead>
                  <tr>
                    <th>Factor</th><th>Your n</th><th>Your hit%</th>
                    <th>Ledger hit%</th><th>Weighting</th>
                  </tr>
                </thead>
                <tbody>
                  {dq.factors.map((f) => (
                    <tr key={f.key}>
                      <td>{f.label}</td>
                      <td>{f.n}</td>
                      <td>{pct(f.yourHitPct)}</td>
                      <td>{f.ledgerHitPct == null ? "—" : pct(f.ledgerHitPct)}</td>
                      <td>
                        <span className="bv-pill">
                          {f.weight === "even" ? "balanced"
                            : f.weight === "under" ? "use well"
                            : "over-lean"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
```

Add a `pct` formatter near the top of the file (module scope, after imports):

```tsx
const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${v.toFixed(1)}%`;
```

> If `page.tsx` already defines a `pct`/percentage helper, reuse it instead of adding a
> duplicate. Keep green/red out of these chips — `.bv-pill` is the neutral/cyan style;
> green/red are reserved for under/over outcomes only (CLAUDE.md).

- [ ] **Step 3: Verify compile + lint**

Run: `cd web && npx tsc --noEmit && npm run lint`
Expected: tsc exit 0; lint clean.

- [ ] **Step 4: Commit**

```bash
git add web/app/ledger/page.tsx web/app/globals.css
git commit -m "feat(dq): render Decision-quality section in the Ledger view

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: End-to-end verification in the week-sim

The metric logic is unit-tested; this confirms the page renders against a real Postgres
with real-shaped data (the project's standard verification, per CLAUDE.md week-sim).

- [ ] **Step 1: Full test sweep**

Run from repo root:
```bash
source .venv/bin/activate && python -m pytest -q          # expect all green (154 + new DQ tests)
ruff check .                                               # clean
cd web && npx tsc --noEmit && npm run lint && npm test     # all clean/pass
```

- [ ] **Step 2: Render in the week-sim**

Boot the sandbox + replay a week with graded picks, then open `/ledger`:
```bash
python scripts/simulate_week.py --help    # confirm flags, then replay a real past week
```
Point `web/.env` `DATABASE_URL` at the sandbox PG (the commented sim line), start the
dev server, and load `/ledger`. Confirm the Decision-quality section renders: the three
stat cards populate from the sim's graded picks; the per-factor table appears only if
those picks carry `factors_json_at_pick` (sim picks won't unless re-logged through
`createPick` — the empty-state copy is expected otherwise). Restore `web/.env` to Neon
when done.

- [ ] **Step 3: Screenshot proof + final commit if any fixups**

Capture the rendered section. If Step 2 surfaced fixes, commit them with a clear message.

---

## Self-Review Notes

- **Spec coverage:** beat-my-model (Task 5), CLV (Task 6), timing (Task 7), per-factor
  over/under-weight (Task 8), render in existing Ledger (Task 9), migration + snapshot +
  grade enrichment (Tasks 1–3), TS test infra (Task 4), e2e (Task 10). All spec sections
  mapped.
- **Forward-only per-factor:** handled by the empty-state + `factor_ledger` try/guard
  (Task 8 Step 5, Task 9 Step 2).
- **Type consistency:** `DqPickRow`, `Bucket`, `tally`, `FactorAttribution`, `LedgerRates`
  defined once (Tasks 5/8) and reused; `beatMyModel`/`clvSummary`/`timingSummary`/
  `perFactorAttribution`/`getDecisionQuality` names consistent across tasks and the page.
- **Green/red discipline:** DQ chips use `.bv-pill` (neutral/cyan), not outcome colors.
- **score.ts↔score.py sync:** DQ reuses `parseFactors` + `BoardFactor.color === "green"`;
  no new green-state definition introduced.
