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
- [board] The H-PCT bar sentence (`Bar this week: <bar> pts (top <share>% of <n> priced games).`, one decimal, no gate clause since 2026-09-28) is exact — board.spec.ts › "states this week’s bar exactly"
- [board] The two-line strip (what this is, green means bet, the record is on Results) opens the page and links to How it works — board.spec.ts › "opens with the two-line strip that says what this is"
- [board] The answer bar names the live bet, the placed one (muted, `bet logged`), the three closest with their `needs …` clause, and a `Next update <window> ET` line — board.spec.ts › "the answer bar names the live bet, the placed one, the closest three and the next update"
- [board] A game with a real ticket carries the `bet logged` chip and no other row does — board.spec.ts › "marks the game with a logged ticket"
- [board] The Hard Rock chip sets `?hr=1`, reads `aria-pressed`, hides games without a Hard Rock line and states the pre-filter count — board.spec.ts › "the Hard Rock filter sets ?hr=1, presses the chip and hides the games without a line"
- [board] My teams (signed in) sets `?mine=1`, clears `hr`, shows only MY_TEAMS rows; clicking the active chip clears it — board.spec.ts › "My teams shows only the followed program, one filter at a time"
- [board] Signed out, the Hard Rock chip shows and the My teams chip does not — board.spec.ts › "a visitor gets the Hard Rock filter but not the My teams chip"
- [board] `?days=sat` (parsed, no UI) keeps only Saturday's games and heading — board.spec.ts › "?days=sat keeps only Saturday’s games"
- [board] On the clean fixture no banner renders: no `role=status`, no missed build, no stale results, no pause, no no-model, no no-HR-line — board.spec.ts › "every banner is silent in the clean state"
- [board] `odds_credits_remaining` under the floor lights the OpsBanner (signed in only; a visitor sees none) with the credits text and `/api/health` carries the same warning; restored afterwards — board.spec.ts › "a low Odds API budget lights the ops banner and /api/health warns"
- [board] `rule_paused=true` shows the `Our bets are paused.` banner and `/api/health.rulePaused`; restored afterwards — board.spec.ts › "the real-money pause shows its banner and /api/health reports it"

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

- [results] Every bet: the strip opens on our bets with the record, ROI, "could plausibly be" interval, line value, the units curve with its zero line, and the CSV link; one week heading per week newest first with its record; running units accumulate oldest to newest; the winner shows both first-half scores and the total — results.spec.ts › "every bet: the summary strip, the week groups and the running units"
- [results] Every bet: exactly one `tr.bv-row--won` (--good-bg) and one `tr.bv-row--lost` (--bad-bg) in the real ledger, the pending row bare; the paper ledger's push row is `tr.bv-row--push` with +0.00 and a `-1P` record — results.spec.ts › "every bet: won rows are tinted green and lost rows red, pending rows are not"
- [results] Every bet: `details` opens `tr#bet-detail-<id>` with our number then, the frozen decision sentence, the posted ET stamp (the bet time, with the log time when the ticket was logged later) with hours before kickoff, the book and price provenance, the closing line, price and capture time, and the note; `hide` closes it — results.spec.ts › "every bet: the proof row shows the posted time, our number and the closing line"
- [results] `GET /api/bets?season=` streams every pick as CSV with the documented 31 columns (bet_at_utc beside placed_at_utc), the stored clv beside its displayed negation; a bad season is a 400 — results.spec.ts › "every bet: the CSV holds every pick with the stored clv beside its display"
- [results] The season comparison: every first-half under at the close, every game that cleared the bar on paper, our bets (with negated line value); signed in, the model and the full-game market rows follow (five rows) — results.spec.ts › "the season comparison: every under, the paper rule, our bets, and signed in the model and the full game"
- [results] Signed in (the Monday review): the breakdown toggle by week, by reason and by blocker each sum to the pick count; the blocker view is paper-only with GATE_TEXT labels — results.spec.ts › "the breakdown's three views each account for every pick"
- [results] Signed in: the decisions strip reads the graded real tickets with stored clv negated (+0.25 from −1.0 and +0.5) — results.spec.ts › "the decisions strip reads the graded real tickets with the favourable sign"
- [results] Signed in: the picks table: every pick, prices, results, units, negated line value, badges, and the frozen decision labels under details — results.spec.ts › "the picks ledger: every pick, the labels, and line value negated"
- [results] Signed in, pending picks offer edit and delete; graded picks offer neither — results.spec.ts › "signed in, pending picks can be edited or deleted; graded ones cannot"
- [results] Signed out: the bet ledger reads with details and no edit or delete, the comparison has three rows, and the Monday review is absent — results.spec.ts › "a visitor gets the ledger and three comparison rows, not the Monday review"
- [results] `/results` opens on the latest week with a pick and the signed-in picks table drops the Week column when filtered to one — results.spec.ts › "the default view is the latest week with a pick"

## How it works

- [how] The page opens on what this is, the three-colour key for the Board (with the best time to look) and where bets are priced — how-it-works.spec.ts › "says what this is, how to read the Board and where bets are priced"
- [how] The (hist_2023_25, fbs_only, real, cap5, all) bucket is headed `Backtest, 2023–25 (not money bet)`: win rate, W-L-P, units, ROI, a "could plausibly be" interval, no "Without the cap" sentence — how-it-works.spec.ts › "the backtest is headed as a backtest and carries the cap-5 record"
- [how] The gap ladder draws one bar per band (≥ 4, every bar non-zero height) and the 52.4% break-even rule — how-it-works.spec.ts › "the gap ladder draws one bar per band and the break-even line"
- [how] The real-close records table is the one uncapped 2023–25 row with its interval — how-it-works.spec.ts › "the real-close records table is the one uncapped row"
- [how] The glossary sits at `#glossary` (where `/glossary` redirects) with exactly the ten visitor terms in order — how-it-works.spec.ts › "the glossary is where /glossary lands, with the visitor's ten terms"
- [how] The page links to `/records` and names 1-800-GAMBLER — how-it-works.spec.ts › "links to every game we have rated and names the helpline"
- [how] Signed in: the `<season> so far` panel, the flags with the multiple-comparisons note, and the Method fold (opens on a click, estimated-line table, nothing coloured) — how-it-works.spec.ts › "signed in, the live season panel, the flags and the method fold follow"
- [how] Signed out: the backtest shows, the research section does not — how-it-works.spec.ts › "a visitor reads the page without the research section"

## Every game we have rated

- [records] Opens on the latest graded week, marks its pill, shows `N of M games` and only that week's rows — records.spec.ts › "opens on the latest graded week and shows only its rows"
- [records] Each row: full game, line, our number, gap to one decimal with its sign, actual first half and result or Pending — records.spec.ts › "shows each game's line, our number and the gap to one decimal, signed"
- [records] The previous week's pill filters to its two graded games — records.spec.ts › "the previous week is one click away and holds its two graded games"
- [records] `Download all of <season>` links to the CSV export, which holds every game — records.spec.ts › "offers the whole season as a CSV download"
- [records] The legend explains the columns; no header carries a `title=` tooltip — records.spec.ts › "the legend explains the columns without a tooltip"

## Health and records API

- [health] `/api/health` answers 200 with exactly the documented top-level and gauge keys — health.spec.ts › "answers 200 with exactly the documented keys"
- [health] On the clean fixture: ok, not paused, not stale, no missed build, no warnings, the seeded gauge values (incl. close-window coverage 67 of 72), UTC timestamps — health.spec.ts › "reports the clean fixture as healthy"
- [health] One `lastDispatch` gauge per CRON_JOBS id, each a past instant — health.spec.ts › "carries one dispatch gauge per cron job, each inside its last window"
- [health] One `health` verdict per scheduled job (card, grade, sunday, lines_watch), each `{verdict, at, note}` and ok — health.spec.ts › "carries one health verdict per scheduled job, each ok with its run note"
- [health] The five security headers from `next.config.ts` are on every response — health.spec.ts › "sends the security headers next.config.ts declares"
- [health] `/api/records?season=` streams the season as CSV with the documented columns, one row per game — health.spec.ts › "streams the season as CSV with the documented columns"
- [health] `/api/records` without a valid season is a 400 — health.spec.ts › "refuses a missing or malformed season"

## Redirects

- [redirects] Each of the thirteen moved routes (incl. `/proof` → `/results`, `/proof/records` → `/records`, `/glossary` → `/how-it-works#glossary`) is a 308 to its destination — redirects.spec.ts › "${from} → ${to} is a 308"
- [redirects] A moved route carries its query string across — redirects.spec.ts › "a moved route keeps its query string"
- [redirects] The three tabs (Board, Results, How it works), the records page and login are 200s, not redirects — redirects.spec.ts › "the three tabs and the game route are not redirects"

## Gate

- [login] Every page and every GET is public — login.spec.ts › "every page and every GET is public"
- [login] POST/PATCH/DELETE on the pick routes and POST /api/logout are 401 without the cookie — login.spec.ts › "writes are refused with a 401 before any body is read"
- [login] Signed out, the footer offers Unlock, the header does not, and there is no Lock — login.spec.ts › "the footer offers Unlock"
- [login] Signed out, the game page offers `Unlock to log a pick` with `?next=` and no log button — login.spec.ts › "the game page offers the way in, and remembers the game"
- [login] A wrong password is a 401 and the form says `Wrong password.` — login.spec.ts › "a wrong password is a 401 and the form says so"
- [login] The right password returns to `?next=`, shows Lock and the log button; Lock signs out and writes are refused again — login.spec.ts › "the right password returns to ?next=, Lock appears, and Lock signs out"
- [login] Signed in, the footer offers Lock and the game page the log button — login.spec.ts › "the footer offers Lock and the game page offers the log button"
- [login] Signed in, a write reaches validation (400) rather than the gate — login.spec.ts › "a write reaches validation instead of the gate"

## Layout and silence (every page, both widths)

- [layout] Every page renders with no console errors and no failed requests — a11y-layout.spec.ts › "renders with no console errors and no failed requests"
- [layout] Every page has no horizontal scroll and exactly one h1 — a11y-layout.spec.ts › "has no horizontal scroll and exactly one h1"
- [layout] No tap target under 24px beyond the named known ones — a11y-layout.spec.ts › "adds no tap target under 24px beyond the known ones"
- [layout] The sticky header is 69px on every page but login, signed in — a11y-layout.spec.ts › "keeps the header at ${HEADER_PX}px"
- [layout] Signed out the header is 69px at both widths, with Unlock in the footer and not the header — a11y-layout.spec.ts › "keeps the header at ${HEADER_PX}px with Unlock in the footer"

## Visual (opt-in, local baselines only)

- [visual] The board, results, how it works and a game page match their local full-page baselines — visual.spec.ts › "${name} matches its local baseline"
