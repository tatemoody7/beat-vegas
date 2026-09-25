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

## 7. The card holds a game; the board lets you bet it

Found live on 2026-09-10 when a real bankroll bet was logged on a game the card
had held.

`build_card` marked Old Dominion @ Virginia Tech `paper_blocker: "degraded"`,
`degraded_inputs: ["pace"]` — paper only. The board rated the same game a clean
BET with no blocker and the API accepted a real-money log.

The cause: **`degraded` exists only on the card.** `homeBoard.ts`, `edge.ts` and
`verdict.ts` contain zero references to it, and `pickRules.checkPolicy` gates on
slate / kickoff / duplicate / kill line / kill price / weekly cap — never the
card's blocker. So the two halves of the system disagreed and the half the owner
acted through said nothing.

The bet itself was defensible (gap 3.36, -105, implied share 0.458 well inside
the model's normal range, and the missing pace was the benign FCS-opponent gap
of §--). That is the point: it needed a human to reason it out afterwards, which
is what the flag exists to avoid. On a week where an input genuinely broke, the
board would be equally silent.

Worth recording alongside it: the kill-price gate DID fire correctly the same
evening. Alabama @ Kentucky was carded at kill price -115, Hard Rock moved to
-120, and the API refused the log. The gates are not decorative — this one just
does not see the card's blocker.

**Owner decision (2026-09-10): note it, decide after the first real-money
weekend.** The options considered were (a) warn on the board but still allow,
(b) make the card's hold binding on the API like the kill price, (c) stop
holding on a missing pace read at all since the model still produces a number.

## 8. Green board, refused log — RESOLVED 2026-09-13, and the diagnosis was wrong

Hit live on 2026-09-11 on Alabama @ Kentucky at -120. This section used to say
the cause was two gates running different tests. **It is not.** Re-measured
against the code:

| price | EV vs a 53.1% fair | board green? | logger accepts? |
|---|---|---|---|
| -125 | -4.4% | yes | yes |
| -120 | -2.7% | yes | yes |
| -115 | -0.7% | yes | yes |
| -130 | -6.1% | no | no |

They agree at every price, and they agree *by construction*:
`killPrice = breakEvenPrice(marketFairUnder)` returns the worst 5-cent rung whose
EV still clears the bar, so `price >= killPrice` and `ev >= bar` are the same
test. The "-113" this section used to quote was true break-even worked out by
hand; the code's kill price on that game was **-125**, and -120 clears it.

**The real cause is staleness.** `checkPolicy` compared a LIVE price against a
`killPrice` read off the stored card payload, and `marketFairUnder` moves between
builds. Measured across week 2's eight builds on game 401862707:

```
2026-09-10 20:09   fair 0.4838   kill +100
2026-09-11 20:18   fair 0.4884   kill -105     <- a full 5-cent step
2026-09-12 12:00   fair 0.4863   kill +100
```

The card is internally consistent (stored `kill_price` matches a recompute on
249 of 251 priced items). It is consistent with *the market at build time*, which
on a Saturday afternoon is hours old.

**Fixed (PR "the close is real, and one price gate"):**

1. `POST /api/picks` recomputes the kill price from `lib/lineCheck.ts`, the same
   loader the board renders from. The card's number is now only a fallback for
   the line, never for the price.
2. **The money path fails closed.** No verifiable live price, no real-money BET —
   `PRICE UNAVAILABLE`, a deliberately distinct rejection from the kill-price
   one, because "we could not check" and "we checked and it is too dear" are
   different failures and a post-mortem that conflates them reads an outage as a
   run of discipline. A cached price may be displayed; it may not authorize money.
3. The bar has one name, `BET_MIN_EV`, shared by `verdict.ts`, `card.py::is_bet`,
   the kill price and `checkPolicy`. It equals `EV_FLOOR` today, so behaviour is
   unchanged. `edge.ts`'s price *blocker* now reads that bar too rather than the
   `evVerdict` display chip, which would have reported "gap" once the bar moved.

## 8b. `ev` is not the expected value of the bet

Worth stating plainly, because §8's original diagnosis followed from assuming it
was, and the obvious "fix" — gate on `ev >= 0` — is much worse than the bug.

`ev` is `ev_under(fair_under, hr_price)` where `fair_under` is the **market's**
no-vig fair probability at Hard Rock's number (`card.py::market_read`). It asks
*"is Hard Rock's price better or worse than the rest of the market's?"* — a
price-shopping question. The model's edge is not in it. That lives in `hr_gap`,
in POINTS, on a different scale, and the two are never combined into one
expected value.

So `ev >= 0` is not a strict gate, it is an **unsatisfiable** one: it asks Hard
Rock to price better than the no-vig consensus, which is a free arb. Measured
2026-09-13 on the live week-2 card in Neon:

| tier | rows priced | clearing `ev >= 0` | mean ev |
|---|---|---|---|
| BET | 5 | **0** | -0.040 |
| EDGE | 18 | **0** | -0.069 |
| PASS | 19 | **0** | -0.055 |

All six real week-2 tickets were negative (-0.0086, -0.0301, -0.0400, -0.0463,
-0.0465, -0.0530). Nothing on the board has ever cleared zero.

The other direction fails too. Implying `P(under)` from the gap and `bv_sigma`
(a constant **11.26** on all 156 of 2026's prediction rows) makes a 5.32-point
gap worth `Phi(0.47) = 68%`, i.e. **+30% EV at -110** — while the same season's
grading says the model is LESS accurate than Hard Rock in every spread bucket.
That gate bets everything.

**A true EV gate needs a calibrated `P(under)`,** which is what the two-team
hurdle engine is for. `BREAK_EVEN_EV = 0.0` exists on both sides, mirrored by
`tests/test_gate_parity.py`, wired to nothing, waiting for it.

**Owner decision (2026-09-13): keep the bar on the price metric; fix the
mechanics; defer the EV gate to the engine.**

## 9. BetMGM is not quoting a centred main line

Raised by the owner from the Lines table, where BetMGM sat 5 points below the
field. Confirmed against the live API on 2026-09-12.

| Book | Avg abs distance from market median | Games 2+ pts off | Avg price skew from -110 |
|---|---|---|---|
| **betmgm** | **4.86 pts** | **61 of 63** | **235** |
| hardrockbet | 1.72 | 31 of 80 | 101 |
| draftkings | 0.27 | 1 of 81 | 37 |
| fanduel | 0.19 | 1 of 82 | 18 |

The price-skew column is the tell. A centred main total prices both sides near
-110; every normal book sits 15-47 points away from that, BetMGM sits 235.

**It is NOT our parser and NOT staleness** — both were checked:

- A live `totals_h1` call returns exactly **2 outcomes at a single point** for
  every book including BetMGM, so the last-wins loop in
  `sources/odds.py::_normalize_totals` has nothing to pick wrongly here. (That
  loop IS still fragile — it takes the last outcome and would mix rungs if a
  book ever returned several — but it is not the cause of this.)
- BetMGM's `last_update` was the FRESHEST of the seven books on the probe.

BetMGM simply serves an off-centre rung as its main first-half total. On
Western Kentucky @ Georgia it posted **36.5 over +195 / under -275** (fair under
68.4%) while six books sat at 30.5-32.5 (fair under 47-54%). That is internally
coherent — 36.5 at -275 is roughly 31.5 at -110 — it is just not a comparable
number.

**How much damage:**

- **Fair price: none.** `fairPriceWindow` only admits books within 0.5 pts of
  Hard Rock's line (1.5 below when HR is above market), so a book 5 points away
  is already excluded.
- **Market median: bounded but real.** Taking the MEDIAN rather than the mean
  absorbs most of it — across 63 games the median moved on **13**, by at most
  **0.5 points** (avg 0.087). The thinnest game still had 5 books.
- **That 0.5 matters.** `HR_OFF_MARKET_PTS` is exactly 0.5 and the gate is
  `market - hr > 0.5`, so a half-point shift in the median can flip the
  off-market gate on a borderline game — in either direction.
- **Trust: the visible cost is the real one.** A Lines table showing 28.5 beside
  six books at 33.5 reads as a broken system, which is how this was found.

**Options, not yet built:** exclude betmgm from the consensus median; or better,
exclude ANY book whose two-way prices are skewed beyond some threshold from
-110, which generalises to whichever book does this next rather than naming one.
Either way the Lines table should label or drop it rather than showing it plain.

**Owner decision (2026-09-12): record for a future build.**

## 9b. Hard Rock's own alternate lines — FIXED 2026-09-25 (H-PCT-U)

On Friday's card (2026-09-25, `fri_pm`) Texas @ Tennessee read Hard Rock **30.5,
over +125 / under -160** while six books and the Hard Rock app said **27.5**. A live
call the same evening showed the Odds API returning that alternate **alone** as
Hard Rock's `totals_h1` (one Over/Under pair), so it was not our parser. Liberty @
Coastal had done the same the day before (21.5 at -160 vs 24.5).

**Why it kept happening.** The only guard was `is_centred_quote`, which rejects a
side worse than -160. That bar was set from BetMGM's rungs (-235 average skew).
Hard Rock prices a 2-point alternate at about -145/-150 and a 3-point one at
exactly -160, so they passed. Nothing compared Hard Rock with the other books,
and Hard Rock was deliberately exempt from every centring filter so the board would
show the number Tate bets.

**The rule (Tate's choice).** `devig.is_hr_rung` / `devig.ts::isHrRung`: a Hard
Rock 1H quote is an alternate if either side is **-140 or worse**, OR it sits
**2.0+ points** from the median of the other books' centred lines in the same sweep
(needs 3+ books; exchanges and the synthetic consensus never count). The golden
vectors in `tests/fixtures/hr_rung_vectors.json` pin both languages. The general
-160 bar is unchanged, because other books post real main lines at -140..-159.

**What it does.** When Hard Rock's newest quote is an alternate, the card and the
board show its **last main line with its capture time** ("u27.5 -105 · as of Thu
4:07pm") under blocker `hr_alt_line`. That line is display only: it is out of the
slate bar, never qualifies, never logs a paper pick, and `POST /api/picks`
refuses a real ticket (`PRICE UNAVAILABLE`) until a sweep serves the main line.
Hard Rock's closing line and price (`lines.book_closing_*`, 1H only) skip
alternates too. The card log prints `HR ALT LINES IGNORED: n (...)` and the card
health note carries `hr_alt_ignored=n`.

**Measured** (read-only replay over all 747 pre-kickoff 2026 Hard Rock 1H
snapshots): the old bar let **33 alternates through on 31 games** (27 priced
-140..-160, 6 at normal juice 2+ points off the field). **0 of 563** Hard Rock
quotes within 2 points of a 3+ book field are rejected. The 6 normal-juice
rejections may include real Hard Rock disagreements (Ole Miss @ Florida 28.5 vs
30.5 on 09-25; South Florida @ Bowling Green 26.5 vs 24.5 on 09-22). Tate accepted
that trade for a check that does not depend on Hard Rock's price ladder. Replaying
Friday's card as of its build: the same 3 BETs, Texas @ Tennessee shown at 27.5 and
no longer qualifying (8 qualify, not 9), the bar still 5.54 over 40 games instead
of 46, and 15 games whose newest Hard Rock quote was an alternate.

**Not changed:** the 12 paper picks already logged on alternates (weeks 2-4) stand
as logged (Tate). `sources/odds.py` now keeps the most balanced pair when a book
sends several, instead of the last one, and warns. No book has done that yet.

## 10. What is still open

- Build the two-section board (§1).
- Decide on the share sanity check and its threshold (§3).
- Whether the weeks 9-12 concentration (§4) is a real seasonal effect or noise.
  It cannot be settled on 295 bets; 2026 adds to the sample.
- The answer bar wording (§6) — highest priority of these, it is read first and
  it is read wrong. Ships with the board rebuild, not before it.
- The card/board split on `degraded` (§7) — pick one of the three options.
- ~~The two disagreeing price gates (§8)~~ — **resolved 2026-09-13**: it was stale
  card data, not two rules (§8).
- BetMGM polluting the consensus median (§9). The last-wins outcome loop in
  `sources/odds.py` is fixed (over-first, and a market whose two outcomes sit at
  different points is skipped as rungs).
- ~~`game_records` has no graded rows~~ — week 2 froze pre-kickoff and graded;
  week 1 was backfilled on 2026-09-15 from the 09-10 re-score with `captured_at`
  after kickoff, so it is self-evidently retro and the records grid marks it
  "scored after". Accuracy only, never a decision the board could have made.

### Measured live, week 2 (post-mortem `live_2026`, 2026-09-15; Hard Rock-priced, graded)

| Spread | n | Model bias | Model MAE | HR bias | HR MAE | Under % | Gate fired | Gate under % |
|---|---|---|---|---|---|---|---|---|
| <7 | 25 | −3.07 | 6.62 | −1.26 | 7.66 | 32% | 5 | 60% |
| 7–14 | 22 | −0.81 | 6.35 | +0.91 | 8.18 | 55% | 7 | 57% |
| 14–21 | 12 | −2.86 | 5.07 | −0.17 | 8.17 | 50% | 2 | 100% |
| 21–28 | 10 | −0.90 | 8.75 | +0.60 | 8.60 | 40% | 4 | 75% |
| **28+** | **20** | **−10.17** | **12.71** | −7.15 | 10.35 | **30%** | **7** | **29%** |

The blowout blind spot (§2) confirmed live at n=20: model implied share .459
against a realized .684, and the gate fired on 7 of 20 games that went under 29%
of the time. Under 28 points the model's MAE is competitive with Hard Rock's at
this n. Week 1 (retro-scored): model bias −1.57, MAE 8.12 vs the line's 7.71 over 50
games. Decision (Tate, 2026-09-15): **hold the frozen 1.75 rule for real money; keep
measuring by spread bucket.** Week 3 is the first live week inside the regime the
rule was validated on (the 2023-25 backtest holds ~1 game from weeks 1-2).
