# Knowledge base — what the CFBD community knows that we did not write down

**Track C of the 2026-10-06 program.** Curated entries from the CollegeFootballData Discord
(read in Tate's own session, channel by channel, at reader pace; raw text in the gitignored
`research/discord/<channel>/`), the Patreon posts (`docs/CFBD_CATALOGUE.md`) and the blog. One
entry per item worth keeping; noise is dropped here, not stored. Tags: `idea` (a new angle),
`challenge` (contradicts something we do), `metric` (explains a number better), `source` (a
data source), `angle` (a betting angle), `ops` (automation or data-timing), `product`,
`marketing`. Each entry says what it changes for us; anything that implies a test becomes a
`docs/HYPOTHESES.md` row PROPOSAL, never a code change. Nothing here changes the champion.

Columns: date · channel · who (Bill / member) · tag · the point · what it changes for us.

## data-and-analytics, 2026-08-01 → 2026-10-04 (sitting #1, 130 messages)

| Date | Who | Tag | The point | For Beat Vegas |
|---|---|---|---|---|
| 2026-08-25 | members (john, Charlemagne, JP+, tan tan) | challenge / source | A member consensus that weather does not move outcomes "unless it's extreme conditions… nearly impossible to quantify beyond enormous error bars"; the counter: "Wind, cold, rain and snow all can impact the TOTALS, you can backtest on CFBD"; a shared essay "NFL Weather Data is Lying to You" (The Spade, Substack) on forecast-vs-actual mismatch. | Matches our record: R06 rejected, R09 null on decision-safe data, the Historical Forecast API tracks actuals (`docs/WEATHER.md`). Keep weather as a decision-safe wind-threshold ARM of the shadow family only; the essay is the external statement of the actuals-vs-forecast trap we fell into. |
| 2026-08-25 | NSRankings | metric | Home-field prior: 2.5 pts FBS; Massey ratings run ~2.2 average/median. | A sanity anchor for any full-game margin work (H-FG rows); not a first-half input. |
| 2026-09-11 → 09-18 | tan tan, Dangerwich, Deke, Matt (POWR), Josh, shox | source / challenge | PFF Pro ($199/yr) ships a data API with snap counts, player grades, routes run, targets; the open question "does player data help a spread model at all, or is it still captured by opponent-adjusted EPA/play?"; one answer: "some descriptive, some signal — weekly routes run and targets spot ROLE CHANGES"; terms forbid redistribution. | The same question `docs/DATA_STACK_REVIEW_2026-10-05.md` §5 parked: PFF only after a free input has moved a paper arm. Role-change detection is the first-half-relevant use (QB/skill availability → H-INJ). No purchase. |
| 2026-09-23 → 09-24 | shox, Matt (POWR) | source | Depth charts: CFBD lacks them; PFF's are live-only; `cfbdepth.com` spot-checks accurate; "Thetwodeep" is tracked weekly with week-over-week changes. | Candidate inputs for H-INJ's availability measure beside `injury_snapshots` (Rotowire). A weekly snapshot of a two-deep would be the leak-free form. |
| 2026-09-14 | wreckhouse24, elydata | metric / idea | Tempo from CFBD's free data: `possession_seconds / plays` from the game box as seconds per play; "directionally it makes sense for the fast/slow teams". | A free cross-check for TeamRankings `team_tempo` (our pace input) and a fallback if that scrape breaks. Descriptive first; a row if it disagrees with TR. |
| 2026-09-04 | Connor, shyguyy | source | Historical TEAM totals exist at The Odds API from 2023; approximate from game total and spread otherwise. | Not a first-half market; noted for the full-game paper arm's context only. |
| 2026-08-11 | Bill | metric | Returning production has no defensive side and will not: "built from previous year's play data and defensive players are very rarely referenced". | Explains why our `returning_*` inputs are offense-only; a defensive returning-production feature is not available anywhere. |
| 2026-08-07 / 08-27 | Bill, Pmann12 | ops | Talent composite lands on the API the day 247 releases it (2026-08-27); "Talent could be a week or so into the season"; returning production is live pre-season. | Our Sunday frame's `talent` column is stale until late August each year; week-1 NaNs are expected, not a bug. |
| 2026-09-29 → 10-04 | CanesFan3O5, Sissipher | challenge | "How do you handle stat adjustments for early weeks — carry over prior season and regress, or a preseason prior?" Unanswered beyond "forecast bench players who now start". | The exact blind spot of weeks 1-4 (`MIN_GAMES_FOR_REAL_MONEY`, H-LEVEL rejected, prior-season anchor tested-null). No one in the community has a published answer either. |
| 2026-09-08 | Bill, Flocho | ops | Weekly poll refresh "job got stuck" and was fixed on request; data settles ~24 h after games. | Any CFBD-derived weekly input needs a freshness probe (the review's `throughWeek` check for CORE); never assume the Monday state is final. |
| 2026-09-03 | Bill | ops | "Everything should be UTC." | Confirms our naive-UTC convention against CFBD timestamps. |
| 2026-08-24 | Justice | ops | Week-0 FBS game ids for 2026 (401856766, 401864494, 401858202, 401864577, 401866408, 401858201, 401864570, 401862693); `/calendar` gives week boundaries, week 1 includes week 0. | Reference for the week-1 rows in the frame. |
| 2026-08-31 | Bill | source | The enriched passing endpoints carry target data; 2025 partial, 2026 onward mostly complete. | Style features someday; two seasons of history by 2027 (as the catalogue says). |

Dropped as noise from this window: CBB roster and recruiting questions, D2/D3 schedules, NHL
APIs, Wikipedia editing, TV channel data, FCS coverage before 2022.

## data-and-analytics, 2025-07-31 → 2026-07-31 (sitting #1b, 1,156 messages, read in full by a research agent; curated here)

The channel's substantive year. Bill's own statements about how CFBD data is made, refreshed and
regenerated are the bulk of what matters; the members' modelling debate of 2025-09-17 → 09-26 is
the single most relevant exchange for our rank-by-gap design.

| Date | Who | Tag | The point | For Beat Vegas |
|---|---|---|---|---|
| 2025-09-26 | Bill | challenge | His 2024 Pick'em table: the three models that beat the market's MAE (12.02 / 12.07 / 12.09 vs 12.18) went 51.3-51.7% ATS; the two best ATS models (54.1%, 53.8%) were LESS accurate than the market. "if I did [bet] I would have a completely different model specialized in identifying which games to bet on." | Accuracy and profit are different objectives. Our "model less accurate than Hard Rock" (MAE 9.03 vs 8.39) and "gap did not sort unders in weeks 4-5" are two separate facts; track both, conflate neither. The hand-built selector (gap rank + price gate) IS our second model; the retired classifier was the ML one. |
| 2025-09-26 | shyguyy | challenge | "backtesting against the vegas line, and then trying to filter on the delta between your y_pred and vegas opens the door to essentially target leak. Because I can filter my way to a great backtest." Also: too far from the line and you are missing something; too close and you cannot escape the juice. | The community states our own rule: 2023-25 is exhausted for rule selection. The gap trade-off behind the per-slate bar, said plainly. |
| 2025-09-17 → 09-26 | Hypercube, PEARatings | metric | Market MAE in the Pick'em: 2024 12.18, 2023 11.94, 2022 12.04, 2021 12.61; "The best full season ever … had an MAE of 11.95." | Nobody beats the full-game market by more than ~0.2 pts over a season. Our first-half deficit is the normal order of things, not a defect to engineer away. |
| 2025-08-28 / 09-18 | Bill | challenge | "/ratings … tracked by season but updated continually through the season"; "Elo is the only thing that is tracked weekly"; "opponent-adjusted metrics by week are only available in the Model Training Pack." | The leak boundary of every in-season input. An SP+ or adjusted stat pulled for a past season is the END-of-season figure; our frame joins season−1 (safe). The Tier-3 weekly CSVs were the only leak-free source for H-WEPA-F (confirmed); pregame Elo is the one weekly, leak-free rating. |
| 2025-09-08 / 10-19 | Bill | metric | "every 25 Elo points implies 1 spread point … plus a 33% regression to the mean value of 1500 over the offseason"; a 538-style MoV Elo ("ND won by a smaller MOV than Elo expected" loses points). | How to read `homePregameElo` if it ever enters a shadow arm (proposal below). |
| 2025-08-31 | Bill | challenge | "No, I don't retrain. And much of the data simply won't be available until then." | CFBD's author trains once on prior seasons, as our champion does; in-season learning is not something he claims either (H-INSEASON-T remains the registered test). |
| 2025-09-14 / 2026-03-21 | Bill | ops | "game box score data tends to update up to a day … which is why I always do a full refresh of the previous week's games on Sunday morning" / "a final resync of everything on Sunday mornings." | Our `grade.yml` 10Z Sunday tick may read pre-resync values; the 16Z tick (or Monday) should be the authoritative finals pass. Measurement first: compare 10Z vs 16Z finals for a few weeks. |
| 2025-08-25 | Bill | challenge | CFBD `/weather`: "pregame forecast for games in the future and actual weather for games that are completed." | The actuals-vs-forecast trap in one table. Never backfill decision-time weather from CFBD; `docs/WEATHER.md` stands. The CFBD weather job also stalled three times in autumn 2025 (09-23, 10-28, 11-03). |
| 2025-08-18 → 10-30 | Bill, saiemgilani, members | ops | Duplicated plays in weeks 2 and 5, OT plays missing from ESPN and overwritten from Fox, ~60 games missing Q4 plays (2024 incl.), ~1% of drives with impossible scores, and "ESPN seems to have flipped a switch in week 9 and now has completely different play by play format." Both consider leaving ESPN as the PBP source. | Every PBP-derived feature we have (`fh_factors`, `mm_havoc`, the running-score half proof) sits on this. Check `fh_*` distributions across the 2025 week-9 seam; add a plays-per-game sanity bound before a Sunday frame trusts a week. lineScores stay primary for the half total. |
| 2025-09-12 / 10-07 | Bill | ops | "clock is not at all reliable"; order by drive_number/play_number; use `/plays` (cleaned) never `/live/plays`. | Verify `etl/first_half.py` keys half boundaries on `period` and reads no clock field. |
| 2025-10-07 | buddavis | ops | "they don't have it all finalized before wednesday morning most weeks" (PBP). | Our Sunday refit reads PBP-derived columns before they settle; measure the Sunday→Wednesday drift once. |
| 2025-11-13 / 11-25 | Bill | ops | Weekly Tier-3 CSVs drop games with no line at posting and are re-posted ("(Update)" files). | The H-WEPA-F table used the base files on purpose; any future weekly snapshot must record which posting it read. |
| 2025-08-26 | Bill | metric | Raw `/stats/game/advanced` exist by week; adjusted ones "are season only." | Any as-of adjusted input is ours to compute (ridge, below) or comes from the weekly CSVs. |
| 2025-08-18 / 10-31 | buddavis, Bill | idea | The ridge-regression opponent-adjustment recipe (blog); Bill: "It's just ridge." | The in-season opponent adjustment we lack is buildable from our own tables (proposal below; the data-stack review's own-adjustment item). |
| 2025-08-17 → 08-21 | p_soich, Swarly30 | source | ESPN's hidden event API carries a pregame FPI matchup win probability ("competitions → predictor"), live from ~Aug 20 each year. | A free, market-free pregame quality prior for a shadow engine (proposal below); same no-custom-header rule as our ESPN scores. |
| 2025-09-26 | Miles | idea | "about 75% of the time my model prediction is within 21 points … if vegas has a line that's more than 21 points from my prediction, there's a good chance I will win that bet." | A bet threshold tied to the model's own error distribution instead of a slate percentile — an alternative to H-PCT worth a paper arm (proposal below). |
| 2025-09-26 / 11-09 | OmegaJack391, Miles, dlshew19 | angle | Members bet openers ("that's when it's easier to identify"); "the close is the scorecard … cashing out is −EV." | Hard Rock's 1H lines barely move, so the opener premise may not transfer; H6 (`WHEN_TO_BET`) on 2026-12-07 is the test; H-STOP-2's line-value clock is already the scorecard. |
| 2026-07-26 | Bill, dharkmeat | challenge | "Personally, I use the Bovada line and then fall back to the consensus line … best to have a lines_provider feature if you are switching providers." Bovada vs TeamRankings: 3,500+ lines, mean difference 2.3%. | Our bought 2023-25 closes and the live Hard Rock line are different books: the honest forms are one book throughout or a provider column. Confirm the bought-close provider is recorded on every `line_real` row. |
| 2025-08-05 / 08-13 | Bill | metric | PPA "is much more valuable at the team level than at the player level"; returning production = last year's PPA share held by this year's roster, transfers included. | Any QB-out adjustment (H-INJ) is team PPA with/without the QB, not a defensive player stat; the exact definition of our `returning_*` inputs. |
| 2025-08-15 / 08-26 | Bill | ops | Neutral-site games sometimes swap home/away upstream; "The issue usually presents itself with betting lines being flipped." | A CFBD-sourced spread needs a neutral-site sign check; our Odds API path is unaffected. |
| 2025-10-28 | Bill | ops | `/stats/season/advanced`: an end-week param EXCLUDES postseason, none INCLUDES it. | State whether bowls are in our prior-season `advanced_frame` and keep it the same every year. |
| 2025-10-09 / 2026-01-03 | Bill | ops | Historical PBP gets repaired after the fact (~60 games since 2020 "from alternative sources"); his shot-location job "failed a few weeks ago and … I didn't notice." | A frame built from an old cache differs from one built now — the frame-fingerprint rule exists for this; CFBD-derived inputs need our own freshness probe (HEALTH-style). |
| 2026-06-16 | Bill | ops | Offseason schedules sync rarely; "distinction between whether data is actually incorrect or just hasn't updated yet" (97% of June kickoffs TBD, placeholder 00:00Z). | The August schedule load must re-pull before week 1 and never read a TBD time as a midnight kickoff. |
| 2025-09-30 | Bill | source | TDs/FGs per game are not aggregated anywhere; lineScores or PBP parsing. | A first-half TD/FG split (field-goal-heavy teams and unders) is a possible style feature; descriptive first. |
| 2026-07-25 | amccaman | idea | The only concrete early-weeks answer in the channel: last year's PFF grades weighted by snap count over the current roster. | Needs PFF ($199); parked by the data-stack rule until a free input moves a paper arm. |
| 2025-09-01 / 10-03 / 09-07 | Bill | product | "No AI code support"; a public GitHub suggestion board; one announcements channel "because otherwise I get 20 people all messaging." | Support boundaries and a public backlog keep a one-person product sustainable — a model for any public picks site. |
| 2025-10-19 | boggo | marketing | "claude.ai suggested I incorporate collegefootballdata.com's API … you've 'arrived' when AI language models start recommending you." | LLM referral is a real acquisition channel for a niche data product. |
| 2025-09-26 / 09-30 | shyguyy, aces_high | marketing | Ed Miller's "The Logic of Sports Betting" recommended with the caveat that markets have moved on; "Most content is not very good. Usually aiming to sell something." | The public betting-content market is distrusted; an honest ledger-first site fills exactly that gap (Track F). |

**Proposed registry rows from this sitting (proposals only; Tate decides whether any is written):**
- **H-FPI-P** — ESPN's pregame FPI matchup win probability as an added input to a paper shadow
  engine (free, market-free, live each August; the ESPN no-custom-header rule applies).
- **H-RIDGE-F** — ridge opponent-adjusted season-to-date first-half scoring from our own tables as
  shadow-engine inputs (the data-stack review's "own adjustment vs WEPA" item, now with the recipe).
- **H-ELO-F** — CFBD pregame Elo (`homePregameElo` / `awayPregameElo`) as the one weekly,
  leak-free in-season quality input, shadow only.
- **H-ERRBAND-P** — a paper arm that bets only when the gap exceeds the model's prior-seasons
  75th-percentile absolute residual, instead of the slate percentile.

**Threads worth reading in full** (raw text in `research/discord/data-and-analytics/`): accuracy
vs profit (2025-09-17 → 09-26); what is as-of and what leaks (2025-08-28, 09-18, 10-28,
2026-07-17); how bad the PBP is (2025-08-18 → 10-30); how Bill runs his own model (2025-08-31);
when a finished week is final (2025-09-14, 2026-03-21); ESPN's hidden FPI (2025-08-17 → 08-28);
betting timing and line-movement sources (2025-11-09, 11-28 → 12-05); switching line providers
(2026-07-26); how to report a data problem (2025-10-27).

Dropped as noise: college basketball, D2/D3/FCS gaps, package and auth help, logos/venues,
NFL draft, recruiting/NIL, roster spellings, one-off score corrections.

## projects-and-showcase, 2025-07-31 → 2026-10-06 (sitting #2, 550 messages, read in full by a research agent; curated here)

The channel where members show what they built. Inventory of 55 projects in
`research/discord/projects-and-showcase/candidates.md` (gitignored). The landscape, in four
sentences: 13 of 55 are betting-oriented and every one prices full-game spreads or moneylines;
the only first-half model mentioned in 14 months "barely breaks even on backtesting" and is not
published; six publish some record and **none states an interval, a stopping rule, a
pre-registered criterion, a book-specific close or a paper-vs-real split**; nobody posted a price
(free-to-build-an-audience is the observable model). The ledger-first, rule-bound posture is
unoccupied — that is the differentiation Track D named, confirmed from the builders' side.

| Date | Who | Tag | The point | For Beat Vegas |
|---|---|---|---|---|
| 2026-08-26 | WagerP393 | challenge | "I do have a 1st half model but it barely breaks even on backtesting." | The only other first-half model in the channel, and it breaks even. Consistent with our honest status; nobody here publishes first-half picks. |
| 2026-08-05 → 08-26 | WagerP393, Matt (POWR) | challenge | A 138-filter trend table (week-1 dogs +21 to +27.5; "Hammer" coaches) that read 59% over five seasons and 50% last year. | Trend mining and its decay: the failure pre-registration exists to prevent. |
| 2026-09-03 | 6P (6ppredictions.com) | product | Slate-percentile confidence tiers (top 10% Strong, bottom 25% Weak), a pre-kickoff freeze of line/pick/edge, visible W/L, "No claim that this is some magic betting system." | A structural twin of our card for full-game spreads, launched the same week. Honest framing is becoming the genre default; our differentiation has to be the registered rule, the price gate and the ledger, not the tone. |
| 2026-07-27 → 08-06 | JP+ (jpplusratings.com), dharkmeat, darren | product / idea | "60% is on selection picks. Across every pick (3,600+ games) it's closer to 52%"; CLV in points (47% positive); picks gated by a sigma model "and several layers of vetos … it may just not have a good read on a certain conference." | The closest published analogue. Publish selection-vs-all side by side (our gap ladder is the all-games half). The learned segment veto is a cheap leak-free paper arm we never tested (proposal below). darren's "CLV in % not points" is a display decision for Tate. |
| 2026-08-26 / 09-08 | Crucialoneshot (cfpadvantage.com) | marketing / challenge | "public model receipts so every prediction can be followed"; "43-8 (84.3%) picking winners through Week 1." | "Receipts" is the public's word for our ledger; a straight-up winner % has no line and no edge content — never let one stand alone on our pages. |
| 2026-03-16 | Criviere (SharpSharks) | marketing / challenge | "Model-filtered picks are hitting 70.5% WR at +37.7% ROI in backtesting." | The backtest-ROI headline the public distrusts; we state prospective records with intervals and never a backtest ROI. Keep it. |
| 2025-08-13 | buddavis | idea / challenge | Preseason power ratings fitted to vig-adjusted season WIN TOTALS and the schedule (iterate until implied win totals match); "Betting Odds probably already incorporate returning production, recruiting, portal." | The one concrete preseason-prior recipe for the weeks 1-4 blind spot (proposal below; Tate decides whether a win-total prior is still "market-blind"). The second sentence is why our 2026 factor screen found nothing: the book already has those inputs. |
| 2025-10-27 | buddavis, Charlemagne | metric | Ridge opponent adjustment "will have the more efficient one ranked better … the higher n for same epa provides a bigger sample size to overcome the penalty term." | H-RIDGE-F (proposed above) has a known tilt toward success rate over explosiveness; note it in the row before the first read. |
| 2026-08-30 → 09-01 | Audible Analysis, saiemgilani | ops | `venues.elevation` is metres; `startTimeTBD` placeholders cross midnight westward (a Saturday reads as Friday); a win-probability garbage-time rule flagged 34.8% then 15.8% of plays across a vendor boundary — "use score points rather than wp because wp is so heavily influenced by spread." | Three cheap checks: elevation unit if ever used; kickoff fields re-pulled before week 1 (any weekday/rest feature on an unplayed slate is wrong on half the rows); grep the PBP ETL and `BV_FEATURE_COLS` for any win-probability field — it smuggles the spread into a market-blind model. |
| 2026-09-08 | Leithal, Crucialoneshot, Flocho, Deke | source | Three builders asked where injuries come from; "The AI agent just checks ESPN for anything reported. No endpoint." | Nobody has a feed; our Rotowire `injury_snapshots` is ahead of the channel. |
| 2026-07-24 | Bill | ops / product | On a paid product built on CFBD data: "No issues … so long as it isn't enabling bulk download of raw data from the API or repackaging into your own API. Attribution is always appreciated!" | The licence boundary in the author's words (cross-reference `docs/LEGAL_MEMO_2026-10.md`): a follow-our-picks product is inside it; a CSV of raw CFBD columns would not be. |
| 2026-05-26 → 07-13 | dupreesdiamond, Flocho, JIMMY CULTURE | product | Team logos: "if you're not making money on the thing don't worry about it"; a paid app read the licences and dropped them as "entirely too cost prohibitive." | Our vendored logos become a decision the day the site charges (Track F). |
| 2026-09-28 | justlikekevin, Bill | marketing | A CFBD directory page of community projects: Bill: "That's a fantastic idea. I love that actually." | A free, credible listing is coming; have a one-line description and the URL ready. |
| 2026-09-30 | jmarcion (BallKnower) | product / idea | "1,000 Ball Bucks a week to bet on real games at real lines … no deposits, no payouts." | Play money at real lines as an engagement shape with no tout exposure — a paper-ledger league around the card is a product idea for Tate. |
| 2026-08-05 | amccaman | angle | "have you thought about incorporating Kelly?" | Kelly needs a calibrated P(under); we have none (`bv_sigma` is one number per slate). Flat units stay by policy. |
| 2026-01-12 | Caesar Analytics, Connor | challenge | "there's no data prior to week 0 and my model uses in season data … not particularly good for the first half" of a season. | The early-season blind spot is universal and unpublished; our no-money-before-two-games rule is the community norm said aloud. |
| 2026-08-19 | Jakee66 | source (tool) | `fbs-cli`: read-only YAML for all 71 CFBD GET routes (`npm i -g @jvorndran/fbs-cli`). | A cheap spot-check tool for research sessions, outside the engine's cache. |
| 2025-10-30 | PEARatings, Steven | product | Results cards: "turn 'Spread' green when you win ATS"; "Hard to read that red." | Colour on the number, not a separate tick column; red-on-dark fails — our "if it isn't obvious, cut it" rule for the ledger. |

**Proposed registry rows from this sitting (proposals only):**
- **H-SEGVETO-P** — a paper arm identical to the champion except that it refuses segments
  (conference pairings or spread buckets) where the champion's PRIOR-season absolute residual
  against the close was largest. Leak-free, cheap; tests a selector the 2026 factor screen did not.
- **H-MKTPRIOR-F** — a preseason team-strength prior fitted to vig-adjusted season win totals and
  the schedule, as a shadow-engine input for weeks 1-4. Decision first: a win-total prior is a
  DIFFERENT market from the game's total, captured in August — does it count as market-blind?

## pick-em, development, cfbfastr-questions, cfb-chat (sittings #3-#6, 1,189 messages, read in full by a research agent; curated here)

**How CFBD runs a public model benchmark (pick-em, 650 messages since 2024-10).** Submit a
predicted final margin per game (web form, CSV `id,home,away,predicted`, or an API with a
permanent per-user key); the universe is "every game for which there is a spread" and games
appear as spreads post, often on game day; picks are editable until kickoff; the leaderboard
counts FBS-vs-FBS only and a model must pick **≥ 70% of the available games to qualify**;
corrections preserve a user's logged pick ("I've flipped them while maintaining existing picks");
Bill enters his own model from week 5 and posts weekly top-5 tables to X/Bluesky; participation
(30+ picks in week 5) went 18 → 36 → 39 → 37 → **65** from 2021 to 2025. Totals were asked for once
(2025-09-26) and declined: "No imminent plans … a substantial rewrite." Which spread grades a pick
(submission-time or kickoff) was asked and never answered.

| Date | Who | Tag | The point | For Beat Vegas |
|---|---|---|---|---|
| 2026-01-02 | dharkmeat (pick-em) | source / metric | "146,508 picks from 264 unique users plus one ever-present Vegas Line" — a five-season per-user-week table of Straight Up / ATS / MAE / MSE / Bias (`cfb_leaders.csv`, a Discord attachment only). In-season 2025 the field self-reported ~75-80% straight up and 48-56% ATS; "my model went 20-30-1 ATS, but the residuals were better than ever." | The only public distribution of what hundreds of models achieve against the full-game spread. Worth asking for: it calibrates "how bad is MAE 9.03 vs 8.39" and shows the field's ATS ceiling. The accuracy-vs-profit split, live, from a participant. |
| 2025-08-06 | Bill (pick-em) | challenge / idea | His early-season feature list: "talent … recruiting composite class ratings, portal composite class ratings, **spread**, pregame Elo ratings, returning production data (accounts for transfers), head coach experience" and 3/5-year rating averages; Elo "usually scores pretty highly in my SHAP analysis … carries over between seasons and has historical inertia." | Bill's model is NOT market-blind (the spread is an input); ours is by design. The rest is our weeks 1-4 list: Elo (H-ELO-F proposed), returning production (have), talent (late), coach experience and multi-year averages (untested). Portal class ratings are not in the API. |
| 2025-10-15 | nickseevers, john (pick-em) | challenge / idea | "it is obsessed with predicting the score to be almost exactly the same as the over/under"; "predict just one thing, either margin or win probability, then convert … with a very simple scaler." | A totals model that tracks the market carries no gap information — the failure a market-blind model avoids by construction; never "fix" level by feeding the market back in. A gap→P(under) scaler fitted on prior seasons' real closes is the leak-free way to the calibrated probability `BREAK_EVEN_EV` waits on (proposal below). |
| 2025-10-04 | spaceman, PEARatings (pick-em) | challenge / idea | "If your model is 8pts off market … probably need to caution yourself"; PEARatings' pipeline "raw -> opp adj -> ewma." | The spread-side statement of "too far from the line and you are missing something": a very large 1H gap is a flag for a stale or alternate line or a missing input, not more edge (our weekly hit rate by gap band measures it). An EWMA recency weight is a second knob for the H-RIDGE-F proposal. |
| 2025-11-30 | Dave Swain (pick-em) | challenge | "Only bet games where model showed edge 50 picks: 88% straight up (44-6), 76% ATS (38-11-1)." | The unregistered selection claim in its purest form: no criterion stated in advance, no line source, no interval. The genre norm the registry exists to be different from (with 6P's and CFP Advantage's receipts above). |
| 2026-09-08 / 2026-08-29 | Bill (cfb-chat, pick-em) | product | The ≥ 70% coverage floor; corrections that never rewrite a logged pick. | Two public-ledger rules worth stating on Results: a coverage rule ("every card BET placed and nothing else") and that no logged ticket is ever rewritten if a game row or line is corrected. |
| 2025-08-18 | Bill (cfbfastr-questions) | product / legal | "Redistribution of raw CFBD API data, whether CSV, RDS, Parquet, or any other format, is not allowed … Hosting or publishing your own derived or augmented metrics is fine." cfbfastR was brought inside the terms that night (attribution + live API calls). | The sharpest statement of the licence line: our `/api/bets` CSV and any public download must carry OUR numbers, never raw CFBD fields verbatim. Attribution asset: `cdn.collegefootballdata.com/cfbd-watermark.png` (and `-dark`), offered 2026-09-10 — How it works should carry one. Cross-reference `docs/LEGAL_MEMO_2026-10.md`. |
| 2025-08-29 / 2026-03-22 / 2026-08-19 | Bill (development) | ops | A 429 is ambiguous: the burst limit "50 requests in a 10 second period … time out … 10 minutes" (Cloudflare error 1015, exponential backoff — "the more calls you made while in time out, the longer the wait") versus the monthly quota. Safe pace: "making requests synchronous … a short sleep (e.g. 500 ms)". | `CFBDQuotaExceeded` is raised on the spot; check the body for `error_code 1015` before declaring the quota gone, and pin a ~0.5 s sleep in any sequential backfill. |
| 2025-07-05 / 2025-08-25 | Bill (development) | ops | Adjusted season stats "don't go up until after 4 or 5 weeks … then updated weekly"; the Tier-3 weekly CSVs "starting week 5." | No weekly adjusted data exists for weeks 1-4 of any season; bounds the n of any in-season adjusted input (H-WEPA-F's 561 games started at week 5 for this reason). |
| 2025-08-26 | Bill (development) | ops | "certain things aren't tracked until 2016 so havoc calcs differ wildly between 2015 and 2016." | A 2016 training floor for any havoc-family feature (`mm_havoc`); record it so a future history purchase cannot cross it. |
| 2025-08-07 | Bill (development) | ops | `lineScores` "is just an ordered array with a length of 4 for normal completed games. There will be additional elements added for each OT period." | The exact contract behind `etl/first_half.py`'s half proof: elements 0+1 are the half, and OT appends rather than folding into Q4. |
| 2025-09-24 / 2025-10-21 / 2025-12-15 | Bill, Vik (development) | ops | `/calendar`: "Week 1 is indeed extended to include week 0"; CFBD week ends run a day past ESPN's; "CFP and Bowl games are both postseason week 1"; 2025's week 16 (Army-Navy) overlapped postseason week 1 and broke `/scoreboard`. | Date-joins of ESPN ids to CFBD weeks go through `/calendar`, never ESPN's week; the week loop must accept 16 and the postseason filter must not drop it. |
| 2025-11-10 → 2026-09-22 | saiemgilani, members (cfbfastr-questions) | ops | ESPN's week-9 2025 provider switch from the parser's side: play text changed format ("(06:45) #92 B.Thorson"), rusher/receiver names "not reliable from then", unfixed for ten months. | Any `fh_*` or havoc feature parsed from `play_text` or player fields must be checked across week 9 of 2025; `play_type`-based features are safer. |
| 2026-04-16 | Bill (development) | ops | "upgrade your membership and then downgrade before next month's renewal … validate that the newer benefits and call limit is applied before downgrading." | How to buy one month of a higher tier for a one-off history pull — relevant to the Nov 6 Tier decision. |
| 2025-09-27 / 09-28 | Bill, PEARatings (pick-em) | marketing | Participation nearly doubled in 2025; "Twitter still has a lot more engagement"; "Post easy to read visuals, and engage with people"; Bill polls newcomers on how they found the contest. | Hobby-model builders are a real, growing segment; X plus readable visuals is the distribution the room looks up to; ask arrivals how they found us once a sign-up exists (Track F). |

**Proposed registry rows from these sittings (proposals only):**
- **H-PCAL-P** — a gap→P(under) calibration fitted on prior seasons' REAL closes (never on
  `bv_sigma`), reported beside each paper pick; a pass licenses nothing but makes `BREAK_EVEN_EV`
  meaningful.
- **H-DESERVED-F** — a PBP-based "deserved first-half points" label as a shadow-engine target;
  contingent on the week-9 seam check.
- Notes: add an EWMA recency arm to H-RIDGE-F; H-ELO-F must name which Elo (per-game pregame vs
  the rankings table).

**Ops hygiene implied (measurement or hygiene, no code change proposed here):** distinguish
Cloudflare 1015 from the monthly 429; a 2016 havoc floor; week 16 and the postseason overlap;
`/calendar` for date joins; PBP features across the 2025 week-9 seam; the CFBD watermark on How it
works and no raw CFBD fields in any public CSV; ask dharkmeat for `cfb_leaders.csv`.
