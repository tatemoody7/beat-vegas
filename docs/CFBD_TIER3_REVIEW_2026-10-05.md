# CFBD Tier 3 — what it gives Beat Vegas (2026-10-05)

Written Monday 2026-10-05 after Tate bought Patreon Tier 3 ($10/mo). Four lanes, all in
`research/swarm/2026-10-05-cfbd-tier3/` (gitignored): `lanes/api-inventory.md` (52 live probes,
raw JSON in `probes/`), `lanes/docs-repos.md` (27 claims from the API source, docs site, blog,
info sheets), `lanes/discord.md` (79 lines: announcements Oct 2025 → today, six server-wide
searches, seven threads read in full), and this morning's `lanes/cfbd-tiers.md` from the data
stack review. **Provenance:** key `/info` before 13:59Z = Academic/3,000; Tier 3 reached the
key at 14:10Z (75,000/mo, all five feature flags true); 57 CFBD calls spent in total (16 on the
Tier 3 counter), 74,984 remaining at writing. **The week-6 CSV was supplied by Tate and measured** (`lanes/training-csv.md`); patreon.com
itself is refused by both browsers this app provides, so the locked posts' body text is the
one thing unread. Nothing here changed a gate, a model constant, a registry row or a ledger
row; every "test" below is a proposed `docs/HYPOTHESES.md` row for Tate to accept.

**Recommendation first.** Tier 3 is the wrong tier for this system, but a harmless one: at
$10 it buys 75,000 calls we cannot use (measured ~45 a day), GraphQL we do not need, and a
weekly full-game, market-aware CSV with nothing first-half in it. Everything of value is
**Tier 1** data: `/wepa/team/season`, CFBD's opponent-adjusted in-season efficiency, is the
one input the model has been missing by construction (every quality number it uses is last
season's all year). Two free endpoints matter as much: `/game/box/advanced` splits EPA,
success and explosiveness by quarter, which is a play-by-play-free way to bring back the 57
first-half inputs B-SERVE had to cut; and `/ratings/core`, `/ratings/elo`, `/ratings/fpi`
are in-season strength priors we never pulled. The most important thing found is not a
dataset: **CFBD changed its PPA calculation in September and rewrote history** (past-season
PPA and adjusted EPA moved 35-40%), so any frame built from a pre-fix cache is on a different
scale from today's pulls. Our current cache is post-fix (verified); earlier studies are not.
Keep Tier 3 through the season if the $10 is immaterial, otherwise drop to Tier 1 at the next
renewal; nothing in the plan below needs more than Tier 1.

## 1. What Tier 3 actually gives us

Gating is enforced in CFBD's open-source API (`src/config/middleware/patreon.ts`) and was
confirmed live: every refusal reads "Tier 1 or higher"; nothing probed is Tier-2- or
Tier-3-only except GraphQL and the Patreon download.

| Tier | Price | Calls/mo | What it unlocks | Beat Vegas use |
|---|---|---|---|---|
| Free / Academic | $0 | 1,000 / 3,000 | everything not below: `/games`, `/lines`, `/plays`, `/drives`, `/ppa/*`, `/stats/*/advanced`, `/game/box/advanced`, `/ratings/sp|fpi|elo|srs|core`, `/coaches/*`, `/player/*`, `/talent`, `/passing/*`, `/rushing/*`, `/teams/ats`, free game previews, `/info/usage` | 9 endpoints used today; ~12 more worth using |
| Tier 1 | $1 | 5,000 | `/wepa/team/season` (2010-26), `/wepa/players/passing|rushing|kicking`, `/games/{id}/preview/adjusted`, `/games/weather` (2001-), `/scoreboard` (quota-exempt) | **WEPA is the prize**; weather and scoreboard are validation |
| Tier 2 | $5 | 30,000 | `/live/plays` (per-play EPA, `wallClock`, `garbageTime`; metered since June 2026), exporter bookmarks, office hours | nothing live-betting here; post-game use only |
| Tier 3 | $10 | 75,000 | GraphQL (Hasura, 59 query = 59 subscription roots; live data only via `scoreboard`), the weekly model-training CSV (Sun/Mon, week 5 → CFP) | neither adds a dataset REST lacks |
| Tiers 4-6 | $15-30 | 125K-500K | calls | — |

Also included at every tier, from the Terms (2026-08-12): commercial and betting-related use
is permitted, model training and publishing derived outputs are permitted, bulk
redistribution and raw-response resale are not; data may be retained after cancelling.

## 2. Most valuable discoveries, ranked

1. **`/wepa/team/season` — opponent-adjusted in-season efficiency (Tier 1).** 26 fields,
   0% null, 138 teams, 2010-2026: adjusted EPA / EPA allowed, success rate, explosiveness,
   rushing line/second-level/open-field yards, each side. Correlation with the raw season PPA
   we already pull is 0.90 (offense), 0.89 (defense), 0.88 (success), only 0.55
   (explosiveness); the adjustment shrinks extremes (Georgia offense 0.427 raw → 0.241
   adjusted). It is exactly the "opponent-adjusted in-season ratings" `SYSTEM_REVIEW
   2026-10-04` §7 named as the SOS answer. Two hard limits: it has **no week parameter and no
   as-of stamp** (one overwritten row per team-season), and it **does not exist for weeks
   1-4** of a season ("not mathematically possible"; first 2026 refresh 2026-09-27). So it is
   a feature only if we snapshot it every Sunday from week 5 on; history before this season
   is end-of-season values and cannot be used for a leak-free backtest.
2. **CFBD rewrote PPA history in September 2026.** Bill, 2026-10-01: "I fixed an issue around
   how PPA handles changes of possession, including turnovers on downs, and applied historical
   corrections. Those changes also affect adjusted EPA." A patron measured 2025 offense PPA
   0.168 → 0.106 and adjusted EPA 0.155 → 0.091. **Our Mac cache (`data/cache/adv_2025.json`,
   Sep 22) reads mean 0.112 and a live pull today reads 0.112**, so current serving is
   consistent; frames and studies built before mid-September used the old scale, which is a
   concrete mechanism for the 40-of-196-column June → September drift the system review
   recorded. Historical WEPA/PPA are also regenerated whenever play-by-play is backfilled
   (Fox Sports fills for missing ESPN games, several a week in 2024). CFBD reference values
   are not frozen; the frame fingerprint is the only defence.
3. **SP+ strength of schedule and every sub-rating are null from 2019 on** (populated
   2014-18; checked in our own `data/cache/sp_*.json` and live for 2023/2025/2026).
   `SYSTEM_REVIEW` §11's planned `sp_sos` input for `bv_shadow_f` is a dead column.
   `specialTeams.rating` is populated except 2020-21. FPI's `resumeRanks.strengthOfSchedule`
   is the populated SOS.
4. **`/game/box/advanced` (free) is the only endpoint with a first-half split**: PPA, success
   and explosiveness by quarter plus cumulative PPA, points per opportunity, havoc. One call
   per game (~65 a week; ~2,400 for 2023-25) rebuilds the 57 first-half rates B-SERVE removed
   without parsing play-by-play, and `/drives` (free, one call a week, 2,718 rows) gives
   first-half drives, points per opportunity and seconds of possession by `startPeriod`.
5. **The weekly Tier 3 CSV is a full-game, market-aware frame for CFBD's notebook models.**
   One row per FBS game, opponent-adjusted EPA / success / explosiveness / line yards / havoc
   / points per opportunity / field position, pre-game Elo, talent, and the **closing spread**;
   no over/under, nothing first-half (patron, 2025-11-10: "I'd like to get totals and other
   lines as well"). Games can be missing from a week's file. Bill's own best result with it:
   #2 in the 2024 Pick'em, MAE 12.07 on margin. The pack history is **still on the pre-fix
   PPA scale** ("needs refreshing"). For us: a reference answer for our own opponent
   adjustment, not an input.
6. **The refresh contract is documented in Discord, nowhere else.** Game data settles for
   ~24 h after a game; the full weekly refresh runs Sunday 09:00-10:40 ET (SRS, Elo, FPI,
   CORE, Team and Player WEPA, PAAR), SP+ follows 30 min to 4 h later when Connelly posts, the
   Tier 3 CSV follows Sunday afternoon/evening (sometimes Monday). Our Sunday job ticks at
   2-4pm ET, after all of it on every 2025-26 Sunday on record except the 2025-11-30 delay.
7. **Free in-season strength priors we never pulled**: `/ratings/core` (2016+, carries
   `throughWeek` and `modelVersion` — the only CFBD rating with provenance), `/ratings/elo`,
   `/ratings/fpi` (with SOS ranks and a special-teams efficiency), and `homePregameElo` /
   `awayPregameElo` already inside the `/games` response we pay for.
8. **`/games/weather` (Tier 1)** covered 59/59 played FBS games in week 5 (observations) and
   58/58 unplayed week-6 games on Monday (forecasts five days out, condition text 64% null),
   22 fields, numerics 0% null — but no issued-at or forecast/observed flag, so it is only
   decision-safe if snapshotted, which is what `weather_obs` already does. Value: cross-check
   of our Open-Meteo rows and a 2001-2022 observed-weather backfill. Also found: CFBD
   `/venues` coordinates have geocoding errors (lower-division venues placed in Alabama by
   county-name collisions); our weather keys on those coordinates.
9. **Quota is not the constraint it was.** `/info/usage`: 1,395 calls in 31 days (~45 a day,
   reference endpoints 152-195 each), not the ~20 a day in `CLAUDE.md`; the ISO-week cache is
   not absorbing the Sunday refetches. On 75,000 that is irrelevant; on Tier 1's 5,000 it is
   comfortable; the Academic 3,000 was the only tier it threatened.
10. **`/lines` semantics, from Bill**: the stored line is the last 5-minute capture before
    scheduled kickoff, frozen there, no timestamps; `spreadOpen`/`overUnderOpen` are the
    earliest recorded; DraftKings appeared under two provider names ("Draft Kings" and
    "DraftKings") until 2026-09-25, when it was consolidated on id 888888. Our
    `cfbd_lines.py` priority matches on name, so any 2026 week 1-4 row captured under
    "Draft Kings" fell through to Bovada. No first-half field, no timestamp, DraftKings and
    Bovada only in 2026: CFBD still cannot replace The Odds API.
11. **Rate limits changed in 2026**: besides the monthly cap and Cloudflare bursts, six
    stats/live endpoints now allow two concurrent requests per user (429 `Retry-After: 1`);
    Bill's guidance is strictly sequential calls. Our client is sequential.
12. **Coaches endpoints are free** (`/coaches/profile`, `/seasons`, `/tenures`, since
    2026-07-30, with ratings/FPI/recruiting/talent context per season) — H-COACH needs no tier.
13. **GraphQL adds nothing we lack**: live data only through the `scoreboard` subscription
    (which stalled twice in September), player-stat aggregates unusable, same Postgres rows
    as REST, no plays/drives. Skip.
14. **Nobody in CFBD's community has first-half market data or models first-half totals**
    (one 2023 question, never answered). Our 2023-25 first-half closes remain unique here too.
15. **Tate's Discord is not linked to Patreon**, so the patron role and the
    `supporter-lounge` channel are missing from the sidebar (its messages are readable through
    search). Link at patreon.com/settings/apps.

## 3. What we should add

- **A weekly WEPA snapshot table** (`cfbd_wepa_snapshots`: season, week, team, 26 fields,
  `captured_at`, fingerprint) written by `sunday.yml` after the refresh from week 5 on, one
  call. It is the only way to make WEPA leak-free; this season's rows start the dataset.
- **CORE, Elo and FPI snapshots the same way** (three calls a week; CORE carries its own
  `throughWeek`). Plus read `homePregameElo`/`awayPregameElo` off `/games`, zero calls.
- **A first-half lag table from `/game/box/advanced`** (`fh_box_scores`: game, team, quarter-1
  and quarter-2 PPA/success/explosiveness, cumulative PPA, PPO, havoc), one call per finished
  FBS game, backfilled 2023-25 once (~2,400 calls, inside one month of Tier 1). It feeds the
  "last week's values" version of the 57 removed inputs.
- **`/drives` by `startPeriod`** for first-half pace and red-zone rates (one call a week).
- **A fingerprint on every CFBD reference pull** (already the rule for model runs; extend to
  the cache files: record `X-CallLimit-Remaining`, row count and a column hash per file).
- **`/games/weather` as a validation feed**: a weekly comparison of its forecast rows against
  `weather_obs` for the same games, and a one-time 2001-22 observed-weather backfill into
  `weather` (now that the clock bug is fixed) — the 647 "empty" venues in the Open-Meteo log.
- **One-time FBS venue coordinate check**: distance between `/venues` lat/long and the venue
  city's centroid; flag > 50 miles.
- **A `cfbd_provider` column** on the full-game line rows we take from `/lines`, so the
  "Draft Kings" / "DraftKings" split is visible, and a re-pull of 2026 weeks 1-4 lines.

## 4. What we should change

- **The quality inputs' timing.** Today `home/away_sp_*`, `*_ppa`, `*_success`,
  `returning_ppa`, `talent` are joined at season+1 (`etl/features.py:465-473`): last season
  all year. The champion stays as is (H-STOP-2 clock); the change enters as the shadow arm
  `bv_shadow_f`'s successor: in-season WEPA/CORE/Elo from the snapshot tables, prior-season
  values before week 5.
- **Drop `sp_sos` from the PR6 spec** (null since 2019) and use FPI's SOS or none.
- **Re-pull every CFBD reference table in one pass** before the next registered study and
  record the fingerprint, so no study mixes pre- and post-September PPA. Reads of
  `model_runs` fingerprints before mid-September should be labelled "pre-PPA-fix".
- **Stop citing ~20 CFBD calls a day**; measure with `/info/usage` (free) in the ops gauge.
- **The ISO-week cache**: either make the Sunday refetch the intended cache fill (restore on
  Sunday, save after, every later job hits) or stop pretending it saves calls; on Tier 1 or 3
  it no longer matters for quota, only for runtime.
- **Weekly refit stays weekly**, but the frame it reads should be built after CFBD's Sunday
  refresh and after SP+ posts; add a probe that `/ratings/core` for the current season
  reports `throughWeek = week − 1` before scoring, and degrade (not fail) if it does not.
- **Backtesting**: do not backtest WEPA on 2010-25 values — they are end-of-season rows. The
  only honest WEPA test is prospective from this week's snapshot (paper arm).
- **Line-value and CLV tracking**: unchanged; CFBD has nothing for the 1H market.
- **Coaching, matchup, SOS, player availability, recency weighting**: see §7 — each becomes a
  row, none a change to the champion.

## 5. Model training data analysis (the weekly CSV)

**Measured on the week-6 file Tate supplied** (`downloads/training_data_2026_week06.csv`,
79 KB; `lanes/training-csv.md`), plus the 2025 Data Info Sheet for the history layout.

- **Shape**: 57 rows x 83 columns, zero nulls. One row per upcoming FBS-vs-FBS game; `id` is
  the CFBD game id, which is our `games.id`, so the join is direct.
- **Coverage**: 57 of the 58 week-6 FBS games CFBD itself lists; Coastal Carolina @ Marshall
  is missing (our `games` table holds two Marshall rows for the week, a rescheduled fixture).
  Patrons reported the same kind of gap twice in 2025. Never assume the file is the slate.
- **Columns**: 15 context/market (`id, start_date, season, season_type, week, neutral_site,
  home/away team + conference, home/away elo, home/away talent, spread`) and 68 features, each
  for home and away: adjusted EPA, rushing EPA, passing EPA, success, standard-down success,
  passing-down success, line yards, second-level yards, open-field yards, explosiveness, rush
  and pass explosiveness, each with its "allowed" twin (48); total / front-seven / DB havoc on
  offence and defence (12); points per opportunity offence/defence (4); average starting
  field position offence/defence (4). **No outcomes, no over/under, no totals, nothing
  first-half, no weather, rest, travel or injuries.**
- **Provenance of every column, verified**: the 48 adjusted columns are `/wepa/team/season`
  (Tier 1) to the last digit (Bowling Green `home_adjusted_epa` 0.0343301327144653 = the
  endpoint's `epa.total` 0.03433013271446539); havoc, points per opportunity and field
  position come from `/stats/season/advanced` (free); Elo and talent are free endpoints;
  `spread` is `/lines`. **Nothing in the file exists only at Tier 3.**
- **The spread** is the DraftKings/Bovada line as of Sunday posting: it equals the provider's
  opening line in 38 of 57 games and the current line (Monday) in 26, negative = home favoured
  (mean −4.8, range −38 to +13.5). Market-aware by design; banned from our regressor.
- **Scale**: these 2026 values are on the post-PPA-fix scale (they match the live API today);
  the Gumroad history (2016-25) is on the old scale until Bill refreshes the pack, so the two
  cannot be stacked yet.
- **What it is for**: scoring CFBD's own notebook models (margin, win probability, team
  points). CFBD's best result with it: MAE 12.07 on margin, #2 in the 2024 Pick'em.
- **How we could use it**: (a) a reference answer for our own opponent adjustment (a patron
  did exactly that); (b) a weekly check that our WEPA snapshot equals CFBD's file; (c) never as
  a training set — full-game target, market column, no first-half anything.
- **Verdict**: 3/10 as a dataset, 6/10 as a validation tool. One useful side effect: it is
  the only place CFBD publishes WEPA *as of a date* (the file is a frozen Sunday snapshot),
  which is what the endpoint itself lacks — keeping every weekly file is a free, dated WEPA
  history for 2026.

### The Patreon posts, one by one

Thirty posts on the campaign (Patreon's API lists them; bodies are not served anonymously, so
the public ones were read through their Discord and blog mirrors, which carry the same text):

| Post | Date | Access | What it is | For Beat Vegas |
|---|---|---|---|---|
| Week 6 Model Training Data (Tier 3+) | 2026-10-04 | locked | the file measured above | §5 |
| New Tutorial: A Practical Introduction to Opponent Adjustment | 2026-09-29 | public | SRS-style iterative margin adjustment on 2025 FBS (762 games, 136 teams, 2.5-pt home field, 50% relaxation, 206 iterations, free endpoints only); Florida 103rd raw → 42nd adjusted | the method for H-ADJ-OWN; adjusts margin, not EPA — our version would adjust PPA/success per side |
| Week 5 Model Training Data (Tier 3+) | 2026-09-27 | locked | first 2026 file, same layout | same as week 6 |
| New passing endpoints: air yards, ADOT, pass locations | 2026-08-30 | public | five `/passing/*` endpoints, 2025+ only: air yards, aDOT, YAC, seven location buckets | style features someday; two seasons of history by 2027 |
| College Football Is Back... and I've Been Busy | 2026-08-29 | public | season-start recap: CORE, CFP data, coaches and player endpoints, FCS coverage, conference history, new docs portal, Workbench, account self-service, CSV exports | nothing new beyond the endpoints already listed |
| The 2026 CFBD Model Pick'em is live | 2026-08-12 | public | free weekly margin contest; picks via site, CSV or API (`POST predictionsapi…/api/picks`); leaderboard, head-to-head, crowd wisdom | free public validation of a full-game margin proxy; not for 1H |
| Introducing CORE Ratings | 2026-08-08 | public | Context & Opponent-Relative Efficiency: play-level PPA vs expected for the situation, then a regularised opponent network; offence = points above average per 100 plays; 2016+; excludes special teams, OT, garbage time, FCS games; "not a forecast or betting system" | the one CFBD rating with a `throughWeek` stamp; a free in-season prior for the shadow arm |
| The 2026 CFB Model Training Pack is now available on Gumroad | 2026-08-06 | public | $69: 5,133 games, 86 fields, 2016-19 + 2021-25, nine notebooks (margin, score, logistic, XGBoost, FastAI, SHAP, stacked ensemble), seven prediction exports | history is on the pre-fix PPA scale; reconstructible from free endpoints; skip |
| New guide: 10 projects you can build with CollegeFootballData | 2026-07-29 | public | project ideas incl. a watchability score from lines and an in-season prediction pipeline with time-aware validation | nothing for us |
| The new CFBD AI Builder Pack | 2026-07-24 | public | $49-69: Python/TypeScript starters, Claude Code / Codex context files, fixtures, request logs, review checklists | we already have a working client; skip |
| Your First CFBD Analysis: Build a Team Profile in Python | 2026-07-21 | public | tutorial: three requests, pandas frames, FBS percentiles, a profile chart | nothing for us |
| The CFBD Blog Is Becoming Rad Sports Analytics | 2026-07-16 | public | blog moved; CFBD/CBBD stay the data platforms | update bookmarks only |
| CFBD AI API Launchpad Pack | 2026-07-13 | public | $19 beginner API-literacy kit | skip |
| The 2026 College Football Data Starter Pack is here | 2026-06-18 | public | $49: 2025 season CSVs, 2026 schedule, 14 notebooks, team-trajectory notebook | skip |
| CFP Semifinals / Quarterfinals / Postseason (+ Army-Navy) Model Training Data | 2026-01-06, 2025-12-24, 2025-12-10 | locked | the 2025 postseason drops | shows the drop continues through the playoff |
| Week 15, (Update) Week 14, Week 14, Week 13, (Update) Week 12, Week 12, Week 11, Week 10, Week 9, Week 8, Week 7, Week 6 Model Training Data | 2025-09-28 → 2025-12-01 | locked | the 2025 regular-season drops; two mid-week "(Update)" re-posts | cadence evidence only |
| CBB season tips off Monday: CBBD's first full season | 2025-10-31 | public | basketball | not relevant |

The two 2026 locked posts' body text (schedule and caveats as Bill states them) is the one
thing still unread; a paste of either post closes it.

## 6. Discord findings

- **Operational contract** (pinned, Bill): game data updates for ~24 h after games; weekly
  refresh Sunday morning; support through the forum; "I do not monitor DMs"; a single
  maintainer with regular AFK notices; "Week 0 is a soft launch" every season.
- **Cadence, 2025 and 2026 Sundays**: refresh 09:00-10:40 ET; SP+ 10:32-13:07 ET; Tier 3 CSV
  13:14-22:37 ET or Monday morning; WEPA and SRS absent until after week 4.
- **The PPA rewrite** (2026-10-01 thread, §2.2) and the 2024 pattern of regenerating WEPA
  after play-by-play backfills.
- **Rate limits** (2026-09-09): new per-endpoint concurrency limits; sequential calls.
- **`/lines` closing semantics** and the DraftKings provider duplication (§2.10).
- **Weather**: consensus that it is not worth modelling beyond extremes; a venue-coordinate
  defect report with a CSV of bad rows; `/scoreboard` carries 4 weather fields and a
  provider-less line per game.
- **GraphQL**: live only via the scoreboard subscription, which stalled on 09-10 and 09-26.
- **How patrons use the data**: "raw → opponent-adjust → EWMA" (PEARatings); re-running the
  ridge adjustment up to each week for leak-free training (two users); the Tier 3 file as the
  reference for one's own adjustment; the Pick'em as a free public validation venue for
  margin models.
- **Nothing on first-half totals**, no first-half line source, no totals model reporting a
  record against the close.
- **Data-quality threads, September 2026**: bad drives for two games, duplicate team rows,
  a wrong score vs ESPN, scoreboard stalls on a Monday game, wrong yards-to-goal on two
  field-goal plays, a wrong week-10 Virginia Tech game. Per-game defects every week, fixed
  within days; the Sunday reconciliation is the trusted state.
- **Account**: Tate's Discord is unlinked (no patron role; `supporter-lounge` hidden but
  searchable).

## 7. Implementation plan

**Implement immediately (zero risk to money, no registry row needed because they record,
not decide)**
- Weekly snapshot tables for WEPA, CORE, Elo, FPI from the next Sunday job (4 calls).
- Fingerprint + remaining-calls stamp on every cached CFBD reference file.
- `/info/usage` in the ops gauge; retire the "~20 calls a day" sentence.
- The FBS venue-coordinate check and the `/lines` provider re-pull for 2026 weeks 1-4.
- Link Discord to Patreon (Tate).

**Test or backtest first (each a proposed `docs/HYPOTHESES.md` row; paper arms only)**
- **H-WEPA-F**: `bv_shadow_f` successor with in-season WEPA (off/def adjusted EPA, success,
  explosiveness, line yards) + CORE + pregame Elo replacing the season+1 quality columns from
  week 5 on. Judged on paired absolute error vs the champion and the two paper clocks,
  prospective 2026 weeks 6-15, n ≈ 500 scored games; PASS = lower paired MAE with a bootstrap
  95% CI excluding zero AND line value not worse. No 2010-25 backtest (end-of-season rows).
- **H-FHBOX**: the 57 first-half inputs rebuilt from `/game/box/advanced` as last-week lag
  values; backfill 2023-25 (~2,400 calls), walk-forward MAE vs the champion on the 1,902
  real-close games, criterion as `MODEL_LEVEL_2026` used (paired bootstrap).
- **H-ADJ-OWN vs WEPA**: our own ridge adjustment from free endpoints vs WEPA, judged by
  agreement (r) and by H-WEPA-F's criterion in a second arm; decides whether Tier 1 is needed
  at all.
- **H-COACH** (already named): free `/coaches/tenures` join on 2023-25 closes.
- **H-WX-VALID**: `/games/weather` forecast rows vs `weather_obs` (same game, same lead):
  agreement check only; a disagreement > 5 mph wind or 10°F flags the Open-Meteo row.
- **H-INJ** (named): QB usage share from `/player/usage` + `injury_snapshots` as the
  availability measure; after a season of snapshots.

**Useful later**
- 2001-22 observed-weather backfill from `/games/weather` (one call per week-season, ~350).
- `/drives` first-half pace and PPO features (after H-FHBOX reads).
- `/passing/teams/season` and `/rushing/*` style features (2025+ only; two seasons of
  history by 2027).
- `/wepa/players/*` for backup-QB quality (needs the backup to have played).

**Probably not worth using**
- The weekly Tier 3 CSV as an input or training set; GraphQL; `/live/plays`; `/scoreboard`
  as a data source (a live board someday, not a model input); `/metrics/wp/pregame` (carries
  the spread); `/teams/matchup`, `/recruiting/teams` (we have `/talent`); the Gumroad packs.

## 8. Top 10 opportunities

1. In-season opponent-adjusted efficiency (WEPA + CORE + Elo) as the shadow arm's quality
   inputs — the structural gap the system review named, now one call a week.
2. Re-pull and fingerprint every CFBD reference table once, post-PPA-fix, and label every
   earlier study accordingly.
3. Rebuild the 57 first-half inputs from `/game/box/advanced` quarter splits as a leak-free
   lag table (the only first-half signal source outside our own data).
4. Snapshot discipline: WEPA/CORE/Elo/FPI weekly from week 5, so 2026 becomes the first
   leak-free in-season rating history we own.
5. Replace the dead `sp_sos` in the PR6 spec with FPI's SOS (or nothing).
6. Build our own opponent adjustment from free endpoints and judge it against WEPA; if it
   matches, Tier 1 is optional and the method is ours.
7. Validate `weather_obs` against `/games/weather` and backfill 2001-22 observed weather.
8. Fix the `/lines` provider-name split and the venue-coordinate risk at the source.
9. Align the Sunday job to the documented refresh (probe CORE `throughWeek`; degrade when
   stale) and measure usage with `/info/usage`.
10. Use the Pick'em and the Tier 3 file only as external validation of our full-game margin
    proxy — free, public, no effect on the 1H system.

## Limitations

Monthly cap 75,000 (Tier 3) is a hard 429; Cloudflare burst blocking (~10 min); two
concurrent requests per user on `/stats/*/advanced`, `/live/plays`, `/plays/stats`,
`/stats/player/*`; `/games/weather` and `/live/plays` count against the pool, `/scoreboard`
and `/info*` do not. Data settles ~24 h after a game; the Sunday reconciliation is the trusted
state; historical PPA/WEPA are regenerated after play-by-play backfills and after calculation
fixes, with no changelog beyond Discord. WEPA has no week dimension and no weeks 1-4; SP+
sub-ratings null since 2019; passing/rushing enriched endpoints 2025+ only; 2020 excluded
from the pack; weekly CSV can omit games. Terms: personal use for Gumroad packs; Patreon API
use permitted for betting research; no redistribution. Single maintainer.

## Evidence table (key claims)

| Claim | Source | Confidence |
|---|---|---|
| Tier gating list; nothing Tier-2/3-only but GraphQL | `cfb-api-v2` middleware + live 401s (`lanes/api-inventory.md` A0-A7) | verified |
| WEPA fields, 2010-26, no week param, r vs raw PPA | probes `wepa-team-season-*.json`, `analyze.py` | verified |
| SP+ sos/sub-ratings null 2019+ | probes `ratings-sp-2023/2025/2026.json`, `data/cache/sp_*.json` | verified |
| PPA recalculation Sept 2026 with historical corrections | Discord thread 1555075398675595354 (Bill, 2026-10-01) | verified |
| Our cache post-fix (2025 mean 0.112 = live 0.112) | this session, 1 call, `data/cache/adv_2025.json` (Sep 22) | verified |
| `/game/box/advanced` quarter split | probe `game-box-advanced-401856705.json` | verified |
| Weather 59/59, 58/58, no issued-at | probes `games-weather-*.json` | verified |
| Weekly CSV = 83 cols, 57/58 games, adjusted cols = WEPA, spread = Sunday line | `lanes/training-csv.md` (week-6 file measured) | verified |
| Refresh cadence, WEPA after week 4 | announcements Oct 2025 → Oct 2026 | verified |
| `/lines` closing semantics, DraftKings dup | Discord threads 1553135190153363646, general 2025-07-06 | verified |
| 1,395 calls / 31 days | probe `info-usage.json` | verified |
| 429 concurrency limits | middleware (D8/D15) + Discord 1547307736986026166 | verified |

## Unconfirmed / needs a human

The locked posts' body text (schedule/caveats); CFBD's weather provider; GraphQL row/depth limits; the exact date of the PPA fix
("a few weeks back" from 2026-10-01; our Sep 22 cache is post-fix, the patron's late-August
pull was pre-fix); whether FBS `/venues` rows carry the geocoding defect; Bill's answer on
"team WEPA by week" (asked 2025-10-23, not found).

## Decisions for Tate

1. Keep Tier 3 ($10) or drop to Tier 1 ($1) at the Nov 6 renewal — nothing above needs more
   than Tier 1.
2. Approve the four snapshot tables and the fingerprint stamp as PR7 of the week-6 stack.
3. Register H-WEPA-F, H-FHBOX, H-ADJ-OWN, H-WX-VALID (rows proposed above), or a subset.
4. Approve the one-time 2023-25 `/game/box/advanced` backfill (~2,400 calls, one Actions run).
5. Link Discord to Patreon for the patron channel.
6. Paste the body text of the week 5 and week 6 Patreon posts (the file itself is measured).
