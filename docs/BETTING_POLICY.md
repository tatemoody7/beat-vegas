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
- Only games whose verdict on the This Week page is **BET** are bettable. Real bets are placed in one sitting Saturday morning (~9am ET) off the final card's Bet Slip; a weeknight (Tue–Fri) game may be bet off that evening's card and counts toward the same weekly cap. BETs are ranked by gap — the 6th+ by gap is paper only (`blocker: cap`).
  WATCH is not a bet. Passing costs nothing.
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
| Tue / Fri 9am                | News + injuries / QB-out → This Week cards                 | `research_preview.yml` |
| Wed 2pm; Thu 10am, 4pm; Fri 8am, noon, 4pm | **Opener sweeps**: every Hard Rock-priced game without a Hard Rock 1H line yet (a game stops being polled once its opener is in) | `lines_watch.yml` |
| Tue–Thu ~4:05pm              | Weeknight card: sweep tonight's games, build, paper-log games kicking off within 10 h | `card.yml` |
| Fri ~6:05pm (retry 7pm)      | **Preview card** after a full sweep of the weekend slate; paper-logs Friday-night games only | `card.yml` |
| Every 30 min, Tue–Mon evenings + all Saturday | **Per-game closes**: Hard Rock 1H line re-captured for each game ~30–75 min before its own kickoff (`last_seen_at` when unchanged) | `lines_watch.yml` |
| Sat ~8:05–8:45am             | **FINAL card**: forced fresh sweep + injury refresh, then build; paper-logs every qualifying Saturday game with its blocker. Gated on the Eastern clock so DST needs no edit | `card.yml` |
| Sat 8:50am                   | **Card routine**: verify/kick the final, text the BET list (line, price, kill numbers) | `cfb-saturday-card` |
| Sat ~9am                     | **Tate places every real bet in one sitting** off the Bet Slip on the Board (one tap logs the ticket) | you |
| Mon 8am / 10am / 1pm         | Finals + 1H play-by-play refreshed; all ledgers graded; post-mortem refreshed | `grade.yml`         |
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
  BET, `price`, `off_market`, `qb_out`, `cap` = the 6th+ by gap that week).
  That measures each gate, not just the survivors. The cloud card
  (`scripts/build_card.py`, rules in `beatvegas/card.py`) logs one paper pick
  per qualifying game at its decision build — the Thursday/Friday evening
  card for weeknight games, the Saturday-morning card for the Saturday slate
  (`--paper-log-window-hours`) — never twice for one game. A paper pick never
  blocks your real ticket on the same game, and vice versa (the duplicate
  guard is per ledger). The card ranks BETs by gap (the cap-5 rule the
  backtest measured), so the text order is the cap order.

## Pre-flight checklist (do once)

- [ ] GitHub Actions email notifications on for failed runs (GitHub → Settings →
      Notifications → Actions). That email plus the Claude routines are the only
      failure alert; there is no push layer.
- [ ] Vercel env: `BANKROLL_USD=100`, `UNIT_USD=10` (defaults match).
- [ ] Hard Rock account funded ($100).
- [ ] After the `is_paper` migration (`migrate.yml`) — done 2026-09-01.
