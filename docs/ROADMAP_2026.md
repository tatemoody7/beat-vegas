# Beat Vegas — the 2026 R&D roadmap

**Version 1, adopted 2026-10-07 (Tate).** This document governs the rest of the 2026 season. Any
change is an explicit, versioned amendment logged at the bottom (v1.1, v1.2 …), never a quiet edit.
Where this document and an older decision disagree, this document wins; `docs/HYPOTHESES.md`,
`docs/BETTING_POLICY.md` and `CLAUDE.md` are updated to match it.

## Why it exists

Tate reset the project on 2026-10-07. Beat Vegas started as a first-half-unders system because that
was the market he liked; it is now treated as a potential business that follows the evidence to
whatever college-football market holds the strongest, most repeatable, most defensible edge. 2026
is the research year. The assessment behind the reset: the measurement discipline (registry, real
closes, line value, every result public) is the asset; the market-blind first-half model is level
with the close at best (2026: 8.34 vs Hard Rock's 8.22 average first-half miss over 213 games); an
87-input screen found nothing predicting the residual against the close; and 50 real bets a season
cannot tell skill from luck by wins and losses. Twelve rounds of questions and one outside critique
settled what follows. Every decision below is Tate's.

**2026 is the year Beat Vegas builds a research process capable of telling the truth about whether an
edge exists.**

## The five answers
1. **What we are building:** a CLV-judged research lab for college-football betting markets that
   becomes ONE product with TWO tiers — free public picks + record (recreational bettors) and paid
   tools (serious bettors). Paid anything is a 2027 decision. In 2026 the public output is
   "experimental paper signals, not certified strategies."
2. **Where the edges might be (hypotheses, not evidence):** derivative prices (1H, team totals) vs
   the sharp full-game consensus; early/stale lines; team-total markets; documented spread/total
   inefficiencies (travel, top-10 hangover, rivalry, national-TV overs, full-game weather).
3. **What 2026 tests:** up to 7 paper betting arms, each a pre-registered sequential test on CLV vs
   the vig-free consensus close, inside a 5% family-wise error budget; one-shot history looks for
   literature hypotheses. Real money PAUSED until an arm is promoted.
4. **What we need:** the Statistical Protocol (written + simulated), the consensus fair-price engine
   (first build), multi-book spread + moneyline capture (now), a team-total probe, literature tags.
5. **What would justify a business (all required):** promoted on CLV; real-money confirmation after
   promotion; the edge shows in two seasons (defined now, in the protocol); payment rails + legal.
   Season success = one promoted edge by January; the bar never moves — "not yet" said plainly.

## Decisions
- **Scoreboards:** Tate-at-Hard-Rock and customer-at-best-price across major US books in the feed.
- **Primary metric:** EV vs the vig-free consensus closing fair probability **at the wager's exact
  terms** (line + price; half-point value table per market, frozen and versioned). Raw point
  movement and Hard Rock-close CLV are secondary diagnostics; profit is secondary.
- **Consensus v1 (frozen before any confirmatory row):** per snapshot, each feed book's centred
  main-line quote de-vigged; consensus = MEDIAN probability; rungs excluded (`is_hr_rung` logic);
  close = newest consensus snapshot ≤ kickoff and within 2 h, else the bet is excluded and counted.
  Book set, aggregation, stale-quote rule, close window and version recorded; raw quotes kept.
- **Error control:** 5% family-wise Type I across the 2026 confirmatory program; FIXED LEDGER,
  K = 10 tests max, 0.5% each up front; a killed or timed-out test's alpha is spent, never recycled.
- **Each test:** sequential test designed to detect **+3% EV** (rough: ~160 bets at 80% power;
  simulation gives the real numbers); promote at the success boundary → $10 live validation;
  kill at the failure boundary (CLV clearly negative); timeout at max N or season end, whichever
  first → NEEDS MORE EVIDENCE (may restart in 2027 as a new test with new alpha).
- **Clocks:** every confirmatory clock starts at the first eligible build after the protocol is
  registered; all existing rows (1H paper ledger, H-FG-P, H-NEGGAP-P's three arms, real tickets)
  are development evidence only.
- **Paper arms carry no weekly cap** (the cap was a money rule); a promoted arm bets its own weekly
  volume at $10 flat.
- **Models:** three tracked numbers out of sample — MARKET ONLY, BV BLIND (market-blind football
  model), BV + MARKET BLEND (weight fit on prior seasons only); no closing information in any
  pre-close prediction.
- **History:** literature rows verified against the papers; overlapping years = reproduction;
  post-sample years = the clean extension and the verdict; pass → paper forward test only; fail →
  REJECTED unless the data was flawed.
- **Real money paused now**; H-STOP-2 closed inconclusive (n 10 / 9); Tate does no personal betting
  until a promotion; official plays system-only.
- **Publication:** signals private until the market closes; results after close + Monday report,
  pre-kickoff timestamps as proof. Site = research lab in public.
- **Timestamps:** naive-UTC storage convention kept; new evidence tables also store the book's own
  update time beside our capture time; public exports ISO with Z.
- **Cuts:** Pick'em dropped (H-MARGIN closed); offline backtest engine retired; real-money web
  machinery frozen (kept working); 1H-model study backlog parked.
- **Contradictions resolved by Tate:** 10-06 "real money unchanged" → paused; 10-07 "enter the
  Pick'em" → dropped; "enjoys betting his picks" → no betting until promotion; critique's "retire
  overs, 6 slots" → overs kept, 7 slots; critique's success wording → Tate's kept.

## Hypothesis ledger (evidence bucket stays honest; a slot is Tate's call, not proof)
| Hypothesis | Slot | Evidence bucket | Basis |
|---|---|---|---|
| 1H unders, per-slate bar, uncapped (H-PCT-TIE folded) | 1 | NEEDS MORE EVIDENCE | H-STOP-2 inconclusive; model ≈ close |
| 1H overs, bottom-20%-of-slate mirror | 2 | NEEDS MORE EVIDENCE | two-sided study null; old arms = dev data |
| Full-game unders, uncapped | 3 | NEEDS MORE EVIDENCE | post-hoc positive only |
| Derivative consistency (1H vs FG-implied fair) | 4 | NEEDS MORE EVIDENCE | untested |
| Early/stale lines (absorbs H-TIMING) | 5 | NEEDS MORE EVIDENCE | tiny n |
| open (team totals after probe, or a literature pass) | 6-7 | — | must earn entry |
| Shadow engines H-SHADOW-F / H-INSEASON-T | outside slots | NEEDS MORE EVIDENCE | judged on accuracy |
| Travel/TZ, top-10 hangover, rivalry, national-TV overs, FG weather, team-total censoring | history look | NEEDS MORE EVIDENCE | literature, unverified |
| 1H-game-total censoring; weather × style (1H); two-sided overs 2023-25; HR lag (day); WEPA-F; ELO-F; margin ATS | — | REJECTED | our registered tests |
| Reverse line movement / public fade | — | not pursued | literature negative; no data |

## Build sequence (each its own PR; registry row before any script)
0. **Starter Pack notes** — shipped as PR #317 (`docs/CFBD_PACK.md`).
1. **Reset bookkeeping**, split in two: **1a** (this PR: this document, the registry, the betting
   policy, the brief) and **1b** (the site: research-season banner, BET shown as a paper rating,
   signals hidden from the public until the close, owner still sees them). Contents: `docs/ROADMAP_2026.md` (this roadmap, v1); `docs/HYPOTHESES.md` —
   H-STOP-2 closed inconclusive, H-CLOSE-W withdrawn, H-MARGIN closed, H-NEGGAP-P superseded,
   H-PCT-TIE folded, H-TIMING absorbed, H-FG-P re-scoped as development; `docs/BETTING_POLICY.md`
   (parity-tested) — real money paused; site banner "research season", BET → paper rating, signals
   hidden until close (owner sees them); `CLAUDE.md` rewritten once (mission, reset, Open items).
2. **Consensus fair-price engine v1** (Tate's first build): reuse `beatvegas/devig.py`
   (`devig_two_way`, `is_centred_quote`, `is_hr_rung`), `centred_snaps(strict=True)`, the
   `fairPriceWindow` logic; half-point value tables per market from historical scoring
   distributions; consensus close; EV-at-terms CLV on every paper/challenger row for both
   scoreboards; book source timestamps. Run over the development rows to measure the per-bet
   spread of EV-at-terms CLV — the input the protocol simulation needs.
3. **Statistical Protocol** (a protocol document + registry row `H-PROGRAM-2026`): ledger K=10,
   per-test boundaries, +3% target, max N, timeout, exclusions, correlated-arm note, entry rule,
   the "two seasons" definition; a simulation using step 2's measured spread, reporting each
   arm's power and expected N at its expected weekly volume. Tate approves the simulated numbers
   before freezing; no confirmatory observation before this is registered.
4. **Capture expansion:** multi-book full-game spreads + moneylines in `poll_full_game`; one
   team-total probe dispatch (credits printed) → Tate decides capture; pace vs the $150 ceiling.
5. **Literature looks:** verify each paper and its sample years; tags (time zones from venue
   coordinates, CFBD rankings, CFBD media, one rivalry list Tate picks and we freeze); one
   `study.yml` dispatch per row on the clean post-sample years.
6. **Confirmatory arms go live** (each registered under the protocol before it logs): 1H unders,
   1H overs mirror, FG unders, derivative consistency, early/stale lines.
7. **Shadow engines** (outside slots), 8. **public research-lab page**, 9. **retire the offline
   backtest engine**.

## What every paper row records
Arm, protocol version, game, market, side, book, line, price, our capture time (naive UTC) and the
book's own update time, decision build id, MARKET ONLY / BV BLIND / BLEND fair prices at bet time,
consensus fair probability at bet time, best major-book price, Hard Rock price, consensus close +
Hard Rock close (line, price, snapshot time), EV-at-terms CLV vs consensus, point CLV, CLV vs Hard
Rock, exclusion flag + reason, result, units at the logged price, push flag, frame fingerprint.

## Weekly cadence
Builds unchanged (Tue/Thu/Fri pm, Sat am) feeding paper arms; Monday program review stays the one
decision point (arm positions vs boundaries, promotions, kills, entrants while ledger slots remain).

## Verification
Per PR: registry + docs-parity tests, full pytest with its exit code checked, vitest + tsc on site
PRs, `bv-site-check` before any web PR, `bv-ship` to merge (CI incl. e2e, prod health). Protocol
PR: simulation output reviewed by Tate. Engine PR: EV-at-terms CLV hand-worked on one game per
market with the sign checked; first-rows check at the next card build. Capture PR: credits per
sweep printed against the plan.

## Open questions carried into the Statistical Protocol (step 3)

- **The shadow engines' error budget.** H-SHADOW-F and H-INSEASON-T sit outside the betting slots
  and still hold 1.67% each from Option 2 of 2026-10-07. Whether that stays separate or moves into
  the K = 10 ledger is decided in the protocol, before either engine logs anything.
- **H6** (`docs/WHEN_TO_BET.md`, one confirmatory look on 2026-12-07) is a finding that licenses
  nothing and keeps its own 5% unless the protocol says otherwise.
- **Collectors already running** (the first-half paper ledger, H-NEGGAP-P's three over arms,
  H-FG-P's full-game unders) keep logging; every row they write is development evidence and feeds
  the protocol's simulation. None counts toward a confirmatory boundary.
- **The licensed CFBD Starter Pack** (`docs/CFBD_PACK.md`): learning only, or a data source? Open.

## Amendment log

| Version | Date | Change | Decided by |
|---|---|---|---|
| v1 | 2026-10-07 | Adopted. | Tate |
| v1.1 | 2026-10-07 | The consensus specified (`docs/CONSENSUS.md`): every centred book except Hard Rock and Fliff (exchanges count), multiplicative de-vig, the 2-hour close window for every market (the full-game capture's 3 hours does not apply to the judge), at least 3 books, at most 1.5 points of line conversion, first-half table built from 2013–25 games by the full-game-close proxy. "Rungs excluded (`is_hr_rung` logic)" is moot for the consensus: Hard Rock never counts. | Tate |
| v1.2 | 2026-10-07 | The Statistical Protocol p1 (`docs/PROTOCOL_2026.md`, `H-PROGRAM-2026`): the observation is a completed WEEK's mean line value (WEEK-SHOCK measured the shared week move; the design assumes 0.02); spread 0.06 per bet; at least 30 readings over 3+ weeks; Hard Rock's price; the kill is the sequential LOWER bound and its label is NEEDS MORE EVIDENCE, not REJECTED (replacing "kill at the failure boundary (CLV clearly negative)"); timeout 200 readings or season end; "two seasons" = the unchanged rule passes again in 2027; the shadow engines leave the alpha budget (exploratory). | Tate |
