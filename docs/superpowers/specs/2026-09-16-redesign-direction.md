# Site redesign direction — agreed 2026-09-16

Discovery session with Tate: every page and state captured at 1440 and 390, seven rounds
of questions, two mockup rounds, and two research reports (`2026-09-16-redesign-research-
inspiration.md`, `2026-09-16-redesign-research-workflow.md`, same folder). This file is the
record of what was decided, so a later session does not re-ask.

## The one-line direction
Same family, sharper. Structure, cards, typefaces, colours and the board's action sentence
all stay. Copy is cut to the bone. Results and Track record change form (cards that only
hold numbers become tables; single sentences stop getting boxes). Board and game page get a
refinement pass. Desktop first; the phone must work.

## Stays exactly (do not re-litigate)
- Three tabs: Board / Results / Track record, plus `/game/[id]` and `/proof/records`.
- Board: a gradient card per game, badge colour driven by the score band (green means the
  gap clears 1.75, NOT "bet today" — Tate chose to keep that), the FULL action sentence (a
  trimmed "Not yet · needs -110" form was shown and rejected), the answer bar as is, both
  filters, the tier-count line, day grouping.
- Game page: the three stat tiles, the full per-book Lines table, the tinted factor bars
  and the five small rows, Rotowire injuries, ESPN headlines, the log form as is.
- Results content: the rule's paper record, bankroll + curve, the four comparison records,
  the breakdown (week / reason / blocker), decisions (vs close, timing), the factor read
  table, the picks table, week and season selects, the paper chip per row.
- Geist / Geist Mono / Archivo at today's sizes; navy + cyan + green/red.

## Changes
1. **Copy.** Every caption and footnote a returning user does not need goes. Keep: the
   banners (stale results, missed build, paused), the one caveat line under the headline
   number on Track record, and any caption that states a threshold (52.4% break-even,
   "counts until 30"). A definition lives once, in the glossary.
2. **Game page decision block** = badges, three tiles, action sentence, log button. Removed:
   `GapBar`, the gap caption, the amber blocker line, the price line, the tier word in the
   sticky header, the full-game footer under Lines.
3. **Results → "Scoreboard".** One card-band with three numbers (the rule on paper / my
   money / line value, each with its record and interval or note) and the bankroll curve
   inside it. The season summary is ONE table (Market 1H, Model 1H, the rule on paper, You,
   Market full game dimmed). "Your decisions" is one two-column key/value strip. The factor
   read is a coloured word, not a pill. The picks table is unchanged in content.
4. **Track record → "One finding".** The headline and the gap ladder share one card; games
   and units print under each bar, so the band table goes. The record cards become one
   table with a "plausibly" interval column. The three 2026 cards become one table. "What
   to change" is unchanged. ONE fold, "Method and sanity checks", holds the estimated-line
   grade, how the number is built, the accuracy table and the line study. The glossary is
   a two-column list of one-liners; the `#glossary` anchor keeps working.
5. **Boxes.** A single sentence never gets a card. The records-page legend is a plain list.
6. **Header.** One row at every width: wordmark, three tabs, Lock (an icon below `sm`).
   Measured 69px at 360 / 375 / 640 / 1440; `--header-h` is one value (4.25rem).
7. **Consistency.** Dead classes deleted (`.bv-stat`, `.bv-stat-value`, `.bv-fac-tier`,
   `.bv-badge--good/--bad/--wrap/--solid*`); `--border-soft` collapsed into `--border`;
   `--push` is an explicit alias of `--text-dim`; `--accent-line` replaces five spellings
   of cyan-at-alpha; one `.bv-chip` for the board filters and the breakdown tabs;
   `.bv-btn--ghost` for Lock; every board row (a link) lifts on hover; the bankroll chart
   uses the same three colour constants as the other two charts.
8. **`/proof/records`** opens on the latest week with a graded game (it opened on week 15,
   one pending row, because the schedule is present from day one).

## Order of work and how it ships
Foundations (this PR) → Results → Track record → game page → Board, one PR each. Tate
reviews the Vercel preview and merges on any day of the week. Gate semantics never move:
`pickRules.checkPolicy` is the money path and `tests/test_gate_parity.py` reads the
constants out of `verdict.ts` / `grade.ts` / `edge.ts` / `lineCheck.ts` / `books.ts` /
`card.ts` by regex — renaming or deleting an export there breaks the card/site agreement.

## Measuring it
`web/scripts/shots.mjs` captures every page at 1440 and 390 with Playwright driving the
installed Chrome (`channel: "chrome"`, no download) and writes height, horizontal overflow,
header height, scroll depth to the first answer, text under 12px and tap targets under
24/44px to `report.json`; `--diff before after` prints the deltas. Baseline on 2026-09-16
(main): Board 7,396 / 11,053px, Results 3,408 / 5,999, Track record 2,840 / 4,470 closed,
game page ~1,900–2,200 / ~2,700–3,100; zero horizontal overflow anywhere. Look at the
picture as well as the numbers: screenshots caught four defects on 2026-09-13 that the DOM
checks could not. The Browser pane's screenshots are useless for this; its JS is fine.

## Usability checks per page (before and after)
Task 1: from `/`, name this week's bets and the price each needs, under 10 seconds, no
scroll on desktop. Task 3: from `/results`, the real-money record and bankroll with no
clicks. A five-second fold test per page: "what is this page telling you to do?" Nothing
ships that makes task 1's time or the first answer's scroll depth worse.
