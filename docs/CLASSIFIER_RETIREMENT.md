# Retiring the classifier and the Under Score — plan (execute after 2026-09-19)

**Decision (Tate, 2026-09-15): retire it, after week 3, not before.** This is the
plan; nothing here has been changed yet.

## Why

- `under_score` **gates nothing**. `card.py::build_item` reads it only to freeze onto
  the paper pick; the tier, the rank and the kill line are the gap alone.
- The 2026-09-06 post-mortem (`POST_MORTEM.md`, `score_gate`): 48.9% under at score
  ≥ 60 against 49.0% below 47 — it does not separate outcomes.
- **Its training label reads a mutable column.** `features.py:599-607` computes
  `proxy_line` from `games.spread`, the last-captured spread, and labels
  `under = first_half_total < proxy_line`. `lines.py:146-153` documents that reading
  `games.spread` historically is the look-ahead trap. Every classifier hit-rate in
  `backtest/engine.py` rests on it.
- It costs a `HistGradientBoostingClassifier` fit on every `score_slate` call and a
  column on every surface, and `GLOSSARY.md` has to keep explaining that "50" is not
  break-even.

## What goes

| Piece | Where | Action |
|---|---|---|
| Classifier fit + `under_probability` | `beatvegas/model/score.py` (`score_slate`), `backtest/engine.py::_new_model` | remove the fit; `under_probability` and `under_score` become NULL on new `predictions` rows |
| `under_score` on the card | `card.py::build_item` → `build_card.log_paper_picks(model_score=…)` | drop the field; `model_score_at_pick` stays NULL going forward (legacy rows keep theirs) |
| Model ledger | `scripts/grade.py::is_model_bet`, `grade_model`, `MODEL_BET_THRESHOLD` | retire the "Model 1H" `Result` rows; the Results page's Model card goes with them |
| Parity constants | `model/score.py::MODEL_BET_THRESHOLD`, `web/lib/verdict.ts::MODEL_BET_THRESHOLD`, `tests/test_gate_parity.py` | delete on both sides in one PR (the parity test enumerates every numeric export in `verdict.ts`) |
| Web | `verdict.ts` (`underScore` input), `homeBoard.ts`, `records.ts` (`under_score` column + CSV), `proof.ts`, `GLOSSARY.md` "Under Score" entry | remove the input and the column; the records CSV loses `under_score` |
| Docs | `BV_LINE.md`, `PROJECT_BRIEF.md`, `GLOSSARY.md`, `BETTING_POLICY.md` | strike "secondary lean" and the 0–100 index |

## What stays

- `data/multiplier.json` (the step proxy) — still used to **grade** history where no
  real line exists (`postmortem.py`), not to label a model.
- `proxy_line` in the feature frame only if something still reads it after the
  classifier is gone; otherwise it goes too (it is the leak-shaped column).
- `game_records.under_score` and `predictions.under_score` **columns** — legacy
  rows keep their values; no destructive migration.

## Order

1. Branch after the week-3 grading lands (Mon 09-21 at the earliest).
2. Python first: remove the fit and the model ledger; run `pytest` (expect the
   classifier tests to be deleted, `test_gate_parity` updated).
3. Web second: drop the input/columns; run `vitest`, `tsc`, then `test_gate_parity`
   again (it reads `verdict.ts` by regex).
4. Docs + glossary in the same PR; `tests/test_docs_parity.py` guards the constants.
5. Verify on the live site: Results shows no Model card, `/proof/records` CSV has no
   `under_score` column, a game page still renders the decision block unchanged.

Blast radius on the money path: **none** — no gate reads the score today. Blast radius
on the display: the "Model 1H" record card and the score chip disappear.
