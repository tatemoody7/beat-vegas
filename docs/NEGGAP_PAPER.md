# H-NEGGAP-P — paper OVERS on the negative-gap band, prospectively

> **Superseded 2026-10-07** (`docs/ROADMAP_2026.md`). The over arm restarts as one arm — the bottom
> 20% of gaps on each slate — registered under the 2026 Statistical Protocol before it logs. Rows
> from the three nested arms below are development evidence only. **Retired 2026-10-08:** the
> registered arm H-ARM-1HO replaced it (`docs/PROTOCOL_2026.md`); `NEGGAP_COLLECT` is no longer set.

Registry row **H-NEGGAP-P** (`docs/HYPOTHESES.md`), written 2026-09-28 before any
observation. Measurement only on the real-money side: **nothing here licenses a real
bet on an over.** `docs/BETTING_POLICY.md` is first-half unders and this row does not
amend it.

> **STATUS 2026-10-04 — COLLECTING; FIRST WEEK GRADED, NO BOUNDARY CROSSED** (table at the end). Collection
> switched on with card 22 (`cards.id` 22, `tue_pm`, 2026-09-29, 0 rows: the 48 h paper
> window held every week-5 game); card 23 (`thu_pm`, 2026-10-01) also wrote 0 (the 24 h
> window: no negative-gap game kicked off Thursday or Friday night). **Card 24 (`fri_pm`,
> 2026-10-02, run 37058936969) wrote the first rows — 27 across 15 games: `neggap_lt0` 15,
> `neggap_le175` 7, `neggap_le3` 5** — recorded here the same evening, before the first of
> them kicks off (Sat 2026-10-03 16:00Z) and before Saturday's 10Z grade reads a result.

## What prompted it, stated so it is not mistaken for support

Live 2026: Hard-Rock-priced games whose first-half line sat BELOW our number went over
**23 of 26** in weeks 2–3 and then **3 of 12** in week 4 — 26 of 38 cumulative (Wilson
52.5–80.9%). Two things that count hides (`docs/TWO_SIDED.md`, live section):

1. **23 of the 38 were Hard Rock ALTERNATE lines** the feed served as the 1H total — 2–4
   points under the field with the over at −160..−325 — the defect H-PCT-U removed from the
   universe on 2026-09-25. A line three points under the market going over is the line.
2. **On main lines only it is 10 over of 15** (0 of 4 in week 4; Wilson 41.7–84.8%).

The 2023–25 real-close history says 52.4% over on 1,200 negative-gap games (row R07), and
the pre-registered two-sided test found NO over-side signal there. So this is a hypothesis
for a prospective test and nothing more; the history is the answer until the clocks say
otherwise.

## The arms — frozen

Three nested arms on `gap = hr_line − bv_line` (Hard Rock's MAIN line minus our number,
off the card item at the decision build):

| arm | logs a paper OVER when |
|---|---|
| `neggap_lt0` | gap < 0 |
| `neggap_le175` | gap ≤ −1.75 |
| `neggap_le3` | gap ≤ −3 |

A game at gap −4 logs one row in each arm (nested by construction — the question is
where, if anywhere, the value sits). Universe = **H-PCT-U's**: Hard-Rock-priced games whose
NEWEST Hard Rock quote is its main line (`hr_live`), with a model read and a Hard Rock OVER
price captured at that build; the Friday-anchored decision build with the champion's paper
windows (`ci.PAPER_WINDOW_HOURS`), one row per game per arm, deduplicated per arm. Rows go
to **`challenger_picks`** with `side='over'` and `arm` = the label — never `manual_picks`,
so no query feeding the bankroll, the cap, Results or H-STOP-2's observations can see them.
Price = Hard Rock's over price at the build (no fair-price or off-market gate: the arm is
judged at the price it would have paid).

## The clocks — the champion's, reused

Two SPRT clocks per arm, the H-STOP-2 shape (`docs/STOPPING_RULE.md`, Clock 2):

- **Profit**, priced picks: per-pick alternative `mu1_i = 0.04 / b_i`, `b_i` the break-even
  the OVER price implies (`stopping.mu1_for_price`: 0.0764 at −110, 0.0650 at −160, 0.0800
  at +100); observation = units won per 1u at that price.
- **Line value**: `+(closing − bet)` against the centred consensus close confirmed inside
  `REAL_1H_CLOSE_WINDOW_H` (2 h) of kickoff, H1 **+0.50 pts**; a pick without a close inside
  the window is excluded from this clock and counted. **The sign is the reverse of the
  under ledger**: stored `clv` is `closing − bet` for every row, and a RISING line is what
  favours an over.
- **Sigma known and frozen** at the champion's: profit **0.929**, line value **1.371**
  (H-STOP-2's, from the 55 graded 2026 paper picks as stored 2026-09-22). Tate's call
  2026-09-28: the arm is held to the champion's bar in the champion's units, not to a sigma
  estimated on 15 rows.
- **Budget**: total false-decision 5%, split /3 arms (Bonferroni, 1.667% per arm) then /2
  clocks = **0.833% per arm-clock**, power 80%; bounds **A = +4.5643**, **B = −1.6011**
  (`sprt_bounds(0.05/6, 0.20)`).
- **Decisions**: an arm PASSES only when BOTH clocks cross A; an arm is DROPPED when EITHER
  crosses B; otherwise it accrues and weekly reporting is descriptive. **If more than one
  arm passes no threshold is chosen here** — that choice needs its own registered row. A
  pass is a finding for Tate and licenses nothing at real money.
- **Secondary, reported never optimised**: hit rate, selection share, and the champion's
  under record on the same games.

Constants: `beatvegas/backtest/stopping.py::NEGGAP`; position:
`scripts/neggap_position.py` (lands with the collection code); `tests/test_stopping.py`
pins the numbers to this document.

## Touches nothing live

No real-money selection, no model edit, no change to `BET_GAP_PTS`, the slate bar, the
price gate or H-STOP-2. The collection is switched on by `NEGGAP_COLLECT=1` in `card.yml`
(the build step's env, decision builds only — a `--no-paper` manual build logs nothing) and
off by unsetting it. Code: `beatvegas/neggap.py` (arms, universe, the writer),
`beatvegas/grading.py` / `beatvegas/picks.py` graded side-aware (`result` stays the
outcome; units pay the over; the no-vig price CLV flips sign), `lines.book_closing_price_
before_kickoff(side="over")` for the close price, `scripts/neggap_position.py` (also
`study.yml` → `neggap_position`). `challenger_picks.closing_captured_at` is new: run
`migrate.yml` before the first grade of an over row.

## Data note

- Collection on: card 22 (`tue_pm`, 2026-09-29), 0 rows (the 48 h window).
- Card 23 (`thu_pm`, 2026-10-01): 0 rows (the 24 h window).
- **First build with rows: card 24** (`cards.id` 24, `fri_pm`, built 2026-10-02T20:15:39Z,
  run 37058936969, bar 2.12 over 44 games, 9 Hard Rock alternates out of the universe).
  `SELECT arm, side, count(*) FROM challenger_picks GROUP BY 1,2` → `neggap_lt0` 15,
  `neggap_le175` 7, `neggap_le3` 5, all `side='over'`, all `placed_at` 20:15:39, nested as
  built (every `le3` game is in `le175`, every `le175` in `lt0`). No `manual_picks` row
  from this path: the week's 9 paper rows are the champion's unders. The 15 games, by gap
  (`gap = hr_line − bv_line` off the card item; price = Hard Rock's OVER at the build):

  | game | gap | HR line | over | arms |
  |---|---|---|---|---|
  | Texas State @ San Diego State | −10.01 | 27.5 | −130 | lt0, le175, le3 |
  | Bowling Green @ Miami (OH) | −4.40 | 23.5 | −105 | lt0, le175, le3 |
  | Baylor @ Arizona State | −4.28 | 23.5 | −130 | lt0, le175, le3 |
  | Texas Tech @ Colorado | −3.87 | 25.5 | −120 | lt0, le175, le3 |
  | Arkansas @ Texas A&M | −3.40 | 26.5 | −110 | lt0, le175, le3 |
  | San José State @ Hawai'i | −1.94 | 26.5 | −110 | lt0, le175 |
  | Vanderbilt @ Georgia | −1.79 | 27.5 | −115 | lt0, le175 |
  | BYU @ TCU | −1.68 | 23.5 | −120 | lt0 |
  | Maryland @ Nebraska | −1.43 | 27.5 | −120 | lt0 |
  | Army @ Louisiana Tech | −1.42 | 23.5 | −125 | lt0 |
  | Auburn @ Tennessee | −1.20 | 27.5 | −110 | lt0 |
  | Virginia @ Florida State | −0.95 | 26.5 | −120 | lt0 |
  | Old Dominion @ Georgia State | −0.42 | 25.5 | −110 | lt0 |
  | Michigan @ Minnesota | −0.42 | 21.5 | −115 | lt0 |
  | Miami @ Clemson | −0.22 | 24.5 | −105 | lt0 |

  Two things to read with it. Texas State @ San Diego State's −10 is the model (37.5) sitting
  nine points above the whole market (28.5), not a Hard Rock number; on Thursday's card its
  newest Hard Rock quote was a rung and it was outside the universe, Friday's feed served the
  main line at −130 over and it came in. And the universe is Friday's: a game whose Hard
  Rock row drifts to an alternate rung by Saturday (`docs/RANKING_AND_TRUST.md` §9b;
  measured 2026-10-01, HISTORY) keeps its row — the pick is judged at the price captured here.
- Weekly: per arm, n logged, n graded, hit rate, units at price, favourable line value,
  excluded-no-close share, both LLRs against A/B.

## Weekly positions (`scripts/neggap_position.py`)

### 2026-10-04 — week 5 graded (30 rows: 27 from card 24, 3 from card 25 `sat_am`)

| arm | logged | graded | over (won) | units | profit n / mean / LLR | line value n / mean / LLR | verdict |
|---|---|---|---|---|---|---|---|
| `neggap_lt0` | 16 | 16 | 5 | −6.71 | 16 / −0.419 / −0.630 | 16 / +0.125 / −0.532 | running |
| `neggap_le175` | 8 | 8 | 3 | −2.45 | 8 / −0.307 / −0.236 | 8 / +0.125 / −0.266 | running |
| `neggap_le3` | 6 | 6 | 2 | −2.32 | 6 / −0.387 / −0.216 | 6 / +0.333 / +0.133 | running |

Bounds A +4.564 / B −1.601; no close excluded (all 16 inside the 2 h window). The band went
12 under / 5 over on main lines this week — the reverse of weeks 2-3. Measurement only.

## Result

None yet.
