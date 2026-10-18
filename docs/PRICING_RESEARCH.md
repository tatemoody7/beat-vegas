# Pricing research: Hard Rock against the market (H-PRICE-HR, exploratory)

**Question (Tate, 2026-10-11; roadmap v2.1):** at the moments we captured it, is Hard Rock's price
ever better than the vig-free market reference for the same wager? By how much, how often, where
in the week, and did the market later move toward Hard Rock (Hard Rock knew something) or not
(Hard Rock was off)? This replaces nothing and changes nothing: it reads the same `odds_snapshots`
the arms read and writes a report. The six registered arms, the judge `cv1` and protocol `p1.1`
run unchanged to the final read (2026-11-30, roadmap v2.6; it was the January review).

## The frozen rule `pv1` (`beatvegas/pricing.py`; a change is `pv2`, read beside it)

- Hard Rock's MAIN quote only (`devig.is_hr_rung`: no price at −140 or worse, not 2+ points off the
  field's median with 3+ books).
- Reference: every other centred book, Fliff and the feed's consensus row excluded, whose quote is
  confirmed present at the capture minute (its latest row captured at or before that minute, and
  captured in that minute or re-seen at or after it). At least 3 books.
- Totals (first half, full game): each reference quote de-vigged (multiplicative) and converted to
  Hard Rock's exact line through the frozen `hp1` table within 1.5 points; the median converted
  under-probability is fair. **A flag is EV ≥ +2% at the lower bound of the table's integer masses**
  (1.96σ from each centre's game count): a one-point line difference is worth one integer's mass,
  and that mass carries sampling error (at a 28.5 centre, P(28) = 5.4%, P(29) = 0.4%, P(31) = 8.4%).
- Moneylines: each reference book's de-vigged home probability, the median is fair; no conversion.
  **Only games where both of Hard Rock's prices sit within ±200**: on lopsided lines the
  multiplicative de-vig overstates the longshot's fair chance (the favourite-longshot bias). The
  first local read flagged 18 longshots at +275 to +1100 and nothing else, so that range is a
  counted drop (`lopsided`), reported, never compared.
- **Spreads are not compared**: the frozen table has no spread market, so two spreads a point apart
  cannot be priced against each other honestly. They join when a spread table is frozen.
- One opportunity per game-side: the first qualifying price state in time.

## Evidence tiers (every flag carries one)

| tier | evidence | may be called |
|---|---|---|
| 0 | one feed observation | unverified: quoted by the feed |
| 1 | the provider's stamp within 5 min of our capture AND the price re-seen at a later poll | unverified: quoted and persisting (NOT "available between polls") |
| 2 | a Florida-app screenshot within 10 min showing the same line and prices | available in Florida |
| 3 | a ticket at that price | bet in Florida |

Tiers 2 and 3 come only from Tate's records (the paired screenshots and the personal ledger). The
Odds API serves no Florida-specific Hard Rock key (probe 2026-10-11, `scripts/archive/probe_hr_keys.py`):
`hardrockbet` is the only key, which the provider's table calls the Indiana book "currently same
odds as several other states". Until the paired checks exist, every flag is a feed observation.

## What the report shows, and how to read it

Per market: states compared, mean EV against the reference (Hard Rock's hold shows here as about
−4%), the counts above 0, +1% and +2% (point estimate) and the flags at the lower bound; then the
opportunities with EV against the reference (point and lower bound), EV against the close, line
value, the share where the market moved toward Hard Rock, the realized record and units; then the
flag share by hours to kickoff and by weekday; then the drops. **EV against the close is not
independent evidence when the close is the same number as the reference** (the market did not
move): the `market moved` column is the honest reading of that. Breakdowns are descriptive and can
never become a criterion without a new row.

## Development versus forward (Tate, 2026-10-12)

Every state captured before **2026-10-13 00:00 UTC** (`pricing.FORWARD_CUTOFF`, the first day with
provider stamps) is DEVELOPMENT evidence: the rule was chosen after looking at it. Every state from
that instant on is the forward test. The report prints the two blocks apart and the cumulative
verdict reads the forward opportunities only. `pv1` is frozen (`tests/test_pricing.py` pins every
constant); any change to a threshold, a market filter or a probability treatment is `pv2`, a new
row read beside this one, never a replacement.

## The weekly verdict (forward opportunities only)

| reading | rule |
|---|---|
| **insufficient** | fewer than 40 forward opportunities; the count is printed and no direction is read |
| **strengthening** | the 90% upper bound of the share of opportunities where the market moved toward Hard Rock is below 50%, AND the mean EV against the close is at least +1% with its interval above zero |
| **weakening** | the share's 90% lower bound is above 40% (Hard Rock as often right as wrong), OR the mean EV against the close is at or below zero |
| **inconclusive** | neither |

EV against the close is not independent evidence when the close equals the reference; the
"market moved" share is the honest reading of that, and it is the first thing the verdict uses.

## Florida verification (`data/fl_app_checks.csv`)

Tate's screenshots, one row each: `checked_at_utc` (ISO, naive UTC), `game_id` (`games.id`),
`market` (`1H_total`, `full_game_total`, `full_game_ml`), the app's `app_line`, `app_over`,
`app_under` (totals) or `app_home`, `app_away` (moneyline) exactly as shown, `note`. A compared
state rises to tier 2 only when every check for the same game and market within ten minutes of its
capture shows the same line and prices. A different quote is a **mismatch**; agreeing and
disagreeing checks together are **ambiguous**; no check is **none**. Only a match changes a tier;
a missing, mismatched or ambiguous comparison stays unverified. Rows with an unreadable time,
game id or market are counted as invalid and skipped, never guessed.

## How it runs

Every Monday, the Vercel `pricing-monday` entries dispatch `.github/workflows/pricing_monday.yml`:
a primary tick at 12Z and a retry at 15Z (8am and 11am EDT), both inside a 6am to noon ET window.
The cron route re-dispatches only when the first run failed and suppresses the retry when it
succeeded; two runs on one Monday cannot double-count, because the script writes no table and
both would print the same numbers from the same rows. There is no GitHub schedule (a scheduled Neon
job must carry a health contract, which would reach into the site's health list); the manual
fallback is

    gh workflow run pricing_monday.yml --ref main

**Where to read it:** the run's Summary page at
https://github.com/tatemoody7/beat-vegas/actions/workflows/pricing_monday.yml (the newest run,
"Summary" tab shows the whole report), and the `pricing-report` artifact
(`pricing_check_<UTC>.{md,json,csv}`; the CSV holds every compared state). `study.yml` can still
run `pricing_check` by hand. Decision read: the 2026-11-30 final read (roadmap v2.6, 2026-10-18; the 12-07 mid-point and the January review were dropped).

## Reads

### Read 1 — 2026-10-11 UTC, `study.yml` run 38179348954 at `b04ae60` (2026 weeks 1-6, development)

| market | HR states (games) | mean EV vs ref | EV>0 | ≥+1% | ≥+2% (point) | flags (lower bound) | opportunities | tiers |
|---|---|---|---|---|---|---|---|---|
| 1H_total | 931 (358) | −4.15% | 38 | 21 | 11 | 3 | 3 | all tier 0 |
| full_game_total | 1,485 (469) | −3.23% | 59 | 31 | 16 | 2 | 2 | all tier 0 |
| full_game_ml (within ±200) | 73 (35) | −3.19% | 1 | 0 | 0 | 0 | 0 | — |

Drops: first half 235 alternate rungs, 24 without a confirmed reference, 6 outside the table;
full game 12 rungs, 17 without a reference; moneylines 121 of 194 Hard Rock states lopsided
(beyond ±200) and not compared.

The five opportunities, every one a feed observation (tier 0):

| market | game | captured (UTC) | h to kick | Hard Rock | reference | side @ price | EV ref | EV lower bound | EV close | market moved | result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1H | Sam Houston @ Liberty | 10-08 22:31 | 0.5 | 28.5 (−110/−120) | 27.5 | under @ −120 | +4.2% | +2.4% | +4.2% | unchanged | win |
| 1H | Ole Miss @ Vanderbilt | 10-10 11:58 | 7.5 | 28.5 (−120/−110) | 27.5 | under @ −110 | +4.8% | +2.9% | +4.8% | unchanged | loss |
| 1H | Ball State @ Northwestern | 10-10 11:58 | 4.5 | 30.5 (−130/+100) | 30.5 | under @ +100 | +2.2% | +2.2% | +2.2% | unchanged | loss |
| FG | Washington @ USC | 09-27 18:58 | 148.5 | 54.5 (−105/−115) | 55.5 | over @ −105 | +6.0% | +3.7% | — | unknown | loss |
| FG | Buffalo @ Toledo | 10-09 20:11 | 23.3 | 54.5 (−110/−105) | 55.5 | over @ −110 | +4.5% | +2.2% | −2.5% | toward HR | loss |

**What it says.** Hard Rock's average price is its hold below fair in every market (−3% to −4%).
Discrepancies exist but are rare: about 4% of first-half states and 4% of full-game states read
positive at the point estimate, and once the half-point table's sampling error is applied, 3 of 11
first-half and 2 of 16 full-game candidates survive the +2% bar. Five opportunities in six weeks,
less than one a week, all unverified for Florida (tier 0), 1-4 realized. In the three first-half
cases the market never moved, so "EV vs close" there is the same disagreement counted twice; in
one full-game case the market moved toward Hard Rock. The moneyline stratum shows nothing once
lopsided prices are excluded; the 18 longshot "flags" the unrestricted first pass produced were
the de-vig's favourite-longshot bias, not Hard Rock, and the rule was fixed before it froze.

**What it does not say.** Nothing here is validated: the rule's +2% bar and the lower-bound
treatment were chosen after Step 0's look at these same weeks, so this read is development
evidence; the forward weeks are the test. No flag has a Florida screenshot or a feed stamp yet
(the stamps begin 2026-10-13). Persistence is a lower bound at poll resolution. Spreads are
untested for want of a spread table.

**What we learned.** The table's sampling error halves the candidate count, so calibrating it
(bootstrap, and the market's own point values from alternate ladders) is the highest-value
modelling task. The favourite-longshot bias of multiplicative de-vig is large enough to
manufacture flags; any future side-market comparison needs a price range or a different de-vig.
Flags cluster inside 24 hours before kickoff on Thursday to Saturday; nothing qualified more than
three days out, where Hard Rock's prices read a full point worse (about −5%).
