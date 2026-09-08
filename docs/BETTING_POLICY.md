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
- Only games whose verdict on the This Week page is **BET** are bettable. Real bets are placed off that day's morning card (Tue–Sat ~8:05am ET) via the Bet Slip; Thursday and Friday games are bet off their own morning card and count toward the same weekly cap. BETs are ranked by gap — the 6th+ by gap is paper only (`blocker: cap`).
  A BET whose blocker is `degraded` is **held**: paper only, no cap slot (see
  "Degraded card" below). WATCH is not a bet. Passing costs nothing.
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
  carry our real-money market. **Use: price comparison only.** Kalshi,
  Polymarket, Novig and ProphetX flow into the Sunday full-game capture via
  The Odds API region `us_ex` and sharpen the "market fair price" Hard Rock
  is judged against on each This Week card. FanDuel Predicts is not in any feed we use.
- **Sweepstakes / DFS** — Fliff (sweepstakes book; its lines are in our feed),
  PrizePicks, Underdog, DraftKings Pick6. Not used.

## The board (web/lib/homeBoard.ts + edge.ts)

The site is one page: every game on the week in a single ranked list.

- **Universe** — games Hard Rock has priced a full-game total on. If Hard Rock
  will not take the game, it is not a decision we have to make.
- **Score (0-100)** — one number per game, and the only thing the list sorts on.
  With a model read it starts at 50 and moves 10 points per point of gap between
  the line you can bet and our number, then adjusts for Hard Rock's price (up to
  8 points either way), minus 10 for an off-market Hard Rock number and minus 5
  for a starting QB listed out. With no model read (weeks 1-2, derived rows) it
  is a context-only score: 40 plus/minus pace, wind, dome, spread and last
  season's first halves, capped at 49 — 55 when Hard Rock's price alone beats the
  market. The score RANKS; it never overrides the BET rules below.
- **Tiers** — BET is exactly the verdict rule below, every gate passed. EDGE is
  score 60+ (or a price-only edge with no model) with one gate still failing, and
  the card names which one: no Hard Rock line, off-market number, price worse
  than fair, QB out, or a gap short of 1.75. Everything else is PASS, kept in the
  same list, dimmer.
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
  **paper only, takes no weekly-cap slot**, is never in the BET list or the Bet
  Slip, and appears under "Held" on the board and in the Saturday text. The
  build prints `CARD STATUS: <status> slot=<slot> held=<games> (bets <n>)` as
  line 2 of its summary; the Saturday text flags a non-final status up front
  (its BETS header reads `BETS (DEGRADED - n held back)`), lists the held bets
  under `HELD BACK (input failed)`, and spells the status and each failed input
  out in its CARD STATUS section.

## What BET means (lib/verdict.ts)

A game is BET when all of these hold:

1. The model has a read (both teams have played 2+ games; weeks 1–2 never
   qualify by design).
2. **Hard Rock's own** first-half number sits **≥ 1.75 points above our number**
   (not the consensus line — the consensus can sit 1.75 above while Hard Rock
   posts a lower number). This is the top-20% gap band. (≥ 3.0 points = top-10%,
   "high" confidence. The classifier's under_score no longer gates the label: the
   2026-09-06 post-mortem found it carries no information about the outcome, so
   it stays a display chip only.)
3. A **live** first-half line has actually been captured — never an estimate.
4. Hard Rock's under price is no more than 5 cents (per $1) worse than the
   market's no-vig fair price. Standard -110 juice on a balanced market
   passes; -115 or worse fails unless the market itself leans under. (Decided
   2026-09-05: the earlier 2-cent version could almost never fire.)
5. Hard Rock's first-half total is **not more than 0.5 points below the
   market's** — a lower number is a worse under, and Hard Rock's house rules
   can void bets on lines that differ materially from the general market.
   Off-market numbers are WATCH until Hard Rock moves back toward the market.

Sigma (~12 points) is the noise of any single game's outcome. It is why
every card says "still close to a coin flip on any single game" and why we
bet many small edges rather than one big one. It is not a gate.

## Weeks 1–2 (no model)

- Any bet is a **price bet**, not a model bet: Hard Rock's under paying
  better than the market's fair price. These show as WATCH — "price edge
  only". Fewer bets is the right answer; the bar is high.
- Before any bet: read the injuries and news block on each This Week card (unofficial Rotowire / ESPN) — the
  number does not know about a starting QB being out.

## Weekly rhythm

GitHub cron drops some single-slot runs, so every job has retry slots, the card
job re-sweeps before it builds, and two Claude routines re-dispatch what cron
dropped (`cfb-saturday-card` for the final card, `cfb-sunday-ops` for the Sunday
capture). Odds API: paid 100K-credit plan (since 2026-09-06), ~800 credits a
week expected (`lines_watch.yml` header).

| When (ET)                    | What                                                    | Where               |
| ---------------------------- | ------------------------------------------------------- | ------------------- |
| Sun 2pm / 3pm / 4:30pm       | Full-game openers captured; pace/weather refreshed; board scored; derived 1H lines posted | `sunday.yml`        |
| Sun 4:45pm                   | **Ops routine**: verify/kick `sunday.yml`, text the weekend recap | `cfb-sunday-ops` |
| Tue–Sat ~8:05–8:45am         | **Morning card** (the decision build, every day): forced fresh sweep of the whole week's Hard Rock games + injury refresh, then build; paper-logs every qualifying game kicking off within 24 h with its blocker. Gated on the Eastern clock so DST needs no edit. The board is one rolling week — each game locks at its own kickoff | `card.yml` |
| Tue / Fri 9am                | News + injuries / QB-out → board cards (also refreshed by every morning build) | `research_preview.yml` |
| Every 30 min, Tue–Mon evenings + all Saturday | **Per-game closes**: Hard Rock 1H line re-captured for each game ~30–75 min before its own kickoff (`last_seen_at` when unchanged) | `lines_watch.yml` |
| Sat 8:50am                   | **Card routine**: verify/kick the morning build, text the BET list (line, price, kill numbers) | `cfb-saturday-card` |
| Game days                    | **Tate bets off the Bet Slip** on the Board once that day's morning card is up (one tap logs the ticket); Thu/Fri games the same way, off their own morning card | you |
| Daily 6:30am (retry noon)    | Finals + 1H play-by-play refreshed; all ledgers graded; post-mortem refreshed — a game is graded the morning after it is played; Monday is the full weekly pass | `grade.yml`         |
| Mon 9am                      | Coaching digest includes a one-line grading check (kicks `grade.yml` if needed) | `monday-coaching` |
| Monday                       | Weekly review together; adjust for next week            | `/results`    |

## Measuring, not promising

- The truth metric this season is the **graded record over every qualifying
  game**, plus closing-line value (CLV) on Hard Rock's own opener and pre-kick
  close (captured per game) and the consensus close. The real-close backtest
  (docs/POST_MORTEM.md) found the 1H market barely moves between open and
  close (mean |move| 0.42 pts, 45% unchanged), so CLV alone cannot resolve the
  edge in one season — volume of graded gated games can.
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
  per qualifying game at its decision build — the Thursday/Friday evening
  card for weeknight games, the Saturday-morning card for the Saturday slate
  (`--paper-log-window-hours`) — never twice for one game. A paper pick never
  blocks your real ticket on the same game, and vice versa (the duplicate
  guard is per ledger). The card ranks BETs by gap (the cap-5 rule the
  backtest measured), so the text order is the cap order. A real ticket this
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
      Notifications → Actions). That email plus the Claude routines are the only
      failure alert; there is no push layer.
- [ ] Vercel env: `BANKROLL_USD=100`, `UNIT_USD=10` (defaults match).
- [ ] Hard Rock account funded ($100).
- [ ] After the `is_paper` migration (`migrate.yml`) — done 2026-09-01.
