# The consensus fair-price engine — v1 (`cv1`, table `hp1`)

**What it is:** the judge of the 2026 research program (`docs/ROADMAP_2026.md`). For every graded
pick it reads the EV per unit of that wager — its own line and its own price — against the
vig-free median of the market's closing prices. Code: `beatvegas/consensus.py`; table builder
`beatvegas/halfpoint.py` + `scripts/build_halfpoint_table.py`; frozen table
`data/halfpoint_hp1.json`; catch-up + report `scripts/consensus_backfill.py`. Specified by Tate on
2026-10-07 (roadmap amendment v1.1). **A change to any rule below is a new version, never an edit.**

**First development read (2026-10-07, `study.yml` run 37703161461, development evidence only):**
the paper and real first-half unders carry EV of about −5% per unit at the close (paper −0.054,
n 26; real −0.046, n 9) — roughly the vig, so the market's close made them about a coin flip
(mean P(win) 0.505 / 0.510 against a 0.524 break-even at −110). The over arms read −3% to −6%.
**EV varies by about 4 points per bet** (sd 0.038–0.047), far tighter than the rough 11% assumed in
the Q&A — the input the Statistical Protocol's simulation needs. Most rows without a reading are
**stale closes from weeks 2–4**, before the close capture was fixed: graded picks with a close
inside 2 hours were 0/31 (week 2), 0/34 (week 3), 3/16 (week 4), 13/15 (week 5).

## The rules (cv1)

| Rule | Value | Tate's call, 2026-10-07 |
|---|---|---|
| Books counted | every book in the feed with a centred main line, **except Hard Rock, Fliff** and the synthetic `consensus` rows; exchanges count when they post | "All centred books but HR" |
| Centred | both prices present, neither worse than −160 (`devig.is_centred_quote`) | existing rule |
| De-vig | multiplicative (`devig.devig_two_way`) | "Multiplicative" |
| A book's close | its newest centred row captured at or before kickoff | — |
| Close window | the book's latest pre-kick confirmation (`max(captured_at, last_seen_at)`) within **2 hours** of kickoff, every market | "2 hours for every market" |
| Line conversion | a book counts only if its line is within **1.5 points** of the wager's line | "1.5 points" |
| Minimum | **3** counted books, else no reading | "3 books" |
| Consensus | the median, across counted books, of each book's chance converted to the wager's line | roadmap v1 |
| EV | per unit staked at the wager's price; a push returns the stake | roadmap v1 |

A row without a reading records why in `cons_excluded`: `few_books` (fewer than 3 counted books
quoted it at all), `stale_close` (too few confirmed inside the window), `far_lines` (too few within
1.5 points), `outside_table`, `no_kickoff`, `no_line`, `no_table`. Exclusions are counted, never
dropped silently.

## How a line is converted (the half-point table)

A two-way price on an integer line carries no push, so a book's de-vigged under is the chance of
the under **given a decision**. The engine makes it unconditional — `q × (1 − P(push at its line))`
— then moves it to the wager's line by adding or removing the chance of landing on each integer in
between: under 28.0 wins on 27 and below; under 28.5 also wins on 28. Those chances come from
`data/halfpoint_hp1.json`:

- **Inputs:** FBS-vs-FBS games 2013–2025 (never the season being tested), played; first half only
  where the total is trusted (`grading.trusted_first_half_total`). 18,637 games read, 9,822
  FBS-vs-FBS; 9,794 first-half and 9,822 full-game pairs.
- **Expected total:** full game = the closing full-game total. First half = the closing full-game
  total × the step share in `data/multiplier.json` (0.4975, or 0.5375 at a 21+ spread) — no real
  first-half line exists before 2023, so the proxy only chooses which games describe the shape near
  a line. Nothing is graded against it.
- **Per half-point center:** the games whose expected total is within 1.0 point give the empirical
  chance of each integer within 8 points; a center needs 300 games (32 first-half centers, 20.5–36.0;
  53 full-game centers, 42.5–68.5). The engine uses the center nearest the median of the counted
  books' lines.
- **What it shows:** first-half key numbers — a first half lands on exactly 24 about 8.9% of the
  time, 31 about 7.7%, 34 6.2%, 27 6.0%, 28 5.2%, 21 5.5%; on 25, 29, 32 or 36 under 0.5%. That
  matches the 5.66% push rate `docs/CENSORING_STUDY.md` measured on integer first-half closes.

Built once on the runner (`study.yml` run 37702656840, `build_halfpoint_table`); the committed file
is that run's artifact.

## Where it runs

- `grade.yml` runs `scripts/consensus_backfill.py --write --missing-only` every day: a pick is
  read an hour after kickoff (p1.2 R3′), graded or not, and the columns land on its row
  (manual_picks and challenger_picks: `cons_version`, `cons_books`, `cons_line`, `cons_close_at`,
  `cons_p_win`, `cons_p_push`, `ev_cons`, `ev_hr`, `cons_excluded`).
- `picks.grade_pick` computes the same reading when the pick is graded; a row the backfill has not
  reached gets it there. A missing reading never blocks a grade.
- **The columns are write-once (2026-10-18, final-2026 plan PR-01;
  `picks.apply_judge_reading`).** The first reading is the evidence. A grade after the backfill, a
  `pick.py grade --regrade`, or a `--write` without `--missing-only` that computes something
  different writes nothing to the pick: one `judge_reading_audit` row records the stored values,
  the computed values, which fields differ, the reason (grade / regrade / backfill) and the run id.
  An identical recomputation writes nothing at all. The Monday read and the final report list the
  audit; no gate or position reads it.
- `study.yml` runs the same script as a report (refuses `--write`).
- `ev_hr` is the secondary reading against Hard Rock's own closing main quote (its rungs dropped,
  `lines.hr_main_snaps`).

## Not in v1

The bet-time consensus and the best major-book price at bet time (the customer scoreboard's
inputs), spreads and moneylines (their capture is step 4 of the roadmap), and any smoothing of the
table. Each is a later version.
