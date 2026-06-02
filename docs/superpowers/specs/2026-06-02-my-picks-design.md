# My Picks — writable pick logging (Phase C)

**Date:** 2026-06-02 · **Status:** approved, implementing

## Goal
Let the user log their own 1H-under picks in the web app and have them **stored
durably and graded** so the track record sharpens week over week — especially to
learn from losses. Picks are immutable history once graded; the Python engine
remains the grader. Decisions: pick only the **scored slate**; **snapshot the
model's score + line at log time**; capture a free-text reason note.

## Data model (Python owns the schema)
Add to `ManualPick` in `beatvegas/db/models.py` (+ idempotent `_apply_migrations`
ALTERs), then `prisma db pull` to re-introspect:
- `model_score_at_pick` (Integer, nullable) — model `under_score` when logged.
- `model_line_at_pick` (Float, nullable) — model `line_used` when logged.

Existing fields unchanged: `note` (the reason), and grader-filled `result`,
`units`, `clv`, `closing_line`, `graded`, `actual_first_half_total`. The web app
only ever writes the bet + snapshot; `scripts/pick.py grade` fills the rest.

## API routes (`web/app/api/picks/…`)
- `GET /api/picks?season=&week=` → user's picks for scope, joined to matchup,
  pending first then graded. Also returns the 3-way "You" `Record3` summary.
- `POST /api/picks` → `{ gameId, line, stake?, price?, note? }`:
  1. Load game (season/week/home/away) + its latest prediction (under_score,
     line_used).
  2. Insert `ManualPick`: `side='under'`, `placed_at=now`, `graded=false`,
     `model_score_at_pick`/`model_line_at_pick` frozen from step 1, defaults
     `stake=1.0`, `price=-110`.
  3. Return created pick.
- `DELETE /api/picks/[id]` → delete only while `graded=false` (fix mistakes);
  graded picks immutable (409 otherwise).
- Validation: `gameId` must be in the current scored slate; `line` required
  numeric. Duplicates on a game allowed (re-bet); all shown in history.

## UI (`web/app/picks/page.tsx`, nav entry "My Picks")
Server component loads scored slate + existing picks; renders:
- **Running record** at top (reuse Ledger `Record3`: hit% / W-L / units / avg CLV).
- **Log form** (client): game `<select>` (slate, labeled `away @ home · score NN
  · line X.X`); **line** input defaulted to game's current consensus line (else
  model line); **stake** (1.0u), **price** (−110), **note**. Submit → POST → refresh.
- **History table**: Wk · Matchup · Your line · Model@pick (frozen score/line) ·
  Result · Units · CLV · Note. Pending rows get a **Delete** action. This is the
  learn-from-losses surface.
- Empty slate → "no scored games this week."

## Reuse
`web/lib/ledger.ts` (`Record3`, the "you" record logic), `web/lib/board.ts`
(slate query/prediction), `web/lib/prisma.ts`. Python: `beatvegas/db/models.py`
ManualPick + `_apply_migrations`; grading stays in `scripts/pick.py`.

## Auth
No gate yet — the app-wide password gate (`middleware.ts`) is the next Phase-C
task and will wrap this write. Locally it's SQLite on the Mac.

## Verification
- Python `ManualPick` migration idempotent; `prisma db pull` picks up 2 new cols.
- Log a pick on demo.db via the form → persists across reload, appears in history
  with the model snapshot, running record updates.
- `DELETE` removes a pending pick; graded pick delete → 409.
- `POST` with missing `line` → 400. `npx tsc --noEmit` clean; `pytest` 56 green.
