# The gates — what each blocker stopped, and how those games did

**Status: EXPLORATORY. No gate verdict.** Counts, records, units and intervals only; no
COSTLY / PROTECTIVE call and no adoption decision may come from this sample (Tate,
2026-09-15). Run 2026-09-15 with `scripts/gates_study.py --season 2026` (GitHub Actions
`study.yml`); arithmetic in `beatvegas/backtest/gates.py`, rows from
`beatvegas/snapshots.py`, pinned by `tests/test_gates.py`. Registry rows **H4G, H4P, H4C**
in `docs/HYPOTHESES.md`, all `exploratory`.

## Why it was run

Each gate costs bets and none has ever been measured. Week 2 alone the price gate stopped
thirteen games that went 8-5 under. The kill price was defined by price theory, the
off-market line by a house-rule distance, the cap by bankroll; whether any of them earns
its keep is an empirical question the stored builds can begin to answer — and only begin,
because a gate blocks a handful of games a week.

## The rule, written before the numbers were read

Rows: `snapshots.build_rows` for 2026; **primary cut = the last final build before each
game's kickoff** (the state the ledger acted on — Friday anchors), Hard-Rock-priced games
only; a secondary table counts blocked-alone per build. **Every gate is judged alone from
the item's own fields** — the card's blocker ladder stops at the first failure, so the
stored blocker under-counts every later gate:

| gate | recomputed as |
|---|---|
| off_market | `market_line − hr_line > 0.5` (`HR_OFF_MARKET_PTS`, the card's own test) |
| no_fair_price | `ev` is None |
| price | `ev < BET_MIN_EV` |
| qb_out | the item's `qb_out` field where it exists; otherwise only the stored blocker can name it, labelled "blocker only (undercounted)" |
| early_season | `games_played < 2` where the field exists; the gate itself did not exist before the 2026-09-15 card |
| cap | `over_cap` |
| degraded | the build's status, or a `gate_blocker` set by `apply_degraded` |

"Qualifying" = a model number, a Hard Rock line, and `hr_line − bv_line ≥ 1.75`. For each
gate: the qualifying games it **fails**, the ones it blocked **alone** (every other gate
passed — they would have been BETs) and the ones it **passed**, each graded at Hard Rock's
number and price (1u = 1 unit risked) with favourable line value vs Hard Rock's strict
close. Wilson intervals only at **n ≥ 30** decided; counts below that.

**H4P.** A fixed **−115** ceiling (`hr_price < −115` fails) beside the market-relative price
gate, with the four-way partition of the qualifying games.

**H4C.** The week's BETs before the cap (tier BET with no blocker, or blocker `cap`) ranked
three ways — gap alone; gap × trust from the 2023-25 stored walk-forward rows; gap × trust
from the 2026 graded rows — with `trust = (n·ratio + 30)/(n + 30)`, **exactly 1.0 under
n = 10**, `ratio = overall MAE / bucket MAE` of `bv_line`, buckets <14 / 14-21 / 21-28 / 28+.
Top five of each graded at Hard Rock's number.

**Candidate criterion for a future confirmatory row, recorded here and NOT applied:** a
gate is called costly only when the games it blocked alone number ≥ 30 and their per-bet
units bootstrap bound sits above zero; protective when n ≥ 30 and the bound sits below;
otherwise undecided. That row is written later, with the weeks it will use named in
advance.

## What it found (weeks 2-3; 124 games at the cut, 52 qualifying, 25 of them graded)

- **The price gate is the gate.** Of 52 qualifying games it fails 36 — and blocked 15
  **alone**. The blocked-alone set is graded 10 so far: **5-5, −0.57u**. The 13 graded
  games it fails at all went 8-5 (+2.06u); the 12 graded games it let through went 6-6
  (−1.72u). Week 2's "the price gate blocked 8-5 under" is real and is also 13 games.
- **No fair price blocked four alone; they went 3-1** (+0.63u) with line value +2.50 —
  four games, one of which moved 10 points.
- **Off-market blocked nothing alone.** Its four fails all failed price too.
- **The cap took four, and they went 2-2** (−0.22u). Every BET's line value vs Hard
  Rock's close is 0.00: Hard Rock did not move a single BET line (`docs/WHEN_TO_BET.md`).
- **QB-out flagged nothing.** No qualifying row carries the field yet — this evening's
  week-3 Tuesday card was built from `main` before PR #140, which adds it — and no stored
  blocker names it either.
- **Early season blocked four alone on the week-3 Tuesday card** (22 fail in total,
  none graded yet). For week 2's 25 rows the gate did not exist.
- **A fixed −115 ceiling is a different gate, not a stricter one.** Both fail 15 games,
  the ceiling alone 5 (3-2), the market-relative gate alone **21** — of which 8 are graded,
  **6-2, +3.43u**. The market-relative gate refuses games the ceiling would take, and so
  far those games have won. Eight games.
- **Trust from 2023-25 is flat**, as the residual-gate finding predicted: 1.014 / 0.929 /
  1.050 / 0.954. Trust from 2026 is 1.071 at <14 (n 30) and **exactly 1.0 everywhere else**
  because n is 7, 5 and 7 — the 28+ bucket's MAE of 12.7 on seven games is the blowout
  blind spot, and the floor keeps seven games from re-ranking a season.
- **The cap had nothing to reorder.** Week 2's pool before the cap is five games — the
  cap itself — so all three rankings pick the same five (3-2, +0.65u). The comparison
  begins the first week the pool exceeds five.

## Per gate (qualifying games)

| gate | fails: graded/n · U-O-P · hit · units · LV | blocked ALONE (would have been BET) | passed | note |
|---|---|---|---|---|
| off_market | 3/4 · 1-2-0 · 33.3% · -1.00u · LV -2.00 (3) | 0/0 · 0-0-0 · — · —u · LV — (0) | 22/48 · 13-9-0 · 59.1% · +1.34u · LV +0.45 (22) |  |
| no_fair_price | 7/7 · 3-4-0 · 42.9% · -2.37u · LV +0.57 (7) | 4/4 · 3-1-0 · 75.0% · +0.63u · LV +2.50 (4) | 18/45 · 11-7-0 · 61.1% · +2.71u · LV +0.00 (18) |  |
| price | 13/36 · 8-5-0 · 61.5% · +2.06u · LV +0.00 (13) | 10/15 · 5-5-0 · 50.0% · -0.57u · LV +0.00 (10) | 12/16 · 6-6-0 · 50.0% · -1.72u · LV +0.33 (12) |  |
| qb_out | 0/0 · 0-0-0 · — · —u · LV — (0) | 0/0 · 0-0-0 · — · —u · LV — (0) | 25/52 · 14-11-0 · 56.0% · +0.34u · LV +0.16 (25) | 0 of 52 qualifying rows carry the field; the rest are blocker-only (undercounted) |
| early_season | 0/22 · 0-0-0 · — · —u · LV — (0) | 0/4 · 0-0-0 · — · —u · LV — (0) | 25/30 · 14-11-0 · 56.0% · +0.34u · LV +0.16 (25) | field: 27, gate did not exist: 25 |
| cap | 4/4 · 2-2-0 · 50.0% · -0.22u · LV +0.00 (4) | 4/4 · 2-2-0 · 50.0% · -0.22u · LV +0.00 (4) | 21/48 · 12-9-0 · 57.1% · +0.56u · LV +0.19 (21) |  |
| degraded | 3/3 · 2-1-0 · 66.7% · +0.63u · LV +0.00 (3) | 0/0 · 0-0-0 · — · —u · LV — (0) | 22/49 · 12-10-0 · 54.5% · -0.30u · LV +0.18 (22) |  |

### Fixed -115 ceiling beside the market-relative price gate (H4P)

Both fail 15 · fixed only 5 · price only 21 · neither 11.

| set | graded/n · U-O-P · hit · units · LV |
|---|---|
| fails the -115 ceiling | 10/20 · 5-5-0 · 50.0% · -1.74u · LV +1.00 (10) |
| passes it | 15/32 · 9-6-0 · 60.0% · +2.08u · LV -0.40 (15) |
| fixed only (price gate let through) | 5/5 · 3-2-0 · 60.0% · -0.37u · LV +2.00 (5) |
| price only (ceiling let through) | 8/21 · 6-2-0 · 75.0% · +3.43u · LV +0.00 (8) |

### Trust by spread bucket (H4C inputs)

| source | bucket | n | MAE | ratio | trust |
|---|---|---|---|---|---|
| trust_2325 | <14 | 1397 | 8.610 | 1.015 | 1.014 |
| trust_2325 | 14-21 | 282 | 9.480 | 0.922 | 0.929 |
| trust_2325 | 21-28 | 151 | 8.242 | 1.060 | 1.050 |
| trust_2325 | 28+ | 72 | 9.344 | 0.935 | 0.954 |
| trust_2026 | <14 | 30 | 6.488 | 1.141 | 1.071 |
| trust_2026 | 14-21 | 7 | 5.070 | 1.461 | 1.000 |
| trust_2026 | 21-28 | 5 | 8.752 | 0.846 | 1.000 |
| trust_2026 | 28+ | 7 | 12.706 | 0.583 | 1.000 |

### Cap-5 three ways (H4C)

| week | pool | ranking | games | graded/n · U-O-P · hit · units · LV | overlap with gap-only |
|---|---|---|---|---|---|
| 2 | 5 | gap_only | 401856676, 401856783, 401858441, 401860884, 401866414 | 5/5 · 3-2-0 · 60.0% · +0.65u · LV +0.00 (5) |  |
| 2 | 5 | trust_2325 | 401856676, 401856783, 401858441, 401860884, 401866414 | 5/5 · 3-2-0 · 60.0% · +0.65u · LV +0.00 (5) | 5 |
| 2 | 5 | trust_2026 | 401856676, 401856783, 401858441, 401860884, 401866414 | 5/5 · 3-2-0 · 60.0% · +0.65u · LV +0.00 (5) | 5 |

### Secondary: blocked-alone per build

| week | slot | built (UTC) | qualifying | off_market | no_fair_price | price | qb_out | early_season | cap | degraded | BETs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | morning | 2026-09-08 20:03 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| 2 | morning | 2026-09-08 20:40 | 14 | 0 | 0 | 11 | 0 | 0 | 0 | 0 | 1 |
| 2 | morning | 2026-09-09 12:46 | 22 | 0 | 0 | 18 | 0 | 0 | 0 | 0 | 0 |
| 2 | afternoon | 2026-09-09 12:56 | 22 | 0 | 0 | 18 | 0 | 0 | 0 | 0 | 0 |
| 2 | thu_pm | 2026-09-10 20:09 | 30 | 1 | 0 | 20 | 0 | 0 | 0 | 1 | 1 |
| 2 | fri_pm | 2026-09-11 20:18 | 26 | 0 | 3 | 12 | 0 | 0 | 3 | 1 | 3 |
| 2 | sat_am | 2026-09-12 12:00 | 25 | 0 | 4 | 10 | 0 | 0 | 4 | 0 | 1 |
| 3 | tue_pm | 2026-09-15 20:42 | 27 | 0 | 0 | 5 | 0 | 4 | 0 | 0 | 0 |

## What this licenses, and what it does not

Nothing changes. Every n above is under 30, most are under 10, and the study is
`exploratory` by registration: it can point, it cannot decide. The two pointers worth
carrying are that the price gate is where nearly all the friction is (15 blocked alone,
5-5 so far) and that a fixed ceiling and a market-relative price gate disagree on 26 of 52
games. Either becomes a decision only through a pre-registered prospective row with its
weeks named in advance. The script is re-runnable weekly; the tables grow, the status
does not.

## Reproduce

```
gh workflow run study.yml -f script=gates_study -f args="--season 2026 --out reports/gates"
PYTHONPATH=. python scripts/gates_study.py --season 2026 --out reports/gates     # off campus
```

Reads Neon (`cards`, `games`, `odds_snapshots`, `postmortem_games`); writes
`reports/gates_<UTC>.{md,json,csv}` (gitignored); exits 0 whatever the numbers say.
