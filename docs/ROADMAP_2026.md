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
3. **What 2026 tests:** up to 8 paper betting arms (amended v1.8, 2026-10-10; was 7), each a
   pre-registered sequential test on CLV vs the vig-free consensus close, inside a 5% family-wise
   error budget; one-shot history looks for literature hypotheses. Real money PAUSED until an arm is promoted (amended v1.4, 2026-10-08:
   Tate's personal first-half-unders ledger resumes beside the research, never as evidence).
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
  until a promotion; official plays system-only. **Amended v1.4 (2026-10-08):** Tate bets first-half
  unders again as a personal ledger (the old rule, cap 5 by gap, $10 flat, no stop rule), never an
  observation for any arm; a promotion's live validation stays a separate track.
- **Publication:** signals private until the market closes; results after close + Monday report,
  pre-kickoff timestamps as proof. Site = research lab in public. **Amended v1.7 (2026-10-10):**
  the board and game page show every rating to everyone before kickoff, in paper wording, with
  "Florida, 21+"; the bet ledger, `/records` and both CSVs still withhold a game until kickoff.
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
| Weather unders, 10+ mph forecast at kickoff: first half (H-ARM-WX1H) and full game (H-ARM-WXFG) | 6-7 | NEEDS MORE EVIDENCE | v1.6: R09 (1H gust × style) null; full-game weather untested |
| First-half unders when the consensus full-game total at the build is 60+ (H-ARM-HT1H) | 8 | NEEDS MORE EVIDENCE | v1.8: a 2023-25 pattern found by slicing after the fact (58.3% at the real close, n 268); 2026 too thin to say |
| Shadow engines H-SHADOW-F / H-INSEASON-T | outside slots | NEEDS MORE EVIDENCE | judged on accuracy |
| Arscott full-game overs (censoring), national-TV unders, Bennett holdover | history look (one each, Holm 5% across the six, outside the ledger) | **REJECTED** (v2.0) | NOT MET 2026-10-09, final (`docs/LITERATURE.md`); the data was not flawed |
| Coleman eastbound visitor, Cox rivalry (trophy games), Salaga weather unders | history look (one each, same Holm family) | Cox **REJECTED** (NOT MET 2026-10-11, final; amended v2.3); Coleman and Salaga NEEDS MORE EVIDENCE (parked, v2.1) | literature verified (`docs/LITERATURE.md`, v1.3); Coleman waits on the full text, Salaga on `weather_actuals` |
| Team totals: a book's posted team total vs the fair team total implied by the consensus spread + total | tracked candidate → a slot once one frees (8 run at a time, v1.8) | NEEDS MORE EVIDENCE | `H-MKT-PROBE` 2026-10-10 → Tate decides capture → paper arm |
| Full-game weather: totals under-react to bad weather | slots 6-7 (v1.6), plus the 2024-25 history look and the Salaga look | NEEDS MORE EVIDENCE | the three run side by side (v1.6); 1H weather × style was null |
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
**Amended v2.1 (2026-10-11):** the Monday review is one sitting of about 30 minutes on a one-page
read (arms first); the long weekly report stops. Decisions are taken at two reads only, 2026-12-07
(mid-point, none) and 2027-01-25 (final); the arms run unchanged between them (v2.0 decision 3).
**Amended v2.6 (2026-10-18):** paid capture ends after the Saturday 2026-11-28 slate and the one
final read is **Monday 2026-11-30**; the 12-07 mid-point is dropped and the 2027-01-25 read replaced.
Templates: `docs/program/JANUARY_2027_REVIEW.md`.

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
- **H6** (`docs/WHEN_TO_BET.md`, one confirmatory look on 2026-12-07; v2.6 moved it to the
  2026-11-30 final read) is a finding that licenses nothing and keeps its own 5% unless the
  protocol says otherwise.
- **Collectors already running** (the first-half paper ledger, H-NEGGAP-P's three over arms,
  H-FG-P's full-game unders) keep logging; every row they write is development evidence and feeds
  the protocol's simulation. None counts toward a confirmatory boundary. (Amended v2.3: the neggap
  and H-FG-P collectors were retired 2026-10-08; the registered arms log from 2026-10-13.)
- **The licensed CFBD Starter Pack** (`docs/CFBD_PACK.md`): learning only, or a data source? Open.

## Amendment log

| Version | Date | Change | Decided by |
|---|---|---|---|
| v1 | 2026-10-07 | Adopted. | Tate |
| v1.1 | 2026-10-07 | The consensus specified (`docs/CONSENSUS.md`): every centred book except Hard Rock and Fliff (exchanges count), multiplicative de-vig, the 2-hour close window for every market (the full-game capture's 3 hours does not apply to the judge), at least 3 books, at most 1.5 points of line conversion, first-half table built from 2013–25 games by the full-game-close proxy. "Rungs excluded (`is_hr_rung` logic)" is moot for the consensus: Hard Rock never counts. | Tate |
| v1.2 | 2026-10-07 | The Statistical Protocol p1 (`docs/PROTOCOL_2026.md`, `H-PROGRAM-2026`): the observation is a completed WEEK's mean line value (WEEK-SHOCK measured the shared week move; the design assumes 0.02); spread 0.06 per bet; at least 30 readings over 3+ weeks; Hard Rock's price; the kill is the sequential LOWER bound and its label is NEEDS MORE EVIDENCE, not REJECTED (replacing "kill at the failure boundary (CLV clearly negative)"); timeout 200 readings or season end; "two seasons" = the unchanged rule passes again in 2027; the shadow engines leave the alpha budget (exploratory). | Tate |
| v1.3 | 2026-10-08 | Literature verified (`docs/LITERATURE.md`). Six history looks approved, one look each on the years after the paper's sample, Holm-corrected at 5% across the six and outside the K = 10 ledger (a pass licenses a paper arm only, which then spends a ledger slot): Arscott full-game overs; Coleman eastbound visitor (definition frozen from his full text, once read); national-TV unders (ABC, CBS, NBC, FOX, ESPN; not ESPN2); Cox rivalry (trophy games, Wikipedia's list frozen at registration); Bennett holdover; Salaga weather unders (after an observed-weather backfill). Ledger: "team-total censoring" relabelled as Arscott's full-game overs; team totals and full-game weather added as tracked candidates with their next steps. | Tate |
| v1.4 | 2026-10-08 | Real money resumes as Tate's personal first-half-unders ledger, beside the research: the old rule (BET at the per-slate bar, the top 5 a week by gap, every money-path check), $10 flat on $100, no stop rule to the season's end; never an observation for any arm (the protocol reads only an arm's paper picks); a promoted arm's $10 live validation is a fresh, separate track. The 7 paper arms, the protocol, the K = 10 ledger and the judge are unchanged. Site: banner names both tracks; signed in, a BET inside the cap reads "Bet one unit", past it "Paper signal"; a visitor never sees bet wording; Results shows line value vs the consensus close per ticket. Switch `rule_paused` off 2026-10-08 20:00 UTC. | Tate |
| v1.5 | 2026-10-09 | Strategic review topic 3. Protocol `p1.1` (`docs/PROTOCOL_2026.md`): the three arms' clocks are **paused before any completed week** while the model's training leaks are fixed (pace backfilled as of the week's median kickoff, the legacy weather table, same-season roster and talent, the rivalry and conference flags); each clock starts at the first card built on the leak-fixed model, and everything the arms log until then is development evidence. Restart rule: abandoning and restarting a test spends its 0.5% once any completed week has been read; before that it is free. Selection rules, slots, the test and the judge are otherwise unchanged. The literature-ledger question moves to v1.6. | Tate |
| v1.6 | 2026-10-09 | Strategic review topic 3: weather is tested as its own edge, not through the model. Two forward paper arms under p1.1 — H-ARM-WX1H (first-half unders) and H-ARM-WXFG (full-game unders) on every outdoor game whose newest build-time forecast has a sustained kickoff-hour wind of 10+ mph, at Hard Rock's price — take ledger slots **6 and 7** (4-5 stay reserved for derivative consistency and stale lines; team totals wait for a free slot). They run beside the 2024-25 history look and the Salaga look rather than after it (replacing "Salaga look first, then a paper arm"). The leaky kickoff-weather inputs left the model (#344). The literature-ledger question moves to v1.7. | Tate |
| v1.7 | 2026-10-10 | Publication: friends who opened the site saw an empty board (every pre-kickoff rating read "Rating publishes at kickoff."), so a visitor now sees the board and game page as the owner does, ratings before kickoff included, in paper wording (never "Bet one unit"; the owner's "bet logged" chip stays his until kickoff). The site banner adds "Florida, 21+" (`docs/LEGAL_MEMO_2026-10.md`); the build warnings ("card built Nh ago", "build did not run") become owner-only; the bet ledger, `/records` and both CSVs keep withholding a game until kickoff. The literature-nulls amendment proposed for the 2026-10-12 review becomes v1.8. | Tate |
| v1.8 | 2026-10-10 | Market rules over the model. H-MODEL-FIX came back NOT MET (`docs/MODEL_FIX.md`): the live model stays, model work stops, and arms 1-3 start at the 2026-10-13 card. A forward paper arm on the 2023-25 high-total pattern, H-ARM-HT1H, takes ledger slot **8**: first-half UNDERS on every game whose consensus full-game total at the build is 60.0 or more (the judge's books, at least 3), at Hard Rock's price. It reads no model, so its clock starts at its first eligible build. The cap on paper arms rises from 7 to **8**; each arm still spends its own 0.5%, slots 4-5 stay reserved for derivative consistency and stale lines, and 9-10 are free. The literature-nulls amendment moves to v1.9. | Tate |
| v2.0 | 2026-10-11 | **The October review (`docs/program/REVIEW_2026-10.md`), Tate's sixteen decisions.** (1) **Objective:** for the next twelve months Beat Vegas exists to prove, with small real stakes at Hard Rock, that one registered rule beats its prices; "a potential business" and the two-tier product are consequences of proof, not goals, and no product, email list, public research page, paid-tier or Discord work happens this season. (2) **The site is a public record and nothing more:** board, ledger, how it works, `/records`; the owner-only sections (Monday review on Results, research section, answer bar, My-teams chip) are removed. (3) **The arms run unchanged to the January review:** every registered arm (slots 1-3, 6-8), the judge `cv1` and protocol `p1.1` are frozen; readings only; a bug in a reader or a capture is fixed with the before/after shown, a selection rule or threshold is not touched; a bad arm ends on its own boundary. Known weak priors are recorded, not acted on: H-ARM-FGU tests the uncapped reading that failed its Wilson bound; H-ARM-HT1H's threshold came from the 2023-25 slice the registry calls exhausted; the 1H wind history look (H-WX-HIST) read null. (4) **The edge target stays +3% with one-season clocks for 2026**; the target for 2027 registrations is decided at the January review. (5) **Kalshi is measured before anything is built:** lawful from Florida today, not a softer price (about −110 to −121 all-in as a taker, a mirror of the books), unique for line shopping, no winner limits and a free maker side on first-half totals; its data terms keep its prices off the public site. One exploratory registry row reads the two venues on data already in `odds_snapshots` (Kalshi full-game markets via `us_ex`); no account, no capture, no credits. (6) **The next build is Hard Rock off-market capture** (the book's own update time kept, The Odds API event id stored, denser Saturday first-half polling inside 6 h, credits quoted first); the two structural arms (slots 4-5: derivative consistency, early/stale lines) are designed on that data, never before it. (7) **The personal ledger continues** (v1.4 unchanged: the old rule, $10 flat, no stop rule, never evidence) and the site labels it a personal stake; the mission line "bet only when we have an edge" applies to promoted rules. (8) **The cut list** (each its own PR, nothing an arm reads): the offline backtest engine and its tools, the residual engine, the four finished gate workflows, the scripts nothing calls, the margin model, the DraftKings first-try poller; the post-mortem tables and factor ledger leave the live path (the public accuracy number is re-sourced first); GitHub's cron backups go and Vercel is the only trigger. (9) **Measurement fixes, shown before/after:** stored `clv` excludes Hard Rock and Fliff and uses the centred-main filter; `clv_prob` is relabelled or removed; the protocol reader keys bowls by date and never lets an ungradable pick freeze a week; `docs/BETTING_POLICY.md` matches the code on unpriced paper picks; the four side readings print beside each Monday read. (10) **Bookkeeping:** the three literature nulls are REJECTED (table above; deferred since v1.5); `docs/PROTOCOL_2026.md` reads 8 betting slots at a time (v1.8); the brief says the pause switch is off and the ledger ON. The evening alignment calls are v2.1. | Tate |
| v2.1 | 2026-10-11 | **The alignment calls (evening of the October review; `docs/program/JANUARY_2027_REVIEW.md` holds the templates).** (1) **This week:** H-ARM-FGU's week-6 select is replayed read-only before the first read (done 2026-10-11: the build reproduces exactly, `docs/HISTORY.md`); the 2026-10-11 refit is confirmed (`model_runs` 10, `gbm_v1`, with the full-game shadow refit 11); the App State scoreless half waits for play-by-play proof; Claude ships bug fixes and docs alone, and asks first before anything that touches an arm, the judge, the protocol or money. (2) **Cadence:** one Monday sitting of about 30 minutes, Tate opens the session, Claude brings a one-page read (arms first: positions, exclusions, the judge's reading, what broke, decisions). The long weekly report stops; HISTORY keeps one episode per PR; the personal ledger is shown on Results and never in the Monday read. The light read is 2026-10-12, the first full Monday read 2026-10-19. (3) **Two reads:** 2026-12-07, a mid-point with the H6 look and no decisions; 2027-01-25, the final read that decides every arm. (4) **The 2027 default, drafted now as the January template:** +1.5% EV target, two-season clocks, capture-based arms registered first; model arms return only if one passes in 2026. A pass in 2026 earns $10 flat live validation only, decided in January, and a second season is still required before anything else. (5) **Kalshi:** an account is opened only if the January H-VENUE-1 read shows best-of-two beating Hard Rock alone by about 1 point of EV over 100+ games on fee-inclusive prices (a CPA is consulted first). The 2026-10-11 development read (53 week-6 games) showed Kalshi about 4 points better on every under at the same line distance, which is the size of its 7% taker fee: the January read states whether the feed's `us_ex` price includes it before any claim. (6) **Accounts:** CFBD drops to Tier 1 at the 2026-11-06 renewal; The Odds API stays on 20K; the GitHub Actions cap rises to $20. (7) **After 2026-10-19:** one late GitHub cron per job stays as the backup (the retries go); the post-mortem tables stop once the public accuracy number is re-sourced; the Hard Rock alternate-rung drift is accepted for now (the capture's book timestamps will show it; probe in January). (8) **Studies:** the Cox look runs now (`H-LIT-COX`, registered 2026-10-11: the favourite that won the last three meetings); Coleman and Salaga are parked; the `weather_actuals` backfill finishes on quiet days (Monday to Wednesday) only. (9) **Friends** get one plain message from Tate: research season, paper ratings, nothing proven. (10) **2026 success** keeps the promotion bar (one arm passes its registered test); the research-year deliverables are written beside it and reported in January whatever the arms do: a clean reading on every arm, the Hard Rock capture dataset, the judge validated (H-JUDGE), 2027 designed. | Tate |
| v2.2 | 2026-10-13 | **Catch-up ticks for the no-deadline jobs** (from the 2026-10-13 usage review). Grading, the Sunday run and the Monday pricing report each keep one late Vercel tick (grade 20Z daily; Sunday 23Z, window to 8pm ET; pricing-monday 18Z, window to 3pm ET) that dispatches only when no run since its window opened succeeded. v2.1 item 7's "the retries go" still holds for everything else: no catch-up for a card build (a late card would log arm picks at lines outside their registered window) or a close poll (useless after kickoff); a missed one shows on the board. Nothing about an arm, the judge, the protocol or money changes. | Tate |
| v2.3 | 2026-10-14 | **Bookkeeping from the whole-system review (Tate, 2026-10-14; `~/.claude/plans/pasted-content-id-a68f…`, Parts 9-10).** The ledger table records Cox NOT MET (final, 2026-10-11) and the retired collectors (2026-10-08). The 17-step programme is adopted: privacy and integrity fixes first (steps 1-8), the research platform (`arm_positions`, `/research`, the status strip, the Results relabel), the Board fixes (visual/bug now; the four behaviour items by separate decision), the four research proposals (memos and draft rows, each its own decision). Protocol amendment p1.2 (the week rule and the postseason rule) is drafted for separate approval; nothing about the six arms, the judge, pv1, grading or the personal ledger changes by this row. |
| v2.4 | 2026-10-14 | **Protocol p1.2 (Tate, 2026-10-14).** R1: a regular-season pick reads in its CFBD week, a postseason pick in the ISO week of its kickoff (bowls no longer collapse into one reading). R2: a reading week enters only when every pick is graded and the read runs at or after the Monday 12:00 UTC after its last kickoff (no partial week can enter mid-week). The seven-day permanent exclusion of the draft is NOT adopted; its replacement (R3′: the judge reads a pick once its close exists, graded or not) waits on Tate. No arm's rule, start, judge, alpha or boundary changes; measured impact on 2026-10-14: no reading changes. `docs/PROTOCOL_2026.md`. |
| v2.5 | 2026-10-14 | **Protocol p1.2 R3′ and the exploratory EV-at-price collector (Tate, 2026-10-14).** R3′: the judge reads every pick an hour after kickoff, graded or not, because its reading uses only pre-kickoff quotes; a reading week completes when every pick has the judge's decision; an unverified result stays ungraded and is reported. The seven-day permanent exclusion is not adopted. H-ARM-EVP (value at Hard Rock's price, +2%) runs in 2026 as an EXPLORATORY collector: no ledger slot, no alpha, no SPRT, never forward evidence; a 2027 confirmatory registration is decided at the January review. The Board alignment (B1, B2b, B3, B4) merged the same day (#393). |
| v2.6 | 2026-10-18 | **The final-2026 plan (Tate's fourteen decisions, `~/.claude/plans/beat-vegas-final-fluffy-hollerith.md`; the independent audit of 2026-10-18).** (1) **Paid operation ends after Saturday 2026-11-28** (week 13; last kickoff 2026-11-29 04:00 UTC, `protocol.SEASON_LAST_KICKOFF`); conference championships and Army-Navy are not captured. (2) **The final read is Monday 2026-11-30** (`protocol.FINAL_READ_DATE`): it replaces the 2027-01-25 read and the 2026-12-07 mid-point is dropped (it would follow the final read); protocol **p1.3**: every running arm times out there, nothing after the last kickoff is an observation, and `protocol_position --season-over` is implied from 12:00 UTC that day (`pricing_monday.yml` input `season_over`). (3) **Real money ended 2026-10-18**: `rule_paused` on (`app_settings_log` 674) and it stays on; the 30 graded tickets are a frozen historical ledger, never evidence; the owner log path leaves the site. (4) **The model is frozen**: the registered Sunday refit continues, no model-code, feature or input change until the final read. (5) **Collection stops** for play-by-play, weather actuals, the post-mortem tables and the SP+ factor chips; moneylines stay (pv1 compares them). (6) **The Board ranks by arm membership**: rows grouped by which registered arms logged a paper pick, the Hard Rock line, the consensus line and the model number as plain columns, the gap visible but never the sort key. (7) **The Saturday board report stops** (the one Mac task and the one scheduled text); the automated Monday read is the written record. (8) **Alerts are GitHub email only**, from one daily health digest with age checks that exits 1 on any problem. (9) **H-ARM-FGU and H-ARM-WXFG apply `is_hr_rung` forward** from the next card after it merges (past picks untouched and tagged); the rule is its own p1.3 amendment and PR. (10) **After the final read**: a full export (pg_dump + per-table CSVs) is committed to the public repo, then Neon drops to the free tier; the site stays up as the public record. (11) **A weekly immutable evidence snapshot** (`data/evidence/2026-wNN/`) is committed to the public repo by the Monday workflow. (12) **H6, H-JUDGE and H-VENUE-1 all read on 2026-11-30** with the final read (`when_to_bet.CONFIRMATORY_DATE` moves from 12-07; the two January reads move). (13) **The final report is `docs/program/SEASON_2026_FINAL.md`** in the public repo with a generated numbers appendix, plus a Final read section on `/research`. (14) **The pre-arm paper picks (77) and the retired neggap picks** appear in the report in full as development evidence, never confirmatory, never pooled with the arms. No arm's selection rule, start, judge, alpha or boundary changes by this row; 2027 is decided from the final report, not assumed. | Tate |
