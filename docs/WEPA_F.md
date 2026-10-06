# H-WEPA-F, ARM R — dated in-season WEPA against the champion's 2025 residual: tested, null

**Run 2026-10-06 (`study.yml` run 37491506377, `harness_H-WEPA-F_20261006T155546Z`). Verdict:
NOT MET.** Neither sub-arm lowered the champion's paired per-game error; both sit above the
market's accuracy, as the champion does. Nothing changes: the champion, the bar, the stakes and
H-STOP-2 are untouched. ARM P (the 2026 WEPA shadow engine `bv_wepa_f`) is **not licensed** by
this result — the row's text: "a FAIL closes the WEPA question for the 2026 engine". Any future
WEPA engine is a new row with a new question, not a re-run of this one.

Registry: `docs/HYPOTHESES.md` row H-WEPA-F (status `tested-null`). One dispatch, one look.

## What was asked (the row, written before the run)

Does dated in-season WEPA — CFBD's opponent-adjusted efficiency, frozen each Sunday "through
week N−1" in the Patreon weekly files for 2025 weeks 5-15 — explain the champion's first-half
residual (actual − `bv_line`) against the real consensus close in 2025, learned walk-forward
within the season? Two declared sub-arms: `wepa_epa1` (one ridge slope on the adjusted-EPA
composite) and `wepa_k4` (ridge on the EPA, success, explosiveness and line-yards composites),
each fitted for week k only on 2025 rows with week < k. PASS required a lower paired |error|
(bootstrap 95% interval excluding zero, Holm across the two sub-arms) AND close-graded
portfolio units not lower than the champion's.

## Provenance (Analysis Rules order)

- **Data source and n**: the harness feature frame built on the runner (`fbs_only`,
  `min_games 0`): 2586 rows, by season {'2023': 736, '2024': 732, '2025': 744, '2026': 374}; test season 2025 scored by one
  model trained on 2023-2024 (2,479 played rows). 744 trusted 2025 rows; **622 graded** at a
  real consensus 1H close inside 2 h of kickoff (`lines.real_closes`); 572 with a `fri_pm`
  decision line. WEPA rows: `data/wepa_2025_weekly_z.csv` (561 games, weeks 5-15; 48 columns
  z-scored within each weekly file; provenance sha256 in `data/wepa_2025_weekly_z.meta.json`).
- **Grading rule**: `trusted_first_half_total` vs the consensus close; under at a flat −110;
  top 20% of each slate by gap (`slate_bar`), cap 5 — the champion's rule, applied unchanged to
  every arm. The EV/price gate is not reproduced (no book prices in the history).
- **Line source**: consensus close (zero `hardrockbet` 1H rows exist for 2025 — the declared
  substitution). Price provenance: none (no price CLV is reported here).
- **Proxy rows**: none. Every graded row has `line_real` (a captured close inside the window).
- **Sign convention**: Δ|err| negative = candidate more accurate; "favourable CLV" positive =
  the market moved toward the pick. Hand check: `wepa_epa1` bias +0.04 vs the champion's +0.53
  (pred − actual), so the correction removed the level error and nothing else.
- **Frame fingerprint**: `see harness_H-WEPA-F_20261006T155546Z_frame.json` (sklearn
  1.9.1, Python 3.11.16, Linux x86_64 runner; generated 2026-10-06T15:55:56.878098+00:00).
  The report triple (`.md`, `.json`, `.csv`, `_frame.json`) is the `study-harness_report`
  artifact of run 37491506377 (`reports/harness_*` is gitignored).

## Result

Market benchmark, 2025, n 622: close MAE 8.90, bias (actual − close) +0.92; blanket under
298-316-8 (48.5%, −45.1u).

| Arm | MAE | bias (pred − actual) | pct picks W-L-P | hit % [95%] | units | cap-5 W-L | cap units |
|---|---|---|---|---|---|---|---|
| champion (`bv_line_for_slate`) | 9.14 | +0.53 | 68-56-2 | 54.8% [46.1, 63.3] | +5.82 | 33-29 | +1.00 |
| `wepa_epa1` | 9.11 | +0.04 | 66-56-3 | 54.1% [45.3, 62.7] | +4.00 | 35-27 | +4.82 |
| `wepa_k4` | 9.15 | +0.03 | 65-58-2 | 52.8% [44.1, 61.4] | +1.09 | 37-25 | +8.64 |

Paired on the game (candidate − champion), bootstrap n 2000:

| Candidate | Δ \|err\| (− = more accurate) | Holm p | Δ signed err | Δ portfolio units / game |
|---|---|---|---|---|
| `wepa_epa1` | -0.034 [-0.121, +0.050] p=0.455 | Holm 0.910 | +0.490 [+0.408, +0.570] | -0.003 [-0.020, +0.014] p=0.723 |
| `wepa_k4` | +0.008 [-0.109, +0.122] p=0.916 | Holm 0.916 | +0.495 [+0.375, +0.608] | -0.008 [-0.024, +0.011] p=0.390 |

- The one thing WEPA did was fix the LEVEL: the champion under-predicts 2025 by 0.53 pts and
  both corrected arms read +0.04 / +0.03. That is the B-SERVE lesson again — a level fix is
  not an accuracy fix (MAE 9.11 / 9.15 vs 9.14; the market 8.90).
- Pick overlap with the champion: Jaccard 0.77 on the pct selection (109 shared / 16 / 17).
  Favourable line value is NEGATIVE for every arm (−0.14 to −0.16 pts, p ≤ 0.016): on 2025's
  historical frame the close moved AWAY from the picks, champion included — the same reading
  as `docs/SYSTEM_REVIEW_2026-10-04.md` §1 for the historical seasons.
- Money population (≥ 2 games played): champion 60-54-2 (+0.55u), `wepa_epa1` 58-54-3
  (−1.27u), `wepa_k4` 57-56-2 (−4.18u). The lt2 slice (8-2) is identical across arms (no WEPA
  before week 5) and is not evidence.
- Overfit controls: deflated Sharpe champion 0.639, `wepa_epa1` 0.575, `wepa_k4` 0.465;
  PBO 0.80 over the three arms — the cap-5 edges of the candidates (+4.8u, +8.6u on 62 picks)
  are the kind of number PBO says not to read.

## What this does and does not say

- It says: with leak-free, dated, within-season-standardised WEPA, a linear residual correction
  on top of the champion carries no first-half accuracy information beyond the level in 2025.
  The pre-registered gate was not reached by either sub-arm, by a wide margin (Holm p 0.91).
- It does not say: that WEPA is useless as a training INPUT to a retrained engine (that needs
  dated history for the training seasons, which does not exist before 2025), or anything about
  CORE/Elo/FPI. Those are different questions and would be different rows.
- Decision for Tate: close ARM P as written (recommended by the row's own text), and let the
  weekly WEPA snapshot table (PR7) accumulate for a possible 2027 question with two dated seasons.

## Caveats (the harness prints these on every report)

One-shot. Consensus stands in for Hard Rock on 2025. The price gate is not reproduced. One fit
per test season, not the weekly refit. Selection uses the close's gap (no decision-time line in
the history). The frame drops played games whose 1H total equals the proxy line. 2023-25 is
exhausted for rule selection — this run measured, nothing here may pick a threshold. Weeks 1-5
and games absent from the files entered the paired test as zero differences (conservative).
