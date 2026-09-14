# Beat Vegas — project brief for Claude Code

College football **full-game + first-half (1H) unders** research & decision-support
system, focused on **Hard Rock Bet** (the only book bettable from Florida).
Research only — it never places bets or automates gambling.

## Current state (read this, then the pointers — don't restate history from memory)
- **2026-09-13 (RESULTS + TRACK RECORD REBUILT, PR #122).** The Board is not SHORTER than
  the other two pages — 6,877px against 7,753 and 9,159. It works because it is **one
  element repeated 34 times under 5 headings**, and because it never makes you read a
  visual. Results had **16 headings**, Track record **19**, each block its own shape with
  its own paragraph. So the fix was consolidation, not deletion.
  **Results is READ-ONLY** (Tate: "all the logging should happen on the board page. The
  results is just to see what I picked and how it turned out"). `BetSlip`, `CardPanel` and
  `BankrollStrip` are DELETED — all three are about a bet not yet placed. Logging is
  `/game/[id]` only (`LogPickButton`/`LogPickForm`, already linked from every board row).
  **Nothing was lost on safety: the kill line/price is enforced SERVER-SIDE for every path
  by `pickRules.ts::checkPolicy`**, not by the slip — check there before ever "porting" it
  again. `CardStatusBanner` moved to the BOARD, beside the missed-build and stale-results
  banners. Three tables became one (`Breakdown.tsx`, a By week / By reason / By blocker
  toggle); the blocker view drops the real-money columns rather than dashing them.
  **"Vs our number" is gone** — a game is only logged when Hard Rock's line sits ABOVE our
  number, so "went against it" was `— (0)` by construction. The picks table lost `Market`
  and hides `Week` when filtered to one; **`Stake` STAYS** — it looks constant but a bonus
  bet is staked differently.
  **Track record leads with the finding.** The gap ladder (48.4/44.5/53.9/54.9/58.8) was an
  8-column table under a 60-word caption while a tangent had the only chart;
  `GapLadderChart.tsx` draws it (same Recharts pattern as `LineStudyView`, and
  **`isAnimationActive={false}` is load-bearing there too**). Everything secondary folds
  away (`Fold.tsx`, a native `<details>`): the estimated block, methodology, calibration,
  the line study, and the WATCH tier of "What to change" (7 cards, 6 of them the same
  sentence). `/proof/records` paginates by week — it was **3,681 rows and 255,202px**.
  **Measured:** Results 7,753 → **3,327px** at 1440 (16 → 12 headings, 5 → 3 tables) and
  7,811 → 5,662 at 375; Track record 9,159 → **2,840px** and 9,199 → 4,529. No horizontal
  overflow at either width. Web tests 414, Python 890.
  **The design rule that came out of it (Tate): "if it isn't obvious I don't want it."** He
  rejected three proposed Results charts as unreadable — a chart that needs a paragraph
  under it has already failed, and the plain big numbers ($103.60, +5.1%) are the right
  form there. Only the gap ladder earned one. **Screenshots caught four defects the DOM
  checks could not**: the break-even label rendered dark-on-green ON the tallest bar, the
  y-axis label clipped to "How often the under wo", auto-ticks came out 40/47/54/61/65, and
  the 4-card grid stranded one alone. **Look at the picture, not just `scrollHeight`.**
- **2026-09-13 (THE PAPER LEDGER WAS MEASURING ONE BUILD OUT OF FOUR).** Every one of
  week 2's 25 paper picks was placed Sat 12:00 UTC — the `sat_am` build. Across the week's
  six builds **33 distinct games qualified**; the ledger holds 25, and the FRIDAY card's
  **three clean BETs were never logged at all** against the one Saturday recorded (8 games
  that qualified Thursday never qualified again). Cause: `PAPER_WINDOW_HOURS` gave each slot
  the gap to the next build, and college football kicks off on **Saturday** — `thu_pm`'s 24 h
  reached 6 games on the whole slate, `fri_pm`'s 16 h reached 8, neither of them a priced
  Hard Rock game, and `sat_am`'s 80 h swept up the rest. The design was doing exactly what its
  comment said. **Tate's call: Friday anchors the weekend** — `fri_pm` and `sat_am` are now
  `None` (the rest of the week), `tue_pm`/`thu_pm` keep their gaps so they can never claim a
  Saturday game before Friday prices it. Replayed against the REAL week-2 payloads: Friday
  logs 26, Saturday adds 1, nothing double-logged.
  **Second, independent bug: `add_pick` never wrote `model_line_at_pick` /
  `model_score_at_pick`.** The Next.js `createPick` was the only writer in the repo, so every
  card paper pick and every `pick.py add` left OUR NUMBER NULL — which prints "—" in the picks
  table and, because `decision-quality.ts::beatMyModel` filters on `model_line_at_pick != null`,
  dropped the whole paper ledger out of the agreed/against split. `add_pick` now takes both;
  the card reads them off the item (`card.py` exports `under_score` beside `bv_line`, same
  prediction row) and `pick.py add` reads them through the new `picks.py::model_read`, which
  mirrors the web's rule (model row over the display-only `derived_lines` row). Week 2 is
  backfilled by two `_DATA_MIGRATIONS` entries: our number reconstructs EXACTLY as
  `hr_line_at_pick - gap_at_pick` (a card item only qualifies when Hard Rock priced it, so the
  gap basis is always `hardrock`) — verified to 0.000 on all 25.
- **2026-09-13 (every scheduled text retired; PR #118).** The Mac routines were **local**
  Claude sessions, and on battery this Mac sleeps after ONE MINUTE with no `pmset` wake
  events — so they fired only if the laptop happened to be awake. Measured:
  `cfb-saturday-card` ran **twice all season** (once two days late, once 6:45pm instead of
  8:50am, on the first real-money Saturday); `cfb-weeknight-card` **never fired on a Tue,
  Thu or Fri**; `cfb-sunday-ops` ran once, three days late. iMessage cannot move to the
  cloud (it needs the Messages app and `send-verified`'s local `chat.db` read-back).
  **Tate's call: no scheduled texts at all, and no fixed decision rhythm** — which dissolves
  the problem rather than fixing it. Deleted `cfb-saturday-card`, `cfb-weeknight-card` and
  two long-dead tasks; `ainhub-ai-daily-brief` is KEPT; `cfb-sunday-ops` is PAUSED until the
  new cron below is seen to fire on a real Sunday, then delete it. A deleted task leaves its
  SKILL.md on disk.
- **`sunday.yml` finally has a Vercel cron** (`/api/cron/sunday`, three Sunday entries,
  1pm–5pm ET window). It was the LAST workflow whose only trigger was GitHub's cron, and its
  last SCHEDULED run was **2026-09-06** — a week of nothing, on the only full-game opener
  capture, which also refreshes pace, weather, scoring and the derived 1H lines. Empty
  `inputs` (it declares one OPTIONAL `force`, unlike `grade.yml` which declares none and
  422s on any). `cronJobs.test.ts` already checks every entry lands whole in both DST regimes.
- **The board is now the ONLY failure signal**, so `web/lib/boardHealth.ts` (was
  `gradeHealth.ts`) reports stale RESULTS and a MISSED BUILD. A missed build means no card
  *and no line sweep*, which otherwise looks completely normal. The build check asks whether
  a `cards` row exists since the most recent build window OPENED — not a fixed threshold,
  which would have to tolerate the ~72h Sat→Tue gap and would then never fire.
- **When to look at the board** (measured on week 2): Hard Rock posts 1H lines Tue 31%,
  Wed 59% cumulative, Fri 78%, Sat morning 97% — and then they barely move (**48 of 71
  games never changed**, mean drift −0.18 pts). So waiting costs nothing on price; what
  improves is selection (BET-qualified by build: Tue 1, Wed 0, Thu 1, **Fri 3**, Sat 1).
  Best single look: **Friday after 5:30pm ET**, second: Saturday after 8:30am ET.
- **2026-09-13 (week-2 review; PRs #111-#115, all merged): THE SYSTEM DID NOT MEASURE ITS
  OWN WEEK.** `grade.yml` failed four consecutive runs from Sat 2026-09-12 morning and
  nobody knew for two days — the only failure channel is GitHub's failed-run email. Root
  cause: `backfill.py`'s FIRST action was an unguarded `backfill_venues()`, and CFBD
  returned 429. Week 2 finished with finals for **14 of 303** games, **0 of 31** picks
  graded, no CLV anywhere. Fixed in four layers: scores load BEFORE reference data and a
  venue failure warns instead of raising (a season failure is still fatal); the CFBD retry
  ladder is (5, 20, 60) over 4 attempts and honours `Retry-After`; `grade.yml` marks the
  two *enrichment* steps `continue-on-error` (PBP, factor ledger) while grading stays
  fatal; and the board carries a **stale-results banner** (`lib/gradeHealth.ts`,
  also on `/api/health`) so this can never again be invisible.
- **CFBD IS OUT OF MONTHLY QUOTA** (`{"message":"Monthly call quota exceeded."}`, every
  endpoint, resets ~Oct 1). No retry clears it — the wait is the rest of the calendar
  month, and CFBD sends **no `Retry-After`** with it, so until 2026-09-13 every call of
  every job spent the full 5/20/60s ladder and three extra calls against a budget already
  at zero. `cfbd.py` now raises **`CFBDQuotaExceeded`** on the spot (an `HTTPError`
  subclass, so existing handlers are unaffected), recognised by
  `x-calllimit-remaining: 0` or a "quota" body. Measured against the live exhausted key:
  1 call, 0.68s, was 4 calls + 85s.
  **The budget is now visible before it runs out:** CFBD reports
  `x-calllimit-remaining` on EVERY response (including the 429) and nothing read it,
  which is why this went unnoticed until grading had been dead two days.
  `CFBDClient.calls_remaining` holds the last value, every run prints it once, and under
  `_LOW_CALLS_WARN` (200) it raises a `::warning::` annotation. Tiers:
  https://collegefootballdata.com/api-tiers — free 1,000, Academic 3,000 (.edu), Tier 1
  $1/mo 5,000, Tier 2 $5/mo 30,000.
  **Scores now have a second source:**
  `sources/espn_scores.py` + `scripts/backfill_scores_espn.py` read ESPN's public
  scoreboard — no key, no quota — and ESPN's event ids ARE `games.id`, so it UPDATES
  scores on existing rows and never inserts a game, touches a team name or a line. It
  emits CFBD's key names so `etl/first_half.py` (incl. `line_scores_trustworthy`) applies
  unchanged. **ESPN cannot replace CFBD for SCORING**: no 247 talent composite, no SP+,
  no returning production — 8 feature columns are CFBD-only. Week 2 went 14 → 94 finals
  and all six real tickets graded exactly as the Hard Rock slips read.
  **The quota went on reference data**: `season_stats.py::_cached` writes to `data/cache/`,
  a GHA runner starts cold, and a feature build re-fetches sp/talent/roster/returning for
  every season (~17 calls) on all 26 card builds + 17 Sunday runs + 10 previews.
  `.github/actions/cfbd-cache` now shares that across each week's runs — keyed by ISO week
  with **no restore-keys on purpose**, since `_cached` has no expiry and a longer key would
  silently freeze SP+ at week 1. Tate is registering the **free Academic tier** (3,000
  calls, .edu) — if that is not enough, Tier 2 is $5/mo for 30,000.
- **2026-09-13 (LINE VALUE WAS REPORTED WITH THE SIGN INVERTED, PR #115).**
  `grading.py::clv_under` = `closing - bet`. Every bet is an UNDER and a HIGHER number is
  easier, so a line that **FALLS** after the bet is the GOOD one — **negative clv is
  favourable**. The glossary always said so; `decision-quality.ts` counted `clv > 0` as
  "moved your way" and `record.ts` fed the raw mean to every RecordCard's "Line value", so
  the site reported the share that moved AGAINST us. Stored values are UNCHANGED (the raw
  difference is the fact); the direction now lives in exactly two named places —
  `decision-quality.ts::favourable` and `record.ts` — and `lib/clvDirection.test.ts` pins
  it against Tate's real six week-2 tickets, so a "fix" to the sign fails CI. Displayed
  figures are negated: **+1.45 means the market came 1.45 pts toward us.**
- **2026-09-13 (week 2 graded — the first real measurement).** Real money **2-3, −1.18u
  (−$11.78)**; the bonus won, so **+0.36u (+$3.60)** all in. Paper **13-11, −0.57u**.
  **CLV is the good news: of 30 graded picks, 11 lines moved toward us, 18 flat, 1
  against** (+1.45 pts mean). **Model accuracy is the bad news.** Over 98 graded games
  (weeks 1+2) the model is LESS accurate than Hard Rock's number in every spread bucket,
  and on 21+ spreads it runs **−5.23** (book −1.79) while the 1.75-pt gate fires on **27
  of 36** of them. Realized 1H share rises with the spread (0.51 → 0.57 over 4,392
  historical games, again in 2026) and the model's is flat ~0.46 — `spread` is not in
  `FEATURE_COLS`. **Tate's call 2026-09-13: no model or gate change for week 3; fix the
  measurement, keep tracking.** Full review + every decision:
  `~/.claude/plans/here-are-all-the-hashed-lantern.md`.
- **2026-09-13 (THE LEVEL ANCHOR WAS TESTED AND REJECTED, PR #124).** Seeding
  `_season_to_date`'s expanding window with `k` synthetic games of prior-season form
  was the fix for weeks 1-2 being scored with 68 of 115 features NaN. **It does not
  work, and `etl/features.PRIOR_SEASON_WEIGHT` stays 0** (the seeded code ships inert;
  `k=0` reproduces the unseeded frame exactly, so the incumbent is an ARM of the gate).
  Weeks 1-2 showed nothing (pooled n=180, gains −0.019 to +0.131, every 95% CI spanning
  zero, not monotone in k); weeks 3+, which nobody was testing, improved monotonically
  (+0.038 to +0.117, CI excluding zero at k≥1) — the seed is ordinary shrinkage and helps
  where a team already has SOME data.
  **The NaNs were never the problem: `HistGradientBoostingRegressor` handles missing
  values natively**, learning a routing direction for them, so "no games played yet" is a
  usable SIGNAL to the tree rather than an absence. Counting NaN cells and concluding the
  model is starved conflates *missing* with *harmful*.
  **And MAE is close to blind to what the change does.** The seed genuinely lifts
  bv_line's level (2026 wks 1-2: 24.26 → 25.20 at k=3 against a realized 26.90, about a
  third of the bias) while MAE barely moves — ~1 pt of bias is nothing against ~11 pts of
  per-game spread. But the system spends `gap = line − bv_line` against `BET_GAP_PTS`, so
  a level shift moves SELECTION even when accuracy is flat: on the 23 of those games with
  a real close, the count clearing the bar fell 14 → 11. The gate now reports **bias and
  gate-crossings**, fixed before that question is put to the **still-untouched 2025**
  season. Do not rebuild this: read `docs/LEVEL_ANCHOR.md` and re-run
  `scripts/level_anchor_gate.py` (or the `level_anchor_gate` workflow).
  Two real defects shipped alongside: **`season_stats._cached` served an empty payload as
  a permanent hit** (the 2026 sp/adv/talent/roster/returning caches were all 2 bytes,
  written 2026-06-03, so any LOCAL 2026 feature build silently NaN'd eight more columns —
  GHA starts cold and refetches, which is why it hid for three months), and **a season
  whose priors cannot be fetched now warns instead of killing the build** (`_cached_soft`,
  the same trade `backfill.py` makes for venues).
- **2026-09-14 (EVERY WEATHER ROW WAS WRONG, AND "FORECAST" MEANT TWO THINGS).**
  Coverage was the reported problem (38.3%, 729/1,902 modelled games). The real one
  is that **all 2,647 outdoor rows were wrong**. Both writers asked Open-Meteo for
  `timezone=auto` and then indexed the **local** hourly array at the **UTC** kickoff
  hour — `Game.start_date` is naive UTC — so every reading was displaced by the
  venue's UTC offset, 4-10 h for US venues, onto the wrong calendar day for a late
  kickoff. LA Coliseum `2023-08-27 00:00Z` stored **63.2°F** (local midnight) against
  **78.1°F** at the real 5pm PDT kickoff; Cramton Bowl stored 93.6 against 99.8 via
  `backfill_enrichment.py`'s blind `T19` string-replace fallback. That is almost
  certainly why `docs/POST_MORTEM.md` calls `wx_temp`/`wx_wind` **noise in every row**
  while `factors/registry.py` still labels them tier 1 — the feature was never
  measured, it was measured wrong. Fix is `timezone=UTC` everywhere, which makes the
  hourly index equal the UTC hour; the ERA5 lookup then returns 78.1 and 99.8 exactly.
  `sources/weather.py` had **zero tests** and **no retries** (a 429 and a network error
  both returned `{}` — that is the 647 `empty` venues in `data/backfill_weather_full.log`
  and why coverage stalled at 21%); it now shares `sources/_http.py` with `cfbd.py` and
  raises `WeatherUnavailable`.
  **Second, and it reshaped the design: "the forecast before kickoff" is not one
  thing.** Open-Meteo's Historical Forecast API stitches the first hours of successive
  runs, so it TRACKS ACTUALS — measured over 12 real kickoffs it sits **1.82°F / 1.55mph**
  from the ERA5 actual, closer than a 1-day-lead forecast (2.30 / 1.67) or a 3-day
  (3.55 / 2.26). Calling it decision-time would have been look-ahead bias. So the new
  **`weather_obs`** table keys on `(game_id, lead_hours)` and stores `decision_safe`:
  **lead 0 = near kickoff, never decision-safe**; **leads 24/72 = the Previous Runs API**,
  the forecast that genuinely existed that far ahead, and the ONLY rows a market-edge
  study may use. Fixed-lead **wind/gusts/precip start with the 2024 season** (2023 is
  temperature-only), max lead is 7 days, and the model is **pinned to `icon_seamless`**
  because the default `gfs_seamless` returns **gusts BELOW the mean wind** from 48h out
  (7-9 of 18 samples; icon 0/18 at every lead). Gusts are captured for the first time.
  **Repairing the data does NOT activate it**: the backfill writes a table nothing reads,
  and `etl/features.py::WEATHER_OBS_LEAD_HOURS` ships `None`, reproducing the legacy
  frame exactly — the incumbent is an ARM, same shape as `PRIOR_SEASON_WEIGHT = 0`.
  Venue coordinates were audited BEFORE spending the requests (720 venues, lat
  21.29→53.34, lon −157.82→−0.28, **zero** lat/lon swaps despite `backfill.py:183-184`'s
  GeoJSON `x`/`y` fallback); `etl/venues.py::coord_problems` is the standing guard and
  the backfill refuses to start on a bad pair. `backfill_enrichment.py`'s weather path
  is DELETED. Read `docs/WEATHER.md` before touching any of this.
- **2026-09-14 (THE CENSORING PREMISE WAS TESTED AND THE MARKET WINS).**
  The two-team probabilistic engine was to exploit the fact that an underdog's 1H
  score is censored at zero and the censoring grows with the spread. **It is not
  being built.** `scripts/censoring_study.py` (report: `docs/CENSORING_STUDY.md`)
  asked the only question that matters — *does censoring leave information the
  PRICE has not already absorbed?* — by controlling for the book's own de-vigged
  probability and testing whether spread still predicts the Under. On 1,873
  decided games with a real 1H close: **spread coef +0.00369/pt, bootstrap 95% CI
  [−0.0083, +0.0157], includes zero.** The sign FLIPS by season (+0.0057 / −0.0038
  / +0.0093); out of sample it improves Brier in the fourth decimal (0.25040 →
  0.25029); and taken at face value it is worth **+1.94 pp across the whole 7-to-28
  spread range against a 2.38 pp vig hurdle**. Bucket diffs are non-monotone
  (−1.4 / −0.1 / +2.7 / **−6.2** / **+6.7**) with every Wilson interval spanning
  the implied value.
  **The mechanism is real — that is the useful part.** Dog 1H shutout rate runs
  8.6% → 12.0% → 16.3% → 17.0% → **23.1%** by spread bucket while the favourite's
  falls to **0.0%**. So the finding is not "no censoring", it is "the censoring is
  real, strong and monotone, and the market prices it correctly."
  **Correction to an earlier figure:** the 37.6% dog-shutout rate at 28+ quoted in
  planning is from the full 3,601-row population; on the real-close cut it is
  **23.1%**. The unpriced games are not a random sample. Split on `line_real`.
  **PUSHES ARE NOT OPTIONAL when comparing a de-vigged price to a hit rate.** A
  two-way de-vig gives `fair_over + fair_under = 1` and so carries NO push mass.
  27% of 1H closes are integer totals and those push **5.66%**; the Under rate is
  48.74% counting pushes and **49.49% among decided games**, a 0.75 pp gap — the
  same order as the effect being hunted. On an integer line a push VOIDS the bet,
  so the book's two prices already price `{under|decided}` vs `{over|decided}`:
  compare against the DECIDED rate and report push rate separately.
  **New, and reusable:** `beatvegas/backtest/censoring.py` carries the repo's first
  `brier`, `log_loss`, `brier_multi`, `wilson` and `reliability` — there was no
  proper scoring rule anywhere before (the only model probability, `score.py`'s
  `predict_proba`, is uncalibrated and squashed into `under_score` without ever
  being scored). Written THREE-OUTCOME-aware so a future engine emitting
  P(under)/P(push)/P(over) is graded by the same functions and its numbers stay
  comparable. Also validated for later: the dog's 1H score is extremely lumpy
  (7/10/0/14/3 = 63% of games), so any future scoring model must be **discrete**.
- **Decided, NOT yet built (next session):** delete `MovementChart.tsx` + its
  `GameDetail.tsx:165-170` call site and the now-dead `movement.ts::pivot` — keep
  `BookTable` (Tate: the graph "looks like scribbles"; the per-book list stays); and mark
  already-placed bets in `AnswerBar` (muted + a marker, sorted below open ones — the data
  is already on `HomeGame.picked`, `answerBar.ts::buildAnswer` just never sees it).
  (The Results / Track record rework SHIPPED — see the PR #122 bullet above.)
- **2026-09-10 (full system review, PR #98, MERGED):** a code + security pass over the
  engine, the workflows and the site. **Two things were actually broken.**
  (1) `grade_records` was the ONLY one of eight grading paths that skipped
  `grading.trusted_first_half_total`, so a line-score false zero would have booked a
  fabricated UNDER win into the records grid, the credibility ledger and bv_line
  recalibration. Nothing live was corrupted (no graded rows yet, no false zeros on file);
  the fix is preventive and its test fails against the old code.
  (2) A mid-sweep Odds API 5xx/429 produced **NO card at all** — `poll_lines` exits 1 after
  writing its status file and `card.yml`'s sweep step had no `continue-on-error`, so the job
  died before `build_card`. The sweep now continues on error and a final `always()` step
  fails the run: the card ships DEGRADED **and** the failed-run email still goes out.
  `sources/odds.py` gained the retries `cfbd.py` always had (the free API retried; the paid
  one did not).
  **Security:** `next` 16.2.7 → **16.3.4** (1 critical + 3 high; prod `npm audit` is now 0).
  The auth cookie was literally `sha256(APP_PASSWORD)` — unsalted, so a leaked cookie was
  permanent access *and* a fast offline crack of the password; it is now
  `v1.<issuedAt>.<hmac>` under a **PBKDF2-derived key memoised per instance** (100k
  iterations would otherwise be paid on every request the middleware sees), with the
  issued-at inside the MAC so a stolen cookie ages out server-side. `POST /api/login` has a
  per-instance throttle (10 per IP per 15 min). **The middleware matcher's exemptions were
  unanchored prefixes** — `/api/healthz`, `/api/cronjobs`, `/loginhelper` would all have
  been public the moment anyone added them; anchored and verified in prod. `next.config.ts`
  gained security headers (the board was framable). Actions pinned to SHAs +
  `permissions: contents: read` on all twelve, with `.github/dependabot.yml` as the other
  half of that trade.
  **Money path:** `uq_manual_pick_per_ledger` — a partial unique index on
  `(game_id, COALESCE(market,'1H'), COALESCE(is_paper,false))`, because Postgres treats
  NULLs as distinct and legacy rows carry NULL in both. The cap + duplicate check were three
  round-trips with no transaction; a double-click could log twice or reach six bets.
  `updatePick`/`deletePick` are one guarded statement now. None of the pick endpoints had
  any try/catch, so a Neon blip showed `failed (500)`.
  **Measured** (raw queries per render, counted against a live server): `/results` 34 → 26,
  `/game/[id]` 36 → 26, via React `cache()` on `loadPicks`/`loadResults`/`getBoard`/
  `getLineCheck`. Routes 25 → 14. `app/error.tsx` + `not-found.tsx` added — there was no
  error boundary anywhere, so one bad table took down all of `/results`.
  `sunday.yml`'s three crons each spent 6 Odds credits; the capture is gated on a
  full-game snapshot already written today (ET), `force` to override.
  Tests: Python 837 → 856, web 372 → 389. Plan:
  `~/.claude/plans/run-a-complete-code-review-glistening-hippo.md`.
- **2026-09-10 (site restructure, branch `board-and-game-page`, NOT merged):** the site
  goes to **three tabs — Board / Results / Track record — plus `/game/[id]`**. A board row
  is now a **LINK**, never a disclosure: `GameCard` is deleted, `GameRow` carries only the
  rank badge, matchup, kickoff, Hard Rock's number and price, one action line, and the two
  chips that change whether to bet (`bet logged`, past the cap). The badge is **rank plus
  colour with no tier word** ("Watch" was true of 35 of 49 games, so it discriminated
  nothing; `ScoreBadge` takes `label={null}`, and still names the tier to screen readers).
  Everything analytical lives on the game page: the decision block with a **gap bar**
  (`GapBar.tsx` — our number against the line on one axis, split at `BET_GAP_PTS`, kill
  number ticked), Lines, What is behind it, Injuries and news. **There is no "Our number"
  section** — Tate cut it as a repeat of the decision block, which also took the 0-100
  score, the confidence meter and the 7-35 range off the page (the score still sets the
  tier and the ranking). An **answer bar** (`AnswerBar.tsx` + pure `lib/answerBar.ts`)
  replaces `BankrollStrip`/`BetSlip`/`CardPanel` at the top of the board and carries the
  live bets, the three closest with the action trimmed to its "needs …" clause, and the
  next build window from `lib/nextBuild.ts` (derived from `CRON_JOBS`, stated as a WINDOW
  because Vercel Hobby fires within the hour). **Nothing renders below the last game row.**
  The slip, card panel, card status banner and bankroll strip now sit at the **TOP of
  `/results`** — `/slip` was built and deleted the same day. `lib/labels.ts::distinctTag`
  drops a blocker tag the action line already says (they share a blocker, so most Watch
  games printed the sentence twice). `CardPanel` rows link to `/game/[id]`, so its
  `onBoard` prop and the "Not on the board" fallback are gone. Week 2: 11,608px → 7,329px,
  839KB → 198KB HTML; web tests 336 → 351.
  **Results + `/proof` shipped the same day (see the next bullet).**
  **Team logos shipped 2026-09-10** (see the bullet below). The eleven legacy redirect
  files are gone as of the system review below — as `next.config` redirects, not deletions,
  so every old bookmark still resolves.
  Audit, per-page layouts and every decision: `~/.claude/plans/i-like-a-lot-cuddly-dusk.md`
  and `~/.claude/plans/session-handoff-beat-staged-sutton.md`.
  **Screenshot with headless Chrome, never the Browser pane** (it caps captures at 800x500).
- **2026-09-10 later (Results reorganised + `/proof` built, same branch):** the nav is now
  **three tabs — Board / Results / Track record — plus `/game/[id]` and `/proof/records`**.
  `/research`, `/research/records` and `/glossary` are redirect stubs; `lib/research.ts` is
  now `lib/proof.ts` (the gap-vs-line-value table died — n=1 buckets).
  **Results** (5,000px → ~2,300px) is the money page: slip block, then a **bankroll hero**
  (`BankrollHero.tsx` — bankroll at display size, units, ROI, curve beneath; `BankrollStrip`
  gave those numbers up and keeps the cap + the rules), then only the record cards that have
  data, then the review tables and the 9-column picks table (three frozen fields behind a
  per-row expand that composes with, and does not fight, the edit form). **An empty section
  is ONE LINE, never a card** (`Section` / `EmptyLine` / `.bv-empty`) — week 2 had eight
  placeholder boxes. The per-week scorecard is deleted; "closest to a bet" is gone from
  `CardPanel` (the board's answer bar already names them, off LIVE lines rather than the
  frozen card).
  **`/proof`** is organised **by grading basis, not by era** — the same cap-5 rule returns
  +15.9% at the real close and +5.4% at the estimate, so real closes lead (Hard Rock's own
  number counts as real) and the estimated block sits under a divider with every number
  **NEUTRAL**: green and red only ever appear on a real closing line, and `RecordCard` /
  `BandTable` take `basis="estimated"` to enforce it. 60.8% leads with three caveats —
  169 bets, a cap applied to the history afterwards rather than lived, and no Hard Rock in
  those seasons. **The coverage caveat is WRONG for this cut** and was dropped: within
  `fbs_only`, 1,902 of 1,934 games carry a real close (98%); the unpriced games the gotcha
  below warns about are almost all non-FBS and are already excluded (`postmortem.ts::coverage`
  reads those counts from the data). The **real-close gap ladder** (48.4 / 44.5 / 53.9 /
  54.9 / 58.8) is on the site for the first time — only the estimated one was ever shown.
  `PostMortemPanel` is broken into `BandTable` / `PmFlags` / `PmLiveNotes` + the shared
  `RecordCard`. `--header-h` is UNCHANGED and was measured, not assumed (97px at 375, 69px
  at 640/1440): the nav takes its own full-width row below `sm` whatever the label count.
  Three fixes rode along: **a bonus bet no longer spends a cap slot on screen**
  (`picks.ts::countsAgainstCap`; the server already excluded them, the display did not, so
  the site said 2 of 5 when four slots were free); **the line study buckets over the UNION
  of seasons** and defaults to all of them (per-season bucketing then merging drops any
  total under `minGames` in every single year, and 2026 has none that clear it); and
  **`LineStudyView`'s bars were invisible** — under Recharts 3.8 they animate up from
  height 0, the animation never completes, and a zero-height rectangle renders as an empty
  group, so `isAnimationActive={false}` is load-bearing there. Web tests 351 → 368.
- **2026-09-10 (team logos):** a small **18px mark before each team name** on the board row
  and the `/game/[id]` header — nowhere else, and **no fallback**: a team with no artwork
  renders NOTHING (no circle, no initials, no reserved box). The marks are **vendored**,
  not hotlinked: `scripts/fetch_team_logos.py` pulls CFBD `/teams` and writes 264 FBS+FCS
  PNGs into `web/public/logos/<cfbd id>.png` (929 KB of actual bytes; `du` reports 1.4M because
  264 tiny files each take a 4 KB block) plus the index `web/data/team_logos.json`,
  refreshed each August alongside `fetch_fbs_teams.py`. **Use the `logos-dark/` variant** —
  it is the dark-background artwork (Iowa's black Hawkeye renders gold), which is what the
  navy canvas needs. The ids are the ones `games.home_team_id` already stored and never
  selected; `board.ts` now carries `awayTeamId`/`homeTeamId`. The script composites every
  mark over `--bg-2` and PRINTS the low-contrast ones rather than shipping a navy blob
  (only Montana, 1.86, on the 2026 set — legible, kept). **The mark is centred on the text's
  CAP BAND, not sat on the baseline** — `vertical-align: calc(0.355em - var(--bv-logo-size)/2)`,
  because Archivo's cap height is 0.71em; one rule covers both the 16px row and the 24px header,
  where a single em value could not (the mark is a fixed size, cap height is not). Measured
  centring error: 0.01px on the board, 0.00px in the header. Spacing is an even **6px each side
  of the mark** (9px in the header) via `margin-right: 0.375em` plus a `margin-left: 0.1394em`
  that tops the preceding word space up to match; the `@` keeps the natural word gap, which binds
  each mark to its own name. **Do not use `word-spacing` for this** — it also loosens the space
  INSIDE a name ("Southern Miss", "Oklahoma State"), and the literal text spaces must stay because
  they are the matchup's only line-break opportunities on a phone. `web/data/team_logos.json` is
  web-only and deliberately NOT in `dataMirror.test.ts`; `lib/teamLogos.test.ts` guards the
  index against the vendored files in both directions. `TeamLogo` uses `next/image` with
  `unoptimized` — a bare `<img>` would be the repo's first lint warning, and the files are
  already the size they render at. **Measured cost:** desktop is free (page height identical
  at 1440); at 375 the board grows 520px (+5.5%) and matchups on two lines go 18 → 38 of 49.
  Tate accepted that rather than shrinking or hiding the mark on phones. Web tests 368 → 372.
- **2026-09-09 night (PR #94, merged):** the board **ranks** instead of scoring. Each card's
  badge is its place on the week (`#1` = best), assigned in `homeBoard.ts::assignBoardRanks`
  over the whole board inside `getHomeBoard` — before `page.tsx` filters, so a day or team
  filter never renumbers. A kicked-off game has no rank: `inPlayAt` (5 h) gives it LIVE,
  then FINAL, then the result word. **A live BET card is lit green** (`.bv-card--lit`:
  `--good` border + `--good-bg` wash, plus a hover companion because `.bv-card:hover`
  hard-codes cyan); Watch and Pass are untouched, so lit means act. The 0-100 score still
  sets the colour, still decides the tier, and still drives Results/Research — it moved
  inside the card under "Our number", and the glossary gained a Rank entry. `capRank` is
  unchanged but renders as "cap slot" so it can't be read as the board rank. Two fixes rode
  along: `sortGames` now breaks a score tie on **gap** (the score clamps at 100 and a slate
  can pin a dozen games there — kickoff order was silently deciding "best game of the
  week"), and a played-but-ungraded game says FINAL rather than claiming to be live.
  Spec: `docs/superpowers/specs/2026-09-09-ranked-board-design.md`.
- **2026-09-09 evening (PRs #87-#92, all merged; real money Sat Sep 12):** four changes
  landed together. (1) **Per-event 1H calls cost 1 credit**, not 2: `odds_api.bookmakers_1h`
  names ten books, which the Odds API bills as ONE region and which overrides `regions`
  (verified live — same event, same eight books incl. `hardrockbet`, half the credits).
  The BULK full-game pull still prices by region and needs `us_ex`; an 11th book key
  doubles every sweep, so `sources/odds.py` refuses to start with one. (2) **Four decision
  builds a week** replace the daily morning card: `tue_pm`/`thu_pm`/`fri_pm` (~4:05pm ET)
  and `sat_am` (~8:05am ET), all status `final`, paper windows 48/24 h midweek and the
  REST OF THE WEEK on Friday and Saturday (they were 48/24/16/80 h = the gap to the next
  build until 2026-09-13; see the top bullet). `manual` builds publish but paper-log NOTHING. Expected spend
  ~567 credits/wk (was ~1,308) on a measured basis of **82** HR games, not the 60 the old
  comments assumed. (3) **A Vercel cron is the primary trigger** (`web/vercel.json` ->
  `/api/cron/[job]`, table in `web/lib/cronJobs.ts`); GitHub cron is the backup and the
  `cards`-row probe now suppresses a duplicate DISPATCH too (`force=true` overrides).
  (4) **Bonus bets + pick editing** — see the gotchas.
- **Board:** anchor jumps from the bet card now clear the sticky header (one `--header-h`
  property drives `scroll-padding-top` and the day heading); a card row whose game is not
  on the board reads "Not on the board" instead of a dead link.
- **2026-09-08 (site rebuild + rolling week, PRs #76-#81; real money from week 2, Sep 12):**
  the board (`/`) is ONE rolling week grouped by ET day; each game locks at its own kickoff.
  Grade = a coloured 0-100 **score** (`web/lib/grade.ts`: 70+ green/bet, 55-69 amber/watch,
  <55 red/pass; settled games colour by result), scaled so a gap of exactly `BET_GAP_PTS` at a
  fair price = 70 (`edge.ts`/`card.py` `SCORE_PER_GAP_PT`). "EDGE" renders as **Watch**. A
  strong-but-blocked game keeps its colour and carries a plain tag (`lib/labels.ts::blockerTag`).
  Score/gap basis = Hard Rock's line → market consensus → our reference line, said in words;
  a real-money BET still needs Hard Rock's own line. **Model minimum is 0 games** (every FBS
  game scored off last season's priors; rows with <2 games carry `h/a_games_played` → "early
  season" tag). Schedule, credits and triggers: see the 2026-09-09 bullet above.
  `grade.yml` runs daily 6:30am ET; `lines_watch` opener crons retired.
  Every raw enum goes through `lib/labels.ts`; no Trust page, no honesty
  caveat line (Tate). Specs: `docs/superpowers/specs/2026-09-08-*.md`. Dev on a network that
  filters Neon:5432: `NEON_HTTP=1` in `web/.env` (Prisma Neon adapter over 443).
  **Score is gap only (no price bonus, no off-market/QB-out penalty) since 2026-09-09**, floored so
  70 ⇔ gap ≥ 1.75 exactly; no-model rows are always Pass; the settled colour only grades against a
  real book line (Hard Rock, else market) — a reference-only played game shows a neutral final.
- **2026-09-01 (week-1 audit, PRs #23-#26):** verdict logic (BET / WATCH / PASS + why,
  `web/lib/verdict.ts`) behind the board; `/board` redirects to `/` since 2026-09-02. Betting rules live in
  `docs/BETTING_POLICY.md` ($100 roll, $10 flat units, ≤5 bets/wk, 1H unders only).
  **Gates are in POINTS from the validated top-20%-by-gap rule (≥1.75 pts) — never
  σ:** `bv_sigma` ≈ 12 pts is per-game outcome noise, so a 1σ gap never occurs.
  Paper picks (`manual_picks.is_paper`, stake forced to 1 flat unit so units/ROI are
  comparable) sit apart from the real ledger. Sunday job now refreshes pace/weather before scoring; Monday job refreshes
  1H PBP and grades `game_records` + the factor ledger. (Grading is daily and the
  model minimum is 0 games since 2026-09-08 — see the top bullet.) **Florida platforms (verified
  2026-09-01):** Hard Rock Bet is still the only sportsbook; "FanDuel in Florida"
  = FanDuel Predicts (CFTC prediction market), not a sportsbook. Exchanges
  (Kalshi/Novig/ProphetX/BetOpenly, Odds API `us_ex`) are captured on the Sunday
  full-game poll only as a no-vig PRICE-COMPARISON source (`web/lib/books.ts`
  `EXCHANGE_KEYS`) — never bet there (no 1H totals). See `docs/BETTING_POLICY.md`.
- **What ships today:** decision-support for **full-game + 1H unders on Hard Rock Bet** (the only FL book). The model number is a reference chip, not a pick gate; the edge is *measured* via CLV, not promised (full-game backtest found no edge on the thin 2023-25 regime).
- **2026-09-06 (post-mortem):** `scripts/post_mortem.py` (pure math in `beatvegas/postmortem.py`)
  regrades every rated game vs its outcome — the 2023-25 walk-forward ratings at the flat 0.52 AND
  the fair step proxy (FBS-only + all), plus the season's cards at Hard Rock's numbers — into
  `postmortem_runs/buckets/games` (last step of `grade.yml`) and `docs/POST_MORTEM.md`; the Results
  page renders the headline records, rating bands and change flags (`web/lib/postmortem.ts`).
- **2026-07-17 (review closed):** the pre-season readiness review is fully worked
  off — blockers (PR #16), 13 should-fixes (PR #17), and the remainder (S8 strict
  pick matching, S15 postseason capture, S16 multiplier margin gate — fitted curve
  REVERTED to flat 0.52, S17-S19, S21-S22, nits). Accepted as-is: GHA cron lag
  (S20), sunday.yml DST double-fire (N12), plaintext local keys (N14), no login
  rate limit (store-less); N13 is moot since the push-notification layer was removed 2026-09-02. Since PR-1 data plumbing
  (2026-09) the Odds API bulk pull requests `totals,spreads` together (4-6 credits per slate), so each
  book's row carries its home spread; `Game.spread` is the run's cross-book median and Monday's CFBD
  upsert no longer clobbers Odds-API-sourced totals/spreads (`*_source` columns + `line_sources.py`).
- **2026-07 (Hard Rock pivot, PRs #7-#9):** multi-book capture incl. Hard Rock via The Odds API (`hardrockbet`; the `hardrockbet_fl` key folds onto it at write time); web views `/preview`, `/line-check`, `/weekly-review`; both markets logged + graded (`manual_picks.market`, `market_fg` ledger). Before season: GH secrets set, `odds_api.regions: "us,us2"`. (The phone push-notification layer shipped here was removed 2026-09-02 — failure alerts are GitHub's failed-run email + the routines.)
- **2026-06 (cloud + board):** Neon-writing jobs run in GitHub Actions, not launchd (campus network can't reach Neon:5432; DK 403s GHA IPs → CFBD `/lines` fallback). Derived-1H lines post to the board as "DERIVED · no model pick"; board query is season-scoped.
- **2026-05 (opener capture):** Sunday DK full-game opener via free hidden API + gated spread-adjusted 1H multiplier (`data/multiplier.json`; absent = flat 0.52). Next.js on Vercel is the product (Streamlit removed).
- **2026-09-02 (FBS-only training):** the `games` table holds every CFBD game incl.
  FCS/D2/D3, and from 2022 CFBD carried lines for FCS games, so ~40% of trainable
  rows in 2022-25 had no FBS team. `etl/fbs.py` + git-tracked `data/fbs_teams.json`
  (per-season CFBD `/teams/fbs`, refresh each August via `scripts/fetch_fbs_teams.py`;
  run `scripts/fetch_team_logos.py` in the same pass — see the team-logos bullet)
  now filter training/backtest/scoring to FBS-vs-FBS. Like-for-like on demo.db
  (2015-25, flat-0.52 proxy): gbm_v2 top-20% 53.9%/+2.9% → **55.7%/+6.3%**, 7 of 8
  seasons profitable (2018 the loser). Still proxy-graded: realized FBS 1H share is
  ~0.51, so the 0.52 proxy flatters unders; proxy re-fit is a separate open item.
  Details: `research/swarm/2026-09-01-1h-under-edges/FBS_FILTER_RESULTS.md`.
- **2026-09-02 (fair proxy):** `data/multiplier.json` is now a STEP share fitted
  MAE-optimally on FBS-vs-FBS games with spreads (2023-25): **0.4975 of the total
  below a 21-pt spread, 0.5375 at 21+** (walk-forward MAE 8.289 vs 8.347 flat,
  cleared the 0.05 gate in `derive_multiplier.py`). The mean 1H ratio is ~0.52 but
  the MEDIAN game lands near half the total, which is what books post. Against this
  fair proxy the proxy-graded edge disappears: gbm_v2 top-20% = 50.2% / -4.1% on
  2023-25 (was 58.5% / +11.6% at flat 0.52) and 52.7% / +0.6% on 2015-25. The old
  54-56% reads were the flat-0.52 artefact. The model is a reference number; only
  real-line CLV can show an edge. Details: `research/swarm/2026-09-01-1h-under-edges/PROXY_FIX_RESULTS.md`.
- **Engine:** market-blind 1H-total regressor ranks the board by line-vs-prediction gap (`score_slate`, gbm_v2). Proxy-graded selection stats are no longer quoted as an edge (see fair-proxy note above); 117-factor framework in `beatvegas/factors/`.
- **History & details live in:** git log + PR descriptions, `docs/` (`PIVOT.md`, `BV_LINE.md`), `~/.claude/plans/`, and this project's memory dir (auto-loads). Read those instead of reconstructing from this file.

## What it does
Pulls free data (CFBD, **bulk play-by-play via cfbfastR parquet + CFBD /plays**,
TeamRankings tempo, Open-Meteo weather, The Odds API 1H totals), derives ground-truth
1H points, builds leak-free features (incl. **1H-specific PBP factors**: EPA/success/
explosive/opening-drive/havoc/redzone/4th-down), predicts each game's 1H total with a
market-blind regressor, ranks the board by line-vs-prediction **gap** (the mispricing
signal), tracks line movement, and grades market vs model vs
the user's own picks. Also generates a weekly report (`scripts/weekly_report.py`).

## Architecture
- **Engine** (`beatvegas/` + `scripts/`): capture → enrich → score → grade,
  run by **GitHub Actions** (`.github/workflows/`: `sunday.yml`, `lines_watch.yml`,
  `card.yml`, `grade.yml`, `research_preview.yml`). No notification code: GitHub emails
  failed runs. Nothing runs the engine on the Mac, and **since 2026-09-13 nothing texts
  Tate either** — every scheduled routine was retired (see the bullet below). The bet
  card is built in the cloud (`card.yml`; slots in
  `beatvegas/ci.py::resolve_slot`: `tue_pm`/`thu_pm`/`fri_pm` ET-gated 3:45–5:15pm and
  `sat_am` ET-gated 7:45–9:15am — four whole-week decision builds timed to when Hard Rock
  actually posts 1H lines; `manual` on dispatch is always a `preview`. Builds are triggered
  by a **Vercel cron** dispatching the slot by name, with GitHub cron as the backup; the
  `cards`-row probe (never `gh run list`) now suppresses a duplicate DISPATCH as well as a
  duplicate cron, so the two triggers cannot both build — `force=true` overrides.)
  `rescore.yml` (dispatch: season + week) re-scores a past week without snapshots.
- **DB**: SQLAlchemy. `DATABASE_URL` env → Postgres (Neon); else local SQLite
  (`data/beatvegas.db`). See `beatvegas/config.py::database_url` + `db/store.py`.
- **Dashboard**: Next.js app in `web/` on Vercel, reading/writing Neon, is the
  product (the old Streamlit dashboard was removed — see git history if you need
  the original `_score_color`/chip reference). Plain-English copy + a modern
  "sportsbook" visual system (deep navy + electric-cyan accent; green/red reserved
  for under/over outcomes) live in `web/app/globals.css` (`.bv-*` component classes).

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
cp config.example.yaml config.yaml   # add CFBD + Odds API keys (gitignored)
pytest -q                            # run `pytest -q` / `cd web && npx vitest run` for current counts
```
Inside a **git worktree** run tests as `PYTHONPATH=. python -m pytest -q` — the venv's
editable install points at the main checkout, so a bare `pytest` imports the wrong tree.
Key scripts: `backfill.py`, `backfill_enrichment.py` (pace),
`backfill_weather.py` + `weather_validate.py` (weather -> `weather_obs`), `weekly_update.py`
(score), `poll_lines.py` (1H lines), `grade.py`, `pick.py`, `line_study.py`,
`retrain.py` (logs model_runs + BV calibration), `backfill_bv_line.py`, `seed_demo.py`.
**Pivot scripts**: `backfill_pbp.py` (1H PBP aggregates → `fh_team_game`),
`backfill_context.py` (venue/talent/roster), `rank_factors.py` (factor ranking →
`factor_scores`), `validate_engine.py` (gbm_v2 gate + MAE ablation), `inspect_combo.py`
+ `explain_pbp.py` (factor deep-dives), `weekly_report.py` (markdown board), `deploy_neon.py`
(additive Neon push). **Opener/cloud scripts**: `poll_full_game.py` (full-game capture,
`--source dk|cfbd|auto|oddsapi`; prod uses `oddsapi`), `derive_multiplier.py` (gated spread
multiplier), `backfill_spread.py` (surgical `Game.spread` from CFBD), `deploy_neon_games.py`
(additive games+spread push), `post_derived_lines.py` (writes display-only `derived_lines`
predictions for the board), `build_card.py` (the weekly bet card → `cards` row + paper picks
via `beatvegas/picks.py::add_pick`, the same insert `pick.py add` uses), `residual_gate.py`
(one-shot walk-forward report: residual engine vs incumbent vs the close, dispatched by
`.github/workflows/residual_gate.yml`; the report itself is the doc). **Sim/dev scripts**: `pg_sim.py` (throwaway local PG16 sandbox at
`~/.cache/beatvegas/pg_sim`) + `simulate_week.py` (replay a real week into it, rendered by
the real Next.js app, Neon-isolated). **Lint/format**: `ruff check` + `ruff
format` for Python (`[tool.ruff]` in `pyproject.toml`, pragmatic F/E/I/B set — NOT pyupgrade,
which would break the py3.9 runtime); `npm run lint` + `npm run format` in `web/`
(ESLint flat config via Next 16's native arrays + Prettier).

## Honest status of the edge (don't oversell)
- Backtest is **proxy-graded** (no free historical 1H lines). The proxy is the
  step share in `data/multiplier.json` (~0.50 of the total, 0.54 in 21+ blowouts),
  fitted on FBS-vs-FBS games. Real Hard Rock/DK lines collected forward are the true test.
- **Predict-total engine (gbm_v2) shows NO proxy-graded edge against the fair proxy**
  (top-20% by gap 50.2% / -4.1% on 2023-25; 52.7% / +0.6% on 2015-25). The earlier
  54.0% / +3.0% and 55.7% / +6.3% figures were graded against a flat 0.52 line that
  sits ~1 pt above fair and flattered every under selection.
- **The proxy-under ROI is partly a PROXY ARTIFACT**: the flashy proxy-leaders
  (1H explosive/turnovers) actually correlate with *more* 1H scoring — they win the
  under via the flat-0.52 proxy over-pricing low-1H-share games, not real low scoring.
  The `corr_1h` diagnostic (`rank_factors.py`) measures genuine 1H-scoring signal,
  immune to this. **Genuine signal = pace + efficiency/scoring levels.**
- The heavy PBP backfill **did not improve 1H-total prediction** (MAE ablation in
  `validate_engine.py`: 9.22 full vs 9.18 without) — base features already capture
  it. PBP factors confirmed the thesis + exposed the artifact; they stay as display
  chips and could be trimmed from the predictor.
- **ALWAYS split the post-mortem on `line_real` before concluding anything.** Only 1,902
  of the 3,601 `hist_2023_25` rows carry a real captured 1H close; the other 1,699 are
  proxy-graded, and they are not a random sample — they are the games no book priced.
  Measured 2026-09-09: model bias by spread reads −0.70 / +0.37 / +0.53 / +2.00 over all
  3,601 rows, but the whole effect sits in the unpriced games (+3.36 at 28+) while the
  book-priced ones are flat (−0.47 at 28+), and wide-spread bets swing from −20.8 units
  at the proxy to +1.3 at the real close. This is the same artifact as the flat-0.52
  bullet above, one level up: it bites analysis of the model, not just of factors. State
  which grading basis every number came from, and the n for the real-line cut (thin at
  width — 72 games above a 28-pt spread).
- The edge is real but **small and unconfirmed**. The system's job is to *measure* it
  honestly vs real lines, not to promise profit.

## Web app (`web/`) — shipped + redesigned
Next.js (App Router) + TypeScript + Tailwind v4 + **Prisma** + **Recharts**, live on
Vercel (Neon-backed, password-gated) at https://beat-vegas.vercel.app.
- **Views (3 tabs)** — Board / Results / Track record, plus `/game/[id]` and
  `/proof/records`. Historical description of the old four-tab shape follows; see the
  2026-09-10 bullets above for what ships now. Board (`/`, THE home page — the week grouped by day, every game with a
  Hard Rock total, coloured **rank badge** (`#1` = best game of the week, assigned over the
  whole board before filters so a filter never renumbers; no rank once a game kicks off —
  it reads LIVE for 5 h then FINAL, then the result) + Bet/Watch/Pass word + action line from
  `web/lib/edge.ts` + `web/lib/grade.ts`, composed by `web/lib/homeBoard.ts`; bankroll strip,
  day/my-teams/Hard-Rock filters, expandable cards with Lines / Our number / What is behind it /
  Injuries and news, writable picks via `POST /api/picks`), Results (market/model/you ledgers with
  line value + bankroll curve + post-mortem), Research (accuracy, gap vs line value, line study),
  Glossary (15 terms). `/board` redirects to `/`. Grade bands live in `web/lib/grade.ts`
  (`SCORE_BET_MIN`/`SCORE_WATCH_MIN` mirrored in `model/score.py`); every enum label lives in
  `web/lib/labels.ts`; the point gates are exported from `model/score.py` and parity-tested
  against `verdict.ts`. API routes read the same SQL
  the page loaders use; the app is locked by `middleware.ts` + `APP_PASSWORD` cookie.
- **Design system**: plain-English copy + a modern sportsbook look in
  `web/app/globals.css` — deep-navy canvas, electric-cyan brand accent, Archivo display
  font, reusable `.bv-card`/`.bv-pill`/`.bv-stat`/`.bv-table`/`.bv-btn`/`.bv-nav-link`
  classes plus `.bv-badge` / `.bv-num` / `.bv-day-head`. **Colour is the grade language:**
  `--good` (bet / won), `--warn` (watch / warning), `--bad` (pass / lost), `--push`; cyan is
  chrome only (links, active nav, buttons) and never a grade. `MainNav.tsx` gives the
  active-route highlight.
- **Dev**: `web/.env` `DATABASE_URL` points at Neon (prod) or the local sim PG
  (`simulate_week.py`); the Neon line is commented as a fallback. On a network that filters
  Neon:5432 (campus) set `NEON_HTTP=1` in `web/.env` — `lib/prisma.ts` then uses the Prisma
  Neon adapter over HTTPS/WebSockets (443). `npm run lint` / `npm run format`
  before committing. Deploy is automatic from `main` (Vercel).

## Gotchas
- **Open-Meteo's free tier weights a request by variables x days, and the cap is per
  UTC DAY.** A full weather backfill does not fit in one day: measured 2026-09-14,
  **5,711 requests exhausted the daily quota in ~2.3 hours** (86% of 6,636
  venue-season-leads), and `"Daily API request limit exceeded"` resets at 00:00 UTC
  rather than on a rolling window — waiting an hour does nothing. Plan for two days or
  split by lead. `backfill_weather.py` resumes from `data/cache/weather_staging.done`
  and halts after 10 consecutive failures instead of grinding through doomed calls.
- **Never ask Open-Meteo for `timezone=auto`.** A local-time series cannot be keyed by
  a UTC timestamp, and `Game.start_date` is naive UTC. That mismatch silently wrecked
  every weather row for three years (see the 2026-09-14 bullet). `timezone=UTC` makes
  the hourly index equal the UTC hour. `tests/test_weather_source.py` pins it.
- **Open-Meteo's Historical Forecast API is NOT "the forecast at decision time".** It
  stitches the first hours of successive runs, so it tracks actuals (1.82°F from ERA5,
  closer than a 1-day-lead forecast). Decision-time forecasts come from the **Previous
  Runs API** (`*_previous_dayN`), 2024+ for wind/gusts/precip, max lead 7 days, and must
  be pinned to `models=icon_seamless` — the default blend's gusts fall BELOW its own
  mean wind from 48h out. Any market-edge query filters `weather_obs.decision_safe`.
- **BetMGM's `totals_h1` is NOT a centred main line** (confirmed live 2026-09-12).
  It serves an off-centre rung: 4.86 pts from the market median on average, 61 of 63
  games 2+ pts off, with two-way prices ~235 points from -110 where every normal book
  is 15-47 (Western Kentucky @ Georgia: BetMGM 36.5 over +195 / under -275 while six
  books sat 30.5-32.5). **Not our parser and not staleness** — a live call returns 2
  outcomes at ONE point per book, and BetMGM's `last_update` was the freshest of the
  seven. The fair price is already safe (`fairPriceWindow` admits only books within
  0.5 pts of Hard Rock), but the consensus MEDIAN moves on 13 of 63 games by up to
  **0.5 pts** — exactly `HR_OFF_MARKET_PTS`, so it can flip the off-market gate on a
  borderline game. Details + options: `docs/RANKING_AND_TRUST.md` §9.
- **`ev` IS NOT THE EV OF THE BET, and gating on `ev >= 0` bets nothing** (measured
  2026-09-13, PR #123). `ev` is `ev_under(fair_under, hr_price)` where `fair_under` is the
  **market's** no-vig fair probability at Hard Rock's number (`card.py::market_read`) — a
  *price-shopping* number: "is Hard Rock's price better than the rest of the market's?"
  The model's edge is not in it at all; that lives in `hr_gap`, in POINTS, on a different
  scale, and the two are never combined into one expected value. So `ev >= 0` is not a
  strict gate, it is an **unsatisfiable** one — it asks Hard Rock to beat the no-vig
  consensus, which is a free arb. On the live week-2 card **0 of 42 priced rows cleared
  it** (5 BET, 18 EDGE, 19 PASS; mean ev -0.04 to -0.07) and all six real tickets were
  negative (-0.0086 to -0.0530). The other direction fails too: implying `P(under)` from
  the gap and `bv_sigma` (a **constant 11.26** on all 156 of 2026's rows) makes a 5.32-pt
  gap worth **+30% EV at -110**, while that season's grading says the model is LESS
  accurate than Hard Rock in every spread bucket. **A true EV gate needs a calibrated
  `P(under)`** — the two-team hurdle engine. `BREAK_EVEN_EV = 0.0` exists in
  `model/score.py` + `verdict.ts`, parity-mirrored, **wired to nothing**, waiting for it.
  The live bar is `BET_MIN_EV` (= `EV_FLOOR`), now the ONE name shared by `verdict.ts`,
  `card.py::is_bet`, the kill price and `pickRules.checkPolicy`.
  `docs/RANKING_AND_TRUST.md` §8b.
- **The "green board, refused log" band was STALENESS, not two rules** (PR #123 — §8 of
  `RANKING_AND_TRUST.md` used to say otherwise and was wrong). `breakEvenPrice` returns
  the worst rung whose EV clears the bar, so `price >= killPrice` **is** `ev >= bar`: the
  two agree at every price by construction. The quoted -113 was true break-even worked out
  by hand; the code's kill price on that game was -125, and -120 clears it. The real cause
  was `checkPolicy` comparing a LIVE price against a `killPrice` read off the **stored card
  payload** — and `marketFairUnder` moves between builds. All six real week-2 tickets had a
  kill price that changed across the week's eight builds (2-4 distinct values each; one game
  went +100 → -105 → +100 in three days). **`POST /api/picks` now recomputes from
  `lib/lineCheck.ts` and FAILS CLOSED**: no verifiable live price, no real-money BET
  (`PRICE UNAVAILABLE`, deliberately a different rejection from the kill-price one — an
  outage must never read as a run of discipline). A cached price may be displayed; it may
  never authorize money. `PolicyContext.livePrice` is REQUIRED so a new caller cannot skip
  the check by omission.
- **`centred_snaps` falls back to the rungs it exists to reject** — `return ok or
  list(snaps)` (`lines.py`). Fine for a multi-book consensus (some number beats none),
  WRONG for one book: there is no consensus to fall back to, so it hands back the quote the
  filter just rejected. Hard Rock is off-centre on 26 of 28 quotes inside 3h of kickoff —
  the close-poll window — so the fallback fired EVERY TIME the filter mattered. Pass
  **`strict=True`** from any single-book read; `book_closing_before_kickoff` and
  `book_closing_price_before_kickoff` now do (the latter had no filter at all). PR #123.
- `sources/odds.py::_normalize_totals` takes the **LAST** outcome in a market
  (`for oc in outcomes: ... over_price, line = ...`). Every book returns one point pair
  today so it is currently harmless, but a book returning alternate rungs would silently
  yield an arbitrary line — and could mix an over price from one rung with an under from
  another. Fix it before trusting any new book.
- **A `web/lib/` export with no TypeScript caller may still be LOAD-BEARING.**
  `tests/test_gate_parity.py` reads constants OUT of `verdict.ts`, `grade.ts`, `edge.ts`,
  `lineCheck.ts`, `books.ts` and `card.ts` **by regex** and compares them to
  `model/score.py` / `card.py` — that guard is what stops the Friday card and the live site
  disagreeing about what counts as a bet. `MODEL_BET_THRESHOLD` and `MIN_GAMES_FOR_MODEL`
  look dead in the web app and are not. Grep `tests/` before deleting any `export const`.
  (`CONFIDENCE_LABEL` and `WATCH_GAP_MIN` were genuinely dead and were removed.)
- **React `cache()` is a NO-OP outside a render/request scope**, so the per-request query
  dedupe cannot be unit-tested with a mocked prisma — a test asserting one call fails
  against correct code. Measure it instead: wrap `$queryRaw` in `lib/prisma.ts` with a
  `console.log` counter, hit the route twice (the first compiles), diff the dev-log lines,
  revert. Also key the cache on the loader with STABLE args: `getHomeBoard` takes
  `now = new Date()`, so caching that dedupes nothing.
- **Chrome headless does not emulate a mobile device from `--window-size` alone.** A 375-wide
  capture lays out at desktop assumptions and looks exactly like horizontal overflow. Confirm
  with the Browser pane's `javascript_tool` (its screenshots are useless, its JS works):
  `document.documentElement.scrollWidth - clientWidth`. Measured 0 on the board.
- `npm run format` reformats `web/data/*.json` (written by the Python lane) into a 1,600-line
  diff on every run. They are in `web/.prettierignore` now — keep them there.
- **Next 16.3 writes its own `AGENTS.md` and `CLAUDE.md` into `web/` on every dev start**,
  which would compete with this file. `agentRules: false` in `web/next.config.ts` turns it
  off; do not remove it.
- Features must stay **leak-free** (only pre-kickoff info; season-to-date shifted).
- Numeric model columns must be clean floats (NaN, never `pd.NA`/None/bool) — see
  `features.build_feature_frame` coercion; `bool(NaN)` is `True` (bit us on dome).
- ESPN/TeamRankings/**DraftKings**/**Rotowire** are **unofficial** — keep isolated in
  `sources/`, fail-silent. **ESPN: use host `site.web.api.espn.com`** — `site.api.espn.com`
  is Akamai-403 from every network we run on (Mac, GHA, fetchers), and ESPN publishes
  **no college injuries** on any endpoint (core API returns 0 for every FBS team).
  Injuries come from `sources/rotowire.py` (one JSON call for the whole slate). DK's hidden API returns **403 without browser-like headers** (set in
  `draftkings.py::_HEADERS`); the host, operator key (`dkusoh`) and league id (`87637`)
  drift — if capture goes empty mid-season, re-discover the `leagues/{id}` XHR in
  DevTools. Schema is `events`/`markets`/`selections` (the old `eventgroups` endpoint
  is dead). The default payload carries only main full-game markets (1H totals post
  later via a subcategory query), which is exactly the Sunday opener we want.
- **Neon is UNREACHABLE from the campus/fgcu network** (port 5432 TLS data filtered;
  HTTPS/443 works — and so does **Neon's HTTPS SQL endpoint**: `POST https://<pooler-host>/sql`
  with header `Neon-Connection-String: $DATABASE_URL` and body `{"query": "..."}` returns
  rows as JSON from campus in <1s. Use it for ad-hoc reads/small writes when 5432 is blocked;
  the SQLAlchemy scripts still need GHA). So **Neon-writing scheduled jobs run in GitHub Actions**
  (`.github/workflows/sunday.yml` + `lines_watch.yml` + `card.yml` + `grade.yml` + `research_preview.yml`).
  **DK's API 403s GHA datacenter IPs** (confirmed), so prod captures full-game lines with
  `poll_full_game --source oddsapi` (`auto` falls back to **CFBD /lines**, `sources/cfbd_lines.py`;
  DK only works from the Mac, which can't write Neon). Local jobs degrade gracefully via
  `store.try_init_db` (logs "unreachable", exits 0). `GET /api/health` reports capture AND
  grading/build freshness over HTTPS (it used to be read by the retired Sunday routine).
  Secrets `DATABASE_URL`/`CFBD_API_KEY`/
  `ODDS_API_KEY` are the only GH secrets. Pushing `.github/workflows/` needs the gh
  `workflow` token scope.
- **Bonus bets book NO loss** (`manual_picks.is_bonus`, 2026-09-09). Grading is
  `stake x units_won` and a loss returns -1/unit, so a $20 bonus logged as 2 units would
  show -$20 on a loss that cost nothing. `picks.graded_pick_fields` floors units at 0 when
  `is_bonus`; the WIN side is untouched because `units_won` already returns profit only,
  which is exactly what a bonus bet pays. Bonus bets are also excluded from the 5-bet
  weekly cap in BOTH `build_card.py::real_bets_this_week` and the web POST cap query.
  A pending pick's price/stake/note/bonus flag are editable (`PATCH /api/picks/<id>`,
  rules in `web/lib/pickRules.ts::parsePickEdit`); line/market/game never are, and a
  graded pick is refused. **Schema ordering:** a new `manual_picks` column must reach Neon
  via `migrate.yml` BEFORE the web deploy — the cap query reads `COALESCE(is_bonus, false)`
  and would throw on a missing column. The READ path degrades gracefully (`isMissingColumn`
  fallback in `web/lib/picks.ts`); the write path does not.
- **The model DISAGREES WITH HARD ROCK ON BLOWOUTS, and who is right is UNMEASURED**
  (found 2026-09-09; re-examined the same day — the earlier "HR is right" reading did not
  survive). On week-2 Hard-Rock-priced games the model's implied 1H share is 0.469 close /
  0.482 at 14-21 / **0.450 at 21+**, against HR's 0.504 / 0.524 / 0.541; average gaps +2.0
  / +2.2 / **+5.0**. HR prices these (5 of 5 at 21-28, 4 of 7 above 28), so `no_hr_line`
  does not filter them, and the top of the board is mostly wide-spread games.
  **But do not treat that as a known model error.** Against the 1,902 rows in
  `postmortem_games` (`hist_2023_25`) carrying a REAL captured close (`line_real`), the
  model has NO spread bias — mean miss −0.01 / −0.02 / +0.41 / −0.47 across
  <14 / 14-21 / 21-28 / 28+ — and wide-spread bets at `gap_real >= 1.75` returned +1.1%
  ROI over 120 bets, positive in 2 of 3 seasons. In 2023-25 weeks 1-4 the model ran a
  0.556 share on book-priced blowouts vs the book's 0.540, with gaps averaging −0.84: the
  2026 sign is FLIPPED. And `game_records` has **zero graded rows** — no 2026 prediction
  has ever been checked against a result (week 1 played but never scored, week 2 scored
  but not played), so nothing yet says which side is wrong.
  **Two traps here.** (1) The big blowout bias (+2.00 at 28+ over all 3,601 rows) is
  concentrated entirely in the 1,699 games NO BOOK PRICED (+3.36 at 28+); always cut
  `where line_real is not null` before concluding anything, and state the n — it is thin
  at width (72 games above a 28-pt spread). (2) Gating 21+ spreads on the proxy numbers
  was proposed and rejected: it drops a third of the board and the drag it targets
  disappears at real lines. Decision (Tate, 2026-09-09): **track it live, do not gate or
  retrain.** `grade.yml` runs `grade_records.py` + `post_mortem.py --write` daily, so each
  week's predictions grade themselves; watch model-vs-HR share by spread week over week.
  If it is an early-season priors effect the gap should shrink as season-to-date features
  fill in. If it persists, options are mismatch features from talent/SP+ (stays
  market-blind), a spread-keyed residual correction (precedent: `data/multiplier.json`,
  `residual_gate.py`), or adding spread outright — note `spread` is NOT in `MARKET_COLS`
  (only `full_game_total` and `proj_1h_ratio`); it was simply never added to
  `FEATURE_COLS`. `rescore.yml` would score 2026 week 1 for ~60 graded results at zero
  Odds credits. Meanwhile: do not read a 9-pt gap as a 9-pt edge.
- **GHA cron is UNRELIABLE, not just late** (Aug 28-30 2026: `lines_watch.yml` fired 2 of 19
  scheduled runs; 2026-09-09: `card.yml` fired 0 of 5 morning builds on time, the 12:05Z tick
  running at 16:33Z; no GitHub incident posted either time). So since 2026-09-09 the card and
  grading builds are **triggered by a VERCEL cron** (`web/vercel.json` -> `/api/cron/[job]`,
  table in `web/lib/cronJobs.ts`) which dispatches the workflow over the GitHub REST API;
  GitHub's own crons stay as the backup and the `cards`-row probe stops both from building.
  **`vercel.json` must live in `web/`** — the Vercel project's root directory — or it is
  silently ignored, with no build error and no crons in the dashboard. Vercel Hobby fires
  within the HOUR after the scheduled minute, so each job carries several UTC hours and the
  route refuses any tick outside its ET window. `/api/cron` is exempted in `middleware.ts`
  (Vercel sends no session cookie) and authenticates on `CRON_SECRET`; the other new env var
  is `GITHUB_DISPATCH_TOKEN` (fine-grained PAT, Actions read+write on this repo). Both are
  production-only and set by Tate in the dashboard. Anything else that must happen at a time
  is still dispatched by hand (`gh workflow run <wf> -f market=1h`), and `card.yml` checks its
  own inputs: it runs the 1H sweep / preview itself when today's is missing before it builds.
- **1H sweeps are RANKED before any cap** (`beatvegas/sweep.py`; the paid tier has no event cap, `--max-credits-per-run` is the runaway guard): close spread
  (|spread| ≤ 14, from the Sunday full-game capture) > wide > none; outdoor > dome; slower pace
  first; kickoff order last. A plain `[:18]` swept Friday night + the noon wave and never
  reached the evening games the card wants.
- **ESPN line scores are not always right.** `sources/espn_scores.py` is the no-quota
  scores fallback, but ESPN's quarter data can be corrupt: SDSU @ UCLA (2026 wk 2) came
  back `[0,0,0,0]` against a 38-point final, and the `summary` endpoint returned nulls.
  `line_scores_trustworthy` caught it and left the game NULL rather than writing a false
  0-0 first half, which is exactly right — that one game stays ungraded until CFBD PBP is
  reachable. Never relax that guard to "fill in" a missing 1H.
- **ESPN: send NO custom headers.** Akamai 403s a bare spoofed UA (`Mozilla/5.0`, or a Chrome UA
  without client hints); requests' default UA is served. The spoof blanked every preview until
  2026-09-02. `research_preview.py` now exits 3 when the team list is empty instead of writing
  455 blank rows. ESPN's CFB `/injuries` feed is usually EMPTY (no official CFB injury reports)
  — the QB-out flag is real but rare; check starters by hand before betting.
- **TeamRankings → CFBD mapping is exact-first** (`teamrankings.map_to_cfbd`). `name_score`
  scores a prefix school as a perfect match ("Kansas St" → Kansas AND Kansas State at 1.0) and
  the old first-scanned tie-break dropped 26 FBS teams/season and stored Ole Miss's tempo under
  Mississippi State (2023-25). Same exact-first rule in `espn.best_team_id`. Any new
  TeamRankings abbreviation goes in `_ALIASES` with the CFBD spelling from the `teams` table.
- `config.yaml` (keys + phone) and `data/*.db|*.log|cache/|pbp_cache/` are gitignored —
  keep it that way (`pbp_cache/` holds 56MB parquet files per season).
- **Neon id-sequence**: rows seeded from SQLite carry explicit ids without advancing
  the Postgres sequence, so the next insert collides on the pkey. Before any bulk
  insert to Neon (`backfill_bv_line.py`, `retrain.py`, `deploy_neon.py`), resync:
  `SELECT setval(pg_get_serial_sequence('<table>','id'), (SELECT MAX(id) FROM <table>))`.
- **Neon bulk inserts must be CHUNKED** (~500 rows/commit) — a single big
  `bulk_insert_mappings` STALLS the Neon pooler indefinitely. See `deploy_neon.py::_chunked_insert`.
- **psycopg3** required for Neon (`pip install "psycopg[binary]"`); the engine normalizes
  `postgresql://` → `postgresql+psycopg://` (config.py). NOT psycopg2.
- **Deploy to Neon is ADDITIVE** (`deploy_neon.py`) — never `--wipe`/full-migrate to
  prod: `manual_picks`, `odds_snapshots`, `results` are live Neon-only data.
- `db/store.py::upsert` **never overwrites a column with None** — a partial row (e.g. the
  Monday finals backfill) must not null `spread`/`full_game_total` on upcoming games. Keep it so.
- **The model scores UNPLAYED games**: target rows have no `first_half_total`. Never re-add a
  `first_half_total` filter to the target slice (it silently empties the board).
- **BV gap is now the PRIMARY ranking** (gate passed in `validate_engine.py`).
  `score_slate` sorts by `bv_gap` desc; verdict gates are in POINTS (`model/score.py`). Calibration
  still uses a **global** intercept + `era_post2023` feature (per-era would double-count).
  The regressor is MARKET-BLIND (`BV_FEATURE_COLS = FEATURE_COLS − MARKET_COLS`) — keep it so.
