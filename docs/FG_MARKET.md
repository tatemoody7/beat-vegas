# H-FG-U-R / H-FG-O-R — a full-game-target regressor at the real full-game close, 2024-25

> **H-FG-P superseded 2026-10-07** (`docs/ROADMAP_2026.md`). The full-game unders arm restarts
> uncapped and judged on line value against the consensus close, under the 2026 Statistical
> Protocol; rows logged under H-FG-P are development evidence only. The study result below stands.

**Run 2026-10-06 (`study.yml` runs 37498128236 unders, 37498146230 overs; one dispatch each after
the data-cell correction of PR #284). Overs: NOT MET on every reading. Unders: the pre-registered
text was ambiguous between two selection sets and the readings disagreed; Tate ruled the same day
that the champion's rule includes the weekly cap, so the capped set is the selected set — MET
(`tested-positive`), **positive only on a reading chosen after the numbers were read (relabelled
2026-10-06, Tate's call); the qualifying-set reading fails. Quote it as a post-hoc positive.** That licenses one thing: registering H-FG-P, a 2026 PAPER arm of full-game
unders (row written below the result; the collector is PR5 of the program).** Nothing changes: the
champion, the bar, the stakes and H-STOP-2 are untouched; the full-game market stays a reference
ledger, never bet. A pass would license only a 2026 paper arm (H-FG-P).

Registry: `docs/HYPOTHESES.md` rows H-FG-U-R and H-FG-O-R (family `fg-market`).

## Why the harness printed no verdict

Both dispatches ran without a `--criterion` function, so the harness wrote "not evaluable (no
criterion function declared)" above the full report. The registered criterion is arithmetic on
the report's own record blocks (a Wilson 95% lower bound on the hit rate; units > 0 in both
seasons; Holm across the two rows). It is applied below BY HAND to the numbers the runner
produced, with the arithmetic shown. No re-dispatch: a second run is a second look.

## Provenance (Analysis Rules order)

- **Data source and n**: the harness feature frame built on the runner (`fbs_only`,
  `min_games 0`): 2,586 rows, by season 2023: 736, 2024: 732, 2025: 744, 2026: 374. Test seasons
  2024 (trained on 2023) and 2025 (trained on 2023-24); 1,476 trusted rows; **1,252 graded** at
  a real consensus `full_game_total` close inside 3 h of kickoff (`lines.real_closes`,
  `REAL_FG_CLOSE_WINDOW_H`): 623 in 2024, 629 in 2025. Zero Hard Rock full-game rows exist for
  those seasons, so the consensus close is the universe and the grade (the declared
  substitution). Zero decision lines (first-half only in v1), so no line value is reported.
- **Grading rule**: actual = `home_points + away_points`; the champion's own rule applied to a
  regressor fitted to that target (`model/fg_line.py::bv_fg_line_for_slate`, the same 58
  market-blind inputs): top 20% of each slate by gap (`slate_bar`), cap 5, flat −110; under
  gap = close − pred, over gap = pred − close. The price gate is not reproduced.
- **Line source**: consensus full-game close; price provenance none.
- **Proxy rows**: none (the frame's `full_game_total` column is a proxy column and no grade
  read it; `PROXY_COLS` is enforced).
- **Sign convention**: "Bias (pred − actual)" +1.43 in 2025 means the model's number sat 1.43 pts
  above the realized total; the unders rule prefers games where the CLOSE sits above the model.
- **Frame fingerprint**: `harness_H-FG-U-R_20261006T164553Z_frame.json` and
  `harness_H-FG-O-R_20261006T164651Z_frame.json` (rows 2,586; sklearn 1.9.1; Python 3.11.16;
  Linux x86_64 runner). Reports are the `study-harness_report` artifacts of the two runs
  (`reports/harness_*` is gitignored).

## The market, and the model's accuracy

| Season | n | close MAE | bias (actual − close) | blanket under | blanket over |
|---|---|---|---|---|---|
| 2024 | 623 | 13.01 | +1.45 | 48.0% (−50.6u) | 52.0% (−4.8u) |
| 2025 | 629 | 12.36 | +0.52 | 52.2% (−2.7u) | 47.8% (−54.3u) |

The full-game regressor is **less accurate than the close** (MAE 13.61 vs 13.01 in 2024; 13.27
vs 12.36 in 2025; pooled 13.44 vs 12.68) — the same relationship the first-half champion has to
Hard Rock. Bias (pred − actual): −0.09 in 2024, +1.43 in 2025.

## Records under the champion's rule

| Row | selection | n | W-L-P | hit % | Wilson 95% | Holm-2 lower (97.5%) | units 2024 / 2025 | pooled units |
|---|---|---|---|---|---|---|---|---|
| H-FG-U-R unders | qualifying (pct) | 250 | 138-107-5 | 56.3% | 50.1–62.4 | 49.2% | +7.91 / +10.55 | +18.45 |
| H-FG-U-R unders | cap 5 | 124 | 78-44-2 | 63.9% | 55.1–71.9 | 53.8% | +12.55 / +14.36 | +26.91 |
| H-FG-O-R overs | qualifying (pct) | 254 | 132-121-1 | 52.2% | 46.0–58.3 | 45.2% | +9.64 / −10.64 | −1.00 |
| H-FG-O-R overs | cap 5 | 127 | 66-61-0 | 52.0% | 43.3–60.5 | 42.1% | +5.73 / −6.73 | −1.00 |

Money population (both teams ≥ 2 games), qualifying selection: unders 124-100-4 (55.4%,
48.8–61.7, +12.7u); overs 120-109-1 (52.4%, 45.9–58.8, +0.1u). Deflated Sharpe (one arm):
unders 0.891, overs 0.474.

## Applying the registered criterion by hand

Criterion: (1) Wilson 95% lower bound of the selected picks' pooled hit rate > 52.4% AND (2)
units > 0 in both 2024 and 2025; Holm across the two rows (the surviving row is held to the
97.5% bound).

- **H-FG-O-R (overs): NOT MET on every reading.** Lower bounds 46.0% / 43.3%; 2025 units
  negative on both selections (−10.64, −6.73). The full-game over question for 2026 is closed
  with this verdict on file; the row's status is `tested-null`.
- **H-FG-U-R (unders): the row text does not say which set is "the selected under picks".**
  The data cell says "selection = the champion's rule unchanged: top 20% of each slate by gap,
  cap 5, flat −110". The harness reports two sets for that rule: the qualifying set (every game
  over the bar, `record_pct`, what H-WEPA-F's criterion used as `portfolio_units`) and the
  capped set (the five the champion would actually bet, `record_cap`).
  - Qualifying reading: lower bound 50.1% (49.2% Holm) → **(1) fails**; (2) passes.
  - Cap-5 reading: lower bound 55.1% (53.8% Holm) → **(1) passes**; (2) passes (+12.55, +14.36).
  The two readings disagree, and choosing between them after reading the numbers would be
  exactly what pre-registration forbids. As first written: **no verdict recorded**, the row kept
  `pre-registered`. [Superseded the same day: Tate ruled (a) below after reading this doc, so
  the row reads `tested-positive` WITH the post-hoc label -- the choice of reading came after the
  numbers, which is exactly the caution this paragraph stated, and the label keeps it visible.]

## What this does and does not say

- The 2023-25 history was already known to be favourable for full-game unders selected by the
  FIRST-HALF gap (post-mortem `fg` column: 53.8% / 61.2%). This run says the same direction holds
  when the regressor is fitted to the full-game total itself, on the capped set strongly, on the
  qualifying set weakly — on a set that is spent for rule selection and with a model that is
  less accurate than the close. Overs show nothing, as the first-half two-sided study found.
- It does not say anything about 2026 or about Hard Rock's full-game line (zero rows), and it
  carries no line-value reading.
- **Decision for Tate** (registered consequences, nothing automatic):
  (a) rule that "selected picks" means the capped set → H-FG-U-R `tested-positive`, which
  licenses REGISTERING H-FG-P (2026 paper full-game UNDERS into `challenger_picks`,
  `market='full'`, own bar, SPRT clocks with σ frozen from this report) — paper only, never money;
  (b) rule that it means the qualifying set → `tested-null`, question closed for 2026;
  (c) decline to rule and register H-FG-P as a measurement-only paper arm regardless, since paper
  costs nothing and the prospective record is the honest test either way.
  **Ruling (Tate, 2026-10-06, after reading this doc): (a).** The σ of per-pick units on the capped
  unders, frozen for H-FG-P's profit clock: 0.913 (n 124; the qualifying set reads 0.939 on n 250),
  from the per-game CSV of run 37498128236.

## Caveats (the harness prints these on every report)

One-shot. Consensus stands in for Hard Rock. The price gate is not reproduced. One fit per test
season, not the weekly refit. Selection uses the close's gap (no decision-time line). The frame
drops played games whose 1H total equals the proxy line, and `training_frame` keys on the 1H
total — full-game rows inherit both. 2023-25 is exhausted for rule selection — this run
measured; nothing here may pick a threshold.

## H-FG-P — the 2026 paper arm (collector shipped 2026-10-06)

Registry row H-FG-P (`docs/HYPOTHESES.md`, pre-registered). **Paper only**: real money stays
first-half unders; a pass is a finding, nothing more.

- **First build**: `cards.id` **TBD**, written here before any observation is read.
- **Engine**: `bv_fg_v1`, scored by `scripts/fg_shadow.py`. It runs after the champion in
  `sunday.yml` (continue-on-error) and by hand through `fg_shadow.yml`. Week 6 of 2026 is scored by
  hand, Tate's call. Each scoring run writes:
  - one `predictions` row per game, `model_version='bv_fg_v1'`;
  - one `model_runs` row noted `fg shadow refit`;
  - no GameRecord. The input vector rides in the row's `factors_json["features"]`.

  None of these rows can be read as the champion: every "the model's line" read uses
  `score.CHAMPION_READ_VERSIONS`, the allow-list from PR #293.
- **Collector**: `beatvegas/fg_paper.py`, switched on by `FG_COLLECT=1` in `card.yml`. At each
  decision build:
  - **Universe**: the week's games not yet kicked off whose newest Hard Rock `full_game_total`
    quote is centred (`devig.is_centred_quote`) and carries a line and an under price, with a
    `bv_fg_v1` read.
  - **Gap**: Hard Rock FG line − bv_fg.
  - **Bar**: `score.slate_bar`, top 20%, ties qualify.
  - **Cap**: 5 a week by gap (then kickoff, then away team). Rows logged earlier in the week hold
    their slots.
  - **Window**: the slot's paper window. A selected game outside the window waits, and its rank
    is kept.

  It writes one `challenger_picks` row per selected game: `arm='fg_under'`, `market='full'`,
  `side='under'`, Hard Rock's under price, `champion_line_at_pick` = the first-half champion's
  number (1H scale, for the paired diagnostic only). It runs inside a savepoint, so a failure
  never costs the real card. It never writes to `manual_picks`.
- **Grading**: `picks.grade_pick` via `grade_challenger_picks` (daily `grade.yml`). It grades
  against the final total, with the consensus full-game close and its last pre-kick confirmation
  time.
- **Position**: `scripts/fg_position.py` (also `study.yml` → `fg_position`). Constants are in
  `stopping.FG`.
  - The profit clock (σ 0.913) runs from the first graded row.
  - The line-value clock reports **not started** until its σ is frozen. It counts only closes
    confirmed inside 3 h.
- **σ freeze procedure (line value)**:
  1. After the second Saturday (2026-10-17), run `fg_position`. It prints the in-window
     (close − build line) moves and their sd.
  2. Write that sd here and into `stopping.FG["sigma"]["clv"]` in one PR, before the clock's
     first reading.
  3. Report the excluded share (no close inside 3 h) weekly.
- **Sandbox gate** (2026-10-06): the e2e fixture week was built twice with `build_card.py`, with
  `FG_COLLECT` unset and set.
  - The card payload hash was identical (`7fb76a4e6960a8bd`), and so were the champion's 9
    `manual_picks` rows and the neggap row.
  - The FG run added 5 `fg_under` rows: universe 12, bar 1.50, 12 qualify on a tied fixture.
  - A second build that week added 0, with 5 held.
