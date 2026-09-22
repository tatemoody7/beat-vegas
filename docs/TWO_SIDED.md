# Two-sided diagnostic — does a negative gap carry over-side information?

**Verdict (pre-registered rule): NO OVER-SIDE FINDING.** Measurement only.
Nothing here changes a gate, a card or a bet. Run 2026-09-15 with
`scripts/two_sided_study.py --n-boot 2000` (`beatvegas/backtest/two_sided.py`
holds the arithmetic and the decision rule; `tests/test_two_sided.py` pins both).

## Why it was run

The system bets first-half unders when Hard Rock's number sits ≥ 1.75 points above
our own and never bets overs. Live week 2 showed the most-negative-gap quartile going
**over 12 of 13 times** — a hint at n=13, not a finding — and an external review
argued that an under-only architecture cannot express the opposite conclusion even
when the evidence says the line is too low. Tate's call: measure it first, in the
same form as the censoring study, before anything is proposed.

## The rule, written before the numbers were read

An over-side signal is claimed only when **all four** hold on the 2023–25 real-close
history (FBS vs FBS, decided games, real captured 1H close):

1. at least **100** decided games at gap ≤ −1.75;
2. the over rate there beats the −110 break-even, **52.38%**;
3. its **Wilson lower bound clears 50%** — a coin flip is excluded, not merely the
   point estimate;
4. the over rate is above 50% in **at least two of the three seasons**.

## What it found

**1,902 games** with a real captured close (1,873 decided).

| gap band (line − our number) | side it points to | n | under rate (decided) | Wilson 95% | side hit rate | follow-the-sign ROI at −110 |
|---|---|---|---|---|---|---|
| ≤ −3 | over | 423 | 44.3% | 39.6–49.1% | **55.7%** | **+6.2%** |
| −3 .. −1.75 | over | 284 | 51.6% | 45.8–57.4% | 48.4% | −7.5% |
| −1.75 .. −1 | over | 219 | 48.1% | 41.6–54.8% | 51.9% | −1.0% |
| −1 .. 0 | over | 274 | 51.7% | 45.7–57.5% | 48.3% | −7.6% |
| 0 .. 1 | under | 278 | **44.5%** | 38.8–50.4% | 44.5% | −15.0% |
| 1 .. 1.75 | under | 129 | 53.9% | 45.3–62.3% | 53.9% | +2.9% |
| 1.75 .. 3 | under | 174 | 54.9% | 47.5–62.1% | 54.9% | +4.8% |
| ≥ 3 | under | 121 | 58.8% | 49.8–67.3% | 58.8% | +12.1% |

**Symmetry at ±1.75:** gap ≤ −1.75 → **over 52.7%** on 692 decided games (Wilson
49.0–56.4%); gap ≥ +1.75 → **under 56.5%** on 292 (Wilson 50.8–62.1%). The rule
fails on criterion 3: the lower bound does not clear a coin flip. By season the over
rate is 53.0 / 53.6 / 52.0% — the same side every year, and never clearly above
break-even in any of them.

**The gap is not symmetric information.** A logistic fit of "under" on the gap
gives a pooled slope of **+0.043 per point** (bootstrap 95% CI +0.011 to +0.080,
2,000 resamples). Fit on each half alone: **+0.147 on the positive side, +0.041 on
the negative side** — the gap carries about 3.5× more information when it says
"under" than when it says "over". The under ladder is monotone (44.5 → 53.9 → 54.9
→ 58.8%); the over side is not (55.7 → 48.4 → 51.9 → 48.3%): only the ≤ −3 band
beats break-even, and the band next to it loses 7.5%.

**Live 2026 (weeks 1–3, Hard Rock's number, n=105; `scripts/two_sided_study.py`
against the live post-mortem, read 2026-09-22):** every negative band went over —
≤ −3: 7 of 7, −3..−1.75: 6 of 7, −1.75..−1: 5 of 7, −1..0: 5 of 5 — so the whole
negative side is **23 over of 26** (3 under; 88.5%, Wilson 71.0–96.0%), and at
gap ≤ −1.75 it is 13 of 14 (Wilson 68.5–98.7%). The positive side above the bar
went under 28 of 51 (54.9%, Wilson 41.4–67.7%). The history above says 52.7% over
on 692 games, so the live band is NOT in the history; it is registered as
**H-NEGGAP** (`live-tracking`, measurement only) in `docs/HYPOTHESES.md`, and this
paragraph is refreshed weekly from the study's output. Two things the live number
carries that the history did not: the model's number runs ~1.8 points below the
market this season (`docs/MODEL_LEVEL_2026.md`), which moves games INTO the
negative band, and first halves run hot in weeks 1-3 of every season. Whether the
band survives once the level deficit is removed is **H-NEGGAP-L**
(`scripts/neggap_level_study.py`: the same games under each H-INSEASON arm's
intercept, from stored rows, measurement only). Read all of it as the picture that
prompted the question, not as a result — the history above is the answer.

**One more thing the table says.** The **0 .. 1** band — a small positive gap —
went under only **44.5%** (Wilson 38.8–50.4%). That is the model's level bias
showing through: a line barely above our number is not a lean under, it is noise
around a number that runs low. It is consistent with the band's exclusion from the
bet rule and argues against ever loosening the 1.75 bar downward.

## What this licenses, and what it does not

- **Does not license betting overs.** Criterion 3 failed; the ≤ −3 band's +6.2% is
  one band of eight, adjacent to a losing one, discovered on the data it is measured
  on. It is a hypothesis for a pre-registered test on 2026, nothing more.
- **Does license the reading that the edge, if any, is asymmetric** — which is what
  the external review asked to have checked. The market-blind number's disagreement
  with the line is informative mainly in one direction, and the under-only
  architecture is not leaving a symmetric mirror image on the table.
- **Confirms the 1.75 bar from below.** The 0–1 band is the worst place on the board.

## Reproduce

```bash
PYTHONPATH=. python scripts/two_sided_study.py --out reports/two_sided --n-boot 2000
```
Reads `postmortem_games` (latest `hist_2023_25` and `live_2026` runs). Writes a
report under `reports/` (gitignored); this file is the finding.
