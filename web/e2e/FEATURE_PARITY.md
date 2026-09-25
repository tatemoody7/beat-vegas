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
- [board] Games group by ET day Thu, Fri, Sat, with played games in a `Played · N` section last — board.spec.ts › "groups the week Thu, Fri, Sat, then Played last"
- [board] Rank badges run #1..#N in the expected order over the whole week; a played game shows its result instead — board.spec.ts › "numbers the week best to worst in the expected order"
- [board] Exactly the live BET rows carry `.bv-card--lit` — board.spec.ts › "lights exactly the two BET rows"
- [board] The `N bet · N watch · N pass` counts line matches the derived tiers — board.spec.ts › "states the tier counts"
- [board] The H-PCT bar sentence (U+2019 apostrophe, two-decimal bar, share, universe, clearing count) is exact — board.spec.ts › "states this week’s bar exactly"
- [board] The answer bar names the live bet, the placed one (muted, `bet logged`), the three closest with their `needs …` clause, and a `Next build <window> ET` line — board.spec.ts › "the answer bar names the live bet, the placed one, the closest three and the next build"
- [board] A game with a real ticket carries the `bet logged` chip and no other row does — board.spec.ts › "marks the game with a logged ticket"
- [board] The Hard Rock chip sets `?hr=1`, reads `aria-pressed`, hides games without a Hard Rock line and states the pre-filter count — board.spec.ts › "the Hard Rock filter sets ?hr=1, presses the chip and hides the games without a line"
- [board] My teams sets `?mine=1`, clears `hr`, shows only MY_TEAMS rows; clicking the active chip clears it — board.spec.ts › "My teams shows only the followed program, one filter at a time"
- [board] `?days=sat` (parsed, no UI) keeps only Saturday's games and heading — board.spec.ts › "?days=sat keeps only Saturday’s games"
- [board] On the clean fixture no banner renders: no `role=status`, no missed build, no stale results, no pause, no no-model, no no-HR-line — board.spec.ts › "every banner is silent in the clean state"
- [board] `odds_credits_remaining` under the floor lights the OpsBanner with the credits text and `/api/health` carries the same warning; restored afterwards — board.spec.ts › "a low Odds API budget lights the ops banner and /api/health warns"
- [board] `rule_paused=true` shows the paused banner copy and `/api/health.rulePaused`; restored afterwards — board.spec.ts › "the real-money pause shows its banner and /api/health reports it"

## Game page

- [game] For a logged BET, an open BET, a price-blocked Watch, a gap-short Watch and a played game: the Hard Rock / Market / Our number tiles, the rank badge and the sentence equal the board row's — game.spec.ts › "${id}: the three tiles, the rank and the sentence match the board row"
- [game] The sentence names the kill line on a gap-short game and the kill price on a dear one — game.spec.ts › "names the kill number for a game short of the bar and the kill price for a dear one"
- [game] When the feed's newest Hard Rock quote is an alternate line, the Hard Rock tile shows the last main line with `· as of <ET time>`, the sentence says so, and only a paper pick is offered — game.spec.ts › "a Hard Rock alternate line: the tile shows the last main line with its time, paper only"
- [game] The ticketed BET carries `bet logged` and its `cap slot N` chip — game.spec.ts › "carries the cap slot and the logged chip on the ticketed BET"
- [game] Signed in: `Log this bet` on an open BET, `Log as paper pick` on a Watch — game.spec.ts › "offers 'Log this bet' on an open BET and 'Log as paper pick' on a Watch"
- [game] Signed in: a ticketed game says already logged; a played game says kicked off; neither offers a log button — game.spec.ts › "says a ticketed game is already logged and a played one has kicked off"
- [game] The log form opens pre-filled with Hard Rock's line and price, offers `Log bet ($10)` and cancels — game.spec.ts › "opens the pre-filled form with Hard Rock's line and price"
- [game] Signed out: `Unlock to log a pick` links to `/login?next=/game/<id>` — game.spec.ts › "offers 'Unlock to log a pick' pointing back at the game"
- [game] Lines: the market open → now line and one row per book with open, now and move, Hard Rock's move included — game.spec.ts › "lists every book's open and current line, Hard Rock's move included"
- [game] With no first-half line anywhere the Lines section says so and shows our reference line — game.spec.ts › "says when no book has posted a first half yet"
- [game] `/game/abc`, an unknown id and a negative id are 404s with the styled not-found page — game.spec.ts › "a non-numeric id and an unknown id are 404s"
- [game] `← Back to the board` returns to the row's anchor — game.spec.ts › "the played game links back to its row on the board"

## Results

- [results] The scoreboard: the rule's paper record and interval, my money with the ledger-modelled bankroll and discipline count, line value — results.spec.ts › "the scoreboard: the rule on paper, my money, line value"
- [results] The season summary table: market 1H, model, the rule on paper, you (with negated line value), market full game — results.spec.ts › "the season summary compares market, model, the rule, you and the full game"
- [results] The breakdown toggle: by week, by reason and by blocker each sum to the pick count; the blocker view is paper-only with GATE_TEXT labels — results.spec.ts › "the breakdown's three views each account for every pick"
- [results] The decisions strip reads the graded real tickets with stored clv negated (+0.25 from −1.0 and +0.5) — results.spec.ts › "the decisions strip reads the graded real tickets with the favourable sign"
- [results] The picks ledger: every pick, prices, results, units, negated line value, badges, and the frozen decision labels under details — results.spec.ts › "the picks ledger: every pick, the labels, and line value negated"
- [results] Signed in, pending picks offer edit and delete; graded picks offer neither — results.spec.ts › "signed in, pending picks can be edited or deleted; graded ones cannot"
- [results] Signed out, the ledger reads but offers no edit or delete — results.spec.ts › "the ledger is readable but nothing can be edited or deleted"
- [results] `/results` opens on the latest week with a pick and drops the Week column when filtered to one — results.spec.ts › "the default view is the latest week with a pick"

## Track record

- [proof] The headline is the (hist_2023_25, fbs_only, real, cap5, all) bucket: win rate, W-L-P, units, ROI, interval, the uncapped rule and break-even placement — proof.spec.ts › "the headline is the cap-5 record at real closing lines"
- [proof] The gap ladder draws one bar per band (≥ 4, every bar non-zero height) and the 52.4% break-even rule — proof.spec.ts › "the gap ladder draws one bar per band and the break-even line"
- [proof] The real-close records table: the uncapped rule with its interval, the live season's bets / good prices / every Hard Rock number, `too few` under 30 — proof.spec.ts › "the real-close records table and its intervals"
- [proof] The live season panel is named `<season> so far` from `live_<season>` and carries the misses, price bands and HR-vs-market rows — proof.spec.ts › "the live season is one panel named after its scope"
- [proof] What to change: the multiple-comparisons note, the acted flags, the watched flags folded — proof.spec.ts › "what to change: the flags, with the watched ones folded"
- [proof] Method and sanity checks opens on a click, holds the estimated-line records and band table, and nothing below that heading is coloured `--good` / `--bad` — proof.spec.ts › "method and sanity checks open on a click and nothing inside is coloured"
- [proof] The glossary sits at `#glossary` (where `/glossary` redirects) with its terms — proof.spec.ts › "the glossary is where /glossary lands"
- [proof] The header button links to `/proof/records` — proof.spec.ts › "links to every game we have rated"

## Every game we have rated

- [records] Opens on the latest graded week, marks its pill, shows `N of M games` and only that week's rows — proof-records.spec.ts › "opens on the latest graded week and shows only its rows"
- [records] Each row: full game, line, our number, gap to one decimal with its sign, actual first half and result or Pending — proof-records.spec.ts › "shows each game's line, our number and the gap to one decimal, signed"
- [records] The previous week's pill filters to its two graded games — proof-records.spec.ts › "the previous week is one click away and holds its two graded games"
- [records] `Download all of <season>` links to the CSV export, which holds every game — proof-records.spec.ts › "offers the whole season as a CSV download"
- [records] The legend explains the columns; no header carries a `title=` tooltip — proof-records.spec.ts › "the legend explains the columns without a tooltip"

## Health and records API

- [health] `/api/health` answers 200 with exactly the documented top-level and gauge keys — health.spec.ts › "answers 200 with exactly the documented keys"
- [health] On the clean fixture: ok, not paused, not stale, no missed build, no warnings, the seeded gauge values, UTC timestamps — health.spec.ts › "reports the clean fixture as healthy"
- [health] One `lastDispatch` gauge per CRON_JOBS id, each a past instant — health.spec.ts › "carries one dispatch gauge per cron job, each inside its last window"
- [health] One `health` verdict per scheduled job (card, grade, sunday, lines_watch), each `{verdict, at, note}` and ok — health.spec.ts › "carries one health verdict per scheduled job, each ok with its run note"
- [health] The five security headers from `next.config.ts` are on every response — health.spec.ts › "sends the security headers next.config.ts declares"
- [health] `/api/records?season=` streams the season as CSV with the documented columns, one row per game — health.spec.ts › "streams the season as CSV with the documented columns"
- [health] `/api/records` without a valid season is a 400 — health.spec.ts › "refuses a missing or malformed season"

## Redirects

- [redirects] Each of the eleven moved routes is a 308 to its destination — redirects.spec.ts › "${from} → ${to} is a 308"
- [redirects] A moved route carries its query string across — redirects.spec.ts › "a moved route keeps its query string"
- [redirects] The three tabs, the records page and login are 200s, not redirects — redirects.spec.ts › "the three tabs and the game route are not redirects"

## Gate

- [login] Every page and every GET is public — login.spec.ts › "every page and every GET is public"
- [login] POST/PATCH/DELETE on the pick routes and POST /api/logout are 401 without the cookie — login.spec.ts › "writes are refused with a 401 before any body is read"
- [login] Signed out, the header offers Unlock and no Lock — login.spec.ts › "the header offers Unlock"
- [login] Signed out, the game page offers `Unlock to log a pick` with `?next=` and no log button — login.spec.ts › "the game page offers the way in, and remembers the game"
- [login] A wrong password is a 401 and the form says `Wrong password.` — login.spec.ts › "a wrong password is a 401 and the form says so"
- [login] The right password returns to `?next=`, shows Lock and the log button; Lock signs out and writes are refused again — login.spec.ts › "the right password returns to ?next=, Lock appears, and Lock signs out"
- [login] Signed in, the header offers Lock and the game page the log button — login.spec.ts › "the header offers Lock and the game page offers the log button"
- [login] Signed in, a write reaches validation (400) rather than the gate — login.spec.ts › "a write reaches validation instead of the gate"

## Layout and silence (every page, both widths)

- [layout] Every page renders with no console errors and no failed requests — a11y-layout.spec.ts › "renders with no console errors and no failed requests"
- [layout] Every page has no horizontal scroll and exactly one h1 — a11y-layout.spec.ts › "has no horizontal scroll and exactly one h1"
- [layout] No tap target under 24px beyond the named known ones — a11y-layout.spec.ts › "adds no tap target under 24px beyond the known ones"
- [layout] The sticky header is 69px on every page but login, signed in — a11y-layout.spec.ts › "keeps the header at ${HEADER_PX}px"
- [layout] Signed out the header is 69px with the Unlock link showing (KNOWN to fail at phone width: the link renders 14×68) — a11y-layout.spec.ts › "keeps the header at ${HEADER_PX}px with the Unlock link showing"

## Visual (opt-in, local baselines only)

- [visual] The board, results, proof and a game page match their local full-page baselines — visual.spec.ts › "${name} matches its local baseline"
