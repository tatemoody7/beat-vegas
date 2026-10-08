# Beat Vegas — data stack review (2026-10-05)

Written Monday 2026-10-05 from a four-lane research swarm (run dir
`research/swarm/2026-10-05-data-stack/`, gitignored: `lanes/cfbd-tiers.md` 26 claims,
`lanes/odds-pricing.md` 47, `lanes/modeling-data.md` 51, `lanes/codebase.md` 353 lines of
`file:line` pointers). Read-only: nothing here changed a gate, a model constant, a plan or a
row. Every "buy / don't buy" below is a recommendation with its evidence; the decisions are
listed at the end for Tate. Cost of the research itself: 1 Odds API credit, 4 CFBD calls.

**Recommendation first.** Keep The Odds API on the 20K plan ($30); nothing else sells Hard
Rock's first-half totals, and the free 500-credit tier would carry only a stripped-down,
Friday-only system. Buy CFBD **Tier 1 at $1**, not Tier 2 or 3: the only Patreon-gated data
with a plausible use for us is `/wepa/team/season` (CFBD's opponent-adjusted in-season
efficiency), and every other endpoint we could want is free. The Tier 3 "weekly model
training data" is a full-game, market-aware CSV built for CFBD's own notebook models; nothing
in it is first-half, and everything in it except WEPA is reconstructible from free endpoints.
Do not buy public-betting splits: no one publishes first-half splits, and the evidence for
fading the public on CFB totals is negative. The data we are missing is mostly free and
already partly on disk: in-season opponent-adjusted quality (we run last season's SP+/PPA all
year), decision-safe weather (captured, read by nothing), explosiveness / special teams / SOS
(fetched, discarded), kickoff hour and travel direction. The literature's plainest lesson is
structural: no published market-blind CFB totals model beats the close; the ones that show
anything show it against the opener. That points at bet timing and a market-aware shadow
engine, not at a new data vendor.

## 1. What the system consumes today (provenance: `lanes/codebase.md`)

| Source | Plan | What we pull | Feeds | Cost |
|---|---|---|---|---|
| The Odds API | 100K ($59) until Oct 6, then 20K ($30) | per-event `totals_h1` from exactly ten books (1 credit/event); bulk full-game totals+spreads (4-6 credits); one-time 2023-25 history (~44.9K credits, Sep 6-8) | the only 1H line in the system: slate bar, kill price, live price check, close capture, CLV, H-STOP-2's line-value clock, H-MOVE | $30/mo |
| CFBD | Academic key (3,000 calls/mo; `/info` read 2026-10-05: 105 used, resets Nov 1) | `/games`, `/lines` (full-game opener reference), `/plays`, `/ratings/sp`, `/stats/season/advanced`, `/player/returning`, `/talent`, `/roster`, `/venues`, `/teams` | schedule, finals, 14 prior-season quality inputs, the 1H play-by-play rates (removed by B-SERVE) | $0 |
| TeamRankings | free pages | two tempo pages | `combined_sec_play`, `combined_plays` — the one input with any record | $0 |
| Open-Meteo | free | ERA5 history + Previous Runs (decision-safe) | the champion reads the clock-shifted legacy table; `weather_obs` is read by nothing | $0 |
| Rotowire | free page | injuries | the `qb_out` blocker only; never a feature; snapshots start with PR #269 | $0 |
| ESPN | hidden API | scores fallback; full-game DraftKings odds exist but no first-half line | grading | $0 |
| Neon / Vercel / GitHub Actions | Launch / Hobby / private repo | — | infra | ~$3 + $0 + ~$7 overage |

Monthly after Oct 6: ~$40 (Odds $30, Neon ~$3, Actions ~$7), plus $1 if CFBD Tier 1 is bought.

**Odds API usage, measured, not estimated.** Dashboard 2026-10-04: 326 credits used Oct 1-4,
which covers a Thursday, Friday and Saturday card (~55 each, `--hr-universe --days-ahead 6`)
plus the 14 hourly Saturday close ticks (each polls only games kicking off inside 120 min, so
single digits per tick). A full week is ~400-450 credits; September's live use read 1,000-1,500
with the close backup firing 3 of 18 slots. Call it **≤2,000 credits a month**. The 20K plan
carries that ten times over; the 100K plan was only ever needed for the history purchase. The
pricing lane's "~4,500/mo" was a worst case that assumed every close tick polls every event;
the measured number wins.

## 2. The Odds API — the six questions

- **What we use it for.** Hard Rock Bet's first-half total and price on every FBS game, plus
  the same market at nine comparison books in the same 1-credit call; the full-game slate on
  Sunday for the opener reference and `games.spread`; the 2023-25 history, bought once.
- **What depends on it.** Everything that touches money. Remove it and there is no line, no
  bar, no `PRICE` check, no CLV and no line-value clock (`odds.py:245-264`, `card.py:491-499`,
  `lineCheck.ts:252-281`). Drop the nine comparison books and `fair_under` / `ev` / the kill
  price are all None and nothing can be a BET (`card.py:528-566`); they cost nothing because
  ten keys bill as one region.
- **Are we using all we pay for?** No, by design: the 100K plan was sized for the history
  purchase and ends Oct 6. On 20K we would use ~10%. There is no tier between free 500 and 20K
  (pricing page re-read 2026-10-05: 500 free / 20K $30 / 100K $59 / 5M $119 / 15M $249, hard
  cap, no overage).
- **Do we need $30?** For the system as built, yes. The free 500 credits buy about eight card
  sweeps a month. A **Friday-only** variant (one `fri_pm` sweep ~55 + `sat_am` ~55 + closes on
  only the ≤5 real tickets ~15) lands at ~125 a week, just over 500 a month; drop `sat_am` and it
  fits at ~300. What that variant loses: the Tuesday/Thursday builds and their paper windows,
  the H-TIMING arm, the close on every paper and challenger pick (every paper clock goes dark;
  H-STOP-2's own line-value clock survives because it reads real tickets), H-MOVE's data, and
  the alternate-rung drift measurement. It keeps real money fully intact. **Option, not a
  recommendation**; see Decisions.
- **Cheaper tier or alternative?** None found that carries Hard Rock NCAAF 1H totals at ≤$30.
  OpticOdds and Unabated are sales-gated enterprise; SportsGameOdds $99+/mo (1H partials, Hard
  Rock not named); odds-api.io £49 for two books, no NCAAF in its docs; SharpAPI $79; OddsBlaze
  $299+; SportsDataIO personal odds packages priced on request with a UCL-only trial; OddsPapi
  free is 250 requests a month; Pinnacle's public API closed 2025-07-23 (Pinnacle is still an
  `eu` key inside The Odds API at no extra cost, and posts 1H on 2 of 52 Hard Rock games).
  Kalshi lists a free 1H-total ladder per game (`KXNCAAF1HTOTAL`) at ~5 contracts of volume
  and 0.01/0.97 quotes: not a reference.
- **Could CFBD or anything free replace it?** No. CFBD `/lines` is free at every tier and
  carries DraftKings on every 2026 game and Bovada on about half, but only full-game
  spread / total / moneyline with openers, **no first-half line, no timestamps, no price on the
  total** (the service's SQL selects nothing more). ESPN's hidden odds endpoints are DraftKings
  full-game only. Sportsbook Reviews Online's archive domain is dead. Our bought 2023-25 1H
  closes are the only Hard Rock first-half history anyone has.
- Two things learned on the way: `alternate_totals_h1` returned nothing for Hard Rock five
  days out and was **not billed**, so the alternate-rung question (open item) costs one credit
  per probe and should be probed on a Saturday inside 2 h; and `hardrockbet_fl` / `_az` / `_oh`
  exist as separate `us2` keys that returned nothing on the probed event — we have no spare slot
  for them anyway.

## 3. CFBD — what each tier actually buys (provenance: `lanes/cfbd-tiers.md`)

Gating as enforced in the open-source API (`cfb-api-v2/src/config/middleware/patreon.ts`):

| Tier | Price | Calls | Gated data |
|---|---|---|---|
| Free / Academic | $0 | 1,000 / 3,000 (ours) | everything not listed below, including `/lines`, all `/ppa/*`, `/stats/*/advanced`, havoc, `/metrics/wp*`, `/ratings/sp|fpi|elo|srs|core`, `/player/returning|usage`, `/talent`, `/drives`, `/plays`, the new `/passing/*` and `/rushing/*`, `/coaches/*`, free game previews |
| Tier 1 | $1 | 5,000 | `/wepa/team/season` + three `/wepa/players/*` (opponent-adjusted EPA, success, rushing, explosiveness; proprietary, unpublished method), `/games/{id}/preview/adjusted`, `/games/weather`, `/scoreboard`; ad-free site, PNG chart export |
| Tier 2 | $5 | 30,000 | `/live/plays` only; exporter bookmarks / saved queries; Discord |
| Tier 3 | $10 | 75,000 | GraphQL (Hasura: joins, field selection, WebSocket subscriptions — no dataset REST lacks); **weekly model training CSV** from week 5 through the CFP |
| Tiers 4-6 | $15-30 | 125K-500K | calls only |

- **The weekly training data (Tier 3).** A CSV of the upcoming slate in the Gumroad Model
  Training Pack's layout so the pack's notebooks (random forest, XGBoost, fastai) can score it:
  one row per FBS game, opponent-adjusted EPA / success / explosiveness / line yards / havoc /
  points-per-opportunity / field position, pre-game Elo, talent, and the **Vegas closing
  spread** (86 fields in the 2026 pack; the locked posts could not be read, so the weekly
  columns are inferred from the pack's info sheet). It is full-game and market-aware. Nothing
  first-half. Nothing says it is the frame behind CFBD's own picks. For us it would be a
  convenience copy of features we can compute from free endpoints, plus WEPA, which Tier 1
  already serves. **Not worth $10 for this system.**
- **"Data Packs"** is a link to Gumroad: Starter Pack $49, Model Training Pack $69 (2016-24,
  2020 excluded, 84 features/row, week 5+), bundle $98, AI Builder Pack $49-69. One-time,
  personal-use licence, no API. Same verdict: reconstructible, full-game, market-aware.
- **Weather (Tier 1).** One row per game from one `gameWeather` table, 2001-present,
  "supplemental, not every game": temperature, dew point, humidity, precipitation, snowfall,
  wind direction and speed, pressure, condition. **No forecast-issued or lead-time column**, so
  it cannot distinguish the forecast we could have acted on from the observation; it does not
  replace our Open-Meteo Previous-Runs rows (`docs/WEATHER.md` §2). Provider unnamed anywhere.
- **Site charts** expose nothing the API lacks (Team Metrics Explorer → `/wepa`, Passing Trends
  → `/passing`, Predicted Points → `/ppa/predicted`, WP chart → `/metrics/wp`).
- **CFBD's own model** is market-aware (714-variable LightGBM/NGBoost with the pregame spread
  and win probability as inputs, RMSE 15.72 on margin, 2020 write-up). CORE (Aug 2026) is an
  efficiency rating that its author says is "not a forecast or betting system".
- **Correction to `docs/SYSTEM_REVIEW_2026-10-04.md` §7**: `/coaches`, `/drives` and
  `/games/teams` are free, not Tier 2. The review's Tier 2 recommendation was about call
  headroom, and Tier 1's 5,000 covers our ~20 calls a day with room for the coach / drive /
  box-score pulls it named.

## 4. Public betting data — don't buy (provenance: `lanes/odds-pricing.md` §4)

- Who sells it: Action Network PRO $19.99/mo ($119.99/yr) for money %; DraftKings Network and
  VSiN publish DraftKings tickets / handle free. All of it is **full-game only**: Action's
  scoreboard JSON ignores `period=firsthalf`; no source found publishes first-half splits.
  Covers "consensus" is contest picks, not book data. Bet Labs' status is unconfirmed (site up,
  "© 2019", no shutdown notice).
- Evidence on totals is negative: VSiN's 2022-25 DraftKings-feed study has the majority-handle
  side at 51.2% on CFB totals (fading it loses); Paul & Weinbach find the contrarian effect in
  spreads, not totals. The system review already set the rule: no purchase until H-MOVE shows
  the move carries something the books' own numbers do not (`docs/HYPOTHESES.md` H-MOVE).

## 5. What serious models use that we do not (provenance: `lanes/modeling-data.md`)

What the literature says first: **no published market-blind CFB totals model beats the
close.** The Power Rank's own record is 55.3% against openers but 51-53% against the close
across four seasons, and the market moved ~3.6 pts toward its opener disagreement 95.6% of the
time; Farinella & Moffett (2016) found no profitable CFB totals rule over ten seasons; Kelly &
Chen show the NFL high-total under edge died after 2010. The one recent peer-reviewed
totals-family inefficiency (Arscott 2023) is censoring in the **full-game** total: overs at
the close when the underdog is expected to score little, 1996-2017 (corrected 2026-10-08 from
"team totals" after reading the paper, `docs/LITERATURE.md`); our `CENSORING_STUDY` examined
the same mechanism on first-half totals and found it priced. Our MAE gap (9.03 vs 8.39) is the
expected state of a market-blind model, not a data defect.

Items we lack, ranked by plausibility and cost:

| Item | We have it? | Cost | Why it matters |
|---|---|---|---|
| In-season opponent-adjusted efficiency (WEPA, or our own ridge/SRS adjustment of `/ppa` + `/stats/game/advanced`) | No: SP+, PPA, talent are last season's all year (`features.py:466-473`) | $1 (WEPA) or $0 (own) | the model's quality inputs go stale by week 4; this is the "SOS answer" the review named |
| Decision-safe weather, wind as a threshold (unders 58% at 15+ mph, 64% at 20+, two sources) | Captured in `weather_obs`, read by nothing; champion reads the clock-shifted table | $0 | the best-documented exogenous under signal; the data is already paid for |
| Explosiveness, SP+ special teams and SOS, opener flags | Fetched, discarded (`season_stats.py:186-224`) | $0 | already in H-SHADOW-F |
| Kickoff hour and travel direction | `away_tz_shift` live (rho −0.11, best in the screen); kickoff hour computed, weak in the Sep-01 swarm | $0 | peer-reviewed: afternoon away teams allow ~5% more points; eastward travel +39% INTs |
| Elo, FPI, CORE ratings | Not pulled | $0 (free endpoints) | cheap second opinions on team strength; CORE is 2016+ |
| Coaches (tenure, cover residual by coach) | Not pulled | $0 (free since 2026-07-30) | H-COACH as spec'd, no tier needed |
| Opener-vs-close as the model's benchmark | Captured since 2026 (`cards`, `odds_snapshots`), reported for real tickets only | $0 | where a market-blind edge shows up, if anywhere |
| PFF team grades (QB/OL quality beyond SP+) | No | $199.99/yr (PFF Pro, the only PFF plan with an API) | plausible incremental signal, untested on 1H totals |
| Referee crews | No | not sold to individuals (Football Zebras covers bowls/CFP only; SportSource / Sportradar are institutional) | dead end |
| Public splits | No | $20/mo, full-game only | negative evidence, see §4 |
| 1H/FG scoring-share table by spread and pace | **Yes** — the 2026-09-01 swarm built it from our closes (share 0.51, step at 21+); no public source has one | $0 | our data is the asset; nothing to buy |

## 6. ROI tiers

**1. Free data we should definitely use**
- `weather_obs` (decision-safe Open-Meteo Previous Runs) instead of the legacy table, with a
  wind threshold — in the shadow arm first (H-SHADOW-F nulls weather today; a successor arm
  turns the repaired rows on). Activation is its own registered gate (`docs/WEATHER.md`).
- The already-fetched CFBD columns: explosiveness, defensive success, SP+ special teams and SOS
  (H-SHADOW-F, zero calls).
- In-season opponent adjustment computed ourselves from free `/ppa/games` +
  `/stats/game/advanced` (ridge or the SRS-style iteration CFBD's Sep-2026 tutorial walks
  through). Candidate inputs for H-INSEASON-T's successor; ~2 calls a week.
- `/ratings/elo`, `/ratings/fpi`, `/ratings/core` (1 call each per week), `/coaches/*` (one
  call a season) for H-COACH.
- Opener-vs-close reporting for every build's BET list, paper included (`when_to_bet_study`
  already has the rows; H-TIMING is registered).
- Keep: TeamRankings pace, Rotowire injuries (now snapshotted), ESPN finals fallback.

**2. Low-cost, probably worth paying**
- **CFBD Tier 1, $1/mo**: 5,000 calls (headroom over the Academic 3,000 that killed grading
  once) and `/wepa/team/season`. One call a week. Judge WEPA against our own adjustment inside
  the same shadow arm; if ours matches, the $1 is only headroom and ad-free.
- **The Odds API 20K, $30/mo**: the floor and the only source. Not optional for the system as
  designed.

**3. More expensive, could help later, not now**
- PFF Pro, $199.99/yr: the one paid feed with an API and plausible incremental signal. Earn it
  only after the free inputs above have been measured in a paper arm; without frozen
  decision-time vectors (PR #269, first rows Tuesday) we could not even tell whether it helped.
- CFBD Tier 3, $10/mo: only if we want the weekly CSV as a reference frame or GraphQL
  subscriptions for a live product. Neither is on the roadmap.
- SportsDataIO / Unabated / OpticOdds: enterprise pricing, only relevant if the product ever
  needs multi-book 1H coverage beyond ten keys.

**4. Probably not worth the money**
- Public betting splits (Action PRO $20/mo): full-game only, negative evidence on totals.
- CFBD Tier 2 ($5): buys live play-by-play we do not use; the headroom argument is met by Tier 1.
- Gumroad data packs ($49-98): reconstructible, full-game, market-aware, one-time, no API.
- Any Odds API plan above 20K; any second odds vendor; referee data; Pinnacle resellers
  ($99/mo for a book that posts 1H on 4% of our games).

## 7. Critique: is this the best approach, and what would I change

**What is right and should stay.** The discipline is the asset: pre-registered rows, paper
arms beside an untouched champion, the price gate (the one filter with a record), the
alternate-line filter, the close capture with its Vercel backup, flat units, the ledger with
price provenance, the stopping rule as the only stop. The infrastructure is right-sized:
GitHub Actions + Neon + Vercel at ~$40 a month is cheaper than any vendor's smallest plan and
every job has a health contract. Nothing in this review argues for a new vendor.

**What is structurally weak, in order.**
1. **The model competes with the close using last season's quality numbers.** SP+, PPA,
   talent and returning production are joined at season+1 and never refreshed; by week 6 the
   market has five weeks of information the model lacks. H-INSEASON-T (in-season training
   rows) and the in-season adjustment above are the two cheapest fixes and both are free.
2. **It benchmarks against the wrong line.** A market-blind number has a documented chance
   against the opener and none against the close. Hard Rock posts 1H on 31% of games Tuesday
   and 97% Saturday; Tate bets off the first BET-rated build, which is the opener-side policy,
   and the Tuesday tickets' line value has never been negative even though they went 1-4. The
   decisive measurement is H-TIMING (paired line value by build), not a new input. If it reads
   the way the literature predicts, the system's product is "our number against Hard Rock's
   first post", and the Friday/Saturday builds become the close-capture and price-check jobs
   they already mostly are.
3. **The 1H-specific signal was cut, not fixed.** The 57 play-by-play rates B-SERVE removed are
   the only inputs that were about first halves; they were NaN at serving because the lag
   table was never built. A leak-free `fh_team_game` lag table (last week's values) returns
   them. That is a pipeline change, free, and already named in the review as "deferred".
4. **Weather is in the champion with wrong data and out of the shadow with right data.** Fix
   the read before judging the factor; the threshold form is what the literature measured.
5. **A market-aware shadow has been tried once and shelved.** R03 (residual engine, trained on
   2023-24 only, 568 games) read 9.01 against the close's 8.73 and the incumbent's 9.23.
   That is a better-than-champion result from a half-sized training set, and it has never been
   re-run on 2023-25 with the bought closes or as a live paper arm. The literature's route to
   the close runs through market-aware models; a `bv_residual` shadow beside `bv_shadow_f` and
   `bv_inseason_t` costs zero credits and one registry row.
6. **The research cadence is right; the research target has been level, not signal.** Four
   registered rows fixed bias; none asked which input carries information until the factor
   screen on 2026-10-04. PR #269's frozen vectors are the precondition; every item above
   should be measured on decision-time values from week 6 on, not on recomputed frames.

**If rebuilding today**, the pipeline would be the same shape (capture → enrich → score →
grade on Actions, Neon, a thin site) with three differences: in-season opponent-adjusted
efficiency refreshed every Sunday as the model's quality inputs; a weekly `fh_team_game` lag
table so first-half rates serve without skew; and two scoring engines from day one, one
market-blind (for the opener) and one market-aware (for the close), each judged on its own
clock. The weekly workflow would keep four builds but label them by job: Tuesday is the
opener read, Friday and Saturday are the price and close jobs. I would remove the dormant
DraftKings poller, the proxy multiplier and the classifier fit in `backtest/engine.py` in the
offseason, and I would not add a single paid feed until a free input has moved paired MAE or
line value in a paper arm.

## 8. Evidence quality and what is unconfirmed

Every claim above is in a lane file with a URL (or `file:line`) and a confidence tag; primary
sources (the CFBD API source code and OpenAPI spec, The Odds API pricing page, live probes,
peer-reviewed papers) outrank search snippets. **Unconfirmed / needs a human check:** the
exact columns of the locked Tier 3 weekly CSV (inferred from the pack's info sheet); CFBD's
weather provider; whether CFBD's spread model changed since 2020; prices for TeamRankings
premium, OddsJam/OpticOdds, Unabated, SportsDataIO (JS-rendered pages refused automated
reads); Bet Labs' status; Sportsbook Reviews Online's archive layout; whether
`hardrockbet_fl` ever serves `totals_h1` (one probe, one credit, on a Saturday).

## 9. Decisions for Tate (nothing above has been acted on)

1. The Odds API on Oct 6: **(a)** 20K at $30 (recommended; system unchanged), or **(b)** the
   free 500 with the Friday-only variant in §2 (real money intact, every paper clock but
   H-STOP-2's goes dark). Either way the new subscription issues a new key: `gh secret set
   ODDS_API_KEY`, local `config.yaml`, then a dry `lines_watch.yml` dispatch.
2. CFBD: **(a)** Tier 1 at $1 (recommended), **(b)** Tier 2 at $5 as `docs/OPS_ACCOUNTS.md`
   item 2 still says, **(c)** stay on the Academic 3,000. `OPS_ACCOUNTS.md` item 2 is updated
   once chosen.
3. Register a `bv_residual` shadow engine beside PR6's two (one registry row; R03 is the
   prior), or leave market-aware modelling shelved.
4. Register the free-input arms for H-SHADOW-F's successor: decision-safe weather with a wind
   threshold, in-season opponent adjustment (own vs WEPA), Elo / FPI / CORE.
5. Schedule the `fh_team_game` lag table (returns the 57 first-half rates) for the offseason
   or for week 8+.
6. PFF Pro: defer until a free input has moved a paper arm, or decline outright.
7. Whether this document joins `CLAUDE.md`'s read-first list and `HISTORY.md` as a dated
   episode (a docs PR), or stays a research note.
