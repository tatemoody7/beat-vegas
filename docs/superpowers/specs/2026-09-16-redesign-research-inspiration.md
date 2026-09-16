# Beat Vegas redesign — visual/UX inspiration research

Researched 2026-09-16 with WebSearch + WebFetch. Each product below has at least one fetched or
search-verified source; where a primary page 403'd (ACM, KenPom, Torvik, OddsJam, Bloomberg UX,
Apple HIG) the claim rests on the secondary source cited and is marked *(secondary)*.
Intended destination was
`/private/tmp/claude-501/-Users-tatemoody-Desktop-Beat-Vegas/a3ffb168-8126-4c01-a78e-8634022b022d/scratchpad/research_inspiration.md`;
plan mode restricted writes to this file. Copy it across when out of plan mode.

Framing rule from the owner: **"if it isn't obvious I don't want it."** Every pattern below is
filtered through that — the question asked of each product is "how does it turn a dense number
into a decision without a paragraph."

---

## Part 1 — Products, by category

### 1. Sportsbooks and betting tools

**Pinnacle** — https://www.covers.com/betting/reviews/pinnacle ·
https://sports-arbitrage.com/opinion/pinnacle-sports/
Function-over-flash book: reviewers describe an interface that "prioritizes functional
efficiency over visual design," a compact layout that carries every market, and a plain
dark/light toggle plus an odds-format toggle. The pattern is *density without decoration*: the
price is the product, so nothing competes with it.
- **Steal:** the odds cell is the only bold thing in the row; everything else is quiet text.
- **Do not copy:** its plainness reads "dated" to several reviewers — there is no hierarchy
  between a game you care about and one you don't. Beat Vegas has a rank; use it.

**Betfair Exchange (market view)** —
https://www.betfair.com.au/hub/education/betfair-basics/read-an-exchange-market/ ·
https://betting.betfair.com/how-to-use-betfair-exchange/beginner-guides/reading-the-betfair-screen-010819-51.html
The best back/lay prices sit in two coloured cells (blue/pink); the next-best sit in white
either side. Each cell: price **bold** on top, liquidity beneath in small type. Two book
percentages sit above the market so you can see the overround at a glance.
- **Steal:** *one colour = "this is the actionable cell"*, neighbours stay neutral; and the
  two-line cell (big fact / small qualifier) — for Beat Vegas: line on top, price beneath.
- **Do not copy:** the six-cell ladder. Beat Vegas has one book that matters; showing depth
  invents a decision that does not exist.

**Unabated (odds screen)** — https://unabated.com/articles/learn-about-the-game-odds-screen ·
https://xclsvmedia.com/unabated-review-2026-premium-sharp-bettor-tool-worth-it/
A grid of books per game with the vig-free "Unabated Line" as the reference column; a
negative synthetic hold or a positive edge "lights up in green," a line move flashes yellow
and fades, and a small latency dot beside each book name says how fresh its price is.
Reviewers call it "a Bloomberg terminal for sports betting, and that's intentional."
- **Steal:** a **freshness dot** next to a price (Beat Vegas already stores
  `price_provenance` and capture time — a one-glyph honesty marker beats a caption); green
  only when a threshold is cleared, nothing for "close."
- **Do not copy:** the many-book grid. The user has one book; the other books belong on the
  game page's `BookTable`, not the board.

**OddsJam (Positive EV tool)** —
https://oddsjam.com/betting-education/how-to-use-the-oddsjam-positive-ev-tool *(secondary:
https://www.rotowire.com/betting/oddsjam-review)*
Each row is one bet; the book/price you should take is **bolded with a blue outline**;
columns are EV%, no-vig fair odds and a Kelly stake; clicking the row expands to every book's
price in place.
- **Steal:** *in-row expansion* for the "why," and the recommended action being the single
  visually loud element in the row.
- **Do not copy:** an EV% column. On Beat Vegas `ev` is a price-shopping number, not wager
  EV (`docs/RANKING_AND_TRUST.md` §8b); printing it as if it were the edge would be the one
  thing the site must never do.

**Pikkit / Juice Reel (bet trackers)** — https://8rainstation.com/blog/pikkit-reviewed-the-most-popular-free-sports-bet-tracking-app ·
https://www.betsmart.co/tool-reviews/pikkit · https://props.com/top-sports-betting-tracking-tools-juice-reel-review/
Synced ledgers with a P&L calendar, CLV per bet, and a dashboard "that shows your habits and
patterns." Reviewers praise Pikkit's polish but "some users find the layout confusing" when
looking for key info.
- **Steal:** CLV shown *per bet in the ledger row*, not only as an aggregate; a month/week
  calendar of P&L as an alternative to a bankroll curve (a grid of coloured days is a chart
  that needs no paragraph).
- **Do not copy:** social feeds, leaderboards, streaks — pure engagement mechanics for a
  one-user tool.

**Kalshi / Polymarket** — https://www.si.com/prediction-markets/reviews/kalshi ·
https://www.humaninvariant.com/blog/pm-interface · https://avark.agency/learn/prediction-market-design-patterns
Price in cents *is* the probability ("65¢ = 65%"), "pricing front and center rather than
buried in a menu," Yes/No as the only two controls. The critique worth reading (humaninvariant)
is that both platforms "tout the midpoint price as the probability … regardless of the spread"
— i.e. they hide how thin the number is.
- **Steal:** one number that *is* the decision, two buttons, nothing else above the fold.
- **Do not copy:** a confidence-free point estimate. Beat Vegas's whole ethic is the opposite
  (see Part 2d).

**Action Network / Hard Rock Bet** — https://rotogrinders.com/sports-betting/guides/best-odds-apps ·
https://www.sharpfootballanalysis.com/sportsbook/reviews/hard-rock-bet-review/ ·
https://www.vegasinsider.com/sportsbooks/hard-rock/app/
Hard Rock: black/white/purple, "minimalist user interface … reacts super quickly," a three-pane
web layout (nav / events / slip). Action: side-by-side book prices so "there's no guesswork."
- **Steal:** speed as design — Hard Rock's reviewers rate responsiveness above looks;
  the board should feel instant (no animation on load; Recharts already needs
  `isAnimationActive={false}`).
- **Do not copy:** the persistent bet slip pane. Results is read-only by decision
  (2026-09-13); logging lives on `/game/[id]` only.

### 2. Trading / finance

**Robinhood** — https://design.google/library/robinhood-investing-material ·
https://www.shadcn.io/design/robinhood
"The user can launch the app and glimpse the health … without reading a single word": the
whole screen tints green/red by portfolio state; each holding is a card whose price is a large
dominant number with the chart secondary. Design-system write-ups record Inter with
`tabular-nums` mandated for all prices so "digits never jitter as values update."
- **Steal:** *state as one colour + one big number*, chart demoted; tabular figures
  everywhere a number can change.
- **Do not copy:** whole-screen tinting. Beat Vegas reserves green/red for outcomes and
  grades; painting the canvas would erase that language.

**Bloomberg Terminal (aesthetic)** — https://mattstromawn.com/writing/ui-density/ ·
https://www.lippihom.com/blog/designing-for-cognition-the-enduring-value-of-high-information-density-interfaces ·
https://www.bloomberg.com/company/what-we-do/ux/ *(secondary)*
Ström's essay reframes density as "the value a user gets from the interface divided by the
time and space the interface occupies," and names Bloomberg's real edge: "it loads data almost
instantaneously." Homnack: "closer to a cockpit than a gallery."
- **Steal:** temporal density — a page that answers before you scroll. And the idea that
  "some whitespace has meaning almost as salient as the darker pixels": space is a grouping
  device, not padding.
- **Do not copy:** the amber-on-black palette and the everything-on-one-screen cockpit.
  One user, one decision per row; the Terminal serves a thousand workflows.

**Stripe Dashboard** — https://www.925studios.co/blog/stripe-dashboard-design-breakdown ·
https://www.webdesignhot.com/design.md/stripe/
Home is "five numbers … with small sparklines showing direction. No chart grid, no
customizable widget layout, no 'add metric' button." Colour signals status only — "a red
indicator always means attention required, not just 'this is the red category.'" Numerics
right-aligned, labels left, hairline rules, **no zebra striping**; `tnum` on data, `ss01` in
prose, the two never overlap. Six type sizes/weights carry hierarchy so colour never has to.
- **Steal:** "the chart is a summary and the table is the truth"; hairline rows; the
  no-add-metric discipline.
- **Do not copy:** sparklines by default. Stripe's numbers are time series; a hit rate over
  31 picks is not a trend and a sparkline would fabricate one.

**Mercury** — https://www.925studios.co/blog/mercury-design-breakdown ·
https://www.themasterly.com/blog/fintech-dashboard-design-guide
"Red and yellow appear only for errors and warnings. There are no aggressive accent colors."
Leads with the balance and a visible trend; controls one level down. Density explicitly
calibrated *low* for its persona (founders) where Ramp's is *high* (finance teams).
- **Steal:** the rule that colour has exactly one meaning site-wide, and the
  "role → metric → density → action" framing: Tate is one role; pick one density and hold it.
- **Do not copy:** Mercury's low density. Tate's job on Saturday is scanning 50 rows; the
  board wants Ramp-level density with Mercury-level colour discipline.

**Ramp** — https://www.themasterly.com/blog/fintech-dashboard-design-guide ·
https://styles.refero.design/style/b38702a0-75ab-474c-9106-00b624535825
Opens on *savings* (the outcome), not spend; near-monochrome with one highlighter accent that
"appears only where money moves — CTAs, live counters, active states."
- **Steal:** the accent marks *where action happens* and nowhere else — for Beat Vegas
  the cyan belongs on the Log-pick control and active nav, never on a number.
- **Do not copy:** bento-grid marketing energy. Rows, not tiles.

**Copilot Money** — https://blakecrosley.com/guides/design/copilot-money ·
https://moneywithkatie.com/copilot-review-a-budgeting-app-that-finally-gets-it-right/
Ultra-dark navy canvas (#000814, cards #001533, elevated #00204D) chosen over pure black
because "pure black creates harsh contrast that causes eye strain during extended sessions";
text at 90% white; one semantic colour per money concept (income green, spending red-orange,
net-worth blue, pending yellow).
- **Steal:** the navy-not-black argument and the three-step surface stack that separates
  cards *without borders*. Beat Vegas's `--bg #070b16 / --surface #111a2e / --surface-2
  #16213a` is already this shape.
- **Do not copy:** "charts as the primary interface." Copilot is a chart app; Beat Vegas
  rejected three charts on Results because they needed captions.

**TradingView** — https://www.tradingview.com/support/solutions/43000745825-mastering-the-tradingview-watchlists/ ·
https://www.tradingview.com/support/solutions/43000718866-tradingview-stock-screener-trade-smarter-not-harder/
Watchlist rows show exactly three metrics (last, change, % change) by default; a menu toggles
more; the screener has a Table/Chart view toggle and hides the filter panel for more table
space.
- **Steal:** three numbers per row as the default and *user-added* columns as the exception.
- **Do not copy:** the screener's 50-column customizability — the board's columns are a
  design decision, not a preference.

### 3. Analytics / data SaaS

**Linear** — https://linear.app/now/how-we-redesigned-the-linear-ui ·
https://blog.logrocket.com/ux-design/linear-design-ui-libraries-design-kits-layout-grid/
The redesign "reduce[d] visual noise, maintain[ed] visual alignment, and increase[d] the
hierarchy and density of navigation elements"; theming moved to LCH so "a red and a yellow
color with lightness 50 will appear roughly equally light to the human eye"; chrome blue was
deliberately *limited* for "a more neutral and timeless appearance"; Inter Display for
headings, Inter for body.
- **Steal:** equal-lightness status colours (good/warn/bad should weigh the same on the
  eye so no grade shouts), and the invisible alignment work — "something users experience
  after extended use."
- **Do not copy:** Linear's row is an issue with six inline properties. A board row needs
  two facts and a sentence.

**Vercel dashboard / Geist** — https://vercel.com/geist/colors ·
https://www.designsystems.one/design-systems/vercel-geist · https://designmd.app/brands/vercel/
Ten-step grey scale with fixed roles: 100–300 backgrounds (default/hover/active), 400–600
borders, 900–1000 text (secondary/primary); "Background 2 should be used sparingly." Third-party
write-ups: accent "appears only in links, active nav items, and status badges — never as a
background fill at rest"; Geist Mono "only for code, commands, paths, timestamps."
- **Steal:** *numbered surface roles* (Beat Vegas's tokens map cleanly onto this) and the
  accent-as-punctuation rule, which the site already states in `globals.css`.
- **Do not copy:** pure #000 canvas — Vercel's identity, not a readability choice
  (see Part 2f).

**PostHog** — https://posthog.com/blog/posthog-as-a-dev-tool · https://getdesign.md/posthog/design-md
Dark mode added by demand; "packs a lot of analytics into a dark UI while keeping charts and
tables legible."
- **Steal:** their dark mode is *grey-neutral with warm text*, which keeps status colours
  legible without desaturating them.
- **Do not copy:** the hedgehog whimsy and multi-product nav — irrelevant to a 3-page tool.

**Grafana** — https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/ ·
https://oneuptime.com/blog/post/2026-01-30-grafana-stat-panel-thresholds/view
"A dashboard should tell a story or answer a question"; "if I show this to someone else, how
long will it take them to figure it out?"; stat panels turn colour at thresholds and **the
threshold on screen should equal the threshold you act on** ("if an alert fires at 90% CPU, the
panel should turn red at 90%").
- **Steal:** *display threshold = action threshold*. Beat Vegas's 70-score/1.75-pt gate is
  exactly this; the colour flip must sit at `BET_GAP_PTS`, never a rounded neighbour.
- **Do not copy:** panel sprawl and per-panel legends.

**Observable Framework** — https://old.observablehq.com/blog/seven-ways-design-better-dashboards ·
https://observablehq.com/blog/takeaways-from-building-showcase-dashboards
"Big numbers also help with the visual hierarchy. They say, look here first!"; Shneiderman's
"overview first, zoom and filter, then details-on-demand"; "if a color is used in multiple
data visualizations, it should mean the same thing."
- **Steal:** the big-number card as the *entry point* to a section, with detail folded
  beneath (`Fold.tsx` already does this).
- **Do not copy:** coordinated multi-view brushing — interaction the owner will not use.

**Metabase** — https://www.metabase.com/learn/metabase-basics/querying-and-dashboards/dashboards/bi-dashboard-best-practices
"Avoid mistaking a good looking, colorful dashboard for one that's informative. Often what you
really need is just a mix of time series and tables." Trend arrows recolour so a metric you
want *down* still gets green; "a simple goal line … or conditional formatting on a table" answers
"are these values good?"
- **Steal:** the goal line as the one annotation a chart earns (the break-even line on
  `GapLadderChart`), and direction-aware colour (CLV: negative stored = good, already
  handled in `record.ts`).
- **Do not copy:** its card-count agnosticism; Results proved fewer headings is the fix.

### 4. Sports analytics / editorial

**KenPom / Bart Torvik** — https://www.hoopshq.com/long-reads/kenpom-com-is-college-basketballs-premier-analytics-site-but-its-founder-never-planned-for-it-to-happen ·
https://www.covers.com/ncaab/what-are-torvik-ratings *(both sites 403 to fetchers)*
One giant table, unchanged for a decade, that "every number is easy to find, read and
understand." Value cells carry a tiny rank beside them; green/red shading is a gradient of the
value itself (dark green high, bright red low, "lighter hues for mid-range"). Torvik copies the
layout almost exactly and adds a date-range filter "similar to searching flights."
- **Steal:** *value + tiny rank in the same cell* — Beat Vegas's rank badge could carry the
  gap beside it; and a single-table page with no cards at all as a legitimate design.
- **Do not copy:** heat-map shading of every cell. It works for 360 teams × 20 stats; on a
  50-row board it turns colour back into decoration.

**Baseball Savant (percentile sliders)** — https://baseballsavant.mlb.com/leaderboard/percentile-rankings ·
https://baseballsavant.mlb.com/visuals
Savant's own text: "If a player ranks highly, that data set will be red. As a player fades
toward the 50th percentile, that color will fade to neutral and eventually blue." Each metric
is a horizontal bar with the percentile in a bubble; the actual value is optional.
- **Steal:** the *one-axis bar with a number bubble* — the same object as `GapBar.tsx`.
  Its power is that neutral is grey and colour only appears at the extremes.
- **Do not copy:** stacking 15 of them. On the game page, one bar (the gap) earns colour;
  factor rows stay text.

**FiveThirtyEight (RIP) + the trust research** —
https://mucollective.northwestern.edu/?p=551 (CHI 2024, Best Paper) ·
https://statmodeling.stat.columbia.edu/2020/11/06/is-there-a-middle-ground-in-communicating-uncertainty-in-election-forecasts/ ·
https://magazine.northwestern.edu/exclusives/understanding-uncertainty
538 moved from a headline percentage to frequency framing (grids of maps, ball swarms). The
CHI study of four uncertainty displays found "text summaries and quantile dotplots engender the
highest trust over time" after a surprising outcome; fancier probability-correction tricks
"showed minimal impact."
- **Steal:** *a plain sentence with the interval in it* is the most trusted display there
  is — "58.8% under over 51 bets; could plausibly be anywhere from 45% to 71%."
- **Do not copy:** the animated needle. 538's 2016 needle is the canonical example of
  uncertainty display that destroyed trust (https://plotset.com/blog/the-chart-that-broke-america-s-trust-in-polls).

**ESPN FPI** — https://www.espn.com/college-football/fpi ·
https://fan-insider.com/espns-football-power-index-your-ultimate-guide-key-insights/
The Matchup Predictor is "something you can't miss": one percentage per game, team-coloured,
projected margin beneath. FPI itself is "how many points above or below average a team is" —
a number on the same scale as the thing bet.
- **Steal:** state the model output in the *unit of the bet* (points, not a 0–100 score).
  Beat Vegas already did this on the game page; keep the score off the board.
- **Do not copy:** team-colour-driven UI. Two teams' colours fight the grade colours.

**PFF** — https://www.pff.com/grades · https://www.pff.com/news/pff-premium-stats-2-updates-to-pff-grades
A 0–100 grade with **named bands** (90+ elite, 80–89, 70–79, <70) and one colour per band in
the premium tables (dark blue elite, dark green high quality).
- **Steal:** *banded, named colour* rather than a continuous ramp — five words the reader
  memorises once. Beat Vegas's 70/55 bands are the same idea.
- **Do not copy:** grading everything. PFF grades every player every snap; a board grades
  one thing per row.

**Apple Sports (Lickability critique)** — https://lickability.com/blog/apple-sports/
Scores set in the system variable font with "the weight bold and the width compact"; the
"Yesterday / Today / Upcoming" picker is a low-profile segmented control; table headers wrap
rather than truncate at large Dynamic Type.
- **Steal:** compact-width bold numerals for scores/lines (Archivo has a `wdth` axis — a
  condensed cut for the line column is one CSS line); the three-segment day picker maps
  straight onto Board/Results/Track record.
- **Do not copy:** animated gradient backgrounds.

### 5. Design references for dark data UIs

**Radix Colors** — https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale
12 steps, each with one job: 1–2 app background, 3–5 component bg (normal/hover/pressed),
6–8 borders (6 non-interactive, 7 interactive, 8 strong), 9–10 solid fills, 11 low-contrast
text, 12 high-contrast text. Dark scales are separate, not inverted.
- **Steal:** give each token a *step number and a job*; audit `globals.css` against it
  (`--border` = step 6, `--border-strong` = 7/8, `--text-dim` = 11, `--text` = 12).

**IBM Carbon data-viz** — https://carbondesignsystem.com/data-visualization/color-palettes/ ·
https://medium.com/carbondesign/color-palettes-and-accessibility-features-for-data-visualization-7869f4874fca *(secondary)*
Dark-theme chart backgrounds restricted to the darkest theme grey for maximum contrast;
categorical palettes are *ordered* to maximise neighbour contrast; alert colours are fixed
(red danger, orange serious, yellow warning, green normal).
- **Steal:** chart canvas = page canvas (no lighter chart card), and never more than one
  categorical hue on a bar chart that is really a single series.

**Material 3 data-viz** — https://m3.material.io/blog/data-visualization-accessibility ·
https://m2.material.io/design/communication/data-visualization.html
"Less is more … remove elements that don't directly enhance understanding"; comparisons must
be truthful; one metric set, one colour set, one style set.
- **Steal:** M2's dark surface guidance (#121212 not #000) and the truthful-axis rule —
  the gap ladder's y-axis starts at 0 or is labelled that it does not.

**Apple HIG typography / `monospacedDigit()`** —
https://developer.apple.com/design/human-interface-guidelines/typography ·
https://developer.apple.com/documentation/swiftui/font/monospaceddigit() *(pages are JS-rendered; the API exists precisely for aligning changing numerals)*
SF Mono for aligning columns; system fonts ship monospaced digits as a font variant so numbers
in lists line up without switching typeface; avoid Ultralight/Thin/Light weights.
- **Steal:** never use a weight lighter than Regular for a number on dark.

**Tailwind Plus / shadcn tables** — https://tailwindcss.com/plus/ui-blocks/application-ui/lists/tables ·
https://www.shadcn.io/blocks/tables-sticky-header · https://www.setproduct.com/blog/data-table-ui-design
Setproduct's rules: text left, "numbers, currency, percentages align right, so digits line up
by place value"; "a full grid of lines fights the data for attention" — one subtle row
separator; "a sticky header becomes mandatory the moment a table is tall enough that the column
titles scroll out of view"; ≥24px hit targets (WCAG 2.2), 48dp touch (M3).
- **Steal:** all of it — these are the table defaults the picks ledger should adopt.

**Dark-mode readability sources** —
https://www.smashingmagazine.com/2025/04/inclusive-dark-mode-designing-accessible-dark-themes/ ·
https://nowah.xyz/blog/pure-black-vs-dark-gray ·
https://www.colorcontrast.org/blog/dark-mode-contrast-accessibility-guide/
Covered in Part 2f.

---

## Part 2 — Patterns for Beat Vegas (named, grouped)

### (a) List/row design for a ranked board

**P1. One loud cell per row.** Betfair colours only the best price; OddsJam bolds only the
recommended book; Pinnacle bolds only the odds. *Why:* the eye lands on one thing and the
rest is context. *Beat Vegas:* the loud cell is Hard Rock's **line** (bold, display font,
condensed width). Rank badge, kickoff, matchup, price are quiet. Today the rank badge, the
line, and the action sentence compete.

**P2. Two-line numeric cell (fact / qualifier).** Betfair: price bold, liquidity beneath.
*Beat Vegas:* `41.5` over `−115 · 2h ago`. Puts the price and freshness under the line without
a new column.

**P3. Freshness glyph, not a caption.** Unabated's latency dot. *Why:* provenance is a
per-row fact; a sentence about it repeats 50 times. *Beat Vegas:* one 6px dot before the price
— solid = captured this build, hollow = older, none = no Hard Rock price. It replaces the
"stale results" banner for the row-level case.

**P4. Value with a tiny rank beside it.** KenPom's `52.3 ¹²`. *Beat Vegas:* the rank badge
already exists; the *gap* could sit as a small tabular number beside it so ranking and reason
share one glance (rank is gap-only, per `beat-vegas-rank-is-gap-only.md`).

**P5. Three numbers per row, no more.** TradingView's default watchlist. *Beat Vegas:* line,
price, gap. Anything else is the game page. The action sentence is prose, not a fourth number.

**P6. Row = link, expansion = game page.** OddsJam expands in place; Beat Vegas chose the
link (2026-09-10) and should keep it — in-row expansion "makes row comparison impossible"
(Willison). The pattern to add from OddsJam is *hover/focus reveals the one-line why* on
desktop only.

### (b) Showing a decision and its confidence without a chart

**P7. Verb first, condition after.** Ramp attaches a next action to every metric; OddsJam's
row is a bet you can place. *Beat Vegas* already writes "Not yet — needs −110 or better."
Tighten to a fixed grammar: `BET` / `NOT YET · needs −110` / `PASS · gap 0.8` so the first word
is scannable down a column of 50.

**P8. Display threshold equals action threshold.** Grafana's rule. *Beat Vegas:* the colour
flips at `BET_GAP_PTS` and at the kill price, never at a rounded score; the gate parity tests
already enforce the values — make the colour token derive from the same constant.

**P9. Single-axis bar, grey-neutral, colour at the extremes.** Baseball Savant sliders =
`GapBar.tsx`. *Rule:* grey until the bar crosses the gate, then `--good`; tick the kill number.
No second bar on the page.

**P10. Confidence as a sentence with a range, not a meter.** CHI 2024: text summaries and
quantile dotplots kept trust after a surprise; needles and point percentages did not.
*Beat Vegas:* "The rule has gone 30-21 at real closes (59%); with 51 bets that could plausibly
be 45–71%." One line under the big number. No confidence meter (already removed).

### (c) Ledgers / tables of bets

**P11. The table is the truth; the chart is a summary.** Stripe. *Beat Vegas:* the picks
ledger is the source; `BankrollHero` is its summary. Nothing on Results should exist that
cannot be recomputed from the ledger rows on screen.

**P12. Right-aligned tabular numerals, left-aligned text, hairline rows, no zebra.**
Stripe + Setproduct. Verified this session: **Geist Sans's default digits are proportional
(advance widths 384–663 units), so `font-variant-numeric: tabular-nums` is load-bearing on
every Geist-set number**; Archivo's digits are 575–577 (near-uniform) and it carries `tnum`;
Geist Mono is 600 fixed. `globals.css` already sets `tabular-nums` in four places — extend it
to every `td` holding a number.

**P13. Colour = state, and one state only.** Stripe: "a red indicator always means attention
required"; Mercury: red/yellow only for errors/warnings. *Beat Vegas* already reserves
green/red for won/lost and bet/pass — the ledger's *edit* affordance and *bonus* flag must stay
neutral (cyan chrome or grey pill), never green.

**P14. CLV per row, direction-aware.** Pikkit shows CLV per bet; Metabase recolours arrows
so "down" can be green. *Beat Vegas:* print `+1.5` (already negated for display) with the
arrow pointing the way the market moved *toward* us; the raw stored sign never reaches the UI
(`beat-vegas-clv-sign-is-inverted.md`).

**P15. Sticky header past one screen; paginate by week.** Setproduct; `/proof/records`
already paginates. The picks table needs `position: sticky` on `thead` once it exceeds the
viewport (it will by week 6).

### (d) Presenting a track record honestly (uncertainty, small n)

**P16. Big number, then n, then interval — in that order, same card.** NN/g's
"79% ± 2.1%" and Observable's "look here first." *Beat Vegas:* `58.8%` display size; `51 bets`
muted beneath; `45–71% plausible` dim beneath that. The interval is text, not error bars — the
gap ladder chart is the *only* place bars appear and it already carries the break-even line.

**P17. Split by grading basis, colour only on real closes.** Already the `/proof` rule
(`basis="estimated"` renders neutral). Keep it; it is the honesty version of P13.

**P18. Name the band, do not ramp it.** PFF's five named bands vs KenPom's continuous
shading. Track record's gap bands (0–1, 1–1.75, 1.75–3, 3+) should each have a fixed label and
a fixed colour; a gradient invites reading precision that n=51 cannot support.

**P19. Say what did not replicate.** Not a product pattern but the owner's own rule
(`beat-vegas-run-the-gate-twice.md`). A "What to change" section on Track record lists
findings *with their status word* (`held`, `did not replicate`, `n too small`) as a plain
three-column table.

### (e) Mobile treatment of dense rows

**P20. Priority columns, pinned first cell.** Willison's demo names it the "top recommendation
for comparison tables"; Setproduct: decide "which columns users truly cannot act without."
*Beat Vegas board at 375px:* rank + matchup pinned left; line/price as the one right-aligned
numeric column; the action sentence wraps beneath as a second line (P2 turned sideways). Gap
and kickoff drop behind the tap.

**P21. Two-line row, not a card.** Apple Sports's score rows and Willison's "multi-row
stacking": two lines per logical row keeps the table rhythm; cards "destroy column comparison."
*Beat Vegas* measured +520px at 375 from logos; a two-line row absorbs the logo and the
sentence without going to cards.

**P22. Touch targets ≥44px on the row, not on inner controls.** The whole row is the link
(already); no inline buttons on mobile rows. The Log-pick control lives on the game page.

### (f) Typography and colour for dark quantitative UIs

**P23. Navy over pure black — for this product.** The case *for* #000 (Nowah): 21:1 ceiling,
OLED power, cards float without shadows. The case *against* (Smashing, Material, colorcontrast.org,
Copilot's own rationale): halation on thin text under ~14px, harsher fatigue over long
sessions, and "for non-OLED contexts (desktop browsers, LCD panels), prefer a dark gray
background (#121212 to #1E293B)." Beat Vegas is read on a laptop for an hour on Saturday
morning with 12–14px numerals — the against case applies. **Keep `--bg #070b16`.** What to take
from the pure-black camp is the *three-step surface stack* (bg / card / elevated) so cards
separate without borders; Beat Vegas currently leans on a 2.2:1 border because the surfaces
sit too close (`#070b16 → #111a2e` is one step; add or use `--surface-2` as the elevated
tier consistently).

**P24. Off-white text, never #fff for body.** Copilot uses 90% white; Vercel's *secondary* text
is #888 on #000. Beat Vegas's `--text #eef2f9` is right; `--text-dim #8b98b0` at 6.0:1 is the
floor for table heads — do not go dimmer for numbers.

**P25. Equal-lightness status colours.** Linear's LCH argument. Check `--good #3ddc84`,
`--warn #f0b04a`, `--bad #f87171` in OKLCH: if their L values differ by more than ~5, the
brightest grade shouts. (Quick check, not a redesign.)

**P26. Accent as punctuation.** Geist/Ramp: accent only on links, active nav, focus rings,
the primary control; "never as a background fill at rest." Beat Vegas states this in
`globals.css`; the audit item is `.bv-card:hover` hard-coding cyan (noted 2026-09-09) — hover on
a BET card should stay green.

**P27. Tabular figures via the font, monospace only for the hero.** dev.to/alanwest: "if you're
using a monospace font purely to stop digits from jittering, you almost certainly want
tabular-nums"; madegooddesigns: teams "switch to a monospace only for the large hero metric."
Beat Vegas uses Geist Mono for secondary hero stats (`RecordCard`, `BankrollHero`) — that is the
sanctioned use. In table cells use Geist Sans + `tabular-nums`, not mono, so labels and numbers
share a rhythm. And the silent-failure warning is moot here: both fonts verified to carry `tnum`.

**P28. Weight carries hierarchy; colour does not.** Stripe's six sizes/weights. On the board:
line = 600–800 display; price = 500 sans muted; sentence = 400. Never Light on dark (Apple).

### (g) Navigation for a 3-page tool

**P29. Three segments, top on desktop, bottom on phone.** Segmented controls "keep segments to
three"; bottom tab bars are "the standard for apps … with 3–5 primary sections" for thumb reach;
Apple Sports's three-way picker is the reference look. *Beat Vegas:* keep `MainNav` as a
segmented control at the top on ≥640px; below that, move the three tabs to a fixed bottom bar
and let `--header-h` shrink to the title row (it was measured at 97px on 375 because the nav
wraps — this removes the wrap).

**P30. The page you land on is the one with the decision.** Ramp opens on savings, Mercury on
balance, Robinhood on the portfolio number. Board is home (already). The answer bar at the top
of Board is the "one number you came for" — keep it to *bets live / next build window* and let
the three-closest list be the first rows of the board rather than a separate block.

**P31. Back-links, not breadcrumbs.** With three pages plus `/game/[id]`, a single "← Board"
on the game page beats a breadcrumb trail. Hard Rock and Kalshi both use one-step back.

---

## Part 3 — Dark data-dashboard showcases to look at

Galleries that show *shipped* product UI rather than concept art (SaaSUI's own comparison
ranks them this way — https://www.saasui.design/best-saas-ui-design-inspiration):

1. **SaaSUI — dashboards category** (real screenshots, filter "Dashboard"): https://www.saasui.design/
2. **Mobbin — web dashboards** (real flows; Robinhood, Kalshi, Linear are all indexed): https://mobbin.com/explore/web/screens/dashboard
3. **Nicely Done — Mercury** (367 real screens of the calmest finance UI): https://nicelydone.club/apps/mercury
4. **Refero — Stripe design system styles**: https://styles.refero.design/style/48e5de76-05d5-4c4e-a269-c7c245b291ec
5. **Muzli — 50 best dashboards 2026** (concept-heavy; the two worth opening are QuartRevenue and Analytics Dashboard Dark Mode by Airzon, both restrained green-on-charcoal): https://muz.li/blog/best-dashboard-design-examples-inspirations-for-2026/
6. **Dribbble — sportsbook tag** (for what *not* to do: neon, gradients, five accent colours): https://dribbble.com/tags/sportsbook
7. **Godly — dark-mode websites** (marketing, but the best dark type/contrast work on the web): https://godly.website/

Direct product pages that are themselves the reference: Unabated's odds screen
(https://unabated.com/tools/core/odds), Baseball Savant percentile leaderboard
(https://baseballsavant.mlb.com/leaderboard/percentile-rankings), Betfair market view
(https://www.betfair.com.au/hub/education/betfair-basics/read-an-exchange-market/), ESPN FPI
(https://www.espn.com/college-football/fpi).

---

## Part 4 — Verification notes

- Fetched and read: Unabated odds-screen article, Stripe and Mercury breakdowns (925studios),
  Linear redesign post, Ström "UI Density", Smashing inclusive dark mode, Nowah black-vs-grey,
  Grafana best practices, Observable seven tips, Metabase best practices, Setproduct table
  guide, Willison mobile-tables demo, NN/g confidence intervals, dev.to tabular-nums, Robinhood
  on Google Design, Lickability Apple Sports, Copilot Money guide, Masterly fintech guide,
  Geist colors page, Radix scale docs (via search), MU Collective CHI paper page, Betfair hub,
  Covers Pinnacle review, Hoops HQ on KenPom, Muzli list, SaaSUI comparison.
- 403 / unreadable: OddsJam education page, ACM full text, KenPom, Torvik (bot check),
  Bloomberg UX page, Apple HIG typography and `monospacedDigit()` (JS-rendered), Carbon Medium
  post, Savant Medium synopsis, Gelman 2021 post, mybetstrategy. Each is backed by a second
  source in the text.
- Font facts (Archivo and Geist `tnum`, digit advance widths) were read directly from the
  OpenType GSUB/hmtx tables of the google/fonts and Omnibus-Type variable TTFs with fontTools,
  in memory, this session.
- Repo facts (tokens, current `tabular-nums` usage, Archivo as `--font-display`) read from
  `web/app/globals.css` and `web/app/layout.tsx`.
