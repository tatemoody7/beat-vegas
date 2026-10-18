# Four research proposals — memos and draft registry rows (none registered, none running)

Status: **proposals, 2026-10-14. Tate's decisions the same day: 4.2 approved (shipped with p1.2, #391); 4.3 kept
documented and deferred; 4.4 approved as one run (`scripts/archive/probe_alt_totals_h1.py`); 4.1 needs its exact
rules, assumptions and method confirmed before activation (`docs/program/EVP_SPEC_2026-10.md`).** Programme step 16. Nothing below logs a pick, spends a credit or
takes a ledger slot until Tate approves the row text. Where the evidence argues against building
something, the memo says so.

## 4.1 H-ARM-EVP — select by value at Hard Rock's price, not by raw gap

- **Question.** Do paper first-half unders chosen by estimated value at Hard Rock's price, rather
  than by the model's gap, carry +3% EV against the consensus close?
- **Why it might.** The gap ignores price, and every band of the 1H paper ledger reads negative
  value against the close with no gradient (development rows, judged: <2 pts −1.0% (7), 2–3 −8.4%
  (7), 3–5 −5.3% (9), 5+ −4.5% (13); query P1). The frozen blend weight (H3A, `data/blend.json`,
  w = 0.80 on the market) implies a 3–5 point gap moves a fair line only 0.6–1.0 point, about the
  size of the vig; selecting on price would stop paying the vig on games the gap overrates.
- **Rule (draft, fixed before any build).** At each scheduled build: fair line = 0.8 × consensus
  1H line + 0.2 × our number; fair under-probability at Hard Rock's exact line through the frozen
  half-point table hp1; value = that probability × (decimal price) − 1 at Hard Rock's main-line
  under price; log a paper under when value ≥ **+2%** (Tate's threshold, 2026-10-14). Hard Rock main
  line only (`is_hr_rung` excluded), uncapped, one pick per game, the arm's own paper windows.
- **Method.** Protocol p1.x unchanged: weekly mean `ev_cons`, SPRT +3% vs 0, alpha 0.5%, beta 0.20,
  30 readings over 3+ weeks, timeout 200 or season end. **Ledger slot 9** (slots 1–3 and 6–8 are
  the running arms; 4–5 are reserved for the undesigned derivative-consistency and stale-line arms).
  Clock starts at its first build after registration; nothing earlier counts.
- **Assumptions to state in the row.** w = 0.80 is used as frozen, not re-fit; hp1 conversion
  within 1.5 pts; no game counts twice across arms for the reading (each arm is its own test).
- **Cost.** About a day of build (a collector in `build_card.py`, its tests), no credits.
- **Success / failure.** PROMOTE at LLR ≥ 5.075 → $10 live validation; STOP at LLR ≤ −1.604 →
  needs more evidence.
- **Recommendation.** Approve. It is the one proposal with a mechanism the current arms lack.

## 4.2 Book count beside every exclusion — already stored; a report line, not a field

- **What the data says.** `cons_books` (books in the judge's close) is already stored on every graded
  pick. Every excluded paper pick had 0 or 2 books at the close (51 picks, nearly all September before
  the close polls matured); every judged pick had 4–8 (36 picks) (query BOOKS). The close-time count
  explains every exclusion so far.
- **Recommendation.** Do **not** add a build-time field. Add one line per arm to the Monday read:
  exclusions by close book count. Report-only, no registry row (a measurement of the judge).

## 4.3 H-LATE-SAT — a Saturday-afternoon collector for late lines

- **What the data says.** In weeks 4–6, **zero** Saturday games had their first Hard Rock 1H line
  appear after the Saturday-morning build (55, 54 and 49 priced Saturday games; query LATE). The gap
  the audit worried about does not exist at the first-posting grain.
- **Recommendation.** Do **not** build. Close as not needed. The real late-line issue is Hard Rock's
  main line turning into an alternate rung near kickoff, which 4.4 measures.

## 4.4 The alternate-line probe — one Saturday, about 20 credits

- **Question.** When Hard Rock's feed row drifts to an alternate rung near kickoff (main-line share
  97% beyond 48 h, 31% inside 2 h; 142 main→rung flips vs 5 back, measured 2026-10-01), is the main
  line still offered in the app, and does `alternate_totals_h1` return it?
- **Method.** One by-hand run on Saturday 10-17 at about 3pm ET: request `alternate_totals_h1` for
  about 10 Hard-Rock-priced games kicking off within 2 h (2 credits an event), write nothing, and
  compare with Florida-app screenshots logged in `data/fl_app_checks.csv`.
- **Cost.** About 20 credits of 19,270 remaining this month.
- **Outcome decides.** If the main line comes back in that market: capture it (a design note, then a
  PR). If not: accept the drift (it costs late candidates only) or report it to The Odds API.
- **Recommendation.** Approve; exploratory, no registry slot.

## Decision for Tate

Approve, change or decline each of 4.1–4.4. Approved items become registry rows first
(`docs/HYPOTHESES.md`), then code, each in its own PR.
