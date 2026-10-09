# The literature behind the 2026 history looks

**Finding (verified 2026-10-08, roadmap step 5): every paper the deep-research report cited
exists, but the report misdescribes most of them, and none carries evidence strong enough to
promote anything.**

- **The report's two STRONG rankings are the worst described.** Arscott tests full-game OVERS (not
  team totals). Coleman's travel effect runs the opposite way to the report.
- **The best published results are marginal:**
  - Arscott: 56% on 691 bets, p 0.08 against the 52.4% break-even.
  - Coleman: about 55% on about 330 games.
  - Cox: the one result profitable at 5% is a streak sub-split.
  - Bennett: 83 games.
  - Each was tuned on its own sample.
- **Tate approved six history looks (2026-10-08, roadmap amendment v1.3).**
  - Each gets one look, on years after the paper's sample only.
  - Holm-corrected at 5% across the six, outside the K = 10 ledger.
  - A pass licenses a paper arm only; that arm then registers under `docs/PROTOCOL_2026.md` and
    spends a ledger slot.
- **Team totals and full-game weather** are tracked edge candidates in their own right.
- **Three looks ran, once each (2026-10-09 UTC): all NOT MET, and final.** See "Results"
  below.
  - Arscott 51.6% on 219, national TV 52.4% on 2,385, Bennett 46.7% on 60, against the 52.38%
    break-even. Every p is above 0.5, and every Holm-adjusted p is 1.000.
  - They are final because a raw p above 5% cannot pass at any Holm step, whatever Coleman, Cox
    and Salaga show.
  - The rows are `H-LIT-ARSCOTT`, `H-LIT-TV` and `H-LIT-BENNETT` in `docs/HYPOTHESES.md`, run by
    `scripts/literature_look.py`. Coleman, Cox and Salaga follow in their own PRs.

Provenance: a six-lane research run on 2026-10-08 (`research/swarm/2026-10-08-literature-step5/`,
gitignored: every claim with its URL, retrieval time and confidence). Citations checked against
Crossref, and the publisher pages where open. Full text was read for Arscott (SSRN working paper),
Salaga & Howley, Cox (open access) and Francisco & Moore (JSEM); the rest from abstracts and
citing papers, as marked.

## The papers

| Paper | What it actually tests | Sample | Result | Full text |
|---|---|---|---|---|
| Arscott, *Market Efficiency and Censoring Bias in College Football Gambling*, J Sports Econ 24(5) 664-689, doi 10.1177/15270025221148991 (online 2023-01-17) | Full-game OVER at the closing total when the expected censoring bias of the total exceeds 1.0 point (the underdog expected to score about 11 or fewer). Team scores are implied from spread + total; no team-total lines are used. | Goldsheet closes; totals 1996-2017, 13,276 games | 691 bets, 55.7%, +6.4% at −110, p 0.079 vs 52.4%; at a 1.75 cut 223 bets, 59.2%, p 0.041; the cut was chosen in-sample; no profitable under | working paper (SSRN 4197428) |
| Coleman, *Team Travel Effects and the College Football Betting Market*, J Sports Econ 18(4) 388-425, doi 10.1177/1527002515574514 (online 2015-03-05) | Point spread: late-season games where the underdog visitor travelled one time zone EAST; the home side outscores the line by about 1.2 points | FBS 2004-2011, 5,093 games | Home favourite vs eastbound visitor, second half of the season: about 55% on about 330 games; beats 50%, not 52.4%; no out-of-sample test | no (abstract + two citing sources) |
| Bennett, *Holdover Bias in the College Football Betting Market*, Atlantic Econ J 47(1) 103-110, doi 10.1007/s11293-019-09611-y | Point spread: fade teams from the previous season's FINAL AP top 10 in their first game | 2008-2016 (citing sources) | 52-31 (62.7%, n 83), about z 1.9 vs break-even; #11-25 efficient | no |
| Cox, *Can we throw out the record books? …*, J Econ Finance 50:47, doi 10.1007/s12197-026-09786-6 (online 2026-09-18) | Point spread in rivalry games (KnowRivalry fan index; the cutoff and the list are unpublished) | Action Network closes 2008-2018, 7,670 games (1,814 rivalry) | Rivalry favourites cover 48.1% vs 50.2% (p 0.105); non-P5 vs non-P5 underdog 55.8% (p 0.079); a favourite that won the last 3 meetings covers 56.6% (n 454), the only result profitable at 5% | yes (open access) |
| Weinbach & Paul, *National television coverage and the behavioural bias of bettors: the American college football totals market*, Int Gambling Stud 9(1) 55-66, doi 10.1080/14459790802656887 | Game totals on national major-network games vs regional vs untelevised | Seasons unconfirmed | Totals set too high on national-network games, so unders win (about 60%, per citing papers); not significant overall | no |
| Paul & Weinbach, *Bettor preferences and market efficiency in football totals markets*, J Econ Finance 29(3) 409-415, doi 10.1007/BF02761585 | Game totals: unders at high totals (52+, 54+, 58+) | College ~1999-2003 and arena football | Beat 50% in-sample | no; already re-tested: Francisco & Moore 2018 (J Econ Finance 42(4) 836-840) found 2003-2015 efficient at every threshold |
| Salaga & Howley, *The impact of weather on betting outcomes and market behaviour in the NCAA football totals market*, Applied Econ Letters 31(8) 779-782, doi 10.1080/13504851.2022.2146651 (online 2022-11-14) | Game totals vs OBSERVED game weather (wind, temperature, humidity, rain) | FBS 2012-2015, outdoor, 3,038 games | Under when wind > 7.78 mph, temperature < 64.81 °F and humidity > 56.8% (the sample's own means): 409 games, 58.9%, p 0.005 vs 52.4%; no out-of-sample test; weather did not predict line moves | yes |
| Borghesi, *The home team weather advantage and biases in the NFL betting market*, J Econ & Business 59(4) 340-354 (2007); *Weather biases in the NFL totals market*, Applied Fin Econ 18(12) 947-953 (2008) | NFL only: 2007 = temperature and the spread; 2008 = totals vs heat, wind and rain, 1984-2004 | NFL | 2008: an out-of-sample weather rule "significantly above" break-even; the rule and rate are unreadable | no |
| Francisco & Moore, *College Football Bettors and the Wisdom of Crowds*, J Sports Econ & Mgmt 9(1) 52-64 (2019, no DOI) | Opening vs closing line accuracy, spreads and totals | D-I 2003-04 to 2015-16; 7,557 moved totals | Unders 50.09% at the opener, 50.14% at the close; the close nearer the final 53.35% of the time | yes |
| Francisco & Moore, *Betting with house money: reverse line movement based strategies in college football totals markets*, J Econ Finance 43(4) 813-827, doi 10.1007/s12197-019-09479-3 | Following reverse line movement, college totals 2005-2016 | — | "In general" not profitable | no |
| Nichols, *The Impact of Visiting Team Travel on Game Outcome and Biases in NFL Betting Markets*, J Sports Econ 15(1) 78-96, doi 10.1177/1527002512440580 | NFL travel vs the closing spread, 1981-2004 | NFL | West-to-east visitors underperform the line; the rule is not profitable out of sample | no |

A later null worth weighing beside Coleman: Tenan, Rezai & Vigotsky (2025, American Journal of
Epidemiology) found no jet-lag effect on away teams against the spread over 2013-2022 (6,245 games).

## The six looks (Tate, 2026-10-08)

All read CFBD's closing lines for 2013-2025, about 750 FBS-vs-FBS regular-season games a season,
as each game's median across CFBD's providers (the provider stored in `games` changes by era, so
the looks never read it). A look's judge is the paper's own measure: the win rate at that close,
pushes dropped, by a one-sided exact binomial test against the 52.38% break-even at −110. Each
look's exact rule, side and n are frozen in its registry row before it runs; the family is
Holm-corrected at 5% with m = 6 fixed (a look not yet run counts as p = 1). Tate's calls of
2026-10-08.

| Look | Rule | Years | Definition status |
|---|---|---|---|
| Arscott | Over at the closing total when the expected censoring bias exceeds 1.0 point | 2018-2025 | Frozen in `H-LIT-ARSCOTT`: the formula and both σ from the working paper; spread-0 games excluded. **Ran 2026-10-09: NOT MET** |
| Coleman | Home favourite vs a visiting underdog that travelled one time zone east, second half of the season | 2013-2025 | **Waiting on the full text**: Tate's call is to freeze Coleman's exact "second half" cutoff and line timing, not a guess |
| National TV | Under on games carried by ABC, CBS, NBC, FOX or ESPN (not ESPN2), from CFBD's media listing | 2013-2025 | Frozen in `H-LIT-TV`: any TV outlet that is exactly one of the five. **Ran 2026-10-09: NOT MET** |
| Cox | Rivalry games = FBS series with a named trophy (Wikipedia's trophy-game list, frozen on the registration date) | 2019-2025 | Which of Cox's rules are tested (rivalry underdog; the favourite that won the last 3 meetings) is fixed in the row |
| Bennett | Fade the previous season's final AP top 10 in its first game | 2018-2025 | Frozen in `H-LIT-BENNETT`: 2017 dropped (the paper's 2008-2016 may name the first-game seasons); the literal first game; top-10 pairs dropped. About 70 games, so it reads closer to a description than a test. **Ran 2026-10-09: NOT MET** (60 graded) |
| Salaga | Under when wind, temperature and humidity pass the paper's cutoffs, outdoor games | 2016-2025 | Observed weather comes from `weather_actuals` (ERA5 hourly + a CFBD cross-check, 2013-2026; `docs/WEATHER.md` §7); the game window is fixed in the row. Uses game-time weather, so a pass does not make it bettable as stated |

## Results (one `study.yml` dispatch each, 2026-10-09 UTC, at `4345320`)

The judge was the median closing number across CFBD's providers, with the win rate tested by a
one-sided exact binomial against 52.38%, pushes dropped. Holm ran at 5% with m = 6.

| Look | Run | Record (pushes) | Win rate | p | Holm-adjusted p | Units at −110 | Verdict |
|---|---|---|---|---|---|---|---|
| Arscott: over when the bias > 1.00 | 37863814444 | 113-106 (3) | 51.6% | 0.618 | 1.000 | −3.27 | NOT MET |
| National TV: under | 37864047692 | 1249-1136 (30) | 52.4% | 0.513 | 1.000 | −0.55 | NOT MET |
| Bennett: fade the prior top 10 | 37864196666 | 28-32 (1) | 46.7% | 0.845 | 1.000 | −6.55 | NOT MET |

**The three verdicts are final.** Holm's loosest step tests at 5% itself, so a raw p above 5%
cannot pass whatever the other looks show. Coleman, Cox and Salaga will be adjusted at m = 6
with these three p-values in the family (`literature_look --holm`).

**Secondary numbers.** These are descriptive only. Nothing is tested on them and no rule is
chosen from them.
- **Arscott:**
  - 3.9% of the 5,693 graded games qualified; the paper reports about 5%.
  - The paper's in-sample 1.75 cut went 32-20-1 (61.5%, n 52).
  - Every graded over went 49.4% (n 5,628).
  - Season rates ran from 40.5% (2023) to 62.5% (2020, n 8).
  - 12 spread-0 games were excluded.
- **National TV:**
  - Under rates by network: ESPN 54.4% (n 971), ABC 51.6% (614), CBS 51.4% (247), FOX 50.2%
    (424), NBC 49.6% (125).
  - Other televised games' unders went 50.6% (n 6,154); games with no media row 49.9% (n 670).
  - National games numbered 164 to 226 a season. Games with no media row fell from 98 (2013) to
    6-20 (2023-25).
- **Bennett:**
  - 80 team-seasons. 13 opened against FCS, and 6 were in top-10 pairs: Georgia-Clemson 2021,
    Notre Dame-Ohio State 2022, Ohio State-Texas 2025.
  - Every poll name matched a schedule name.
  - Faded at home: 37.8% (n 45). Faded away: 73.3% (n 15).

**Provenance.**
- The 2013-16 totals came from `teamrankings` and `numberfire`, two near-identical feeds, so in
  effect one source. `consensus` adds a total from 2017, and books arrive from 2018.
- CFBD calls left after the three runs: 74,182.
- The per-game CSVs are in each run's `study-literature_look` artifact.

## Tracked edge candidates (roadmap v1.3)

- **Team totals.**
  - **The hypothesis:** a book's posted team total can sit off the fair team total implied by the
    consensus spread and total. Zero-censoring of the underdog's score is the mechanism Arscott
    and our own `CENSORING_STUDY` describe.
  - **Next steps:**
    1. `H-MKT-PROBE` on Saturday 2026-10-10 learns which books post team totals and first-half
       team totals.
    2. Tate decides capture.
    3. If captured, a paper arm takes an open slot and is judged under `docs/PROTOCOL_2026.md`.
  - **History:** none exists for team totals; nobody in the knowledge base has it either
    (`docs/KNOWLEDGE.md`).
- **Full-game weather.**
  - **The hypothesis:** totals under-react to bad weather.
  - **Next steps:**
    1. The Salaga look first (history, observed weather).
    2. Then a paper arm built on the decision-safe forecasts we already log (`weather_obs`, 2024+),
       judged under the protocol.
  - **Our own record so far:** first-half weather × style on decision-safe data was a null (R09,
    `docs/WEATHER_STYLE.md`); the full game has never been tested.

## Corrections this makes to earlier docs

- `docs/DATA_STACK_REVIEW_2026-10-05.md` §5 called Arscott's finding censoring on team totals. It is
  the full-game total (overs), so `CENSORING_STUDY` was examining the same family, on the first half.
- `docs/EXTERNAL_REVIEW.md`'s source list now carries the full citations. Its Francisco & Moore
  numbers were already exact.
- The deep-research report (Tate's, not committed; kept beside the research run in
  `research/swarm/2026-10-08-literature-step5/`, gitignored) also has these wrong:
  - Bennett's sample.
  - The direction of Cox's streak result.
  - Coleman's direction.
  - Borghesi 2007's variables.
  - "No college weather study exists".
  - A citation title that belongs to a different Francisco & Moore paper.

## Still unconfirmed

- **Arscott:** numbers come from the 2022 working paper. The published abstract is identical, but
  the tables were not compared.
- **Coleman:** opening or closing lines, the "second half" cutoff, and the game count are unknown
  until the full text is read.
- **Bennett:** the line source and timing, and whether ranked-vs-ranked games were excluded, are
  unknown.
- **Weinbach & Paul 2009:** the seasons, n, exact rate and network definition are unknown.
- **Borghesi 2008:** the rule and win rate are unknown, and so is whether "expected weather" means
  forecasts.
