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

**Live 2026 (weeks 1–2, Hard Rock's number, n=49):** 8 of 8 over at gap ≤ −1.75
(Wilson 67.6–100%). Read it as the picture that prompted the question, not as a
result — the history above is the answer.

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
