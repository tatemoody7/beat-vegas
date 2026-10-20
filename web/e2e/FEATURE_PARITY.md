# Feature parity checklist

What the site must keep doing, one line per assertion, each pointing at the
Playwright test that proves it against the synthetic fixture week
(`e2e/fixture/`). `lib/featureParity.test.ts` holds this file and the specs
together in both directions: every line here names a real test, and every
test in `e2e/*.spec.ts` has a line here. A redesign keeps every line, or says
which one it retired and why.

Format: `- [area] what — <spec file> › "<test title as written in the source>"`.

## Board

- [board] Every row is a link to `/game/<id>` and the id set is exactly the fixture week's — board.spec.ts › "every row links to its game page and the ids are the fixture's week"
- [board] One ranked list (no day groups, Tate 2026-10-15 Q2) in a `Ranked` section, with played games in a `Played · N` section last — board.spec.ts › "lists the week as one ranked list, then Played last"
- [board] A Pass reads in a few words under one heading, and its badge is red at every rank (audit 2026-10-17) — board.spec.ts › "says a Pass in a few words under one heading; a Pass is red at every rank"
- [board] Every row with a Hard Rock price shows its ET capture time beside it (`as of Tue 4:44 PM ET`), and a row with no quote shows none — board.spec.ts › "every row with a Hard Rock price shows its as-of time beside it, and no other row does"
- [board] Green marks only a paper signal (a lit row), whatever the rank, and the Board says a gap is not an edge (audit 2026-10-17) — board.spec.ts › "green marks only a paper signal, and the Board says a gap is not an edge"
- [board] Rank badges run #1..#N in the expected order over the whole week; a played game shows its result instead — board.spec.ts › "numbers the week best to worst in the expected order"
- [board] Exactly the live BET rows carry `.bv-card--lit` — board.spec.ts › "lights exactly the two BET rows"
- [board] The slim line (research season, six paper strategies judged against the closing price, readings, next read, the /research link) sits above the week heading, with no bar line, no key line and no separate research list above the games (Tate 2026-10-16) — board.spec.ts › "opens with the slim line and nothing else above the games"
- [board] The Hard Rock chip sets `?hr=1`, reads `aria-pressed`, hides games without a Hard Rock line and states the pre-filter count — board.spec.ts › "the Hard Rock filter sets ?hr=1, presses the chip and hides the games without a line"
- [board] The Hard Rock chip is the only filter chip (the My teams chip went with roadmap v2.0) — board.spec.ts › "the Hard Rock filter is the only chip"
- [board] Everyone reads the same board (D2/D15/D17): the footer carries the one sentence exactly, no answer bar and no tier counts render, every pre-kickoff row carries its rank badge with the BET rows lit, in paper wording — no `Bet one unit`, no `bet logged` chip, no cap slot, no "real money needs" — board.spec.ts › "the footer carries the one sentence and every rating reads in paper wording"
- [board] `?days=sat` (parsed, no UI) keeps only Saturday's games and heading — board.spec.ts › "?days=sat keeps only Saturday’s games"
- [board] On the clean fixture no banner renders: no `role=status`, no missed build, no stale results, no pause, no no-model, no no-HR-line — board.spec.ts › "every banner is silent in the clean state"
- [board] `odds_credits_remaining` under the floor lights the OpsBanner for everyone (D17) with the credits text and `/api/health` carries the same warning; restored afterwards — board.spec.ts › "a low Odds API budget lights the ops banner for everyone and /api/health warns"
- [board] `rule_paused=true` changes nothing on the site: the footer shows the one sentence, no pause box renders and `/api/health` carries no `rulePaused` key (real money ended 2026-10-18, D2); restored afterwards — board.spec.ts › "the real-money switch is nothing the site reads: the board and /api/health ignore it"
- [board] No tier-count line, no `bet logged` or cap chip, no price age and no QB warning on any row (the log path left 2026-10-18, D2) — board.spec.ts › "carries no tier-count line, no chip, no price age and no QB warning on any row"

## Game page

- [game] "What is behind it" opens with the H-1H-FACTORS note and words every factor by scoring ("points to less scoring"), never the bet, including rows stored with the old words (Q5) — game.spec.ts › "words every factor by scoring, never the bet, under the screen's note"
- [game] The wind is one row in the factors list: the steady wind from the newest card forecast, green at 10+ mph, plain below, no gusts; no weather box, no analysis box, the undated Sunday weather rows not shown (Tate 2026-10-16) — game.spec.ts › "shows the newest card forecast's steady wind as a coloured factor row"
- [game] For a logged BET, an open BET, a price-blocked Watch, a gap-short Watch and a played game: the Hard Rock / Market / Our number tiles, the rank badge and the sentence equal the board row's — game.spec.ts › "${id}: the three tiles, the rank and the sentence match the board row"
- [game] The sentence names the kill line on a gap-short game and the kill price on a dear one — game.spec.ts › "names the kill number for a game short of the bar and the kill price for a dear one"
- [game] When the feed's newest Hard Rock quote is an alternate line, the Hard Rock tile shows the last main line with `as of <ET time>` beside it, the sentence says so, and nothing is offered to log — game.spec.ts › "a Hard Rock alternate line: the tile shows the last main line with its time, paper only"
- [ledger] The write path is gone (D2/D16/D17): POST/PATCH/DELETE `/api/picks`, `/api/bets`, `/api/login`, `/api/logout`, `/api/price-refresh` and `/login` all answer 404 — ledger-integrity.spec.ts › "the pick, bet, login and price-refresh routes are gone (404)"
- [game] The paper-read block carries the Hard Rock (Florida) captured-prices note and, on the ticketed BET and the open one alike, no log control, no chip, no price age and no QB warning (D2) — game.spec.ts › "the paper-read block carries the Hard Rock note and offers no log control, chip or warning"
- [game] The top block is headed Paper read, and the Hard Rock tile and the Lines section each carry the quote's ET capture time (`as of Tue 4:44 PM ET`, `captured …`) — game.spec.ts › "a game page shows an as-of time beside the Hard Rock price, and the block is headed Paper read"
- [game] Before kickoff the rating reads in paper wording (`Paper signal:`, never `Bet one unit`), `Our number` and the factor read shown; a played game shows its result — game.spec.ts › "the rating reads in paper wording before kickoff, and the result after it"
- [game] Lines: the market open → now line and one row per book with open, now and move, Hard Rock's move included — game.spec.ts › "lists every book's open and current line, Hard Rock's move included"
- [game] With no first-half line anywhere the Lines section says so and shows our reference line — game.spec.ts › "says when no book has posted a first half yet"
- [game] `/game/abc`, an unknown id and a negative id are 404s with the styled not-found page — game.spec.ts › "a non-numeric id and an unknown id are 404s"
- [game] `← Back to the board` returns to the row's anchor — game.spec.ts › "the played game links back to its row on the board"

## Record (`/results`)

- [results] Headed Record, the Record tab lit; arms first, then the pricing opportunities, then the season comparison; no bet ledger, no units curve, no picks table, no tablist, no week picker, no `Personal stake`, no `/api/bets` link, no dollar (D16) — results.spec.ts › "is headed Record and runs arms, then pricing, then the season comparison, with no ledger"
- [results] The season comparison has three rows: every first-half under at the close (a record, no units), every game that cleared the bar on paper, and the full-game market for everyone; no Personal stake row, no Model row — results.spec.ts › "the season comparison: market research, the paper rule and the full game; no personal stake"
- [results] Every arm's forward picks with its value vs the close or the reason it has none; development rows never listed — results.spec.ts › "the forward picks of every arm, each with its value or the reason it has none; development never listed"
- [results] The pricing study's forward opportunities from the stored Monday row — results.spec.ts › "the pricing study's forward opportunities come from the stored Monday row"
- [results] The season comparison carries the Wilson interval on every win rate — results.spec.ts › "the season comparison carries the Wilson interval on every win rate"

## How it works

## Every game we have rated

- [records] Opens on the latest graded week, marks its pill, shows `N of M games` and only that week's rows — records.spec.ts › "opens on the latest graded week and shows only its rows"
- [records] Lists no season before 2023: training-history seasons in `games` never get a pill (`SITE_MIN_SEASON`) — records.spec.ts › "lists no season before 2023 (training history stays off the site)"
- [records] Hard Rock Records (default): each row graded on Hard Rock's line and price at the last scheduled card before kickoff, gap to one decimal, "No verified Hard Rock line" otherwise; the season totals line (audit 2026-10-17) — records.spec.ts › "grades each game on Hard Rock's line and price at the last scheduled card"
- [records] Market Research tab: graded on the consensus close, a record with no units, its own legend (audit 2026-10-17) — records.spec.ts › "Market Research grades on the consensus close, as a record with no units"
- [records] The previous week's pill filters to its two graded games — records.spec.ts › "the previous week is one click away and holds its two graded games"
- [records] `Download all of <season>` links to the CSV export, which holds every game — records.spec.ts › "offers the whole season as a CSV download"
- [records] The legend explains the columns; no header carries a `title=` tooltip — records.spec.ts › "the legend explains the columns without a tooltip"

## Health and records API

- [research] One card per registered hypothesis (six arms + the pricing study) in slot order; nothing ranked — research.spec.ts › "one card per registered hypothesis, in slot order, never ranked"
- [research] A card shows its own standard (readings of 30 / opportunities of 40), weeks, excluded, logged, the EV with its interval, the read date with its run id and the next read — research.spec.ts › "each card shows its own standard, the counts, the read date and the next read"
- [research] No EV below ten readings; a read older than eight days is `outdated`; a hypothesis with no row reads `not yet read` — research.spec.ts › "not enough data stays a status: no EV below ten readings, outdated past eight days, no row reads not yet read"
- [research] The exploratory collector (H-ARM-EVP) sits in its own section, never among the strategy cards: no progress bar, no LLR, the ten-reading rule on its EV and on the gap rule's EV over the same weeks, the games both rules chose — research.spec.ts › "the exploratory collector sits apart, with no decision bar and the gap rule beside it"
- [research] The judge in plain words with the protocol's numbers (30 readings over 3 weeks, +3%, 200, 40) and the one sentence in place of the personal-stake note; no "personal stake", no "real money" — research.spec.ts › "explains the judge in plain words with the protocol's numbers, and says nothing here is a bet"
- [research] The closed hypotheses from the registry export with their verdicts; no backtest card — research.spec.ts › "lists the closed hypotheses from the registry with their verdicts"
- [research] The glossary sits at `#glossary` (where `/glossary` redirects) with exactly the ten visitor terms in order — research.spec.ts › "the glossary is where /glossary lands, with the visitor's ten terms"
- [research] The Board key, the link to `/records` and 1-833-PLAYWISE — research.spec.ts › "keeps the Board key, links to every game we have rated and names the helpline"
- [research] Every page carries the footer's responsible-gambling line — research.spec.ts › "every page carries the footer's responsible-gambling line"
- [research] The seven cards carry their run ids for everyone (D17), the intro is one line, and no dollar figure shows — research.spec.ts › "the cards carry their run ids, the intro is one line, and no dollar figure shows"
- [health] `/api/health` answers 200 with exactly the documented top-level and gauge keys — health.spec.ts › "answers 200 with exactly the documented keys"
- [health] On the clean fixture: ok, not stale, no missed build, no warnings, the seeded gauge values (incl. close-window coverage 67 of 72), UTC timestamps — health.spec.ts › "reports the clean fixture as healthy"
- [health] One `lastDispatch` gauge per CRON_JOBS id, each a past instant — health.spec.ts › "carries one dispatch gauge per cron job, each inside its last window"
- [health] One `health` verdict per scheduled job (card, grade, sunday, lines_watch), each `{verdict, at, note}` and ok — health.spec.ts › "carries one health verdict per scheduled job, each ok with its run note"
- [health] One body for everyone (D17): the API budgets and each job's run note are public, and no `rulePaused` / `rulePauseReadable` key exists — health.spec.ts › "carries one body for everyone: the budgets and run notes, and no pause switch"
- [health] The five security headers from `next.config.ts` are on every response — health.spec.ts › "sends the security headers next.config.ts declares"
- [health] `/api/records?season=` streams the season as CSV with the documented columns, one row per game — health.spec.ts › "streams the season as CSV with the documented columns"
- [health] `/api/records` without a valid season is a 400 — health.spec.ts › "refuses a missing or malformed season"

## Redirects

- [redirects] Each of the thirteen moved routes (incl. `/proof` → `/results`, `/proof/records` → `/records`, `/glossary` → `/how-it-works#glossary`) is a 308 to its destination — redirects.spec.ts › "${from} → ${to} is a 308"
- [redirects] A moved route carries its query string across — redirects.spec.ts › "a moved route keeps its query string"
- [redirects] The three tabs (Board, Record, Research) and the records page are 200s, not redirects — redirects.spec.ts › "the three tabs and the game route are not redirects"

## Layout and silence (every page, both widths)

- [layout] Every page renders with no console errors and no failed requests — a11y-layout.spec.ts › "renders with no console errors and no failed requests"
- [layout] Every page has no horizontal scroll and exactly one h1 — a11y-layout.spec.ts › "has no horizontal scroll and exactly one h1"
- [layout] No tap target under 24px beyond the named known ones — a11y-layout.spec.ts › "adds no tap target under 24px beyond the known ones"
- [layout] The sticky header is 69px on every page — a11y-layout.spec.ts › "keeps the header at ${HEADER_PX}px"
- [layout] No page offers Lock, Unlock, a `/login` link or a signed-in note (D17) — a11y-layout.spec.ts › "offers no Lock, Unlock or login link"

## Visual (opt-in, local baselines only)

- [visual] The board, record, research and a game page match their local full-page baselines — visual.spec.ts › "${name} matches its local baseline"
