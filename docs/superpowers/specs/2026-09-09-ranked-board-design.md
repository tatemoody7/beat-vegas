# Rank the board, light up the bets

2026-09-09. Agreed with Tate in a brainstorming session.

## Why

The card badge on the board is a 0–100 score. It is an abstract number you have to
translate before it tells you anything, and nothing on the page says the board is already
sorted by it. Because the week is grouped by day, the strongest game of the week can sit
visually below a weaker one.

Say the ordering out loud instead. Every game carries its rank among the whole rolling
week, and the games that clear every gate light up so the eye lands on them first.

The 0–100 score does not go away. It still sets the badge colour, still decides
Bet/Watch/Pass, and still drives Results and Research. It stops being the thing you read
on the board.

## Decisions

| Question | Decision |
| --- | --- |
| Board shape | Keep the Thu/Fri/Sat/Sun day groupings; add a **week-wide** rank to each card |
| Badge content | Rank replaces the score: `#1` big, tier word underneath |
| Played games | No rank. Settled shows `WON`/`LOST`/`PUSH`; kicked off but ungraded shows `LIVE` in grey |
| Filters | Ranks never renumber — filtering to Saturday shows `#2`, `#5`, `#9` |
| Universe | Every game on the board is ranked, including no-model rows |
| Existing `capRank` | Unchanged, but relabelled "cap slot" wherever it renders so the two numbers cannot be confused |
| Lit colour | **Green** (`--good`), the colour that already means bet and won |
| Lit treatment | Green border plus a soft green wash on the card. Bet only |
| Where the score goes | Inside the expanded card, under "Our number" |
| Glossary | New "Rank" term; the score entry stays but is reworded |

## Rejected

- **Gold.** It sits next to `--warn` (`#f0b04a`), which already means Watch. A gold Bet
  card above an amber Watch badge reads as the same signal.
- **Light blue.** `globals.css` reserves cyan for chrome — links, nav, buttons — and says
  never to put it on a grade. Lighting Bet cards in cyan would be the first time cyan
  carries meaning.
- **One flat ranked list.** Dropping the day headings gives a truer best-to-worst order
  but loses "what is on today", which is how the week is actually bet.
- **Renumbering on filter.** A game that changes number depending on your filters is a
  number you cannot trust.

## Design

### The rank

`assignBoardRanks` in `web/lib/homeBoard.ts` numbers an already-sorted list 1…N. Only games
that have not kicked off get a number; a kicked-off game is no longer a decision, so it
carries `null` and shows its result instead. It runs inside `getHomeBoard`, over the whole
week, before the page applies filters — which is why filtering cannot renumber.

It is deliberately separate from `assignCapRanks`, which ranks BETs by `gap` with held
picks first to fill the five-bet weekly cap. The two orders usually agree because score is
a linear function of gap, but they answer different questions.

### The badge

`ScoreBadge` resolves one of three states:

- **settled** — result colour, single centred word `WON` / `LOST` / `PUSH`
- **kicked off, not settled** — grey, single centred word `LIVE`
- **otherwise** — score-band colour, `#N` over the tier word

`#` rather than a bare numeral: it reads unmistakably as a rank, matches how the bet slip
already writes ranks, and keeps two glyphs in a block sized for "81".

### The lit card

A Bet card that has not kicked off gets `.bv-card--lit`: a green border and a green wash
behind the card. Watch and Pass are untouched, so lit means act. The hover rule needs a
companion because `.bv-card[data-interactive="true"]:hover` hard-codes a cyan border that
would otherwise steal the green.

No animation, so the existing `prefers-reduced-motion` block needs no change.

### Copy

The board explainer, the tier legend and the glossary all currently describe the score as
the thing on the board. They are reworded around the rank. The glossary keeps its score
entry — Results and Research still show scores — and gains a Rank entry.
