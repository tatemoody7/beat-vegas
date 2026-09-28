# Beat Vegas as a public site — review and proposed structure (2026-09-28)

A first-time visitor's walk through https://beat-vegas.vercel.app on 2026-09-28 (week 5,
anonymous, no password), followed by the structure the site should have if anyone can open
it and follow the picks. Every quote below was read off the live site or the code that day.
Decisions were Tate's, taken in four rounds of questions; they are listed at the end.
Nothing in this document ships on its own. Mockups: the Artifact linked from
`docs/HISTORY.md` under this date.

## The recommendation

Three tabs: **Board · Results · How it works.** The Board stays the home page and keeps
everything it has, with a two-line strip above it that says what the site is. Results and
Track record become one Results page that opens on the bet ledger. Everything a visitor does
not need, or would not understand, moves one level down to a new How it works page or shows
only when Tate is signed in. Dollars leave the public site; units and ROI stay. Unlock leaves
the header. The site says once, plainly, that bets are priced at Hard Rock Bet in Florida.

The Board was never the problem. The problem is that nothing tells a stranger what they are
looking at, two pages say the same thing, and the owner's instruments (ops warnings, the
Monday review tables, the research flags, the real dollar figures) sit in front of visitors.

## What a stranger sees today

### `/` — the Board
- The page opens on "Board · Week 5", then "No bets yet this week · 0 of 5 slots used",
  three "closest to a bet" lines, "Next build Tue 3:45–5:15pm ET", two filter chips ("My
  teams", "Hard Rock line posted"), an amber box, a blue box, "0 bet · 18 watch · 28 pass",
  then 46 ranked rows grouped Thu / Fri / Sat. **No sentence says what Beat Vegas is,**
  what a first-half under is, or what green means. There is no About, How it works, FAQ or
  trust page anywhere in `web/app/`.
- The amber box reads: "Only 17 of 53 Hard-Rock-priced games on Sat 2026-09-26 had a close
  captured inside 2 h of kickoff (floor 80%). Line value on the rest is graded against an
  earlier sweep, not a close; the Saturday close poll is not reaching its games
  (docs/HEALTH.md#lines_watch)." That is a runbook line for Tate, shown to everyone.
- "My teams" filters to Kansas State, Kansas, Missouri and Florida. A visitor has no idea
  whose teams those are.
- The header reads Board · Results · Track record · **UNLOCK.** A visitor cannot tell what
  is locked or why they would want to unlock it. The login page then explains: "The password
  is only for logging picks. Everything else is open." That sentence belongs before the
  click, not after.
- When lines are posted, a sentence appears above the filters: "This week's bar: 2.10 pts —
  the gap of the top 20% of 41 priced games; 6 clear it. A game must also pass the price,
  market and news gates to be a bet." A visitor does not know what a bar, a gap or a centred
  quote is. It is the one Board sentence that fails the five-second test.
- The rows themselves are clear. "#1 Ohio @ Kent State · Sat 3:30p · no line yet · Not yet —
  Hard Rock has no first-half line. It becomes a bet at under 19.0 or higher." A reader
  understands the row without the glossary. **Keep the Board.**

### `/game/[id]` — one game
- "The decision" with three tiles (Hard Rock / Market / Our number), the sentence, then
  "Unlock to log a pick". The unlock button is the owner's control, offered to every visitor.
- "at Hard Rock" appears with no hint that Hard Rock Bet is a Florida book. A reader in
  Texas does not learn that the number is one they must translate to their own book.
- The rest (Lines, What is behind it, Injuries and news) is dense but readable. The
  "unproven" badges and "Our reference line 25.5" under "no sportsbook has posted" need the
  glossary; noted, not changed — the game page is out of scope for this review.

### `/results` — Results
- Opens on three big numbers: "The rule, on paper 51.5%", "**My money $128.40**", "Line value
  +0.32", then a bankroll curve in dollars, "Your picks", a five-row season table (Market —
  first half / Model — first half / The rule — paper / You — real money / Market — full game),
  a three-tab breakdown (by week / by reason / by blocker), "Your decisions" with six
  key/value rows, a "Factor you leaned on" table, and "The rule's decisions, on paper".
- The record is real money and reads as a personal diary ("My money", "Your picks", "You —
  real money", "modelled from the ledger ($100 + units × $10), not reconciled with the Hard
  Rock account"). Real dollars and the stake size are public.
- "Your decisions", the factor table, the by-reason and by-blocker tabs and "The rule's
  decisions" are the Monday weekly-review instruments. They have no meaning for someone who
  did not place the bets. "Model — first half" and "Market — full game" rows need a paragraph
  each to explain what they are baselines for.

### `/proof` — Track record
- Opens on the same record as Results ("My money 60.0% · 9-6 · 15 bets · +2.84u · ROI
  +17.8% · plausibly 36%–80%", "Line value +0.27"), then the ledger of every bet (this is the
  best thing on the site: each bet with when it was posted, the price, the first-half score,
  the running units and the closing line, plus a CSV).
- Below it, one very long page: the 2023–25 finding ("First-half unders won, 2023–25, 5 a
  week — 60.8%"), the gap-ladder chart, a four-row "At real closing lines" table, a "2026 so
  far" strip ("HR ≤ -0.5 16-41 · 22-35"), "What to change" research flags ("352 comparisons
  were run, so about 18 would look meaningful by luck alone"), a "Method and sanity checks"
  fold, and 16 glossary terms.
- Two of the 16 terms, Rank and Score, describe a 0–100 number that no longer appears on any
  page. "Line basis", "Reference line", "Early season" and "Graded and pending" explain
  things a visitor will not meet.
- The 60.8% is the strongest number on the site and the one most likely to be quoted as a
  live win rate; the caveat that it is "what the method would have returned, not money won"
  sits under it in small type.

### `/proof/records` — every game we have rated
- Fine as a reference table. Its legend explains itself. It is linked from one button on
  Track record and nowhere else.

### Error and empty states
- `app/error.tsx` tells a visitor about "Neon sleeps between requests" and "the Vercel
  runtime logs". `app/not-found.tsx` is fine.

## The proposed structure

### Navigation
`BEAT VEGAS  First-half unders`   **Board** · **Results** · **How it works**

Footer, every page: *This site rates bets. It never places one. 21+. Not financial advice.*
then a small **Unlock** link (or "Signed in · Lock"). Unlock leaves the header; a visitor
never sees a lock they cannot open.

### Routes
| Route | Today | Proposed |
|---|---|---|
| `/` | Board | Board + intro strip |
| `/game/[id]` | one game | unchanged, two owner-only fixes |
| `/results` | scoreboard + Monday tables | **merged Results**, ledger first |
| `/proof` | Track record | **redirect → `/results`** |
| `/how-it-works` | — | **new**: pitch, how to read the Board, Hard Rock, backtest, what we don't know, terms, disclaimer |
| `/proof#glossary`, `/glossary` | glossary | redirect → `/how-it-works#glossary` |
| `/proof/records`, `/research/records` | every game rated | **`/records`** (redirect the old paths) |
| `/login` | password | unchanged; reached from the footer |

The 11 existing redirects in `web/next.config.ts` re-point (`/line-study`, `/research` →
`/how-it-works`; `/ledger`, `/picks`, `/weekly-review` stay on `/results`).

### Board `/` — refine only
| Element | Verdict | Detail |
|---|---|---|
| Intro strip | **add** | Two lines, always shown, no dismiss: *Beat Vegas rates every college football first-half under, priced at Hard Rock Bet. Green means bet one unit; every bet we place is on Results.* → "How it works" |
| Title, Week / Season selectors | keep | |
| Answer box | keep | "Next build …" stays. The best-look windows (Friday after 5:30pm ET, Saturday morning) are said on How it works |
| "This week's bar" sentence | **Tate picks** | (a) keep verbatim, or (b) *Bar this week: 2.1 pts (top 20% of 41 priced games).* with the gate clause dropped — the row sentences already say why a game is not a bet |
| "My teams" chip | **signed-in only** | visitors see "Hard Rock line posted" only |
| Ops warnings (`OpsBanner`) | **signed-in only** | quota, cron, close-poll, health-contract lines |
| Card status banner | keep, reword | "This card was built 9h ago. Today's scheduled update has not landed." is visitor-relevant staleness; drop nothing else |
| Pause banner | keep, reword | "Real money is paused" → *Our bets are paused.* + one sentence; drop "app_settings" reasons for visitors |
| Missed build / results behind | keep | visitor-relevant |
| No model / no Hard Rock lines | keep | |
| Tier counts, day groups, rows, Played | keep | the core |

### Game page `/game/[id]` — two fixes, otherwise observations
- "Unlock to log a pick" renders only when signed in (the same rule as the header).
- One line under the decision: *Priced at Hard Rock Bet (Florida). Your book's first-half
  total may differ; the line and price to beat are the ones shown.*
- Observed, not changed: "unproven" badges, the reference line under an empty Lines section,
  the density of the factor sentences.

### Results `/results` — merged, ledger first
| Section | Verdict | Detail |
|---|---|---|
| Season / Week selectors | keep | "All weeks" default |
| Record band | **rename, trim** | *Our bets* 60.0% · 9-6 · +2.84u · ROI +17.8% · plausibly 36–80% / *Line value* +0.27, "33% of 15 lines moved our way" / *Every qualifying game, on paper* 51.5% · 34-32 · −3.35u. No dollars, no "not reconciled" line |
| Bankroll curve | **units** | y-axis in units, dashed line at 0 |
| Every bet, as logged (`BetLedger`) | **move up, rename chips** | *Our bets / Paper / All*; Running in units; CSV stays |
| Season comparison | **trim to three public rows** | *Every first-half under at the close* (the baseline), *Every qualifying game, on paper*, *Our bets*. "Model — first half" and "Market — full game" show when signed in (option: drop them) |
| Breakdown (by week / reason / blocker) | **signed-in only** | |
| Your decisions, factor table | **signed-in only** | |
| The rule's decisions, on paper | **signed-in only** | |
| "Your picks" table (`PicksList`) | **fold into the ledger** | the ledger already shows every row with details; the edit/delete controls stay signed-in only |

### How it works `/how-it-works` — new page, from today's Track record
1. **What this is.** *Beat Vegas rates one bet: the college football first-half under. Our
   model estimates first-half points without ever seeing the sportsbook line, so the gap
   between our number and the line is a real disagreement. When the gap is wide enough and
   the price is fair, it is a bet — one unit, at most five a week. We bet these ourselves and
   publish every one.*
2. **How to read the Board.** Green = bet one unit. Amber = close, one thing missing. Red =
   pass. The sentence on every row says what would make it a bet. "Not yet" means a line or
   price is missing; "Pass" means the numbers do not disagree enough. The kill line is where
   a bet stops being the bet we rated. Best time to look: Friday after 5:30pm ET, Saturday
   morning.
3. **Where bets are priced.** Hard Rock Bet, the only book in Florida. Your book's
   first-half total may differ; the number and price to beat are the ones shown.
4. **Backtest, 2023–25 (not money bet).** The 60.8% block with its record, units, ROI and
   interval; the gap-ladder chart ("The wider the gap, the more often the under wins"); the
   real-closes table trimmed to two rows (2023–25 every gap 1.75+ · 2026 bets at Hard Rock's
   line). The heading carries the label so the number cannot be read as live.
5. **What we don't know.** The 2026-09-08 trust copy, reused: one first half is close to a
   coin flip; our number misses a typical game by about 8 points; the model reads about 2
   points under the market; we cannot prove the gap makes money; the live ledger on Results
   is the real test.
6. **Terms** (9, from 16): Gap, Our number, Hard Rock line, Market line, Line value, Unit,
   Paper pick, Weekly cap, Kill line and kill price. Cut with reasons: Rank and Score (a
   number no page shows), Line basis and Reference line (game-page internals), Early season
   and Graded and pending (states the row already spells out).
7. **Every game we have rated** → `/records`.
8. **Disclaimer.** 21+. Not financial advice. This site never places a bet.
9. **Signed in only**, at the bottom: "2026 so far" strip, "What to change" flags, the
   Method fold (estimated-line grade, band table, calibration, line study).

## Copy that reaches visitors and should not
| Where | String | File |
|---|---|---|
| Board ops box | "…(docs/HEALTH.md#lines_watch)", "Runbook: docs/HEALTH.md#…" | `web/lib/boardHealth.ts:446,510` |
| Board pause box | "the app_settings table does not exist", "could not read app_settings" | `web/lib/rulePause.ts:74-75` |
| Board bar sentence | "centred quote", "fallback bar", "gates" | `web/app/page.tsx:124` |
| Error page | "Neon sleeps between requests", "Vercel runtime logs" | `web/app/error.tsx:31,53` |
| Results | "My money", "Your picks", "You — real money", "modelled from the ledger ($100 + units × $10), not reconciled with the Hard Rock account" | `web/app/components/ScoreboardBand.tsx`, `RecordTable` rows in `web/app/results/page.tsx` |
| Track record | "My money", "My bets" | `web/app/components/BetLedger.tsx` |
| Track record | "352 comparisons were run…", "counts until a group reaches 30", "HR ≤ -0.5" | `web/app/components/PmFlags.tsx`, `PmLiveNotes.tsx` |
| Glossary | Rank, Score | `web/lib/glossary.ts` |
| Pick form refusals (signed in only, fine) | "RULE PAUSED … scripts/rule_pause.py off resumes", "RULE STATE UNREADABLE" | `web/lib/pickRules.ts:358` |

## The visitor journey the structure has to support
1. Land on `/`. The strip says what this is and where the record lives. The answer box says
   today's bets, or "no bets yet, next build Tuesday".
2. Tap a green row. The game page shows the line, the price, our number, the sentence and the
   Hard Rock note.
3. Doubt it. Results shows every bet with when it was posted, the price, the score, the
   closing line and the plausible range on the win rate. Download the CSV.
4. Still curious. How it works: the method, the backtest labelled as a backtest, what we
   don't know, the nine terms.
5. Come back Friday evening or Saturday morning, when Hard Rock's lines are up.

## Decisions taken 2026-09-28 (Tate)
| Topic | Decision |
|---|---|
| Audience | Anyone; mostly US sports bettors, also friends and the curious |
| Sign-up | Read-only "follow our picks"; no sign-up yet; the site stays fully open; the password stays for Tate's logging |
| Prior locks (2026-09-16) | Reopened, except the Board's core |
| Front door | Board stays `/`; two-line intro strip, always shown, no dismiss |
| Non-Florida | Keep Hard Rock; say it plainly on How it works and the game page |
| Research depth | All reachable one level deeper, trimmed of what a visitor won't need or understand |
| Results vs Track record | One Results page, ledger first; Monday instruments signed-in only |
| Owner-only | Ops warnings signed-in only; "My teams" signed-in only; "My money" → "Our bets" (we/our site-wide); Unlock out of the header |
| Third tab | "How it works" |
| Mockups | 390 and 1440 side by side |
| Dollars | Units and ROI only; dollars nowhere public; units curve |
| Backtest | Keep 60.8%; heading "Backtest, 2023–25 (not money bet)"; chart stays |
| Also | Responsible-gambling line; season and week selectors stay on every page |
| Out of scope | Game page structure (observations only); nothing ships mid-season without a separate go |

## If per-user ledgers come later
The structure above does not change. What changes: Results gains a "Your bets" view beside
"Our bets" (per-user `manual_picks` keyed by account, the same grading), the game page's log
button returns for signed-in users against their own cap, and "Sign in" replaces the footer
Unlock. How it works and the Board are untouched.

## What a build would touch (for the plan, not for now)
- `web/app/components/MainNav.tsx`, `HeaderChrome.tsx`, `layout.tsx` (nav, footer, Unlock).
- `web/app/page.tsx` (strip, `OpsBanner` and "My teams" behind `viewerIsAuthed()`).
- `web/app/results/page.tsx` + `BetLedger`, `ScoreboardBand`, `BankrollCurve`, `RecordTable`
  (merge, rename, units), with the Monday sections behind `viewerIsAuthed()`.
- New `web/app/how-it-works/page.tsx` reusing `GapLadderChart`, `RecordTable`, `Glossary`,
  `Fold`, `PmFlags`, `PmLiveNotes`; `web/lib/glossary.ts` trimmed (its test pins thresholds).
- `web/next.config.ts` redirects; `web/e2e/FEATURE_PARITY.md` and the Playwright specs that
  name `/proof`; `lib/featureParity.test.ts`.
- `tests/test_gate_parity.py` reads constants out of `verdict.ts`, `grade.ts`, `edge.ts`,
  `lineCheck.ts`, `books.ts`, `card.ts` by regex — none of those files change here.
- `docs/RANKING_AND_TRUST.md` and `README.md` name the three tabs; both get one line.
