# When to bet — what did each build's list do at the close?

**Verdict (pre-registered rule): NOT YET EVALUABLE.** Descriptive only. The one
confirmatory look is dated **2026-12-07** (the Monday after the regular season) and the
script refuses `--confirmatory` before then. Nothing here changes a build, a gate or the
Friday guidance. Run 2026-09-15 with `scripts/when_to_bet_study.py --season 2026`;
arithmetic and the rule in `beatvegas/backtest/when_to_bet.py`, rows from
`beatvegas/snapshots.py`, pinned by `tests/test_when_to_bet.py` and `tests/test_snapshots.py`.
Registry row **H6** in `docs/HYPOTHESES.md`.

## Why it was run

The board is built four times a week (Tue / Thu / Fri / Sat) and the guidance to look on
Friday after 5:30pm ET rests on when Hard Rock *posts* first-half lines, not on what the
builds' picks *did*. Every build is stored whole in `cards`, so the timing question can be
asked of results: which build's BET list had the best line value against the number Hard
Rock actually closed at, and against the consensus close, and which build first called
each bet. The only existing reader of `cards` kept the newest item per game, which
collapses the builds; `beatvegas/snapshots.py::build_rows` keeps them apart.

## The rule, written before the numbers were read

Weekly runs are **descriptive**: per (week, build, tier) counts, record at Hard Rock's
number, units at Hard Rock's price (1u = 1 unit risked), median price and mean break-even,
and favourable line value against Hard Rock's own strict-centred close and against the
consensus close inside two hours of kickoff. The builds do not BET the same games, so these
rows are unpaired and no verdict word is printed from them.

**One confirmatory look, on or after 2026-12-07:** on matched games (BET by both builds of
a pair, weeks 2+, the last build of each slot in a week), the paired difference in
favourable line value vs Hard Rock's close, paired bootstrap (2,000 draws), **Holm across
the six pairwise comparisons** of `tue_pm` / `thu_pm` / `fri_pm` / `sat_am` at family
alpha **5%**, each pair with **n ≥ 20** matched games. A build is "best" only if it beats
every other build after correction; otherwise **NO BUILD PREFERRED**. Week 1 ran the
retired daily schedule and week 2's Tuesday and Wednesday builds carry the pre-rename
names `morning` / `afternoon`; both are reported, labelled, and never enter the test.

Favourable line value is the build's Hard Rock line **minus** the close, so + means the
market came toward the under. (The stored `clv_under` is the opposite sign.)

## What it found (season 2026 through week 2, 11 builds, 329 priced build-game rows)

- **Hard Rock's line at every BET build was its close.** Favourable line value vs Hard
  Rock's close is exactly 0.00 on all 15 BET rows (Tue 1, Thu 2, Fri 7, Sat 5). Within
  week 2 there was no line value to harvest by choosing a build; this is the same fact
  `docs/HR_LAG.md` measured (48 of 71 Hard Rock lines never moved). The timing question
  is therefore about **selection** — which games a build calls — not about price.
- **Friday called most of the bets first.** Of the 11 games ever tiered BET in week 2,
  `fri_pm` was first on 6, `thu_pm` on 2, `sat_am` on 2 and the Tuesday `morning` build
  on 1. Four games were BET in two builds; seven were BET in exactly one.
- **Records are tiny and say nothing yet.** BET rows at Hard Rock's number: Tuesday 0-1,
  Thursday 0-2, Friday 3-4, Saturday 3-2 — overlapping games, every Wilson interval
  spanning a coin flip. EDGE rows ran 55-62% under across the four-build slots
  (n 28-34 each, intervals 39-77%).
- **The consensus close is thin.** A strict two-hour consensus close exists for 23 of the
  66 Saturday-priced games and for 3 of Friday's 7 BETs, so the consensus column is a
  smaller sample than the Hard Rock column on every row.
- **The week-2 slate ran over.** Every Hard-Rock-priced game at the Saturday build went
  26-40 under-over at Hard Rock's number (−17.4u across 66 games). That is the slate, not
  a build effect, and it is why the ALL-priced rows are red on every build.
- **Week 1 has no BET or EDGE.** Both daily-schedule builds tiered every game PASS
  (early season); their priced games went 10-7 and 8-7. Descriptive, labelled, excluded.

### Per build, week 1-2 (descriptive)

| week | slot | schedule | built (UTC) | tier | n | graded | U-O-P | hit (decided) | Wilson 95% | units | median price | break-even | line value vs HR close (n) | 95% | vs consensus close (n) | 95% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | — | daily | 2026-09-05 14:12 | ALL priced | 17 | 17 | 10-7-0 | 58.8% | 36.0–78.4% | +2.78 | -105 | 50.8% | +0.00 (17) | -1.06..+1.24 | +0.20 (5) | -1.80..+2.80 |
| 1 | — | daily | 2026-09-05 17:15 | ALL priced | 15 | 15 | 8-7-0 | 53.3% | 30.1–75.2% | +1.65 | -105 | 49.1% | -0.40 (15) | -1.53..+0.73 | -1.00 (3) | -3.00..+0.00 |
| 2 | morning | legacy | 2026-09-08 20:03 | ALL priced | 23 | 23 | 12-11-0 | 52.2% | 33.0–70.8% | -0.57 | -115 | 53.3% | +0.30 (23) | -0.30..+0.91 | +0.12 (8) | -0.25..+0.50 |
| 2 | morning | legacy | 2026-09-08 20:03 | EDGE | 2 | 2 | 2-0-0 | 100.0% | 34.2–100.0% | +1.82 | -110 | 52.4% | +0.00 (2) | +0.00..+0.00 | +0.00 (1) | +0.00..+0.00 |
| 2 | morning | legacy | 2026-09-08 20:40 | ALL priced | 23 | 23 | 12-11-0 | 52.2% | 33.0–70.8% | -0.54 | -115 | 53.2% | +0.30 (23) | -0.30..+0.87 | +0.12 (8) | -0.25..+0.50 |
| 2 | morning | legacy | 2026-09-08 20:40 | BET | 1 | 1 | 0-1-0 | 0.0% | 0.0–79.3% | -1.00 | -105 | 51.2% | +0.00 (1) | +0.00..+0.00 | — (0) | — |
| 2 | morning | legacy | 2026-09-08 20:40 | EDGE | 13 | 13 | 9-4-0 | 69.2% | 42.4–87.3% | +3.93 | -115 | 53.4% | +0.31 (13) | -0.31..+1.00 | +0.00 (6) | -0.50..+0.50 |
| 2 | morning | legacy | 2026-09-09 12:46 | ALL priced | 38 | 38 | 19-19-0 | 50.0% | 34.8–65.2% | -2.38 | -115 | 53.1% | +0.11 (38) | -0.29..+0.50 | -0.07 (14) | -0.36..+0.22 |
| 2 | morning | legacy | 2026-09-09 12:46 | EDGE | 24 | 24 | 14-10-0 | 58.3% | 38.8–75.5% | +2.18 | -115 | 53.3% | +0.04 (24) | -0.33..+0.38 | +0.09 (11) | -0.18..+0.36 |
| 2 | afternoon | legacy | 2026-09-09 12:56 | ALL priced | 38 | 38 | 19-19-0 | 50.0% | 34.8–65.2% | -2.38 | -115 | 53.1% | +0.11 (38) | -0.29..+0.50 | -0.07 (14) | -0.36..+0.22 |
| 2 | afternoon | legacy | 2026-09-09 12:56 | EDGE | 26 | 26 | 15-11-0 | 57.7% | 38.9–74.5% | +2.09 | -115 | 53.3% | -0.08 (26) | -0.50..+0.27 | +0.09 (11) | -0.18..+0.36 |
| 2 | thu_pm | four | 2026-09-10 20:09 | ALL priced | 52 | 52 | 23-29-0 | 44.2% | 31.6–57.7% | -8.57 | -110 | 52.5% | +0.04 (52) | -0.29..+0.37 | -0.24 (17) | -0.47..+0.00 |
| 2 | thu_pm | four | 2026-09-10 20:09 | BET | 2 | 2 | 0-2-0 | 0.0% | 0.0–65.8% | -2.00 | -110 | 52.4% | +0.00 (2) | +0.00..+0.00 | — (0) | — |
| 2 | thu_pm | four | 2026-09-10 20:09 | EDGE | 34 | 34 | 19-15-0 | 55.9% | 39.5–71.1% | +1.86 | -110 | 52.7% | -0.12 (34) | -0.50..+0.26 | -0.08 (13) | -0.31..+0.15 |
| 2 | fri_pm | four | 2026-09-11 20:18 | ALL priced | 57 | 57 | 27-30-0 | 47.4% | 35.0–60.1% | -7.06 | -110 | 51.6% | -0.32 (57) | -0.75..+0.14 | -0.06 (18) | -0.67..+0.33 |
| 2 | fri_pm | four | 2026-09-11 20:18 | BET | 7 | 7 | 3-4-0 | 42.9% | 15.8–75.0% | -1.31 | -110 | 52.0% | +0.00 (7) | +0.00..+0.00 | +0.00 (3) | +0.00..+0.00 |
| 2 | fri_pm | four | 2026-09-11 20:18 | EDGE | 29 | 29 | 18-11-0 | 62.1% | 44.0–77.3% | +4.12 | -115 | 53.3% | -0.17 (29) | -0.72..+0.45 | -0.08 (12) | -0.92..+0.42 |
| 2 | sat_am | four | 2026-09-12 12:00 | ALL priced | 66 | 66 | 26-40-0 | 39.4% | 28.5–51.5% | -17.36 | -110 | 52.2% | -0.22 (65) | -0.58..+0.12 | -0.17 (23) | -0.65..+0.26 |
| 2 | sat_am | four | 2026-09-12 12:00 | BET | 5 | 5 | 3-2-0 | 60.0% | 23.1–88.2% | +0.65 | -110 | 52.3% | +0.00 (5) | +0.00..+0.00 | +0.67 (3) | +0.00..+1.00 |
| 2 | sat_am | four | 2026-09-12 12:00 | EDGE | 28 | 28 | 16-12-0 | 57.1% | 39.1–73.5% | +0.90 | -115 | 54.2% | +0.00 (28) | -0.57..+0.57 | -0.09 (11) | -0.82..+0.55 |

### First build to call each BET

| week | game | first build | slot | builds as BET | HR line then |
|---|---|---|---|---|---|
| 2 | 401856677 | 2026-09-08 20:40 | morning | 1 | 27.5 |
| 2 | 401858221 | 2026-09-10 20:09 | thu_pm | 2 | 26.5 |
| 2 | 401856674 | 2026-09-10 20:09 | thu_pm | 1 | 24.5 |
| 2 | 401856681 | 2026-09-11 20:18 | fri_pm | 1 | 28.5 |
| 2 | 401860884 | 2026-09-11 20:18 | fri_pm | 2 | 32.5 |
| 2 | 401862707 | 2026-09-11 20:18 | fri_pm | 1 | 26.5 |
| 2 | 401858442 | 2026-09-11 20:18 | fri_pm | 1 | 27.5 |
| 2 | 401866414 | 2026-09-11 20:18 | fri_pm | 2 | 23.5 |
| 2 | 401858441 | 2026-09-11 20:18 | fri_pm | 2 | 27.5 |
| 2 | 401856783 | 2026-09-12 12:00 | sat_am | 1 | 28.5 |
| 2 | 401856676 | 2026-09-12 12:00 | sat_am | 1 | 35.5 |

First-to-call counts: fri_pm 6, morning 1, sat_am 2, thu_pm 2

## What this licenses, and what it does not

Nothing changes. The Friday guidance stands on posting rates as before; this study will
judge it on results once, at season end, on matched games. Weekly re-runs add rows to the
tables above and nothing else. If the confirmatory look ends **NO BUILD PREFERRED**, the
four builds stay as they are; if it names a build, the next question is whether the others
can be dropped (credits), which is a separate decision, not this row.

## Reproduce

```
PYTHONPATH=. python scripts/when_to_bet_study.py --season 2026 --out reports/when_to_bet
PYTHONPATH=. python scripts/when_to_bet_study.py --season 2026 --confirmatory   # refused before 2026-12-07
```

Reads Neon (`cards`, `games`, `odds_snapshots`); writes `reports/when_to_bet_<UTC>.{md,json,csv}`
(gitignored); exits 0 whatever the numbers say.
