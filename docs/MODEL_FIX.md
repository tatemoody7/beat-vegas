# H-MODEL-FIX — four fixes to the champion, tested together

**NOT MET (`study.yml` run 38070611660, 2026-10-10; one look, as registered).** With all four
fixes, the champion's first-half number was less accurate than the live champion's: about 0.16
points a game worse (95% interval +0.03 to +0.29), against a non-inferiority margin of +0.10. It
was worse in both test seasons. As the row registered, the live model stays. Tate (2026-10-10):
model work stops, and arms 1-3 start their clocks on the live model at the 2026-10-13 card.
Nothing live changed.

Registry: `docs/HYPOTHESES.md` H-MODEL-FIX (family `model-fix`, one comparison). Code: PR #351
(the study, with every switch off live).

## What was tested

One candidate, the live champion with all four of these changes:

1. **Bowl games out, means by date.** CFBD files every bowl as week 1, so the week-ordered
   season-to-date mean let a bowl into every later regular-season mean of its own season. That is
   a training leak: 836 bowls, 2003-25.
2. **Training from 2015 instead of 2003.**
3. **A seeded start of season.** Early-season averages are seeded with three games' worth of last
   season (`PRIOR_SEASON_WEIGHT` = 3).
4. **Early stopping off.** sklearn's `'auto'` setting stops the 2003+ champion early, because it
   trains on more than 10,000 rows.

## Provenance (Analysis Rules order)

- **Data.** Two frames were built on the runner (sklearn 1.9.1, Python 3.11).
  - Incumbent: fingerprint `ba8101d470e39b9f`, 17,072 rows, 2003-2026, bowls in.
  - Candidate: fingerprint `4908acd2463cc06e`, 8,115 rows, 2015-2026, regular season only; 2014
    was read for the seed and never became a row.
  - Each arm trained on its own frame's seasons before the test season (incumbent 2003-24 and
    2003-25; candidate 2015-24 and 2015-25) and scored the same game ids.
  - The report's "train seasons" block names the candidate's seasons only, because its frame is
    the harness's shared one.
- **Score pool.** 1,021 played FBS-vs-FBS regular-season games with a trusted first-half total:
  743 in 2025 and 278 in 2026, from week 1 through the 2026-10-09 games. Of these, 760 were graded
  at a real consensus `1H_total` close inside 2 h (622 and 138). No proxy row was graded;
  `min_games` 0.
- **Grading.** Actual = the trusted first-half total. The pick records are at a flat −110 at the
  consensus close. Sign: Δ = candidate minus incumbent, so a negative Δ means the candidate was
  more accurate.
- **Data already read.** 2025's closes were read for rule selection before; this row measures
  models on them (the H-HIST precedent).

## Accuracy (the primary test)

| | 2025 MAE | 2026 MAE | Pooled MAE | Pooled bias (pred − actual) |
|---|---|---|---|---|
| Live champion (incumbent) | 8.85 | 7.98 | 8.69 | −0.04 |
| Four fixes (candidate) | 9.02 | 8.10 | 8.85 | −0.01 |
| Consensus close | 8.90 | 7.89 | 8.72 | |

- **Paired change in absolute error:** +0.163 [+0.025, +0.294], p 0.016, n 760, against a margin
  of +0.10.
- **By season:** 2025 +0.17 [+0.03, +0.32] (n 622); 2026 +0.12 [−0.20, +0.47] (n 138).
- **Signed error:** −0.03 [−0.16, +0.10]. The candidate's numbers sat at the same level; they were
  noisier, not shifted.

## Beyond the test (reported, never gated)

- **Spread.** The candidate's numbers are more spread out: standard deviation 2.98, against 2.56
  for the live champion and 3.25 for the close. They also track the result less: correlation 0.18,
  against 0.24 and 0.26.
- **Far from the market.** The candidate was more than 6 points from the consensus close on 19 of
  760 games; the live champion on 8.
- **By the raw early-season projection.** The candidate was worse in 7 of 10 deciles of
  `proj_1h_total` (read from the incumbent's frame). In the top decile, the Georgia @ Alabama kind
  of game (projection 31.9-47.3), it scored 9.41 against 8.84.
- **By week, 2026.**
  - Weeks 1-3, where the seed acts: −0.14 [−0.65, +0.42] (n 61).
  - Weeks 4-6: +0.33 [−0.14, +0.74] (n 77).
- **Picks** (the H-HIST shape: top 20% of each slate by gap, cap 5, flat −110 at the consensus
  close).
  - Portfolio units per game: −0.014 [−0.044, +0.014], not distinguishable.
  - Cap 5: live champion 50-34 (+11.5u), candidate 41-43 (−5.7u).
  - Top 20%: 85-67-1 (+10.3u) against 80-73 (−0.3u).
  - These are 84- and 153-pick records whose intervals span break-even; they are never quoted as
    an edge.

## A flaw in the comparison, and why it does not change the verdict

The incumbent was built the way the live champion trains: bowls in, means in week order. So its
2025 test games also saw the 2025 bowls, which are filed as week 1 and played in December. That is
information the live model never has when it scores a season, and it favours the incumbent on 2025.
It does not explain the result:

- On 2025 games of a bowl team from week 2 on, the candidate was worse by +0.15 [−0.00, +0.31]
  (n 540).
- On the 2025 games the bowls could not touch, it was worse by more: +0.34 [−0.01, +0.71] (n 82).
- 2026, which has no bowls yet, points the same way (+0.12).

This was found after the run, from the run's own per-game file. It is disclosed here and changes
nothing.

## What this does and does not say

- **It says** the four changes together made the champion's first-half number less accurate in
  2025 and 2026, and took it further from the market more often.
- **It does not say** which change did it.
  - H-HIST had already measured a 2015 floor as accurate as 2003 (`docs/HISTORY_DEPTH.md`), so the
    floor alone is the least likely cause.
  - Separating the other three would mean more looks at the same games, and Tate stopped model
    work instead.
- **The bowl leak stays** in the live model's training. It is now documented and measured: taking
  it out, together with the rest, did not help.
- **The live champion is level with the market's close** on these 760 games: 8.69 against 8.72.

## Decision (Tate, 2026-10-10)

- **The live model stays:** the 2026-10-07 champion, 2003+ with the #344 leak fixes. Arms 1-3
  start their clocks at the 2026-10-13 card on the 2026-10-11 refit; `protocol.ARMS_START` is set
  after that card runs.
- **PR #351 keeps the study re-runnable, with every switch off live:**
  - `PRIOR_SEASON_WEIGHT` 0;
  - `CHAMPION_TRAIN_MIN_SEASON` 2003;
  - `build_feature_frame(model_fix_candidate=False)`;
  - early stopping stated as `'auto'`, which is sklearn's default and leaves the model unchanged.

  Each weekly refit now records in `model_runs.metrics` how many trees it grew and its
  early-stopping setting.
- **Effort moves to market rules:** first H-ARM-HT1H (paper first-half unders when the consensus
  full-game total is 60 or more), then a slot-4 design note.

## Reproduce

`gh workflow run study.yml --ref main -f script=model_fix_study`. The arms pin their settings in
`beatvegas/backtest/model_fix.py`, so a rerun measures the same two models whatever the live
defaults become. The frames are rebuilt from the live database, and their fingerprints name what a
rerun saw. A rerun is a second look and goes in `comparisons run`.
