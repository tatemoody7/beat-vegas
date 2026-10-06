# CFBD catalogue — everything CollegeFootballData offers, with a verdict for Beat Vegas

**Track B of the 2026-10-06 program.** One line per asset: what it is, what Bill thinks matters,
the verdict for us (use / test / ignore), and any registry row it implies. Companion to
`docs/CFBD_TIER3_REVIEW_2026-10-05.md` (the API, the weekly CSV, the Gumroad packs, 28 posts
with files) and `docs/DATA_STACK_REVIEW_2026-10-05.md`. Nothing here changes a gate, a model
constant, the champion or a stake; anything that implies a test is a proposed row.

## 1. The Patreon campaign, complete (61 posts, 2019-08 → 2026-08)

The 2026-10-05 pull saved the 28 posts that carry a file. On 2026-10-06 a second gallery-dl pass
with a per-post `metadata` post-processor (`event: post`) captured every post as JSON, text-only
ones included: **61 unique posts, all viewable at Tier 3**, 33 of them unread until now. The
review's line "nothing on the campaign is unread" was wrong by those 33; it is corrected there.
Raw bodies: `research/swarm/2026-10-05-cfbd-tier3/downloads/posts/gallery2/*_post.json`
(gitignored, Patreon terms) and `posts_ingested.md` beside them.

### What Bill models, in his own words

| Date | Post | What it says | For Beat Vegas |
|---|---|---|---|
| 2019-10-31 → 11-20 | Week 10-13 Predictions (4 posts) | His model's full-game MARGIN per game beside the Vegas spread, ~50 games a week. Week 12: "my end goal is aimed at getting an accurate final score margin, not so much beating the Vegas line". Season to date: 72% straight up, **53% ATS**, MAE 11.9 ("beating SP+ for the season" on MAE, not on the other two). | The clearest statement on file of what CFBD is: an accuracy project, not a betting one. His own ATS was coin-flip. Four weeks of margin picks is not a dataset; ignore as data, keep as the framing. |
| 2020-11-16 | New benefits for patrons | No weekly picks in 2020: "the state of the schedule has made it difficult to train a good model". | He trains on the current season's schedule structure; the pandemic year broke it. Consistent with his week-5+ rule below. |
| 2025-08-01 | Model Training Pack is LIVE | "#2 overall in the CFBD Model Pick'em last season … 12.07 MAE, 234.9 MSE, and it only used games from Week 5 onward … clean, opponent-adjusted, no early-season noise." Targets: margin, win probability, team points; notebooks: linear, random forest, XGBoost, FastAI, SHAP, stacking, logistic. | His early-season rule matches ours (`MIN_GAMES_FOR_REAL_MONEY`, the weeks 1-4 WEPA gap). Team points as a target exists in his pack — the nearest thing to a totals target anywhere in CFBD, still full-game. Ignore the pack as data (reproducible, market-aware); the notebook list is the method menu we already use (HGB) or rejected (classifier). |
| 2025-09-21 | Weekly Model Training Data Updates Start | "Each Monday (at the latest) … waiting on Vegas lines to open for this week's slate." | Confirms the weekly CSV is posted after the opener exists and carries it (§5 of the review: `spread` = opener). Market-aware by construction. |
| 2021-06-29 | Historical Weather Data | Weather from 2011 for played games; "does not include weather forecasts for games yet to be played, but that is something I am actively investigating." | The 2001- observed-weather backfill the review priced (~350 calls) is this table grown up; still observed, not decision-time. `weather_obs` (Open-Meteo Previous Runs) stays the decision-safe source. |
| 2021-09-03 | Live Scoreboard endpoint | Live scores "includes betting and weather forecast information". | `/scoreboard` carries a forecast and lines for the current week only; a live board someday, not a model input (review §7). |
| 2021-12-03 | Offseason Projects | "I always like to take the time to reevaluate the various models … hone in on the EPA/PPA model"; FCS data next. | PPA is re-fitted in offseasons: the Sept-2026 rewrite was not the first. Any PPA-derived history must carry its fingerprint date (already our rule). |
| 2026-08-08 | Introducing CORE Ratings | Two stages: play-level PPA vs what the situation normally produces, then opponent adjustment; "what CORE deliberately excludes". | CORE is the one CFBD rating with a `throughWeek` stamp; PR7 snapshots it. Test only as a shadow-arm input (H-SHADOW-F successor), never a retrofit. |
| 2026-08-30 | New passing endpoints | Air yards, aDOT, pass locations, YAC; "2025 data is partial … From 2026 onward, coverage should be mostly complete". | Style features with one partial season of history; revisit 2027. |

**Verdict on the modelling side**: nine years of posts, zero words on first-half markets, totals,
closing lines or an edge. CFBD's modelling is a margin-accuracy benchmark (the Pick'em), and Bill
is candid that beating the line is not the goal. What transfers: the week-5 start, opponent
adjustment as the one input he insists on, the Sunday/Monday rhythm, and the honesty of
publishing MAE/MSE next to the market every week.

### How the business was built (for Track D)

| Date | Post | The move |
|---|---|---|
| 2019-08-19 / 09-05 | Welcome!; Football Season is here! | Patreon opens to cover "monthly server and infrastructure costs"; patrons get a public project board (Taiga) and vote priorities; first perk promised: no ads via Patreon login. |
| 2019-10-26 / 10-28 | Hacked; Most functionality restored | Databases wiped and ransomed; restored from a pre-season backup in two days; the prediction contest's picks lost for the year. |
| 2019-12-22 | Offseason Plans | Patrons "have not only met the threshold for monthly server and infrastructure costs, but have also ensured the site can continue to scale"; the blog is born to explain the models (PPA, win expectancy); CFB Risk as community play. |
| 2020-11-16 / 2021-02-20 | New benefits; API Keys Rolling Out | Abuse forces API keys; patrons get keys first, automatic by email, and "priority access" at peak; the Discord patron role and channel. |
| 2021-06-29 / 09-03 | Weather; Live Scoreboard | "Timed subscriber exclusives": a dataset lands for patrons first, goes public later. |
| 2021-12-03 | Offseason Projects | "Money has never been a primary motivator … Balancing keeping the site open and free while also providing worthwhile benefits to subscribing has always been a struggle." Work, family, third child. |
| 2024-08-16 / 08-19 / 08-22 | API overhaul; v2 beta; Python package | ~10k registered users, ~30M requests a year; v2 rewrite; rate limiting becomes a MONTHLY CALL POOL per tier (Tier 1 5,000 / Tier 2 30,000), live endpoints free; "99% of you … stay in your current Patreon tier". |
| 2025-02-16 / 08-19 / 10-31 | CBB API | Basketball on the same codebase and the same call pool; official clients in Python, TypeScript, R (a volunteer led R). |
| 2025-03-28 / 07-10 | Open Office Hours | Voice chat on Discord for subscribers (Tier 2+), RSVP via the Patreon↔Discord link. |
| 2025-07-12 / 07-24 / 08-01 | Starter Pack; Pick'em; Model Training Pack | Gumroad packs with tier-based discount codes ($5-20 off by tier), a bundle, and the Pick'em as the free weekly benchmark that markets the packs ("I used this same training dataset to finish #2"). |
| 2025-08-08 | Big update | Website sign-in: API key and usage visible, ad-free (Tier 1+), chart export, bookmarks and saved queries (Tier 2+). |
| 2025-09-21 | Weekly training data | The Tier 3 weekly CSV: a recurring deliverable that makes the top tier worth keeping in season. |
| 2026-07-21 / 07-29 / 08-08 / 08-12 / 08-29 / 08-30 | Tutorials, project guide, CORE, Pick'em 2026, season recap, passing endpoints | Rad Sports Analytics as the content arm: tutorials feed the packs, the Pick'em feeds the community, each endpoint release is a post. |

**Verdict on the business side**: the ladder is free data → paid headroom and priority → exclusive
early access → packs and tutorials → community (Discord, Pick'em, office hours). Recurring value
comes from the season rhythm (weekly files, weekly contest) and from new endpoints every few
weeks; credibility from seven years of free, open data, a public project board, candour about
outages and limits, and one maintainer who answers. He sells data and method, never picks.
The full teardown with sources is Track D's `docs/CFBD_BUSINESS_TEARDOWN.md`.

## 2. Still to catalogue (Track B gaps)

- Pre-2025 Rad Sports / CFBD blog posts (referenced only).
- The two YouTube pack walkthroughs (VFiczZNVhhk, ook9dPzb3yQ).
- The GitHub suggestion board (github.com/orgs/CFBD/projects/3).
- The free Starter-Pack PDFs already in hand, read for METHOD (how he adjusts, drops, validates).
- `betting-events-service` (archived repo), the GraphQL docs app, the 2026 Model Pack data
  dictionary (ships inside the zip; nothing bought — Tate 2026-10-06).
