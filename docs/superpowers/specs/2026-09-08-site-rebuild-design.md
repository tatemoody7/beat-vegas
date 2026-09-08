# Part 2 — Website audit + "bet this weekend" rebuild (started 2026-09-08 Tue ~2:30pm ET)

## Context
Tate opened the PR #76 preview and said he cannot understand or trust much of the site.
He wants: a first-time-reader audit with every sentence rewritten in plain English, a more
polished look, red/green grading back, and a board that is graded all week (Thu/Fri games
before they kick, results the next morning), driven by the real schedule. He answered ~20
questions (below). Deadline he set: **everything live before Thu Sep 10 evening** (first
kick 7:00pm ET). Real money now starts **this weekend, Sep 12** (was Sep 19).

## Verified facts (2026-09-08)
- Week 2: 56 FBS games with a full-game total; first kick Thu 9/10 23:00Z, last Sat night.
- `odds_snapshots` for week 2: 1H totals from **Fliff only (19 games)**, last captured Mon
  3:46am ET. Full-game totals from 20 books incl. `hardrockbet` (39 games), Sun 6:15pm ET.
- Live Odds API check (2 credits): Oklahoma@Michigan has 1H totals at FanDuel 21.5 -110,
  DraftKings 22.5 -105, Fliff 21.5 -125; **Hard Rock none yet**. So "lines are out" is
  true for the market, not for Hard Rock, and our board is 1.5 days stale.
- Zero `predictions.bv_line` for week 2: the model needs both teams at 2 games played.
- Odds API header: `x-requests-remaining: 55799` on a plan bought 9/6 — flag to Tate.
- Schedule today is Saturday-shaped (explorer report): card.py drops kicked-off games;
  `CARD_STATUS_BY_SLOT.friday = preview`; `getLatestCard` newest-row; `cardHealth`
  hardcodes Sat; `need_sweep` UTC-day/week-wide; grade.yml Monday only; weekly_update
  scores the week once on Sunday. The live board query is already dynamic and has a day filter.
- Web audit (explorer reports): score renders uncolored (scoreColor/scoreLabel dead since
  `f7033da`); tier cyan-only; `--text-dim` 3.7:1 fails AA everywhere; no right-aligned
  numeric columns; 6 radii / 10 font sizes / 12 badge strings / 2 amber systems; several
  false or inconsistent statements (board intro "every game with a Hard Rock total"; price
  floor stated as "no worse", "2% vig", "-5%"; glossary card time "Sat 11am" wrong; "coin
  flip" vs "breakeven" at 50; Gap vs Edge naming; 3-4 duplicate label maps; raw enums shown;
  repo paths shown; What-to-change flags duplicated twice on Results).

## Tate's decisions (do NOT re-ask)
1. Grade = colored 0–100 score: **70+ green (bet), 55–69 amber (watch), <55 red (pass)**;
   same colors for settled outcomes; BET/EDGE/PASS may remain as small words; EDGE→"Watch".
2. Strong-but-blocked game keeps its color + plain tag ("Not yet — Hard Rock has no line").
3. Audience: Tate + a couple of friends, but **explain everything; assume nothing**.
4. First screen: today's/this week's games, graded, grouped by day. One rolling board;
   each game locks at kickoff. No per-day card artifacts.
5. Model minimum lowered to **1 game played**; early-season tag on those rows.
6. Sweep the whole week's 1H lines **every morning Tue–Sat 8am ET** (~115 credits each).
7. Score/gap basis: **Hard Rock → market consensus → reference line**, stated in words.
8. Real-money BET still needs Hard Rock's own line; slip shows the target and blocks.
9. Grading daily (morning after each game day) + Monday full pass.
10. Results + Research stay; every sentence rewritten. Honesty caveat said **once** ("How
    much to trust this") + one line on the board.
11. Cut: old under score (classifier), Kelly advisory, factor tier headings, Model runs
    table, Candidate trends.
12. Look: "dark sportsbook, denser" — keep navy+cyan and card structure, fix contrast,
    align numbers, one badge/radius/type system.
13. Order: everything before Thursday evening (Tate's call; staging below limits the risk).
14. **Score rescaled so gap 1.75 = 70**: score = 50 + gap × (20/1.75) (≈11.43/pt); 3.0 gap → 84;
    green always means the gap rule passed. Replace `EDGE_SCORE_MIN=60`; `CONTEXT_CAP` /
    `PRICE_ONLY_CAP` stay below 55 so no-model rows can never read green.
15. **Phone order**: graded game list first; slip below with a sticky "Slip · n of 5" bar.
16. **Week-2 stake stays $10 flat**; early-season tag + 5-bet cap are the protection.
17. PR #76 (DEGRADED) is the base for all of this; Tate has opened its preview. Merging it is
    step 0 of this plan (approving the plan approves that merge).

## Workstreams

### B. Web grading colors, basis tags, design system (planner output, condensed)
Corrections found: `homeBoard.ts:237` already has `GapBasis` + `GAP_BASIS_LABEL`; basis is
computed twice (`edge.ts:159` ungated vs `homeBoard.ts:420-428` nulled when no model) — collapse
to one. `lib/score.ts` scoreColor/scoreLabel/buildChips dead + untested. `lib/kelly.ts` used only
by LogPickForm. ~11 label maps to fold into one.
1. **Tokens only** (`globals.css:3-39`): `--text-dim #8b98b0` (5.96:1), `--text-muted #aab6cc`,
   `--border #3a4a6b`, `--border-strong #55688f`; NEW `--good #3ddc84`, `--warn #f0b04a`,
   `--bad #f87171`, `--push #8b98b0`; alias old `--under-strong/--neutral/--over-lean/--over`
   to them until step 8; one amber system (`--warn-bg/--warn-border`); 3 radii `--r-sm/md/lg`;
   6 type sizes `--fs-*`; remove body grid + glow; `.bv-card[data-interactive]` hover; delete dead
   classes; add `.bv-num` (right-aligned tabular) and `.bv-badge` (+ `--solid|good|warn|bad|neutral|accent`)
   and `.bv-day-head` (sticky).
2. **`lib/labels.ts`** (new, tested): BLOCKER_TEXT/SHORT, SLIP_BLOCK_TEXT, REASON_TEXT,
   GATE_TEXT, CARD_INPUT_TEXT, LINE_SOURCE_TEXT, RULE/PROXY/SEVERITY/TIER_TEXT, `labelOf()`,
   `blockerTag(blocker, ctx)` ("Not yet: price -125, needs -115"), `basisPhrase(lineBasis, books)`.
   Delete the duplicates in weeklyReview.ts, postmortem.ts, betSlip.ts, PicksList, LogPickForm,
   PostMortemPanel; repoint `weeklyReview.test.ts:151,156`, `postmortem.test.ts:7,244,258`.
3. **`lib/grade.ts`** + **`ScoreBadge.tsx`**: `gradeOf(score)` 70/55; `settledOf(actual,line)`;
   `<ScoreBadge score settled size label/>` colour = settled ?? grade → `--good/--warn/--bad/--push`,
   never cyan; aria-label carries the word. Tests for boundaries 69/70, 54/55, push.
4. **Data plumbing**: `edge.ts` exports `LineBasis`, `EdgeResult` gains `gap` (gated) +
   `lineBasis` (ungated); `board.ts` BoardRow += `firstHalfTotal` (column exists);
   `homeBoard.ts` HomeGame += `lineBasis`, `basisBooks` (from `check.books`, non-HR non-exchange,
   top 2), `earlySeason` (form.n<=1 or prior_season or null form — verified vs `etl/form.py`),
   `settled`; `groupByDay()`; delete `GapBasis`. Tests updated/added.
5. **GameCard.tsx**: ScoreBadge replaces the plain number + TIER_STYLE; tags via `.bv-badge`
   (logged / over cap / kicked off / early season / blockerTag); settled → inline result line
   replaces action; single basis phrase; delete second basis pill (:577-587); WhySection flat
   (drop tier headings + `groupFactorBoard`); BookTable `.bv-num`; delete per-card caveats
   (:169,:206,:266,:392,:496). CardPanel TIER_CHIP → labels.
6. **page.tsx**: `groupByDay` with sticky Thu/Fri/Sat/Sun headers; ONE caveat line linking
   `/trust`; counts line in grade colours; phone order title → trust line → filters → day groups
   → slip → bankroll → card, with a phone-only sticky `Slip · n of 5` bar (`#bet-slip`) when a
   row is open. **Judgement call to confirm with Tate: slip below the score list on phones.**
7. **Removals**: under score UI (records Score col + legend, PicksList modelScore, PostMortemPanel
   under_score table, glossary term); Kelly (LogPickForm + `lib/kelly.ts` + test + `fairUnder`
   prefill); Research "Model runs" + "Candidate trends" (+ `getModelRuns`, `lib/trends.ts`);
   dead `lib/score.ts` functions; fix `globals.css:22` comment.
8. **Sweep**: `.bv-num` on every numeric th/td (results, PicksList, research, records,
   LineStudyView, PostMortemPanel, BookTable); raw enums → labels (PicksList gate,
   CardStatusBanner inputs, LineStudy source, PostMortem bucket); outcome colours → tokens incl.
   LineStudyView hexes; new `app/trust/page.tsx` + nav tab "Trust"; Archivo on day heads + big score.
Verification: tsc + vitest + lint + prettier; 1280 and 375 screen checklist (13 items) in planner
output — day headers, coloured scores, blocked tag on a green, one caveat line, right-aligned
numbers, no raw enums, no cyan on grades, no grid/glow, phone order + sticky slip bar, reduced motion.

### A. Schedule-driven pipeline (planner output, condensed; verified in Neon)
Facts: wk2 = 56 games w/ FG total, **39 in the Hard Rock universe** (site shows only games with
an HR full-game snapshot); wk2 predictions are 36 `derived_lines` rows, bv_line NULL; min_games=2
clears 2/56 games, **min_games=1 clears 56/56**; ET days: Thu 1 game (FAMU@Miami 8pm, **0 HR → not
on board**), Fri 5 (3 HR, 7–8pm), Sat 50 (36 HR); no Sun/Mon games wks 2–13. Engine = bv_line
(market-blind, weekly features) and `homeBoard.ts:420-449` already computes gap live → **daily
builds need fresh LINES, not fresh scoring**; card.yml's residual re-score step is a no-op today.
1. **Min games 1**: `scripts/weekly_update.py:286` default 2→1; `beatvegas/model/score.py:61`
   MIN_GAMES_FOR_MODEL 2→1 (+comment); `web/lib/verdict.ts:40` 2→1 (`tests/test_gate_parity.py:29`
   asserts parity); reword `verdict.ts:162`, `page.tsx:137`. Do NOT touch `score.py:378` /
   `features.py:363` (training paths). **Early-season data**: append `"h_games_played",
   "a_games_played"` to `CONTEXT_NUMERIC_KEYS` (`score.py:137-152`); features already carry them
   (`features.py:259`, prior games, leak-free) → web `earlySeason = min(h,a) < 2`.
   Rollback = revert 4 constants + `DELETE FROM predictions … week=2 AND model_version='gbm_v1'`
   + re-dispatch post-lines.yml.
2. **Re-score week 2 today** (after PR #76 + step 1 merge): `gh workflow run sunday.yml` (openers →
   pace → weather → weekly_update → post_derived_lines; detect_week → 2; ~3 credits), verify
   56 gbm_v1 rows with bv_line; then `gh workflow run card.yml -f slot=manual -f season=2026
   -f week=2` (~120 credits; `slot=morning` once step 6 lands). Verify 1H snapshots by book using
   `greatest(captured_at,last_seen_at) >= today` (unchanged lines only bump last_seen_at) and the
   newest `cards` row `model_read=true`.
3. **Best available line = compute live, don't store** (already the ladder in homeBoard.ts).
   Fixes: (a) `homeBoard.ts:429-431` drop the `line_kind !== "derived_fg"` term from `hasModel`
   and redefine `derived` (:396) as `check?.hrLine == null && row.curLine == null`, so rows scored
   off the FG total unlock when a real line posts; BET still needs `hrGap` (`verdict.ts:324`,
   `card.py:578-586`) — add a test: market-basis 3-pt gap → WATCH never BET. (b) `card.py:704-712`
   add `"gap_basis"` next to `"gap"`; `card.ts` CardItem/parseCardItem additive. (c) `noModel`
   banner → replace trigger with per-game earlySeason.
4. **Daily grading** = cron-only: `grade.yml:26-28` → `30 10 * * *` (6:30am EDT) + `0 16 * * *`
   (noon EDT); grade.py is season-wide, idempotent, 0 Odds credits; 10:30Z avoids the
   `neon-writers` queue (GitHub cancels the older pending run when a third arrives). Update
   header comment + `docs/BETTING_POLICY.md:158`.
5. **Retire `lines_watch` opener crons** (`:50-52`: `0 18 * * 3`, `0 14,20 * * 4`,
   `0 12,16,20 * * 5`; −240/wk), keep the 4 close crons + the `1h_open` dispatch case. Land WITH
   or AFTER step 6, never before.
6. **`morning` slot** (`beatvegas/ci.py`): SWEEP_ARGS `"morning": "--hr-universe --hours-back 0
   --days-ahead 6"`; CARD_STATUS_BY_SLOT `"morning": "final"` (final = decision build for every
   game kicking before the next build); PAPER_WINDOW_HOURS `"morning": 24.0` (not 30 — one
   decision build per game); CRON_SLOTS → `5 12`, `35 12`, `5 13`, `35 13 * * 2-6` all
   `("morning", None)`; rename SATURDAY_GATE_ET/RETRY → MORNING_* (same 7:45–9:15 / 7:30 values),
   `if slot == "morning"` at :119; force_sweep += morning (:141); force_preview = morning|saturday
   (:143). Keep weeknight/friday/saturday as dispatch-only slots (no crons) so types/tests hold.
   card.yml: 4 crons + header rewrite; `test_workflows.py` cron==CRON_SLOTS passes automatically;
   rewrite `tests/test_ci_slots.py:17-70` for morning + DST table + Monday unmapped.
   Rehearse: `gh workflow run card.yml --ref <branch> -f slot=morning -f season=2026 -f week=2`
   and again `-f max_credits=20` to prove the degraded path.
7. **card.py kicked-off dropping: keep** (card = actionable, board = whole week with locks; cap
   carryover already correct via `real_bets_this_week`). **`web/lib/card.ts:394-460` cardHealth**:
   replace the Saturday branch with "built today (ET)" (`etDay(builtAt) !== etDay(now)` → warn
   "this morning's build has not landed"); preview/manual warn any day; drop STALE_CARD_HOURS +
   weekdayET; rewrite `card.test.ts:928-1000`.
Credits after: morning sweeps 600 + FG refresh 20 + closes 300 + Sunday 9 ≈ **930/wk (≈4K/mo)**,
worst ≈2.4K/wk; net +130/wk vs today. Landing order: #76 → step1 → dispatch (live model today) →
3a/3c → 3b → grade crons → morning slot → opener removal → cardHealth. Each step revertible alone.
Risks: `need_sweep` captured_at-based (harmless with force_sweep); neon-writers contention;
Hard Rock may not post 1H until Fri → no BET reachable until then, by design; one-game features
are noisy (early tag + cap; stake stays $10 per decision 16); week 1 has no predictions (ledger
starts week 2).

## Step -1 — Worktree relocation — DONE 2026-09-08 ~3:40pm ET
Result: `git worktree list` = `Beat Vegas` (main, detached), `.claude/worktrees/gifted-feistel-2c3c42`,
`worktrees/bv-lane-b`, `worktrees/bv-season`, plus new `worktrees/pr-17-week-board`
(`ops/pr-17-week-board` off `8f3b7ce` = #76 merged). Deleted: bv-lane-d, bv-openers,
beat-vegas-postmortem, bv-lane-c (its `web/.env` saved to the scratchpad as `bv-lane-c-web.env`),
branches `fix/postmortem-real-write` + `web/pr-16-intro-collapse`, stray `.claude/worktrees/
determined-roentgen-d499bc`. `worktrees/` added to `.git/info/exclude`. `launch.json` now has
`web`, `web-season`, `web-degraded` pointing at the new paths (web-slip removed). Dev server
`web-degraded` stopped. Part 1 paths above (`~/Desktop/bv-*`) are historical.
Original plan text:
Target layout: `/Users/tatemoody/Desktop/Beat Vegas/worktrees/<name>`; add `worktrees/` to
`.git/info/exclude` (local, untracked; `.claude/worktrees/` is already there). Inventory (all
clean, 0 dirty files):
- **Delete** (merged): `bv-lane-d` (on `main`, PR #74 squash-merged), `bv-openers`
  (`fix/postmortem-real-write`, ancestor of main), `beat-vegas-postmortem` (detached, ancestor),
  `bv-lane-c` (`web/pr-16-intro-collapse`, PR #73 squash-merged; hosts the `web-slip` dev
  server + `web/.env` → sim DB: `preview_stop` the server first, copy `web/.env` to the
  scratchpad for reference). Also prune `.claude/worktrees/determined-roentgen-d499bc` if it is
  a stale dir (only `gifted-feistel-2c3c42` is registered). Commands: `git worktree remove
  <path>` (+ `--force` only if it refuses on ignored files), then `git worktree prune`,
  `git branch -d` the merged local branches.
- **Move**: `bv-lane-b` (PR #76, open) and `bv-season` (PR #75 squash-merged — Tate chose to keep
  it; can be removed later). `git -C "Beat Vegas" worktree move /Users/tatemoody/Desktop/bv-lane-b
  "worktrees/bv-lane-b"` etc. Then update every path reference: this plan file,
  `.claude/launch.json` entries `web-slip`/`web-degraded` (point at
  `worktrees/bv-lane-b/web`), memory files (`concurrent-sessions-shared-checkout.md`,
  `beat-vegas-system-review-2026-09-07.md` lanes), and the Browser pane / pg_sim notes.
- New worktrees for PRs 17–19 are created under `worktrees/` from the start
  (`git worktree add worktrees/pr-17-week-board -b ops/pr-17-week-board origin/main`).
- Verify: `git worktree list` shows only `Beat Vegas`, `.claude/worktrees/gifted-feistel-2c3c42`,
  `worktrees/bv-lane-b`, `worktrees/bv-season`; `ls ~/Desktop` has no `bv-*` /
  `beat-vegas-postmortem`; `git status` in the main checkout shows no `worktrees/` entry.

## Execution schedule (Tue Sep 8 3:15pm ET → Thu Sep 10 evening)
Step -1 (worktree relocation) runs first, ~10 minutes.
Work in fresh worktrees off `origin/main` after #76 merges (never the main checkout). Three PRs,
each CI-green and, for web PRs, previewed by Tate before merge. Skill flow: write the spec
(`docs/superpowers/specs/2026-09-08-site-rebuild-design.md` = Part 2 of this file + the copy
tables extracted from the copy planner transcript) as the first commit of PR 17, then
writing-plans → implement with TDD per step.

**Tonight (Tue)** — PR 17 `ops/pr-17-week-board` (workstream A):
0. `gh pr merge 76 --squash --delete-branch`.
1. A1 min-games 1 + games_played factors → tests → merge → `gh workflow run sunday.yml` →
   verify 56 bv_line rows → `gh workflow run card.yml -f slot=manual -f season=2026 -f week=2`
   → verify 1H snapshots by book + newest card `model_read=true`. **Board shows model numbers
   and gaps tonight.**
2. A3 (hasModel/derived/earlySeason/gap_basis), A4 grade crons, A6 morning slot + ci tests,
   A5 opener-cron removal, A7 cardHealth "built today". Rehearse `-f slot=morning` and
   `-f max_credits=20` on the branch. Merge. Wed 8:05am ET is the first automatic morning build.

**Wednesday** — PR 18 `web/pr-18-grade-colors` (workstream B1–B6 + board/card copy from C):
tokens → labels.ts → grade.ts + ScoreBadge → plumbing (score rescale, LineBasis, basisBooks,
earlySeason, settled, groupByDay, EDGE→WATCH rename with parseItem mapping) → GameCard →
page.tsx (day groups, one caveat line, phone order + sticky slip bar) → CardPanel/BetSlip/
BankrollStrip/CardStatusBanner copy. Vercel preview → Tate checks 1280 + 375 → merge Wed night.

**Thursday** — PR 19 `web/pr-19-copy-and-cleanup` (C + B7–B8): /trust page + nav; Results,
Research, Records, Glossary rewrites; removals (under score UI, Kelly, factor tiers, Model runs,
Candidate trends, dead score.ts); `.bv-num` sweep; raw-enum sweep; outcome tokens. Also the
Python-side strings the copy planner flagged (`card.notes[]`, post-mortem flag text/bucket
labels, factor sentence fallback) get a pass in the same PR. Preview → Tate → merge by Thu
afternoon. **Fri 8:05am ET**: first morning build that can carry Hard Rock 1H lines; Tate bets
Fri/Sat from the slip.

If Thursday runs long, PR 19 splits: /trust + glossary + board-adjacent copy first, Research
tables second (Research is not on the money path).

## Verification (part 2)
- Python per step: full pytest + ruff (see part 1 command); `tests/test_ci_slots.py`,
  `test_workflows.py`, `test_card_degraded.py`, `test_gate_parity.py` green.
- Web: `npx vitest run && npx tsc --noEmit && npm run lint && npx prettier --check app lib`.
- Neon after each dispatch: the SQL in A2; after the first morning build: one `cards` row/day,
  `slot=morning status=final degraded=[]`; `gh run list -w card.yml -L 6` shows one success +
  skips.
- Browser (Tate present, he types the password): 1280 and 375 checklist from B — day headers,
  coloured scores with the 70/55 bands, a green with a "Not yet — Hard Rock has no line" tag,
  one caveat line → /trust, basis phrase in words, early-season tag, right-aligned numbers, no
  raw enums, no cyan on grades, no grid/glow, phone order + sticky slip bar, reduced motion.
- Copy: grep the built app for the banned words (`CLV`, `EDGE`, `under_score`, `BV line`,
  `docs/`, `slot=`, `proxy`, `Kelly`, `coin flip` outside /trust) → zero hits.
- Credits: read `credits_spent=` in the Wed/Thu/Fri card.yml logs; expect ~120/morning.
### C. Copy rewrite (planner output — FULL paste-ready tables live in the agent transcript
`/private/tmp/claude-501/-Users-tatemoody-Desktop-Beat-Vegas/ed26227b-0528-4e82-81b0-f51d104a4140/tasks/a68ec3168bfdd5b29.output`
— extract the final `result` block to `docs/superpowers/specs/2026-09-08-site-copy.md` as step C0)
- **Canonical vocabulary**: score · gap (never "edge") · our number · Hard Rock's line · the market
  line (DraftKings, FanDuel) · our reference line (from the full-game total) · line value (never
  CLV) · Watch (never EDGE) · kill line / kill price · paper pick · weekly cap. 50 = breakeven only;
  "coin flip" survives only on /trust.
- **Constants never typed in prose**: BET_GAP_PTS, STRONG_GAP_PTS, WEEKLY_BET_CAP, new
  `EV_FLOOR_PCT`, MIN_GAMES_FOR_MODEL (→1), BREAKEVEN_PCT, bankrollEnv unit/start, MOVED_PTS,
  new `SCORE_BET_MIN`/`SCORE_WATCH_MIN`, new `SIGMA_PTS`. Table of every current hard-typed site.
- **One label map** (`lib/labels.ts`): TAG + SHORT text for every blocker/reason enum incl.
  degraded input keys; sentence forms given.
- Page-by-page tables: layout/nav/login; board intro (2 sentences) + one caveat line; banners;
  CardStatusBanner in plain words; BetSlip (+ every block reason, typed and live); BankrollStrip
  (tooltips → visible lines); CardPanel; filters; GameCard collapsed + all `lib/edge.ts` action
  templates + killText + priceSentence + Model/Why/News sections; LogPickButton/Form; pickRules
  rejections; **/trust page (161 words)**; Results (49 rows); PicksList; PostMortemPanel (32 rows,
  drop "old 0.52" card + under_score table + repo-path footer); Research (26 rows: "Gap vs line
  value", line study, accuracy; delete Model runs + Candidate trends); Records; **Glossary: 15
  surviving terms, full bodies**.
- **10 strings whose text comes from Python/DB and needs its own pass**: `card.notes[]`
  (build_card.py), `PmFlag.text/code` and `postmortem_buckets.bucket` (post_mortem.py),
  `calib.segments[].label`, `dq.factors[].label`, `BoardFactor.sentence` fallback
  (`${f.label} — ${f.value}` leaks factor keys), `DegradedInput.detail`, Rotowire/ESPN text,
  user notes, `HARD_ROCK_URL` TODO.
- **Code the copy depends on**: MIN_GAMES_FOR_MODEL 2→1; `SCORE_BET_MIN=70`/`SCORE_WATCH_MIN=55`
  vs existing `EDGE_SCORE_MIN=60`/`PRICE_ONLY_CAP=55`/`CONTEXT_CAP=49` **disagree — score =
  50+10×gap puts a rule-passing gap of 1.75 at 67.5 (amber). DECISION NEEDED (asked below)**;
  export EV_FLOOR_PCT/SIGMA_PTS; rename tier EDGE→WATCH across edge.ts/card.ts/homeBoard.ts
  (Python payload still writes "EDGE" → map in parseItem); delete kelly; add /trust + nav link.
