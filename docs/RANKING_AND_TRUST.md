# What the board rank means, and how much to trust the numbers

Written 2026-09-10, out of a session that started with "why are our two bets
ranked #20 and #22?" Every number below was measured against the live database
or the 2023-25 backtest; none is an estimate. The queries are in the git history
of this file's PR if you want to re-run them.

Nothing here changed the code. It is written down so it is not rediscovered from
scratch in November.

---

## 1. Board rank is gap size. Only gap size.

`edge.ts` computes `score = floor(50 + 11.43 x gap)`, clamped to 0-100, and
`sortGames` orders by score then gap. Since score is a straight line in gap, the
ranking IS the gap ordering. Rank 1 means "biggest disagreement between our
number and the line", and nothing else.

It does **not** account for: Hard Rock's price, whether the line is off-market,
whether Hard Rock posted a line at all, whether an input was missing, or the
weekly cap. All of which decide whether a game is bettable.

The live board on 2026-09-10 (week 2), top of the list:

| # | Game | Tier | Gap | Blocked by | Spread |
|---|---|---|---|---|---|
| 1 | Oregon @ Oklahoma State | Watch | +9.92 | price | 23 |
| 2 | Southern Miss @ Auburn | Watch | +8.18 | off-market | 33 |
| 3 | Louisiana Tech @ LSU | Watch | +7.19 | off-market | 35 |
| 4-19 | *(sixteen more, every one blocked)* | Watch | | price / off-market | |
| **20** | **Old Dominion @ Virginia Tech** | **BET** | +3.36 | — | 19 |
| **22** | **Alabama @ Kentucky** | **BET** | +2.92 | — | 10.5 |

Every game above the two bets was unbettable. The board sorted nineteen games
you cannot act on above the two you can.

**Owner decision (2026-09-10):** the board should answer BOTH "what should I bet"
and "where does the market look most wrong", as two labelled sections — bettable
games first, then everything else by gap with its blocker named. Not yet built.

## 2. The top of the board is the model's known blind spot

The eight biggest gaps that week had spreads of 23, 33, 35, 31, 26, 40.5, 26.5
and 44.5 — every one a blowout. Our implied first-half share on them ran 0.36 to
0.48 against Hard Rock's 0.53 to 0.58.

This is the "model disagrees with Hard Rock on blowouts and nobody knows who is
right" gotcha in CLAUDE.md, seen from the front end: it does not just exist, it
**occupies the top of the board**.

## 3. The self-check worth building: our number stops looking like our number

The strongest finding of the session, because it needs no new data and no
opinion about football.

| | n | 1st pct | 5th | median | 95th |
|---|---|---|---|---|---|
| Model predictions, 2023-25 | 3,601 | **0.424** | 0.455 | 0.532 | 0.631 |
| Real book 1H lines, 2023-25 | 1,902 | 0.470 | 0.480 | 0.504 | 0.536 |

In three seasons the model essentially never predicted a first half below 42% of
the game total. Books almost never price outside 47-54%.

On 2026 week 2, **six games sat below 0.42, the lowest at 0.358** — outside the
model's own historical floor. Those six carried an average gap of **+6.44
points** against **+2.00** for the other 42 priced games. They are what generated
the top of the board.

A first half worth 35.8% of a game's scoring is not a bold read; it is the model
doing something it has never done. **Proposed check: flag any prediction whose
implied first-half share falls outside the model's own historical range, and
treat the gap as unreliable rather than large.**

Threshold matters, and it is a live trade-off:

- **1st percentile (0.424)** — flags 6 games that week, neither of the two bets.
- **5th percentile (0.455)** — also flags Alabama @ Kentucky (0.436), a real bet.

Note this is a check on the model's own output distribution, not a football
opinion, and not a gate on the spread — gating on spread was proposed and
rejected on 2026-09-09 for dropping a third of the board.

**Owner decision (2026-09-10):** write it up, do not build it before the first
real-money weekend. Revisit after.

## 4. How much to trust 56.5%

The `gap >= 1.75` rule at real closing lines, 2023-25: **295 bets, 165-127-3,
56.5%, +23.00 units, +7.8% ROI.** (Reproduced exactly from `postmortem_games`
before slicing, so the slices below are trustworthy.)

Split by part of season:

| Cut | Bets | Record | Win % | Units | ROI |
|---|---|---|---|---|---|
| All weeks | 295 | 165-127 | 56.5% | +23.00 | +7.8% |
| Weeks 9-12 only | 102 | 64-38 | 62.7% | +20.18 | +19.8% |
| Everything else | 193 | 101-89 | 53.2% | +2.82 | +1.5% |

**88% of the measured profit comes from one four-week stretch.** Break-even at
-110 is 52.4%.

Two honest caveats in both directions:

- Removing the best stretch is itself cherry-picking. Removing the WORST stretch
  (weeks 5-8, 50.0%) would make the rule look outstanding. The correct reading is
  not "the edge is fake" but "the swing between four-week stretches is large
  relative to the edge", i.e. 56.5% carries much more uncertainty than one number
  suggests — roughly a 51-62% plausible range on 295 bets.
- Temperature does not explain the weeks 9-12 concentration. Slicing 295 bets
  four ways produced a 72% bucket on n=36, which is how you fool yourself. The
  slicing was abandoned deliberately rather than pursued until something looked
  significant.

## 5. Weeks 1-2 are outside everything that was ever measured

| Week | Games in the backtest |
|---|---|
| 1 | **0** |
| 2 | **1** |
| 3 | 141 |
| 4 | 164 |

The model needs season-to-date history, so the backtest could not cover the weeks
where that history does not exist. **Every published figure — 60.8%, 56.5%, the
gap ladder — is week 3 onward.**

Where it WAS measured, the earliest weeks were not weaker: weeks 3-4 went 27-20,
**57.4%, +9.5% ROI**, slightly better than the overall 56.5%. So there is no
evidence that early season selects badly — only that weeks 1-2 are untested.

For the record, 2026 week 1 graded (35 games, already in `results` before this
session — an earlier claim in this session that no 2026 prediction had ever been
graded was wrong, and applied only to `game_records`):

| | Record | Under % | Units |
|---|---|---|---|
| Our model | 17-18 | 48.6% | -2.55 |
| Every game's under | 22-13 | 62.9% | +7.00 |

35 games is noise. It is recorded because it is the only 2026 evidence there is.

**Owner decision (2026-09-10):** bet full units and treat this season as the real
test. The cap already bounds a bad stretch at 5 units a week, and betting smaller
does not make the answer arrive sooner — it makes the same games worth less
information.

## 6. The answer bar says "bets live" when it means "games that qualify"

`answerBar.ts::buildAnswer` fills `bets` from `edge.tier === "BET"` — games the
MODEL currently rates as bets. `AnswerBar.tsx:33` renders that count as
"N bets live", beside a separate "N of 5 slots used" that counts what was
actually logged.

On 2026-09-10 the board therefore read "2 bets live · 1 of 5 slots used", listed
Old Dominion @ Virginia Tech and Alabama @ Kentucky — neither of them bet — and
did NOT list Mississippi State @ Minnesota, which is the one real ticket on file.

"Live" reads as "I have this on". Two people misread it the same way on the same
day, one of them after a full day inside this codebase. It is the highest-risk
wording on the site because it is the first thing read on a Saturday morning.

**Fix**: say what it is — "2 games qualify" / "you have 1 of 5 slots used", and
ideally mark the ones already logged.

**Owner decision (2026-09-10): do NOT fix this in isolation.** It ships as part
of the two-section board rebuild in §1, after the first real-money weekend.
Nothing on the bar is factually wrong, only badly labelled, and the wording
depends on what the two sections end up called — fixing it alone would mean
writing the copy twice and touching the first block on the board two days before
real money.

## 7. What is still open

- Build the two-section board (§1).
- Decide on the share sanity check and its threshold (§3).
- Whether the weeks 9-12 concentration (§4) is a real seasonal effect or noise.
  It cannot be settled on 295 bets; 2026 adds to the sample.
- The answer bar wording (§6) — highest priority of these, it is read first and
  it is read wrong.
- `game_records` still has no graded rows. Until it does, the Track record grid
  and the factor ledger have no 2026 input. `rescore.yml` deliberately does not
  backfill them, because those snapshots are meant to be frozen pre-kickoff.
