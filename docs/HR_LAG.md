# Hard Rock lead/lag and first-half microstructure

**Verdict: at the grain we capture, Hard Rock does not lag the market, and its
price does not move before its number.** Measurement only (Tate, 2026-09-15, both
halves of the question). Run with `scripts/hr_lag_study.py --season 2026 --max-week 2`;
arithmetic in `beatvegas/backtest/hr_lag.py`, pinned by `tests/test_hr_lag.py`.

## The grain, stated first

`odds_snapshots` is written by four whole-week sweeps and 30-minute close polls
inside 75 minutes of kickoff, and only when a book's quote **changes**. Over 2026
weeks 1–2 that is **120 games, 4.3 captures per game, Hard Rock re-observed every
24 hours at the median**. Every book's line at a capture is its last row at or
before it (the `lines.as_of` rule). So "lag" below means *captures*, roughly a day
apart midweek and half an hour apart at the close. Minutes are not observable here.

Two corrections made while running it, both material: **Hard Rock's own quote must
be centred** (inside 3h of kickoff most of its 1H quotes are off-centre ladder rungs;
counting them read Hard Rock as closing 1.2 points below the market on 55% of games —
the true figure is below); and **a Hard Rock move that closes a gap the market had
opened is catching up, not leading**, and a consensus move onto the side Hard Rock
already held is Hard Rock having led, not Hard Rock failing to follow.

## (a) Number lag

**Where Hard Rock sits, and what it does by the next capture** (350 observations
with a centred consensus of ≥ 3 books):

| Hard Rock vs consensus | observations | unchanged by next capture | moved toward consensus |
|---|---|---|---|
| ≥ 1 below | 67 (19%) | 80% | 15% |
| 0.5 below | 12 | 90% | 10% |
| at consensus | 224 (64%) | 84% | — |
| 0.5 above | 6 | 83% | 17% |
| ≥ 1 above | 41 (12%) | 86% | 14% |

An off-consensus Hard Rock number **persists**: a day later it is unchanged 80–90%
of the time and has moved toward the market only ~15% of the time. Hard Rock is not
chasing the consensus.

**Who moves first** — 46 consensus moves of ≥ 0.5 between consecutive captures:

| Hard Rock… | count | share |
|---|---|---|
| was already on that side (it led) | 19 | 41% |
| moved the same way in the same capture | 9 | 20% |
| followed in a later capture | 3 | 7% |
| never followed before kickoff | 15 | 33% |

And when Hard Rock moved ≥ 0.5 while the consensus did not: **led 19 times, the
market followed 4** (21%); **caught up 10 times**.

Read: in 61% of market moves Hard Rock was there first or at the same time; it
followed late in 7%. The 33% it never followed are the games where it stands off the
consensus — which is the same population the `off_market` gate already names, and
which [Hard Rock prices](RANKING_AND_TRUST.md) rather than leaves stale. **There is
no stale-window to bet into at a one-day grain.**

## (b) Price before number

68 centred Hard Rock rows with a row before and after; **30 price-only events** (the
under price changed, the number held). The number moved by the next row after a
price-only event **30%** of the time against a **34%** baseline for any row, and when
it moved it went the way the price pointed **56%** of the time (n ≈ 9; 50% = nothing).
**Null at this grain.** A dearer under does not foretell a lower number a day later.

## Microstructure

**The books diverge toward kickoff, they do not converge.** Mean range of the
centred books' 1H totals within a capture: **0.38 pts** more than 72h out, **0.56**
at 24–72h, **0.81** at 3–24h, **0.83** inside 3h; the share of captures where every
book agrees falls 62% → 46% → 35% → 37%. The first-half total is a thin market that
each book moves on its own flow late; a "close" is a distribution, not a number.
This is the argument for grading CLV against the **centred consensus median** (what
`lines.real_closes` does) and never against a single book's last quote.

**Where Hard Rock closes** (last pre-kick capture, 96 games, centred only): mean
**−0.37 pts** against the consensus; **≥ 1 below on 28%**, at consensus 56%, ≥ 1
above 14%. When Hard Rock is off the market at the close it is below it twice as
often as above — the direction that costs an under bettor points and triggers the
`off_market` gate, and the direction Hard Rock charges for
([hardrock-prices-its-line-position](RANKING_AND_TRUST.md)).

## What would answer the minutes question

The captured data cannot. A pre-registered **capture-cadence experiment** could:
poll Hard Rock plus the centred books **hourly from Thursday noon to each kickoff**
for the Hard Rock-priced slate (~80 games × ~60 polls ≈ **4,800 credits a week**;
three weeks ≈ 14K of the 55K remaining before the Oct 6 renewal). Pre-register:
the distribution of minutes between a consensus move and Hard Rock's, P(Hard Rock
follows within 1h | consensus moved ≥ 0.5), the same for price-before-number, and
whether betting Hard Rock inside a measured stale window beats the consensus close.
**Tate's call — it spends credits and it changes `lines_watch.yml`.** Nothing here
argues it is likely to find a window: at a day's grain Hard Rock leads or matches
the market three times as often as it trails.

## Reproduce

```bash
PYTHONPATH=. python scripts/hr_lag_study.py --season 2026 --max-week 2 --out reports/hr_lag
```
Only played weeks (captures must be pre-kick). Reads `odds_snapshots` + `games`;
writes a report under `reports/` (gitignored); this file is the finding.
