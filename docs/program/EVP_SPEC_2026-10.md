# H-ARM-EVP — exact rules, assumptions and method (exploratory collector since 2026-10-14)

Status: **option A approved by Tate, 2026-10-14: an exploratory collector, no ledger slot, no alpha.**
The collector is `beatvegas/evp_paper.py` (registry row `H-ARM-EVP`, `docs/HYPOTHESES.md`); it logs from
its first scheduled build after it merged, and the Monday workflow stores its read with the gap rule's
readings over the same weeks. The rule below is what it runs; it reproduces this file's replay exactly
(5 / 3 / 2 / 0 picks in weeks 4-7, the same games and values). The original framing follows.

Specification, 2026-10-14. Tate: "I'm interested in testing this, but I want to confirm the
exact rules, model assumptions, and statistical methodology before activating it." Nothing here logs a
pick or takes a ledger slot. It is separate from the six registered arms and from H-PRICE-HR (pv1).

## The question

Do paper first-half unders chosen by their estimated value at Hard Rock's price, rather than by the
model's gap, carry +3% EV against the consensus close?

## The rule, exactly

At every scheduled build (tue_pm, thu_pm, fri_pm, sat_am; never `manual`), for each game on the card:

1. **Eligible** when Hard Rock's newest 1H quote is its main line (`hr_centred`, `devig.is_hr_rung`
   false), its under is priced, the market has a vig-free fair under at Hard Rock's line (`fair_under`,
   the card's own consensus read), and the model has a number (`bv_line`).
2. **Fair centre.** The market's centre `M` (the card's `market_line`) moved toward our number `B` by the
   frozen blend weight: shift `s = (1 − w) × (M − B)` with **w = 0.80** (`data/blend.json`, H3A, fitted on
   2023-25 and read by nothing until now). A positive `s` (our number below the market) means more unders.
3. **Fair chance of the under at Hard Rock's line `L`.** Start from the market's unconditional under
   chance at `L` (`consensus.convert_under` with the frozen half-point table **hp1** at centre `M`), then
   move the distribution down by `s`: add (or remove) the probability of every whole total crossed, with a
   fractional shift taking that fraction of the next whole number's mass (each integer's mass treated as
   spread evenly over ±0.5).
4. **Value** at Hard Rock's under price: `ev = p_win × (decimal − 1) − p_loss` (`consensus.ev_per_unit`,
   pushes return the stake on a whole-number line).
5. **Log** a paper under at Hard Rock's line and price when **ev ≥ +2%** (Tate's threshold). Uncapped; one
   pick per game; the arm's own paper windows (`ci.PAPER_WINDOW_HOURS`); written to `challenger_picks`
   with arm `H-ARM-EVP`; frozen inputs (`M`, `B`, `w`, `s`, `p_win`, `ev`) in the row.

## Assumptions to state in the registry row

- w = 0.80 is used as frozen, never re-fit during the test.
- hp1 describes the shape of first-half totals around the market's centre (it is the judge's own table).
- The market's centre is the card's consensus line at build time; the model's number is the Sunday refit.
- The judge (`cv1`) reads every pick exactly as it reads the other arms; nothing about the judge changes.

## Statistical method

Protocol p1.2 unchanged: observation = a completed reading week's mean `ev_cons`; Wald SPRT on a normal
mean, H0 0 vs H1 +3%; alpha 0.5%, beta 0.20; no decision before 30 readings over 3+ weeks; PROMOTE at
LLR ≥ 5.075 → $10 live validation; STOP at LLR ≤ −1.604 → needs more evidence; TIMEOUT at 200 readings or
the season's end.

## Development replay (cards of weeks 4–7; rows chosen after the fact, so context, never evidence)

| Threshold | Picks per week (wk 4 / 5 / 6 / 7, Tuesday card only for wk 7) |
|---|---|
| ≥ +0% | 7 / 4 / 4 / 3 |
| ≥ +1% | 6 / 4 / 2 / 1 |
| **≥ +2%** | **5 / 3 / 2 / 0** |

At +2% in weeks 5–6 the five picks were Washington @ USC, Penn State @ Northwestern, Alabama @ Mississippi
State, Florida State @ Louisville and Ball State @ Northwestern; four were also gap picks of H-ARM-1HU,
and those four have judge readings of −2.5%, −15.0%, +0.1% and −0.3% (n 4: says nothing).

## The problem the replay shows: volume

At about 2–3 picks a week, with roughly two in three getting a judge reading, the arm collects about 2
readings a week. Thirty readings over 3+ weeks would take about **12–15 weeks**; the 2026 season has about
7 regular weeks and the bowls left. Under p1.2 the arm would almost certainly **TIME OUT** this season,
which ends the test and **spends its 0.5% ledger slot without answering the question.**

## Two ways to proceed (Tate's choice)

**A. Exploratory collector in 2026, confirmatory in 2027 (recommended).** Register `H-ARM-EVP` now as
`exploratory` (no ledger slot, no alpha, no SPRT): the collector logs picks and the judge reads them,
shown on Research as exploratory. At the January review, decide whether to register it as a confirmatory
arm for 2027 with fresh alpha, with its real volume known. Costs nothing from the 2026 ledger.

**B. Confirmatory arm now (ledger slot 9).** Register as above and run the SPRT from its first build.
Expect a timeout at season end unless the edge is large; the slot is spent either way.

A lower threshold (+0%: about 3–4 picks a week) would raise the volume but changes the rule Tate set;
it is listed for completeness, not recommended.

## On approval

One PR: the registry row (text below), the collector in `scripts/build_card.py` / a module beside
`fg_paper.py`, its tests (eligibility, the shift arithmetic against hand-worked values, the threshold,
one pick per game, manual builds log nothing), and — under option B only — the `protocol.ARMS` entry.

### Draft registry row (option A)

| id | question | status | family | data | n | comparisons | criterion | doc |
|---|---|---|---|---|---|---|---|---|
| H-ARM-EVP | Do paper first-half unders chosen by estimated value at Hard Rock's price (fair centre = market + 0.2 × (model − market), hp1, ev ≥ +2%) carry positive value against the consensus close? | exploratory | exploratory (no ledger slot; a 2027 confirmatory registration is decided in January) | 2026 paper picks in `challenger_picks` with arm H-ARM-EVP from its first scheduled build after registration | accruing | 0 | None: the mean `ev_cons` with its interval, exclusions by reason and book count, picks per week; nothing is adopted from it | `docs/program/EVP_SPEC_2026-10.md` |
