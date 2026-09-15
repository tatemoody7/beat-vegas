# Hypothesis registry

One row per idea ever tested or proposed against Beat Vegas data, with its status, the
data it used, its n, how many comparisons were run on that data, the pass criterion that
was written **before** the numbers were read, and the document that holds the result.
`tests/test_hypotheses_registry.py` keeps every study document pointed at from here and
every status word in the vocabulary below.

Why it exists (2026-09-15): nine studies live in nine documents and the count of looks at
the 1,902 real-close games of 2023-25 was written down nowhere. That season set is
**exploratory / in-sample** from here on. Anything important is validated prospectively on
2026+ decisions using locked decision-time state. Add the row first, run the script second.

## Vocabulary

- **status** — `pre-registered` (criterion written, not yet run), `exploratory` (counts
  and intervals only, no adoption decision may come from it), `tested-null`,
  `tested-positive`, `live-tracking`, `rejected`, `adopted`.
- **family** — the error-control family the row's test belongs to. Rows in one family
  share one false-positive budget (Holm across the family, or an alpha split). `exploratory`
  rows carry no confirmatory alpha at all.
- **comparisons run** — how many distinct tests were read on that dataset for that row. For
  rows backfilled after the fact this may be `unknown` or `≥N`, marked `(retrospective)`;
  an invented integer is worse than an honest unknown.
- **n** — the observations the primary test used, with the cut named.

## Backfilled rows (written 2026-09-15, after the fact)

| id | question | status | family | data (seasons, cut) | n | comparisons run | pass criterion (pre-registered) | result doc |
|---|---|---|---|---|---|---|---|---|
| R01 | Does training and scoring on FBS-vs-FBS only improve the top-20%-by-gap rule? | adopted | exploratory | demo.db 2015-25, walk-forward OOS 2018+, flat-0.52 proxy grade | 4,427 OOS games (was 7,136) | unknown (retrospective) | none written before the run | `research/swarm/2026-09-01-1h-under-edges/FBS_FILTER_RESULTS.md` (local only — `/research/` is gitignored; the adopted artefact in git is `data/fbs_teams.json` + `etl/fbs.py`) |
| R02 | Which proxy share (flat, linear, step) predicts the realized 1H total best? | adopted | exploratory | FBS-vs-FBS 2023-25 with a closing spread, walk-forward | 2,264 games (1,514 scored) | ≥3 (retrospective) | step beats flat by ≥ 0.05 MAE (approved before the fit) | `research/swarm/2026-09-01-1h-under-edges/PROXY_FIX_RESULTS.md` (local only — gitignored; the adopted artefact in git is `data/multiplier.json`) |
| R03 | Does a residual engine (market-conditioned) beat the incumbent and the close? | tested-null | exploratory | 2025 test season, real 1H close, train 2023-24 | 568 games | unknown (retrospective) | beat the close's MAE walk-forward (`scripts/residual_gate.py`) | `scripts/residual_gate.py` (report gitignored; close 8.73 / residual 9.01 / incumbent 9.23 / stored 8.96 recorded in the 2026-09-08 session handoff, outside the repo) |
| R04 | Does seeding season-to-date features with prior-season form fix early-season scoring? | rejected | exploratory | 2026 weeks 1-2 pooled, plus 2023-25 weeks 3+ | 180 games (pooled) | ≥4 (retrospective) | paired gain with a 95% CI excluding zero, monotone in k | `docs/LEVEL_ANCHOR.md` |
| R05 | Does censoring of the underdog's 1H score leave information the price has not absorbed? | tested-null | exploratory | 2023-25 FBS, real 1H close, decided games | 1,873 games | ≥3 (retrospective) | spread coefficient CI excludes zero, sign stable by season, OOS Brier gain | `docs/CENSORING_STUDY.md` |
| R06 | Does activating decision-safe weather move the board within an acceptable blast radius? | rejected | exploratory | 2025 test, train 2023-24 and 2024-only, priced games | 622 games | ≥2 splits (retrospective) | ≤ 5 games change side of `BET_GAP_PTS` (eyeball limit, written first) — deferred, re-runnable | `docs/WEATHER.md` |
| R07 | Does a negative gap carry over-side information? | tested-null | exploratory | 2023-25 FBS, real 1H close | 1,902 games (1,873 decided) | ≥3 (retrospective) | the three pre-registered conditions in the doc, all required | `docs/TWO_SIDED.md` |
| R08 | Does Hard Rock lag the market, and does its price move before its number? | tested-null | exploratory | 2026 weeks 1-2 snapshots | 120 games | unknown (retrospective) | stated in the doc before the read | `docs/HR_LAG.md` |
| R09 | Does decision-time gust × offensive style predict market error after the price control? | tested-null | exploratory | 2024-25 outdoor FBS, real 1H close, decided | 1,220 games | unknown (retrospective) | the pre-registered rule in the doc | `docs/WEATHER_STYLE.md` |
| R10 | Does gap ≥ 1.75 at Hard Rock's number hold prospectively? | live-tracking | stopping-rule | 2026 week 3 onward, locked paper decisions | accruing | 0 | the stopping rule (H-STOP) | `docs/STOPPING_RULE.md` (PR 6) |

**Looks at the 2023-25 real-close set so far:** R03, R05, R06, R07, R09 (and R04 in part).
Known comparison counts sum to ≥ 12 with three rows unknown. Treat that set as spent.

## Pre-registered rows (written before the scripts, 2026-09-15)

| id | question | status | family | data (seasons, cut) | n | comparisons run | pass criterion (pre-registered) | result doc |
|---|---|---|---|---|---|---|---|---|
| H6 | Which of the four decision builds gives the best line value? | pre-registered | H6 | 2026 week 2 onward, every stored card build, BET and EDGE tiers (plus every priced item), Hard Rock strict close and consensus close; week 2's Tue/Wed builds carry the pre-rename names `morning`/`afternoon` and week 1 the retired daily schedule — both descriptive only | accruing (week 1 rows kept, labelled, never in the test) | 6 (pairwise builds, one look) | Weekly runs are descriptive only. ONE confirmatory look on or after 2026-12-07: on matched games (BET by both builds), paired difference in favourable CLV vs Hard Rock's close, paired bootstrap, Holm across the six pairwise comparisons at family alpha 5%, each pair n ≥ 20. "Best" only if one build beats every other after correction; else NO BUILD PREFERRED. | `docs/WHEN_TO_BET.md` (PR 2) |
| H3A | What weight w on the market close minimises MAE of w·close + (1−w)·bv_line? | tested-positive | H3a-global | 2023-25 FBS, real 1H close (stored walk-forward bv_line, postmortem_games), walk-forward 2023→2024 and 2023-24→2025; 2026 weeks 1-2 descriptive only at decision-time consensus | 1,902 (626/639/637); 49 (2026) | 1 | Primary: test-season MAE vs realized 1H, one global w chosen on train seasons, reported against w=1 and w=0. Secondary, reported not optimised: bias by spread bucket, gate crossings at 1.75 and the raw-gap equivalent. Never fit on ROI or hit rate. Verdict BLEND WINS AT CLOSE only if the blend beats both arms in both test seasons. Final w fit once on all 2023-25 after evaluation, frozen in `data/blend.json` (read by nothing). | `docs/BLEND.md` — BLEND WINS AT CLOSE by the letter; blend−close paired CI spans zero in both seasons; frozen w = 0.80 in `data/blend.json` |
| H3B | Does a spread-bucket w beat the global w? | tested-null | H3a-buckets | same as H3A, buckets <14 / 14-21 / 21-28 / 28+ | 471/92/57/19 (2024), 473/87/49/28 (2025) | 8 (4 per season, Holm) | Per held-out season, per bucket: paired per-game abs-error difference (bucket-w − global-w), one-sided paired bootstrap; Holm across the four buckets within the season at 5%; a bucket is adopted only if it passes in both 2024 and 2025 with n ≥ 150 in each. 28+ reported, never adopted alone. | `docs/BLEND.md` — no bucket passes in both seasons; 14-21 in 2024 alone (Holm 0.072) |
| H4G | What did each of the seven gates block, and how did those games do? | exploratory | exploratory | 2026 weeks 2-3, last final build before kickoff (secondary: every build), Hard-Rock-priced games | 52 qualifying (25 graded) as of 2026-09-15; accruing | n/a (no confirmatory test) | None. Counts, records, units and Wilson intervals per gate, blocked-alone and passed sets. No COSTLY / PROTECTIVE call and no adoption from this sample. The candidate criterion for a future confirmatory row: blocked-alone n ≥ 30 and a per-bet-units bound past zero. | `docs/GATES.md` — price gate blocked 15 alone (5-5 graded); off_market 0 alone; cap 4 (2-2) |
| H4P | Would a fixed −115 kill ceiling have blocked a different, better or worse, set than the market-relative price gate? | exploratory | exploratory | as H4G | 52 qualifying; both 15 / fixed-only 5 / price-only 21 / neither 11 | n/a | None. Same three records beside the `price` gate. | `docs/GATES.md` — the two gates disagree on 26 of 52; price-only set 6-2 graded (n 8) |
| H4C | Does a trust-adjusted cap ranking (gap × shrunk reliability by spread bucket) pick a better five than gap alone? | exploratory | exploratory | as H4G; trust from 2023-25 real-close residuals and, separately, 2026 weeks 1-2 | week 2 pool = 5 = cap, identical sets; accruing | n/a | None. trust = (n·ratio + 30)/(n + 30), trust = 1.0 under n = 10. Three cap-5 records per week: gap-only, trust-2325, trust-2026. Measurement only. | `docs/GATES.md` — nothing to reorder until a week's pool exceeds five; 2023-25 trust flat (0.93-1.05) |
| H5 | Does any sharp book (Pinnacle, Circa, BookMaker, BetOnline) post CFB 1H totals through the Odds API, and how often? | pre-registered | exploratory | live Odds API, week 3 slate, ≤ 120 credits | one slate | n/a (descriptive) | None. Coverage, mean absolute distance from Hard Rock, update timing. No swap; Tate decides from the doc. | `docs/SHARP_BOOKS.md` (PR 5) |
| H-STOP | When does the paper record of the 1.75 rule end the test, either way? | pre-registered | stopping-rule | 2026 week 3 onward, cumulative across seasons, uncapped paper decisions as logged, one canonical observation per decision; real tickets attach as adherence | accruing | 2 clocks, budget split | Two confirmatory clocks — mean profit per 1u risked at actual per-bet prices, and mean favourable CLV vs Hard Rock's strict close — with the total false-stop budget split so the joint rate equals the stated target. Hit rate is reported and stops nothing. Fixed-n design: one test at the registered n. Sequential design: a sequentially valid boundary, never a repeatedly inspected bootstrap CI. Alternative effect sizes frozen at registration from the 2026 weeks 1-2 mean price. Thresholds chosen by Tate from the candidate table (PR 6) and written here. Failure boundary → real money pauses (`scripts/rule_pause.py`). | `docs/STOPPING_RULE.md` (PR 6) |

## How to add a row

1. Write the row — question, data, the exact criterion — and commit it.
2. Then write the script. The commit with the row precedes the commit with the script.
3. When the result is in, change `status`, fill `n` and `comparisons run`, and point
   `result doc` at the committed document. Never edit the criterion cell after the run;
   if the criterion was wrong, add a new row.
