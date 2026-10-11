# Pricing research: Hard Rock against the market (H-PRICE-HR, exploratory)

**Question (Tate, 2026-10-11; roadmap v2.1):** at the moments we captured it, is Hard Rock's price
ever better than the vig-free market reference for the same wager? By how much, how often, where
in the week, and did the market later move toward Hard Rock (Hard Rock knew something) or not
(Hard Rock was off)? This replaces nothing and changes nothing: it reads the same `odds_snapshots`
the arms read and writes a report. The six registered arms, the judge `cv1` and protocol `p1.1`
run unchanged to the January review.

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
Odds API serves no Florida-specific Hard Rock key (probe 2026-10-11, `scripts/probe_hr_keys.py`):
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

## How it runs

Dispatch only, no schedule (adding a Monday cron is an automation decision for Tate):

    gh workflow run study.yml --ref main -f script=pricing_check -f args="--season 2026"

The report lands in the `study-pricing_check` artifact as `pricing_check_<UTC>.{md,json,csv}`;
the CSV holds every compared state. Reads: 2026-12-07 (mid-point, no decision) and the January
review. The Monday one-page read quotes the per-market table.

## Reads

(The first run's numbers are appended here by the results PR.)
