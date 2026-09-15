# Betting policy — 2026 season

Decided 2026-09-01 (week 1 audit). This is the rulebook the site enforces and
the bet card follows. Change it here first, then in code.

## Bankroll and stakes

- **Starting bankroll: $100. One unit = $10. Every bet is exactly one unit.**
- Flat staking, non-compounding. Units do not grow with wins or shrink with
  losses; they are re-set only when the bankroll is deliberately topped up.
- **Risk note, acknowledged by Tate:** $10 on a $100 roll is 10% per bet,
  five times the usual 1–2% guideline. A normal cold streak (4–5 losses, which
  a 54% bettor hits routinely) removes half the roll. This was chosen knowingly
  for the proving season. When the roll is topped up to $500+, the $10 unit
  becomes a standard 2% and the same rules keep working.
- The Kelly hint on the pick form is advisory context only — it is not a
  stake instruction. Stakes are flat.

## How many bets

- **Edge-driven, capped at 5 real-money bets per week.** The cap is a
  ceiling, not a target. Zero bets is a valid, normal week.
- Only games whose verdict on the This Week page is **BET** are bettable. Real bets are
  placed off the most recent decision build (Tue/Thu/Fri ~4:05pm ET, Sat ~8:05am ET) and
  logged from the **game page** (`/game/[id]` -> Log pick -> `POST /api/picks`); all of
  them count toward the same weekly cap. *(The Bet Slip was deleted 2026-09-13 — logging
  lives on the game page now.)* BETs are ranked by gap
  — the 6th+ by gap is paper only (`blocker: cap`).
  A BET whose blocker is `degraded` is **held**: paper only, no cap slot (see
  "Degraded card" below). WATCH is not a bet. Passing costs nothing.
- **A bonus (free) bet does NOT use a cap slot** (`manual_picks.is_bonus`, 2026-09-09).
  The cap limits how much of the $100 roll is at risk in a week and the book funded that
  stake, so a free bet must not crowd out a real one. It is still a real ticket
  (`is_paper` stays false) and still appears in the "you" ledger — but a LOSS books zero
  units instead of the stake, because it cost nothing. A win is unchanged: a bonus bet
  pays profit only, which is what the units maths already computed.
- A bet placed anyway on a WATCH or PASS game is still logged as real money,
  flagged **off-policy** on Results and broken out separately, so the record
  is complete and the overrides can be judged against the system.

## Which markets

- **Real money: first-half (1H) unders only.** That is the market the system is
  built to measure. The ≥ 1.75-point gap band is the validated **top-20% ranking
  rule**, not a proven edge: against a fair proxy line the backtest shows **no
  confirmed edge**; only real-line CLV this season can show one.
- Full-game is decision-support only. Its backtest on real lines found no
  edge; it stays on the board as context.
- Bets are placed on Hard Rock Bet (the only Florida book). Every This Week card shows
  Hard Rock's price against the market's fair price: a worse price turns a BET
  into a WATCH.

## Where you can legally bet in Florida (checked 2026-09-01)

- **Hard Rock Bet** — the only licensed sportsbook in Florida (Seminole
  compact, 21+). **Every real bet goes here.** FanDuel Sportsbook, DraftKings
  Sportsbook, BetMGM etc. remain illegal in FL.
- **Prediction markets (CFTC-regulated, 18+)** — legal for Floridians:
  **FanDuel Predicts** (launched 2026-01-15 via CME Group; this is what people
  mean when they say "FanDuel is in Florida"), **Kalshi**, **Polymarket**,
  **ProphetX**, **Novig**, **DraftKings Predictions**, Crypto.com, Underdog
  Predict. They sell game-winner / spread / futures contracts priced with no
  vig — and, as far as we can tell, **no first-half totals**, so they cannot
  carry our real-money market. **Use: price comparison only, and FULL-GAME only.** Kalshi,
  Polymarket, Novig and ProphetX flow into the Sunday **full-game** capture via
  The Odds API region `us_ex`. They do **not** sharpen the first-half fair price:
  re-verified 2026-09-07, `us_ex` returns **zero** first-half-total bookmakers, so
  no 1H sweep pays for that region (`beatvegas/ci.py`) and the exchange-first path
  in `card.py` sits dormant on the market we actually bet. (See "The exchanges post
  no first-half totals" below — this file used to claim both things at once.) FanDuel Predicts is not in any feed we use.
- **Sweepstakes / DFS** — Fliff (sweepstakes book; its lines are in our feed),
  PrizePicks, Underdog, DraftKings Pick6. Not used.

## The board (web/lib/homeBoard.ts + edge.ts)

The site is one page: every game on the week in a single ranked list.

- **Universe** — games Hard Rock has priced a full-game total on. If Hard Rock
  will not take the game, it is not a decision we have to make.
- **Score (0-100)** — one number per game, and the only thing the list sorts on.
  It is the GAP ALONE: 50 + gap × (20 / 1.75), floored and clamped to 0-100, where
  the gap is the line you can bet (Hard Rock's, else the market's, else our
  reference line) minus our number. A gap of exactly 1.75 is exactly 70, so green
  always means the gap rule passed. Nothing else moves the number: Hard Rock's
  price, an off-market Hard Rock number and a starting QB listed out are
  BLOCKERS — they decide whether a game is a bet and the card carries a tag —
  never score adjustments. 70+ is a bet (green), 55-69 is watch (amber), under 55
  is a pass (red). With no model read the row gets a context-only score (40
  plus/minus pace, wind, dome, spread and last season's first halves, capped at
  49) and is always a Pass; a good Hard Rock price is said in the action line, not
  a tier. The score RANKS; it never overrides the BET rules below.
- **Tiers** — BET is exactly the verdict rule below, every gate passed. Watch
  (EDGE in the payload) is score 55+ with one gate still failing, and the card
  names which one: no Hard Rock line, off-market number, price worse than fair,
  no comparable price, QB out, or a gap short of 1.75. Everything else is PASS,
  kept in the same list, dimmer. Once a game is played it is coloured by its
  result only when a REAL book line (Hard Rock's, else the market's) was posted;
  a game whose only line was our reference number shows a neutral final.
- **Action line** — one sentence per card saying what to do now: bet it at this
  number and price, wait for a specific number, or pass and why.
- **Kill number** — where the edge is gone: our number plus 1.75 rounded up to
  the next half point, and the worst price still clearing the market's fair under
  by more than the unavoidable 2% of vig. Clearing one and not the other is not a
  bet.
- **Degraded card** — every card carries a `status`: **final** (a morning build:
  the decision card for every game kicking off before the next morning),
  **preview** (a manual or legacy build that a morning card replaces), or
  **degraded** (a build-wide input failed, so the card is not to
  be bet off as-is). A card is degraded when the Hard Rock sweep stopped early
  and never reached a game on the card (`sweep`), the injury read failed so the
  QB-out gate ran on nothing (`preview`), or the tempo table stored zero teams
  (`tempo`). Those inputs hold every game they touched. A missing pace read on a
  single game (`pace`, ~5% of games each week) holds that game only and does
  **not** flip the card's status — the banner would fire most Saturdays with
  every bet fine. A held bet keeps its tier but its blocker is `degraded`: it is
  **paper only, takes no weekly-cap slot**, is never in the BET list, and appears
  under "Held" on the board. The build prints
  `CARD STATUS: <status> slot=<slot> held=<games> (bets <n>)` as line 2 of its
  summary, and the board carries the card-status banner beside the missed-build
  and stale-results ones.

## What BET means (lib/verdict.ts)

A game is BET when all of these hold:

1. The model has a read. **This no longer means "2+ games played"** —
   `MIN_GAMES_FOR_MODEL` has been **0** since 2026-09-08. The model can score a
   game with zero current-season games because `HistGradientBoostingRegressor`
   handles missing season-to-date features natively, and static/prior-season
   features (SP+, talent, returning production) still contribute. The tested
   expanding-mean prior-season **seed remains disabled** (`PRIOR_SEASON_WEIGHT = 0`,
   `docs/LEVEL_ANCHOR.md`) — do not confuse the two.
2. **Both teams have played at least 2 games this season** —
   `MIN_GAMES_FOR_REAL_MONEY = 2`, enforced server-side in
   `web/lib/pickRules.ts::checkPolicy` and mirrored on the card
   (`beatvegas/card.py`, blocker `early_season`) and the board (`web/lib/verdict.ts`
   keeps it at Watch), so the three never disagree. Under that, the game is **PAPER ONLY**.
   Being able to produce a number is not the same as that regime being validated
   for money: the blowout blind spot was traced to exactly this regime (weeks 1–2,
   ~59% of features NaN) and the backtest behind the gap rule is weeks 3+. Such
   games are still scored, ranked and paper-logged so the cohort accrues
   evidence; only the real-money BET is refused, with its own rejection reason.
3. **Hard Rock's own** first-half number sits **≥ 1.75 points above our number**
   (not the consensus line — the consensus can sit 1.75 above while Hard Rock
   posts a lower number). This is the top-20% gap band. (≥ 3.0 points = top-10%,
   "high" confidence. The classifier's under_score no longer gates the label: the
   2026-09-06 post-mortem found it carries no information about the outcome, so
   it stays a display chip only.)
4. A **live** first-half line has actually been captured — never an estimate.
5. Hard Rock's under price is no more than 5 cents (per $1) worse than the
   market's no-vig fair price. Standard -110 juice on a balanced market
   passes; -115 or worse fails unless the market itself leans under. (Decided
   2026-09-05: the earlier 2-cent version could almost never fire.)
6. Hard Rock's first-half total is **not more than 0.5 points below the
   market's** — a lower number is a worse under, and Hard Rock's house rules
   can void bets on lines that differ materially from the general market.
   Off-market numbers are WATCH until Hard Rock moves back toward the market.

Sigma (~12 points) is the noise of any single game's outcome. It is why
every card says "still close to a coin flip on any single game" and why we
bet many small edges rather than one big one. It is not a gate.

## Weeks 1–2 (scored, but PAPER ONLY)

- The model **does** read weeks 1–2 (`MIN_GAMES_FOR_MODEL = 0` since 2026-09-08),
  and those games are scored, ranked and paper-logged like any other. What they
  cannot take is **real money**: `MIN_GAMES_FOR_REAL_MONEY = 2` refuses the bet
  server-side while either team is under two current-season games; the card lists
  the game as Watch with blocker `early_season` and the paper pick carries that
  tag. The board tags them "early season".
- The reason is a measured one, not caution for its own sake: the model's blowout
  blind spot sits precisely here (weeks 1–2, ~59% of features NaN), and the
  backtest behind the 1.75 gap rule is weeks 3+. The regime has never been
  validated for money.
- Before any bet: read the injuries and news block on each This Week card (unofficial Rotowire / ESPN) — the
  number does not know about a starting QB being out.

## Weekly rhythm

GitHub cron drops some single-slot runs, so every job has retry slots and the
card job re-sweeps before it builds. The builds themselves are triggered by a
**Vercel cron** dispatching the slot by name; GitHub cron is the backup.

**There are no scheduled Claude routines and no scheduled texts** (retired
2026-09-13). They were LOCAL Claude sessions, and on battery this Mac sleeps
after a minute, so they fired only when the laptop happened to be awake —
`cfb-saturday-card` ran twice all season. **The board is the failure signal now**:
`web/lib/boardHealth.ts` surfaces a stale-results banner and a missed-build
banner, and GitHub emails failed runs.

Odds API: ~567 credits a week expected (`lines_watch.yml` header), comfortably
inside the **100K/month** tier the project has been on since 2026-09-06.

| When (ET)                    | What                                                    | Where               |
| ---------------------------- | ------------------------------------------------------- | ------------------- |
| Sun 2pm / 3pm / 4:30pm       | Full-game openers captured; pace/weather refreshed; board scored; derived 1H lines posted | `sunday.yml`        |

| Tue / Thu / Fri ~4:05pm      | **Decision build**: forced fresh sweep of the whole week's Hard Rock games + injury refresh, then build. Timed to when Hard Rock actually posts first-half lines. Tuesday and Thursday paper-log only the games kicking off before the NEXT build (48 h / 24 h); **Friday paper-logs the rest of the week** — it is the decision build for the weekend. Gated 3:45–5:15pm ET so DST needs no edit | `card.yml` |
| Sat ~8:05–8:45am             | **Saturday decision build**, same whole-week sweep, before the 9am betting sitting. Also on the rest of the week, but Friday has already priced most of it, so Saturday logs only what newly qualifies | `card.yml` |
| Tue / Fri 9am                | News + injuries / QB-out → board cards (also refreshed by every decision build) | `research_preview.yml` |
| Every 30 min, Tue–Mon evenings + all Saturday | **Per-game closes**: Hard Rock 1H line re-captured for each game ~30–75 min before its own kickoff (`last_seen_at` when unchanged) | `lines_watch.yml` |

| Game days                    | **Tate bets off the Board**, off the most recent decision build; the ticket is logged from the game page (`/game/[id]` → Log pick) | you |
| Daily 6:30am (retry noon)    | Finals + 1H play-by-play refreshed; all ledgers graded; post-mortem refreshed — a game is graded the morning after it is played; Monday is the full weekly pass | `grade.yml`         |
| Monday                       | Weekly review together; adjust for next week            | `/results`    |

## Measuring, not promising

- The truth metric this season is the **graded record over every qualifying
  game**, plus closing-line value (CLV) on Hard Rock's own opener and pre-kick
  close (captured per game) and the consensus close. The real-close backtest
  (docs/POST_MORTEM.md) found the 1H market barely moves between open and
  close (mean |move| 0.42 pts, 45% unchanged), so CLV alone cannot resolve the
  edge in one season — volume of graded gated games can.
- **Correcting a pick:** price, stake, note and the bonus flag can be edited from the
  Results table while the pick is PENDING (`PATCH /api/picks/<id>`). The line, market and
  game are not editable — they are what the bet *was* — and a graded pick is refused. A
  ledger that can be rewritten once the result is known is not evidence of anything.
- Paper picks (`is_paper`, 1-unit stake so units/ROI are comparable) log
  **every game whose Hard Rock first-half line sits ≥ 1.75 above our number**,
  tagged with the gate that blocked a real bet (`blocker`: `none` = it was a
  BET, `price`, `off_market`, `no_fair_price` = no book or exchange priced at
  Hard Rock's number so the price could not be judged, `qb_out`, `cap` = the
  6th+ by gap that week, `degraded` = a card input failed on the build, with
  the gate it overrode kept as `gate_blocker` in the pick's chips). The fair
  price is exchange-first: the exchange
  quotes at Hard Rock's exact line, else the median of the comparable books —
  those within half a point of Hard Rock's number, **widened to 1.5 points
  below it whenever Hard Rock is posting above the market**. That case is the
  best one for an under, and it is exactly where no book sits within half a
  point, so the like-for-like window would leave the price unjudgeable and
  paper the bet. A book at a lower total is a conservative reference for an
  under, so clearing the price gate against it cannot manufacture a bet.
  **The exchanges post no first-half totals** — re-verified 2026-09-07 against
  the live Odds API, where the `us_ex` region returned zero first-half-total
  bookmakers across three upcoming games. So no first-half sweep pays for that
  region (`beatvegas/ci.py` `SWEEP_ARGS`) and the exchange-first path sits
  dormant until an exchange starts posting the market.
  That measures each gate, not just the survivors. The cloud card
  (`scripts/build_card.py`, rules in `beatvegas/card.py`) logs one paper pick
  per qualifying game at its decision build (`--paper-log-window-hours`, per
  slot in `beatvegas/ci.py` `PAPER_WINDOW_HOURS`) — never twice for one game.
  **Friday anchors the weekend** (2026-09-13): Tuesday and Thursday claim only
  the games that kick off before anyone looks again, Friday claims the rest of
  the week, and Saturday mops up what newly qualifies. Every window used to be
  the gap to the next build, which on a Saturday sport handed the whole slate to
  the Saturday build — all 25 of week 2's paper picks came from it, and the
  Friday card's three clean BETs were never logged. Each pick also freezes
  **our own number** (`model_line_at_pick`) and the model's score beside Hard
  Rock's line, which is what the agreed/against split on Results reads.
  A paper pick never
  blocks your real ticket on the same game, and vice versa (the duplicate
  guard is per ledger). The card ranks BETs by gap (the cap-5 rule the
  backtest measured), so the card order is the cap order. A real ticket this
  week on a game that is not on the card (a Thursday game already played)
  still consumes one of the five slots.
- **Unpriced lines.** When Hard Rock has posted the first-half number but no
  price yet, the paper pick is logged with `price` NULL — never a made-up
  -110. The Monday grader fills it from Hard Rock's own pre-kick close when
  the close polls captured one and grades units normally; if no priced Hard
  Rock snapshot exists, the pick still grades for the record and hit rate
  but carries no units (the summary reports `(k unpriced)`).
- **Hook chip.** Each paper pick carries a `hook_side` chip: `key+0.5`
  (half a point above 24/28/31 — the under wins on a landing at the key),
  `key−0.5`, `on_key` (the line is a key number — a landing there pushes),
  or `other`. Chips describe, they never gate.

## Pre-flight checklist (do once)

- [ ] GitHub Actions email notifications on for failed runs (GitHub → Settings →
      Notifications → Actions). That email plus the **board's own banners**
      (`web/lib/boardHealth.ts`: stale results, missed build, card status) are the
      only failure alert; there is no push layer and no scheduled routine.
- [ ] Vercel env: `BANKROLL_USD=100`, `UNIT_USD=10` (defaults match).
- [ ] Hard Rock account funded ($100).
- [ ] After the `is_paper` migration (`migrate.yml`) — done 2026-09-01.
