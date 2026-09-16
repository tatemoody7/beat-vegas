# The external review, read against the repo

**What this is.** On 2026-09-13 Tate ran the question "is there a real edge in college
football totals, and what should Beat Vegas become?" through ChatGPT and saved the 32-page
answer. The file is `docs/external/2026-09-13-chatgpt-cfb-totals-review.pdf`. Three
documents written since — `TWO_SIDED.md`, `WEATHER_STYLE.md` and the share-engine spec —
refer to "an external review"; this is it. This page maps each of its claims and proposals
to what the repo has already tested, decided or left open. **No new numbers are computed
here**; every figure is quoted from the document named beside it, and the write-up's own
figures are attributed to it.

**The write-up's verdict, in its words.** Keep the first-half under as the champion; do not
replace it with a generic full-game model; evolve toward "a college-football scoring and
totals engine with multiple market-specific strategies competing against one another",
promoting a market only when it "demonstrates a real edge out of sample and prospectively".
Its first challenger is two-sided first-half totals, its second is full-game over/under.
It ranks weather × team style, expected possessions, opener-vs-close, 1H-vs-full-game
implied scoring, opponent adjustment, the 2023 rule regime and price-aware EV as the
highest research priorities.

## Claim by claim

| The write-up says | Where the repo stands | Read |
|---|---|---|
| Keep the 1H under as champion; challengers win only under the same standards, prospectively | Adopted as the working frame. The paper ledger is the scoreboard under a registered SPRT with two clocks (profit at actual prices, line value vs Hard Rock's strict close); hit rate stops nothing. The share engine is the registered challenger and stays a challenger until its gate passes. | `STOPPING_RULE.md`, `superpowers/specs/2026-09-15-share-engine.md` |
| Two-sided first-half totals should be the first challenger | Tested first, as a diagnostic on the same 2023-25 real-close set: **NO OVER-SIDE FINDING** under four pre-registered conditions, all required. The engine's outputs feed the under decision only until a separate registered test says otherwise. | `TWO_SIDED.md` (R07) |
| Weather is "potentially underpriced — strong evidence" (Salaga & Howley 2024) | Every historical weather row had been wrong (indexed at the UTC hour into a local-time series, mean 6.79°F off); repaired into `weather_obs` with a `decision_safe` flag. Activation refused on blast radius: 31–62 of 622 priced games cross the bet bar against a pre-registered limit of 5. The write-up's evidence is full-game totals and outcomes; the repo's question is 1H market error at decision-time forecasts. | `WEATHER.md` (R06) |
| The deeper weather opportunity is interactions with offensive style | Exactly R09: decision-time gust × pass rate, after conditioning on the book's de-vigged P(under). **NO FINDING** on 1,220 decided outdoor games. | `WEATHER_STYLE.md` (R09) |
| Market information should be a feature; model `actual − market-implied` (a market-error model) | Tried twice on the spent set. A market-conditioned residual engine did not beat the close (close 8.73 / residual 9.01 / incumbent 9.23 MAE, 2025). A one-parameter blend of close and `bv_line` fits **w = 0.80** and beats the close by 0.020 and 0.006 MAE with paired intervals spanning zero; frozen in `data/blend.json`, read by nothing. The share engine is the third attempt and is registered before it is built. | R03; `BLEND.md` (H3A, H3B) |
| Censoring at zero biases market-implied team scoring (Arscott 2023); model each team's distribution | The mechanism is real (dog 1H shutout rate 8.6% → 23.1% by spread bucket) and the residual after the price control is not detectable: spread coefficient +0.00369/pt, CI [−0.0083, +0.0157], sign flips by season. **DO NOT BUILD** a spread-only price correction. The share engine keeps the discrete, two-team output the study validated. | `CENSORING_STUDY.md` (R05) |
| The 2023 clock change is a regime break; do not pool 2017 and 2025 | `era_post2023` is a feature (the tree learns era-conditional splits); the training frame the studies read starts at 2023; the spec's criterion 5 forbids a claim that leans on pre-2023 rows. | `BV_LINE.md`, `etl/features.py` |
| Build a travel stress score (Coleman): distance, time zones, direction, body clock, short week | `etl/context.py` computes rest days, short week, travel distance, time-zone shift and local kickoff hour for every game. The brief records that situational features did not move the model. A registered row testing them against **market error**, not scoring, has not been written. | `PROJECT_BRIEF.md`, `etl/context.py` |
| Expected scoring ≈ possessions × efficiency per possession | The repo's own finding: genuine 1H signal is pace plus efficiency and scoring levels; the heavy 1H play-by-play backfill did not improve the total (MAE 9.22 with, 9.18 without). Team-level PBP factors stay as display chips. | `CLAUDE.md` (honest status), `scripts/validate_engine.py` |
| Keep "as-of" model states (Sunday, Tuesday, Thursday, Saturday) and ask when to bet | Four whole-week builds are stored whole in `cards`; `snapshots.build_rows` keeps them apart; H6 is registered with one confirmatory look on 2026-12-07. Week 2's answer so far: Hard Rock's line at every BET build **was** its close, so timing is about selection, not price. | `WHEN_TO_BET.md` (H6) |
| Every variable needs an information timestamp; no lookahead | Market reads are `lines.as_of` / `consensus_as_of`, never the mutable `games.spread`; weather rows carry `decision_safe`; week-1 retro predictions are stamped `captured_at` after kickoff and marked "scored after". | `HR_LAG.md`, `WEATHER.md`, `CLAUDE.md` |
| Number + price = bet; grade against a vig-free close | The kill price is enforced server-side on a **live** price and fails closed (`PRICE UNAVAILABLE`); `ev` is a price-shopping read against the market's no-vig fair probability, not wager EV, and 0 of 42 priced week-2 rows cleared `ev ≥ 0`. A true EV gate needs a calibrated P(under), which is what the share engine is for. Line value is measured against the strict-centred close. | `RANKING_AND_TRUST.md` §8b, `pickRules.ts` |
| Early pricing is where an information advantage is most monetizable | In this market, not yet: 48 of 71 Hard Rock 1H lines never moved in week 2 (mean drift −0.18), Hard Rock does not lag the retail market at a one-day grain, and its price does not move before its number. | `HR_LAG.md` (R08), `WHEN_TO_BET.md` |
| Benchmark against a closing sharp-market total | It does not exist for this market through the Odds API: Pinnacle posted a 1H total on 2 of 75 events, BetOnline on 3, both only where Hard Rock had. The retail median stays the reference. | `SHARP_BOOKS.md` (H5) |
| Do not measure success by win percentage; use CLV, ROI, calibration together | The stopping rule's clocks are profit at actual prices and favourable line value; hit rate is reported and stops nothing. Proper scoring rules (`brier_multi`, `log_loss`, `reliability`, intercept/slope) exist and are three-outcome-aware. | `STOPPING_RULE.md`, `backtest/censoring.py` |
| Chronological walk-forward only; every subgroup must survive; every edge needs an ablation | Every 2023-25 study is walk-forward by season. The share-engine gate requires stability across both test seasons (4), survival without the 28+ bucket or any one week band (7) and an ablation that hurts when the market inputs are removed (8). | share-engine spec, `BLEND.md` (H3B) |
| Discovered-in-training vs confirmed-on-untouched must never be confused | The registry marks the 2023-25 real-close set **spent** and lists every look at it; anything important is validated prospectively on 2026+ locked decisions. | `HYPOTHESES.md` |
| Full-game over/under is the second challenger | Not registered. Full-game lines are captured Sunday and both markets are logged and graded (`market_fg` ledger), but the full-game backtest found no edge on the thin 2023-25 regime and nothing models full-game picks. | `CLAUDE.md` |
| Public over bias, reverse line movement, conference and rivalry trends are low priority | Agreed by omission; none is pursued or registered. | — |
| FBS-vs-FCS mismatches are a "high-interest hypothesis" | The repo went the other way by rule: training and scoring are FBS-vs-FBS only (R01, adopted), because non-FBS games score differently and almost none carries a real 1H line to grade against. | `etl/fbs.py`, `HYPOTHESES.md` (R01) |
| Quarterback availability should be an efficiency estimate, not a flag; test QB news vs cluster injuries | `qb_out` is a binary flag from Rotowire, forward-only, gating paper picks. Neither the efficiency estimate nor the cluster-injury question is registered. | `card.py`, `sources/rotowire.py` |
| Coaching as measured behaviour; coordinator changes as regime breaks | Listed as a brainstorm idea in the brief; not registered. | `PROJECT_BRIEF.md` |
| Team totals, 1H spread and full-game markets as one connected system of prices | Not captured: the Odds API pull requests `totals,spreads` only; no team totals or 1H spreads are stored. Not registered. | `sources/odds.py` |
| Opponent adjustment is mandatory | SP+, the 247 talent composite and returning production are features (CFBD-only columns). Opponent-adjusted **1H** efficiency from play-by-play is not. | `etl/features.py`, `CLAUDE.md` |

## Proposals the repo has not registered

Each of these would need a row in `HYPOTHESES.md` — question, data, criterion — before a
script. None is scheduled; the research queue is already spoken for through the share
engine, and the 2023-25 real-close set is spent, so a new row must name prospective 2026
data or a different historical cut.

- **Travel against market error.** The features exist in `etl/context.py`; the test the
  write-up asks for is whether the *book* misses them, i.e. after conditioning on the
  price, which no study has run.
- **Full-game two-sided challenger.** The write-up's second challenger. Needs its own
  frame (second-half scoring is conditional on the first-half state), its own market
  data (full-game closes exist for 2023-25 in `odds_snapshots`), and a decision that
  full game is a research market at all — today it is a logged market, not a modelled one.
- **Team-total / 1H-spread consistency.** Would need new capture first; the Odds API
  bills each added market on every sweep.
- **Coordinator and scheme changes** as a regime flag on season-to-date features.
- **QB news vs lower-profile cluster injuries** — does the book over- or under-react?
  `qb_out` is captured forward-only from 2026, so this is a 2026+ prospective row.
- **Opponent-adjusted 1H efficiency** as a feature family; the PBP ablation says the
  unadjusted version added nothing, which is the null a registered row would have to beat.

## Where the write-up and the repo genuinely differ

- **Weather.** The write-up calls it "one of the strongest candidates" on published
  full-game evidence. The repo's decision-safe, price-controlled 1H test found nothing,
  and activation was refused on blast radius. These are different questions; the repo's
  is the one a bet can act on.
- **The first challenger.** The write-up prefers two-sided 1H. The repo tested the over
  side as a diagnostic first, found no signal at the bar, and chose a market-conditioned
  under-only challenger (the share engine) instead.
- **Early-week edge.** The write-up expects it from the opener-to-close literature. In
  this market and this season Hard Rock's first-half number barely moves, so the
  timing question is selection. H6 will say whether that holds over a season.
- **A sharp benchmark.** The write-up assumes one exists. For CFB first-half totals it
  does not, at any book the Odds API carries.

## Sources the write-up cites

For future rows that want to cite the literature rather than the write-up:

- Francisco & Moore, *College football bettors and the wisdom of crowds* — 7,557 games,
  2003-04 to 2015-16; unders 50.09% at the opener and 50.14% at the close; mean absolute
  deviation from the final 13.28 (opener) vs 13.08 (close). The write-up's figures.
- Salaga & Howley (2024), *The impact of weather on betting outcomes and market behaviour
  in the NCAA football totals market*.
- Coleman, *Team Travel Effects and the College Football Betting Market* (Journal of
  Sports Economics).
- Arscott (2023), *Market Efficiency and Censoring Bias in College Football Gambling*
  (Journal of Sports Economics).
- The 2006-07 clock-rule studies (Coastal Carolina finance/economics working paper) and
  the NCAA's 2023 timing-rule release.
- Unabated on vig-free closing-price comparison; Circa on how opening lines are set.

The write-up's own numbers were not re-derived here. Where the repo has measured the same
thing on its own data, the repo's number is the one quoted in the table above.
