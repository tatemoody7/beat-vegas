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
- Only games whose verdict on the This Week page is **BET** are bettable.
  WATCH is not a bet. Passing costs nothing.

## Which markets

- **Real money: first-half (1H) unders only.** That is the only market with
  any measured edge (backtest: top 20% of games by gap went under 54.0%,
  +3.0% ROI out-of-sample, proxy-graded — small and unconfirmed vs real lines).
- Full-game is decision-support only. Its backtest on real lines found no
  edge; it stays on the board as context.
- Bets are placed on Hard Rock Bet (the only Florida book). Always check the
  Line Check page first: a Hard Rock price worse than the market's fair price
  turns a BET into a WATCH.

## What BET means (lib/verdict.ts)

A game is BET when all of these hold:

1. The model has a read (both teams have played 2+ games; weeks 1–2 never
   qualify by design).
2. The Vegas first-half total sits **≥ 1.75 points above our number** — the
   top-20% gap band the backtest validated. (≥ 3.0 points = top-10%, "high"
   confidence when the classifier agrees at 53+.)
3. A **live** first-half line has actually been captured — never an estimate.
4. Hard Rock's under price is fair or better vs the market's no-vig fair
   price.

Sigma (~12 points) is the noise of any single game's outcome. It is why
every card says "still close to a coin flip on any single game" and why we
bet many small edges rather than one big one. It is not a gate.

## Weeks 1–2 (no model)

- Any bet is a **price bet**, not a model bet: Hard Rock's under paying
  better than the market's fair price. These show as WATCH — "price edge
  only". Fewer bets is the right answer; the bar is high.
- Before any bet: read the Week Preview injury lines (unofficial ESPN) — the
  number does not know about a starting QB being out.

## Weekly rhythm

| When (ET)        | What                                                    | Where               |
| ---------------- | ------------------------------------------------------- | ------------------- |
| Sunday ~1–2pm    | Full-game openers captured; pace/weather refreshed; board scored; derived 1H lines posted | `sunday.yml`        |
| Sun 10am–1:45pm  | Hard Rock opener push alerts (every 15 min)             | `lines_watch.yml`   |
| Tue / Fri 9am    | ESPN news + injuries → Week Preview                     | `research_preview.yml` |
| Friday 1pm       | First-half line sweep (max 18 events, credit-guarded)   | `lines_watch.yml`   |
| Friday evening   | **Bet card**: This Week page reviewed, picks logged, text sent | Tate + Claude   |
| Sat 10:30am, 6pm | Closing 1H lines captured (for CLV)                     | `lines_watch.yml`   |
| Monday 8am       | Finals + 1H play-by-play refreshed; all ledgers graded  | `grade.yml`         |
| Monday           | Weekly review together; adjust for next week            | `/weekly-review`    |

## Measuring, not promising

- The truth metric this season is **closing-line value (CLV)** on real
  Hard Rock/consensus closes, plus the graded record. Win rate over a few
  weeks is noise; CLV shows up fast.
- Paper picks (stake 0, `is_paper`) track what the model alone would bet
  from week 3 on, kept apart from the real record, so "trust the model" is
  an evidence-based call later in the season.

## Pre-flight checklist (do once)

- [ ] Install the Pushover app and register this phone on the user key —
      the API currently answers "no active devices", so alerts reach nobody.
- [ ] Vercel env: `BANKROLL_USD=100`, `UNIT_USD=10` (defaults match).
- [ ] Hard Rock account funded ($100).
- [ ] After the `is_paper` migration (`migrate.yml`) — done 2026-09-01.
