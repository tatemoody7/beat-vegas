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
