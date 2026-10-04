# Beat Vegas — full system review after week 5 (2026-10-04)

Written Sunday 2026-10-04 before the week-6 refit, after the week-5 review
(`docs/HISTORY.md` 2026-10-04). Read-only: nothing here changed a gate, a model constant, the
champion, a stake or a ledger row. Every decision below is Tate's (the question-and-answer
record is in the plan file `let-s-run-a-full-playful-russell.md`). Registry rows for everything
proposed are in `docs/HYPOTHESES.md` under "System review rows".

**Recommendation first.** The system is disciplined and honest; it is not yet sharp, and it
cannot become sharp on its own, because the model never trains on the season it is scoring.
Nothing in the 58 inputs — and not the gap itself — predicted the first-half residual against
the consensus close in 2026 (87 comparisons, best p 0.117). The parts with a live record are
the parts that protect money: the price gate, the alternate-line filter, the close capture, the
ledger. So: real money unchanged for week 6 (≤5 × $10, every card BET), no change to the
champion, and every improvement enters as a paper arm beside it — two shadow engines (the
discarded CFBD inputs; in-season training rows), four paper rules (tie margin, top-3, bet
timing, line movement) — while the tracking gaps that stop us from learning are closed first.

## Provenance

- Ledger: `manual_picks`, season 2026, market 1H, graded (`result` = outcome; under = win);
  real = `COALESCE(is_paper,false)=false`. 20 real tickets, 76 paper picks. Price CLV only
  where `price_provenance='logged'` (week 2 real tickets are `unknown`, week 3 NULL).
- Live scope: `postmortem_games` run `pm-20261004T110219Z` (`live_2026`, 355 card items,
  graded at Hard Rock's number as of the last card build before kickoff; real lines only).
- 2026 factor screen (registry row **H-FACTOR-SCREEN**): `game_records.features_json`
  (runner-made at the Sunday score, first capture per game) joined to the live scope, weeks
  2-5, Hard-Rock-priced with a trusted first half: **212 games**; 43 numeric inputs with ≥ 60
  values; Spearman rho against (actual − consensus close) and (actual − Hard Rock line);
  tercile under-rates at the close; **87 comparisons**, Bonferroni line 0.05/86 = 0.00058.
  Script: ad hoc on this Mac from the runner's frozen frames (no Mac feature frame was
  built), reproduced in the registry row.
- 2023-25: `postmortem_buckets` scope `hist_2023_25`, segment `fbs_only`, graded `real`
  (1,902 games, one consensus close each ~30 min before kickoff). **That set is spent**
  (registry, 2026-09-22); it is quoted here, never re-read, and nothing is chosen on it.
- Sign: stored `clv = closing − bet`; negative is favourable for an under; "line value"
  below is `−clv`. Wilson 95% intervals throughout.
- Model: B-SERVE champion (58 inputs, `model/bv_line.py:51`), refit 2026-09-27 (run
  36342602323). Weeks ≤ 4 were scored by the pre-B-SERVE model (~2 pts low).

## 1. The biggest lessons from weeks 1-5

1. **The model does not learn in-season, and never could.** `score_slate` trains on
   `season < target_season` (`beatvegas/model/score.py:470`). 2026 games reach it only as
   season-to-date averages in the inputs. SP+, PPA, talent and returning production are last
   season's numbers all year (`etl/features.py:466-473, 620-629`). The Sunday refit re-fits the
   same 2015-25 regressor; its only in-season movement came from CFBD revising reference
   tables (40 of 196 columns between June and September). "Getting sharper as we collect
   results" has not been happening because nothing is wired to make it happen.
2. **Level is fixed; accuracy is not.** B-SERVE removed 57 inputs that were NaN on every
   scored row and present on every training row. Bias went from +3.7 / +4.2 (weeks 2-3) to
   +0.18 in week 5, identical to Hard Rock's. MAE did not improve: 9.03 vs the book's 8.39 in
   week 5, 9.15 vs 8.59 in week 4. On the games we qualify, 8.74 vs 7.50.
3. **The gap has not sorted unders from overs since week 3.** Correlation of the gap with the
   residual against Hard Rock's line, main lines only: −0.34, −0.36 (weeks 2-3, but those
   weeks include the pre-09-25 alternate lines), **+0.15, +0.16** (weeks 4-5). Week 5's slate
   went 62% under and the under side sat below our bar: gap < 1.75 went 26-13, gap ≥ 1.75
   7-7. Over 212 games the gap's Spearman with the close residual is −0.06 (p 0.41).
4. **The gates that protect money have a record; the signal does not.** Price-blocked paper
   picks are 14-20 (−7.8u) while BET-rated are 7-4 (+2.5u). The alternate-line filter removed
   a feed defect that had manufactured 23 of 38 "overs" games. The close backup reached 53 of
   53 games on its first Saturday. None of that is edge; all of it is loss avoided.
5. **Every rule we have validated is small, and the only set it was validated on is spent.**
   2023-25 real closes: gap ≥ 1.75 went 165-127 (56.5%, 50.8–62.1, +23u on 295). Live 2026 the
   same rule is 51-43 (54.3%, 44.2–64.0, −0.9u). Both intervals contain break-even. Separating
   55% from 52.4% takes ~2,300 bets; H-STOP-2 expects 466 paper decisions under no edge.
6. **We fix what we can measure and we have been measuring the wrong things.** Four weeks
   of registered work went into level (H-LEVEL, H-INTERCEPT, H-INSEASON, B-SERVE), the bar
   (H-PCT), the universe (H-PCT-U) and the close poll — all correct, all now done. Not one
   registered row has asked whether any input carries signal, because no decision-time factor
   values were frozen on the picks that would answer it.
7. **The system does not repeat mistakes; it repeats the same blind spot.** Every week-5 fault
   (tie at the bar, Tuesday tickets, a Friday-night close gap) was a first occurrence, and
   each had a rule-level answer. What recurs is reading a hot week (the overs band, 23 of 26)
   as a signal; the registry discipline caught it each time before money moved.

## 2. What is working best

| what | evidence | n |
|---|---|---|
| Rule adherence | every card BET placed, nothing else, five weeks running | 20 tickets |
| The price gate (`ev ≥ −0.05` vs market fair) | paper price-blocked 14-20 (−7.8u) vs BET-rated 7-4 (+2.5u) | 45 |
| The alternate-line filter (H-PCT-U) | 33 alternates on 31 games caught in replay; 8-14 per `sat_am` build since | 747 snapshots |
| The close capture | 53 of 53 inside 2 h on the first backed-up Saturday (was 18 of 57) | week 5 |
| Line value at the close | real tickets +0.20 pts/pick season mean; never negative on a Tuesday ticket | 20 |
| The ledger and the clock | every ticket priced with provenance since week 4; H-STOP-2 n=10, LLR −0.26 / +0.73 | — |
| The level fix (B-SERVE) | bias +0.18 vs the book's +0.18 | 53 |
| The card BET tier, live | 6-3 (66.7%, 35.4–87.9), +2.3u — too few to mean anything, stated for completeness | 9 |

## 3. What is working worst

| what | evidence | n |
|---|---|---|
| Model accuracy vs Hard Rock | MAE 9.03 vs 8.39 (wk 5), 9.15 vs 8.59 (wk 4); on qualifying games 8.74 vs 7.50 | 53 / 57 / 9 |
| The gap as a sorter, weeks 4-5 | corr +0.15 / +0.16; qualifying 1-5 and 4-5 | 43 / 48 |
| Every situational input | rest, bye, short week, travel, time zone, kickoff hour, rivalry, revenge, conference game: all flat in the screen (best p 0.117) and flat in the README's own note | 212 |
| Weather inputs | legacy table clock-shifted in history; live rows on 27 of 303 games in week 2 and none since; post-mortem rates them noise | — |
| The "overs" band | 23 of 26 in weeks 2-3 → 3 of 12 in week 4 → 5 of 17 in week 5; paper arm −6.7u on 16 | 55 |
| Concentration (bigger gap = better) | live weeks 2-5 by gap within week: top-1 2-2, top-2 4-4, top-3 5-7, top-5 9-11 | 20 |
| Paper qualifying set | 33-33, −6.3u at Hard Rock's number | 66 |
| Season-to-date scoring as a feature | `away_fh_pf` / `combined_fh_offense` top tercile went 45% / 44% under (rho +0.10) — the wrong sign for an input that should predict scoring | 186 |

## 4. The factor screen (H-FACTOR-SCREEN) — which parts have predictive value?

**None of the 43 inputs crossed the Bonferroni line; the best three are listed so nobody
reads them as findings.** Spearman rho with (actual − consensus close), 212 games:

| input | rho | p | under rate, low tercile → high tercile |
|---|---|---|---|
| `away_tz_shift` | −0.11 | 0.117 | 39% → 55% |
| `week` | −0.10 | 0.153 | 51% → 59% |
| `away_fh_pf` | +0.10 | 0.155 | 56% → 45% |
| … 40 more between p 0.16 and 0.97 | | | |
| **the gap itself** | **−0.06** | **0.41** | — |

Reading: 2026 is five weeks and 212 games. At that n, an input with a true 3-point effect
on a 12-point-sigma outcome reads at |rho| ≈ 0.1 and p ≈ 0.15, which is exactly where the
table sits. The screen cannot find a real small effect; it can only rule out a large one. It
rules out a large one for every input, and for the gap.

**2023-25, quoted not re-read** (`gap175` selection, fbs_only, real closes, n 295; every
interval overlaps every other; ≥ 352 comparisons already counted on this set):

| cut | record | under % | Wilson |
|---|---|---|---|
| all gap ≥ 1.75 | 165-127 | 56.5 | 50.8–62.1 |
| full-game total 52-60 | 82-52 | 61.2 | 52.7–69.0 |
| full-game total 45-52 | 34-39 | 46.6 | 35.6–57.9 |
| pace 27-30 s/play | 79-53 | 59.8 | 51.3–67.8 |
| pace < 24 (fast) | 16-7 | 69.6 | 49.1–84.4 |
| weeks 3-6 | 47-47 | 50.0 | 40.1–59.9 |
| weeks 7-10 | 55-39 | 58.5 | 48.4–67.9 |
| weeks 11-15 | 63-41 | 60.6 | 51.0–69.4 |
| spread ≤ 7 | 58-39 | 59.8 | 49.8–69.0 |
| spread 21+ | 32-28 | 53.3 | 40.9–65.4 |
| temp 60-80 | 40-17 | 70.2 | 57.3–80.5 |
| wind 10-15 | 17-6 | 73.9 | 53.5–87.5 |

The only pattern that repeats across weeks, seasons and the blanket set is **the rule did
nothing in weeks 3-6 of any season** (47-47 historically; 2026 weeks 2-5 qualifying 33-33)
and earned whatever it earned from week 7 on (`beat-vegas-edge-is-concentrated` memory,
2026-09). That is a reason to expect nothing from the next three weeks, not a reason to
change anything: it was found on the spent set and is being tested live by the clock.

**Line movement, descriptive (prompt for H-MOVE, not evidence):** on the 66 qualifying rows,
when Hard Rock's line fell from build to close the under went 9-7, flat 18-23, rose 6-3; on
all 212 games 32-29 / 58-66 / 15-12. Nothing to see at this n; the row is registered because
the data is free and has never been read.

## 5. Winners against losers — what a Beat Vegas bet looks like

Medians over the 96 graded picks (20 real, 76 paper). A profile, not evidence: eight cuts on
96 picks will produce a pattern by chance.

| | real W (10) | real L (10) | paper W (38) | paper L (38) |
|---|---|---|---|---|
| gap at pick | 5.78 | 4.69 | 5.04 | 4.16 |
| \|spread\| | 8.75 | 5.50 | 15.25 | 12.25 |
| 1H line | 28.0 | 28.0 | 29.5 | 27.5 |
| price | −115 | −112.5 | −115 | −115 |
| hours before kick | 53 | 74 | 23 | 23 |
| sec/play (both teams) | 25.2 | 26.7 | 26.5 | 26.5 |
| actual − our number | −2.9 | +10.6 | −3.2 | +10.9 |

All 96 picks, cut one way at a time (W-L):

| cut | W-L | under % |
|---|---|---|
| gap ≤ 3 (within ~1 pt of the bar) | 8-15 | 35 |
| gap 3-5 | 15-14 | 52 |
| gap 5-7 | 16-15 | 52 |
| gap 7+ | 9-4 | 69 |
| \|spread\| ≤ 7 | 14-21 | 40 |
| \|spread\| 7-14 | 13-7 | 65 |
| \|spread\| 14-21 | 6-9 | 40 |
| \|spread\| 21+ | 15-11 | 58 |
| 1H line ≤ 25 | 3-8 | 27 |
| 1H line 31+ | 12-6 | 67 |
| pace ≥ 29 s/play (slow) | 2-9 | 18 |
| price −120 or worse | 13-18 | 42 |
| price −119 to −110 | 26-15 | 63 |
| real ticket placed Tuesday | 1-4 | 20 |

**The high-quality bet, as the profile reads it:** a gap well clear of the bar (5+), a line
in the high 20s or above, a spread of a touchdown or more, two teams that play fast, priced
−115 or better, placed Thursday to Saturday. **The bet to avoid:** a gap within a point of the
bar, a line at or under 25, a one-score spread, slow teams, and a price at the kill number.
Every one of those lines is a hypothesis with n under 40; three of them (the tie margin, the
top-3 cut, the timing) are registered rows from today, and the rest wait for the frozen
factor vector that PR2 adds, so next month's version of this table is built from decision-
time values, not recomputed ones.

What the profile does **not** say: that the system should start filtering on spread, line
level or pace. The 2023-25 set says spread ≤ 7 was the *best* bucket (59.8%) and 2026 says it
is the worst (40%); that is what noise looks like at n 35.

## 6. Is the system learning? — the honest answer

**No, and it was not built to.** Confirmed by reading every writer in `beatvegas/db/models.py`:
nothing changes a weight, gate or constant from results (the factor ledger's Beta posteriors
only tint the display; the slate bar reacts to the gap distribution, not to outcomes; the
pause switch is manual). The evidence the system keeps is a decision ledger — what was bet, at
what price, against what close, which gate blocked what — and that ledger is good. What it
does not keep is what a learning loop needs:

| missing | where it bites | fix (PR2) |
|---|---|---|
| Factor values on paper picks | paper rows freeze market chips only (`build_card.py:255-276`); 76 of 96 picks carry no inputs | freeze `predictions.factors_json` + the 58 inputs on every paper and challenger row |
| Factor values on card items | `cards.payload.items` has no factors (`card.py:930-990`) | add `features` per item |
| Model identity | `model_version` = `gbm_v1` through B-SERVE; `predictions` overwritten per re-score | `refit_id` + fingerprint on `predictions`, `manual_picks`, `challenger_picks` |
| Evidence history | `factor_ledger`, post-mortem tables, `app_settings` deleted and rewritten each run | append dated runs; readers take the latest |
| Injuries at decision time | `game_previews` overwritten; Rotowire never stored; only `qb_out` survives on the card | `injury_snapshots` per build |
| Polling log | change-only snapshots; `last_seen_at` overwritten; "no change" = "not polled" | `poll_log` per sweep |
| Skipped BETs and reasons | nothing records a BET not placed | a `note` on the ticket form stays the record; Tate places every BET, so this is empty by policy |

Two smaller defects found on the way: `grade_factor_ledger.py` reads `results` without a
`model_version` filter, so a `gbm_v1` row (graded at the model's own ranking line) can
overwrite the `market` row for the same game (`:29-43`); and the ledger grades today's
recomputed frame at `min_games=2`, not the values the picks were made on. Both are fixed by
PR2's frozen vectors.

## 7. The 23 factors — useful and measurable, or not

| factor | in the system today | measurable with what we have | verdict |
|---|---|---|---|
| Coaching ATS / cover history | no; no coach data anywhere | buildable 2023-25 from our stored closes + CFBD `/coaches` (1 call/season, Tier 2) | **research, not an input**: cover history is a market residual by coach; test as H-COACH only after PR2, against the close |
| Coaching, favored vs underdog | no (spread is not a model input) | same source + `games.spread_open` | fold into H-COACH; the censoring study (R05) already found no spread information left after the price |
| First-half coaching tendencies | the 1H play-by-play rates existed and were removed (B-SERVE: NaN at serving) | prior-week PBP would need a leak-free lag build | **deferred**; the serving fix must come first (a `fh_team_game` lag table) |
| Weather: wind, rain, temp, heat | `wx_temp`, `wx_wind`, `wx_precip` live but reading a clock-shifted table with near-zero live coverage | yes, `weather_obs` (Previous Runs, decision-safe) exists and is read by nothing | **fix the data before judging the factor**: nulled in the shadow arm (H-SHADOW-F); R06/R09 found nothing on the repaired history |
| Indoor vs outdoor | `wx_dome` live | yes | flat (dome 3-4 on gap ≥ 1.75 historically); keep, it is free |
| Travel distance | `away_travel_dist`, `away_tz_shift` live | yes | flat (rho −0.01 / −0.11, p 0.84 / 0.12); keep as inputs, no gate |
| Short weeks / extra rest | `*_rest_days`, `*_short_week`, `*_off_bye` live | yes | flat (p 0.29-0.41); keep |
| Injuries / late news | QB-out gate only; no history | not yet — PR2's injury snapshots make it measurable from week 6 on | **track first**; one row (H-INJ) after a season of snapshots |
| Starting QB changes | binary `qb_out` blocker | same | same; backup-QB quality needs a source we do not have |
| Offence/defence matchup styles | separate SP+/PPA/success per side; the `mm_*` matchup terms were removed by B-SERVE | prior-season versions are computable now | one `mm_*` term from prior-season data goes in H-SHADOW-F's successor if the first arm earns a second |
| Pace of play | `combined_sec_play`, `combined_plays` live (TeamRankings) | yes | the one enrichment that ever moved error (README); the 2023-25 cut is the strongest bucket on record; **keep**, and the profile says slow teams lose |
| Explosiveness | fetched (`off/def_explosive`, prior season) and discarded | yes, zero calls | **add in the shadow arm** (H-SHADOW-F) |
| Red-zone efficiency | 1H `redzone_td` removed; `pointsPerOpportunity` in a paid response, unread | yes (Tier 2 for drives) | second shadow iteration; not now |
| Turnover luck | raw 1H turnovers removed; no luck measure | `/games/teams` (Tier 2), ~1 call/week | research only — turnover luck regresses, but the 1H total is not where it shows; low priority |
| Special teams | not at all | SP+ `specialTeams` in a response already paid for | **add in the shadow arm**, zero calls |
| Strength of schedule | implicit via prior-season SP+ | SP+ `sos` in the same response | **add in the shadow arm**; the real fix is opponent-adjusted in-season ratings (H-INSEASON-T's successor) |
| Home-field advantage | implicit (home/away split, `neutral_site`) | one explicit term is trivial | not worth a row on its own; H-FACTOR-SCREEN shows no home-side signal |
| Line movement | captured (build → close, 10 books), never read as a signal | yes, free | **H-MOVE registered** |
| Closing-line value | the scoreboard (H-STOP-2's second clock) | yes | keep exactly as is |
| Public betting vs sharp movement | no source; not sold for 1H totals | no | **do not buy** until H-MOVE says the move carries something we cannot read from the books |
| Conference trends | `conference_game` flag only; no conference identity | `games` has no conference column; `data/fbs_teams.json` does not either | one join away; add conference to `game_records` in PR2 so the screen can cut on it; no row until then |
| Situational spots (look-ahead, rivalry, letdown, emotional) | `rivalry_game`, `*_revenge` live; `*_opener` computed, unused | rivalry/revenge flat; the rest need a definition before they are data | **no**; "letdown" without a pre-registered definition is a story told after the game |

## 8. Keep / remove / add / research / track

**Keep unchanged:** the H-PCT champion and H-STOP-2; the price, off-market, QB-out,
early-season and cap gates; the alternate-line filter; the close poll and its backup; the
Sunday refit's serve-skew guard; the bet-timing choice (first BET-rated build); flat $10
units; the registry discipline (row first, script second, no tuning on 2023-25).

**Remove or reduce (the week-6 stack):** the `under_score` classifier (PR3 — fitted every
run on market columns and a mutable spread, gates nothing); the dead H-INSEASON challenger
arms (0 rows, withdrawn); the legacy `wx_*` inputs in the shadow arm (champion untouched); the
card-only degraded hold (PR4 mirrors it on the web so it is either real everywhere or gone).
Legacy routes, the proxy multiplier and the one-off backfills wait for the offseason.

**Add (as paper arms only):** H-SHADOW-F (explosiveness, defensive success, SP+ special teams
and SOS, the opener flags; weather nulled); H-INSEASON-T (in-season training rows, w = 1 and
3); H-PCT-TIE; H-TOP3; H-TIMING; H-MOVE. Account: CFBD Tier 2.

**Research next (after PR2, each its own row):** H-COACH (cover residual by coach, 2023-25
closes + CFBD coaches); opponent-adjusted in-season first-half efficiency (the SOS answer);
a leak-free lag table for the 1H play-by-play rates so the 57 B-SERVE columns can return as
"last week's" values; H-INJ once injury snapshots exist.

**Track (PR2):** the table in §6. Plus `conference` on `game_records`, and the `bet_at` field
on every real ticket (exists; use it).

## 9. The biggest weaknesses and blind spots

1. **No in-season learning path exists** (§1.1). H-INSEASON-T is the first row to test one.
2. **We cannot tell signal from noise on our own picks**, because the picks carry no inputs
   (§6). Until PR2 lands, every "what works" question is answered on the post-mortem's
   recomputed frame, not on decision-time values.
3. **The model is less accurate than the book and the gap is its only output.** With σ ≈ 12
   points per game and a 2-5 point gap, the rule is betting on the model being right by more
   than the book is wrong. 2023-25 said that happened 56% of the time; 2026 says 54% with an
   interval from 44 to 64.
4. **Hard Rock prices our condition.** Every real ticket sits at or within 5 cents of its kill
   price (ev −0.02 to −0.05); the market-fair gate lets us pay up to 5 cents over fair. We are
   never getting a good price; we are paying for the position.
5. **The feed serves alternates near kickoff** (97% main beyond 48 h, 31% inside 2 h). The
   filter handles it, but late candidates read `no_hr_line`, and nothing tells us whether Hard
   Rock pulls its main line or the vendor picks the wrong row (open item).
6. **Weather is in the model with untrusted data** (§7). Nulled in the shadow arm; the
   champion keeps it until the arm reads.
7. **The clock cannot settle a season.** H-STOP-2 expects 466 observations under no edge
   (~1.6 seasons) and 785 under the 4-pp alternative. Weekly reviews will keep reading
   "running". That is correct and it is also the biggest reason not to change the rule on a
   feeling: the feeling is all a single season can give.
8. **Friday-night games have no close inside 2 h** (open item): each one is excluded from
   the line-value clock.
9. **The 2023-25 set is spent**, so every new idea costs a season of paper to validate. That is
   the price of not fooling ourselves; the shadow-arm design pays it in parallel rather than
   in series.

## 10. Week-6 betting strategy

Unchanged: up to 5 × $10 flat, every card BET placed, nothing outside the card, bet off the
first build that rates the game BET, log at bet time (`bet_at`), paper picks beside it on the
same rule. H-STOP-2 is the only stop. Expect nothing from the rule in weeks 6-7 (the history
is flat until week 7) and do not read a second losing week as a verdict: the clock would need
roughly ten weeks like week 5 to fail on profit. Tate's account steps this week: buy CFBD Tier
2; downgrade the Odds API to 20K before its Oct 6 invoice (credits reset on the 1st; the
bill does not); add the Friday-night
`lines-close` entries if he wants that gap closed before the Oct 9 Friday slate.

## 11. Model changes before the next slate

**To the champion: none.** The week-6 refit (today, 1pm ET) runs the B-SERVE champion. Any
change to its inputs is a new champion and would supersede H-STOP-2 at n=10.

**Beside it, as registered shadow engines (PR6, first rows Friday 2026-10-09 or week 7):**

- `bv_shadow_f` — the champion's 58 inputs **plus** `home/away_off_explosive`,
  `home/away_def_explosive`, `home/away_def_success`, `home/away_sp_special_teams`,
  `home/away_sp_sos`, `home/away_opener`, **minus** `wx_temp`, `wx_wind`, `wx_precip`,
  `wx_dome` (nulled). Every added column is already in the CFBD responses the Sunday job
  makes (`sources/season_stats.py:186-224`, `/ratings/sp`); zero extra calls. Own
  calibration intercept, own slate bar on the same universe, paper unders into
  `challenger_picks` arm `shadow_f`. Judged on paired absolute error vs the champion and on
  the two paper clocks.
- `bv_inseason_t` — the champion's inputs, training rows `season < target` plus the current
  season's played games (`week < target_week`) at weight 1 and 3. Leak-free by construction.
  Same scoring, arms `inseason_t_w1` / `inseason_t_w3`.
- Both run under the serve-skew guard, name their frame fingerprint in `model_runs`, and
  stamp a `refit_id` on every prediction they write (PR2).

A shadow engine that beats the champion on both MAE and line value for a month earns a
registered promotion decision; promotion supersedes H-STOP-2 explicitly and restarts the
clock on the new champion. Nothing moves on its own.

## 12. The week-6 stack (dates ET)

| PR | what | by |
|---|---|---|
| PR1 (this one) | this doc, 7 registry rows, HISTORY, brief, ops notes | Sun 10-04 |
| PR2 tracking | frozen factor vector on paper/challenger picks and card items; `refit_id` + fingerprint; append-only `factor_ledger` / post-mortem / `app_settings_log`; `injury_snapshots`; `poll_log`; `conference` on `game_records`; `migrate.yml` first, `prisma db pull` after; sandbox replay | Mon 10-05, live on the Tue 10-06 card |
| PR3 classifier retirement | per `docs/CLASSIFIER_RETIREMENT.md`; `verdict.ts` and `edge.ts` "has a model" = `bvLine` only; parity tests | Mon 10-05 |
| PR4 degraded hold on the web | `pickRules.checkPolicy` refuses a held game; `verdict.ts` WATCH; `edge.ts` ladder; e2e case; `RANKING_AND_TRUST` §7/§10 closed | Tue 10-06 |
| PR5 paper arms | `pct_tie_strict`, `pct_tie_plus05`, `top3` in `build_card`; `scripts/timing_position.py`; `scripts/move_study.py` via `study.yml`; position scripts; `bv-card-check` expects the arms | Wed-Fri 10-07..09 |
| PR6 shadow engines | §11; week sandbox before merge | Fri 10-09 or week 7 |

Real money is untouched by every row of this table.

## The eleven answers, in one place

1. **Lessons:** §1 — the model does not learn in-season; level is fixed, accuracy is not; the
   gap has not sorted outcomes since week 3; the gates have a record, the signal does not.
2. **Working best:** §2 — adherence, the price gate, the alternate filter, the close capture,
   line value, the ledger and clock.
3. **Working worst:** §3 — model accuracy vs the book, the gap in weeks 4-5, every
   situational and weather input, the overs band, concentration.
4. **Keep:** §8 — the champion and clock, every gate, the timing choice, flat units, the
   registry discipline.
5. **Remove or reduce:** §8 — the classifier, the dead arms, the legacy weather inputs (in the
   shadow), the card-only degraded hold (mirrored, not dropped).
6. **Add:** §8 — six paper rows; CFBD Tier 2; nothing at real money.
7. **Deeper research:** §8 — coaches vs the close, opponent-adjusted in-season efficiency, a
   lag table for the first-half play-by-play rates, injuries once tracked.
8. **New data to track:** §6 — frozen factor vectors, refit ids, append-only evidence tables,
   injury snapshots, a poll log, conference.
9. **Weaknesses and blind spots:** §9.
10. **Week-6 strategy:** §10 — unchanged money, the clock decides, expect a flat fortnight.
11. **Model changes before the slate:** §11 — none to the champion; two shadow engines beside
    it, specified to the column.
