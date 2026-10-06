# CFBD business teardown — how Bill Radjewski built CollegeFootballData, and what Beat Vegas takes from it

**Track D of the 2026-10-06 program.** Companion to `docs/CFBD_CATALOGUE.md` (§1: the dated
Patreon timeline), `docs/CFBD_TIER3_REVIEW_2026-10-05.md` (tiers, API, packs, terms, Discord ops)
and the Paramount Sports teardown (`docs/HISTORY.md` 2026-09-26); this is the business read.
Every claim carries a URL and the date read; Patreon quotes come from the campaign Tate pulled
2026-10-05/06 (`research/swarm/2026-10-05-cfbd-tier3/downloads/posts/gallery2/`, gitignored).

**Recommendation first.** CFBD is a seven-year free-data project that became a business by
charging for headroom, convenience and method while keeping the data itself open and refusing,
in writing, to be a betting system. The playbook to copy is the rhythm and the candour (a
deliverable every Sunday, a changelog for every change, losses and outages stated plainly). The
thing not to copy is the product: Bill sells inputs; Beat Vegas's only sellable thing is the
judged OUTPUT — a registered, market-graded ledger — which nobody in his ecosystem offers.

## 1. Who Bill Radjewski is, publicly

**Verdict**: a working software architect in Cincinnati who built CFBD as a side project out of
r/CFBAnalysis; one person, a day job, a family, and a project that "exploded" past what he planned.

- Founder bio: "Bill Radjewski founded CollegeFootballData after compiling and sharing college
  football data with the r/CFBAnalysis community"; the project "is independently operated".
- GitHub `BlueSCar`: "Enterprise Architect at Myriad Genetics and maintainer of
  CollegeFootballData.com", Cincinnati, OH, 38 public repos, 83 followers. The older blog bio
  (now redirected) read "Principal Software Architect for Myriad Neuroscience" and dated the API
  to "the Fall of 2018"; the 2024-08-16 post: "a small, personal project intended to help out a
  small community of CFB analytics diehards on reddit who would collaborate by sharing CSV files."
- Motive, his words (2021-12-03): "Money has never been a primary motivator … as I also juggle
  work and family responsibilities." The Terms name **Rad Sports Analytics LLC** (2026-08-12).
- Fandom: his r/CFBAnalysis flair reads "Michigan • Dayton" (mirror index title; the mirrors
  refuse our fetch); nothing else personal is published or recorded here. Talks/podcasts: none
  found; the FSU Sports Analytics Series lists him under "Some Inspirations and Heros" as "The
  creator of CollegeFootballData.com", not as a speaker.

Sources (all read 2026-10-06 unless noted): https://radsportsanalytics.com/about/ · https://github.com/BlueSCar
· https://blog.collegefootballdata.com/about-2/ (301 → /about/; the bio quoted is the search-index snippet
of the pre-2026 page) · https://collegefootballdata.com/terms · https://fsusac.sportsdataverse.org/ ·
Patreon posts 2021-12-03, 2024-08-16 (on file).

## 2. The product ladder, with prices today

**Verdict**: one free core, six paid rungs selling headroom and convenience, a one-time pack store
selling method, and a free contest that markets the packs. Nothing on the ladder is a pick.

| Rung | Price | Free or paid | Why people pay |
|---|---|---|---|
| REST API + site tools (exporter, team pages, box scores, previews) | $0; 1k calls/mo (3k with a .edu) | free, key required since 2021 | — (the hook: seven years of open data) |
| Patreon Tier 1 | $1/mo, 5k calls | paid | headroom; WEPA, weather, live scoreboard; ad-free; chart export; patron Discord role |
| Tier 2 ("Most Popular") | $5/mo, 30k | paid | live play-by-play; bookmarks + saved queries; Open Office Hours (Discord voice); pack discount = tier |
| Tier 3 | $10/mo, 75k | paid | GraphQL + subscriptions; the weekly model-training CSV (Sun/Mon, week 5 → CFP) |
| Tiers 4-6 | $15 / $20 / $30, 125k / 200k / 500k | paid | calls only |
| Gumroad packs: AI API Launchpad $19; Starter Pack $49 (upgrade $25); AI Builder Pack $49 promo / $69; Model Training Pack $69 ($59 launch); Starter + Model bundle $98 ($79 launch); Organization licence +$130 → $199; CBB Starter and March Madness packs | one-time | paid | skip the backfill grind; notebooks; "clean, opponent-adjusted"; personal licence |
| Model Pick'em | $0 | free | weekly margin benchmark; 101 entries on the 2026 board today; the funnel for the packs ("I used this same training dataset to finish #2") |
| Discord (2,862 members) + Office Hours | $0 / Tier 2+ | mixed | support forum, community; voice with Bill for patrons |
| "My Season Workbench" + docs portal (2026-08); Score Bot (Discord scores, since 2019, rebuilt 2026-08) | $0 | free | convenience; the Discord presence |
| CBBD sister site (2025-02) | same Patreon pool | mixed | one subscription, two sports |
| Rad Sports Analytics blog + newsletter | $0 | free | tutorials that feed the packs; "No fixed schedule" |

Pay reasons, his framing: quota ("more monthly room"), convenience ("skip the backfill grind"),
early access ("timed subscriber exclusives", 2021), method (notebooks), community (role, channel,
office hours), credibility borrowed from the Pick'em. Terms (2026-08-12): commercial and betting
use allowed at every tier; no bulk redistribution; packs personal-use unless the Organization licence.

Sources: https://collegefootballdata.com/api-tiers · https://collegefootballdata.com/exporter ·
https://collegefootballdata.com/terms · https://collegefootballdata.gumroad.com/l/model-training-pack
+ `/l/starter-pack`, `/l/cfb-bundle`, `/l/ai-builder` (embedded product JSON, swarm lane D12/D13, 2026-10-05) ·
https://predictionsapi.collegefootballdata.com/api/leaderboard · https://discord.com/api/v9/invites/Eb3ex5a?with_counts=true
· https://radsportsanalytics.com/ · Patreon posts 2019-09-05, 2025-07-06/11, 2025-08-08, 2026-08-29.

## 3. How value recurs

**Verdict**: the subscription survives because something lands every in-season Sunday and
something new ships every offseason; the contest and the packs re-launch each July/August.

- **Season rhythm.** Every Sunday 8:30-10:40 ET: "All game data has been refreshed for week N"
  plus SRS, Elo, FPI, CORE, WEPA, PAAR; SP+ 30 min-4 h later; the Tier 3 CSV that afternoon or
  Monday. The Pick'em is a weekly submission with a weekly leaderboard.
- **Endpoint cadence.** Each new endpoint is a post: CORE (2026-08-08), passing endpoints
  (2026-08-30), `/games/schedule` (2026-10-02); in-season he keeps shipping pages (Box Score
  09-21, Team Profile 09-22, Preview + Schedule 09-26).
- **Offseason refits.** "I always like to take the time to reevaluate the various models"
  (2021-12-03): PPA re-fitted, win probability rebuilt 2025, the 2024 API rewrite, FCS added. The
  July pack launch and the August Pick'em opening are the offseason retention events ("four new
  … packs, three bundles", 2026-08-29). In season, the weekly CSV keeps the top tier worth paying
  and the discount-equal-to-tier makes a patron month pay for itself on pack day.

Sources: Discord `#announcements` 2025-10 → 2026-10 (swarm lane `discord.md`, 2026-10-05) · Patreon
posts 2021-12-03, 2025-07-24, 2026-08-12, 2026-08-29 + weekly-file posts · https://radsportsanalytics.com/author/bill/.

## 4. How credibility was built

**Verdict**: by giving the data away for years, showing the work, and saying so when it broke.

- **Free, open data since 2018**; ~10k registered users and ~30M requests a year by 2024-08;
  "3,500+ Patreon supporters" and "over 100M API calls per season" on the site today.
- **Open source**: 21 repos in the CFBD org (the API itself, `cfb-api-v2`; `cfbd-python` 221
  stars / 39 forks; TypeScript, .NET, R clients); `cfbfastR` (sportsdataverse, 112 stars) is a
  third-party "R API wrapper around collegefootballdata.com"; MCP servers list CFBD as a source.
- **A public project board** from day one (Taiga, 2019-08-19; GitHub suggestion board since
  2025-07: "This is how I'm tracking your requests now").
- **Candour**: 2019-10-26 "Looks like I've been hacked. My databases have been wiped and are
  being held for ransom"; restored in two days, contest picks lost, said plainly. Docs state gaps
  ("An empty response inside a range should not automatically be treated as a zero").
- **A public benchmark he enters himself**: 2019 "my model is actually leading in picks straight
  up, absolute error, and mean squared error", Vegas beside every pick; 2024 "#2 overall in the
  CFBD Model Pick'em … 12.07 MAE"; 2025: 45 qualified entries, he published the winner
  (u/hypercube42342), not himself.
- **Positioning**: CORE is "not a forecast or betting system"; the Terms: the platform "does not
  operate or endorse a sportsbook and does not guarantee predictions, wagering results, or
  financial outcomes." He never sold a pick; the 2019 weekly picks were a free post whose goal
  was "an accurate final score margin, not so much beating the Vegas line."

Sources: https://collegefootballdata.com/ · https://github.com/CFBD · https://github.com/CFBD/cfbd-python
· https://github.com/saiemgilani/cfbfastR · https://apinext.collegefootballdata.com/data-availability
· https://collegefootballdata.com/terms · Patreon posts 2019-08-19, 2019-10-22, 2019-10-26/28,
2024-08-16, 2025-07-11, 2025-08-01 (on file; 2019 picks quote via `docs/CFBD_CATALOGUE.md` §1) ·
r/CFBAnalysis 2025 Pick'em results post via search index (the mirrors refuse our fetch).

## 5. Marketing channels, cadence and reach

**Verdict**: no paid marketing visible; the channels are the community itself, each release posted
once to all of them. Public numbers where they exist:

| Channel | Public number | Cadence |
|---|---|---|
| Discord `CFBD` (discord.gg/Eb3ex5a) | 2,862 members, 409 online (2026-10-06) | every Sunday + every release |
| Patreon campaign | 61 posts 2019-08 → 2026-10; "3,500+ supporters" is the SITE's claim; Patreon itself shows no patron count or earnings to an anonymous read | weekly in season (Tier 3 file), bursts in July/Aug |
| X @CFB_Data | follower count not readable (x.com 402, speakrj/socialblade/instalker 403); bio links from GitHub | release posts; the 2019 "weekly results" account |
| GitHub org CFBD | 97 followers, 21 repos, 221 stars on the top repo | pushes weekly in season |
| Rad Sports Analytics blog (Ghost) + newsletter | 12 posts since 2025-07; subscriber count not shown | "No fixed schedule"; 5 posts Jul-Sep 2026 |
| YouTube (channel "Bill Radjewski") | two pack walkthroughs found: "CFBD AI API Launchpad Preview", "AI Builder Pack Walkthrough"; views not readable | per pack launch |
| Reddit r/CFBAnalysis | the origin; the annual "CFB Data and Resources" post and the Pick'em results post | annual + season end |
| Pick'em site; Office Hours (Tier 2+, Discord voice) | 101 entries on the 2026 board; "aim to make these a monthly thing during the season" | weekly; monthly (2025) |

Sources: https://discord.com/api/v9/invites/Eb3ex5a?with_counts=true · https://collegefootballdata.com/
· https://www.patreon.com/collegefootballdata (tiers and counts not rendered to our fetch) ·
https://github.com/CFBD · https://radsportsanalytics.com/blog/ · YouTube oEmbed for `VFiczZNVhhk`
and `ook9dPzb3yQ` · https://predictionsapi.collegefootballdata.com/api/leaderboard ·
`docs/CFBD_CATALOGUE.md` §1 (61 posts) · Patreon post 2025-07-06 (office hours cadence).

## 6. Weaknesses and risks (stated by him, or visible)

**Verdict**: everything that makes it trustworthy also makes it fragile — one person.

- **Single maintainer**: travel/AFK notices in `#announcements` (2026-09-19); "I've stopped
  getting notifications when people message me on here" (2021-12-03); pinned rules: "I do not
  monitor DMs". Support latency is a dependency for anyone building on it; the 2019 hack was a
  one-backup recovery.
- **Data regenerated without a changelog**: the September-2026 PPA rewrite shifted past seasons'
  PPA ~35-40% and was disclosed in one Discord reply ("A few weeks back, I fixed an issue … and
  applied historical corrections"); the pack history still sits on the old scale; WEPA history is
  regenerated whenever play-by-play is backfilled. The docs portal has no changelog.
- **Scale breaks**: 429s from three causes incl. new 2026 per-endpoint concurrency limits;
  GraphQL scoreboard subscriptions stalled twice in September; Cloudflare bursts.
- **Coverage edges**: 2020 excluded from the training pack; WEPA/SRS absent for weeks 1-4;
  FBS-centric (FCS "expanded" only in 2026); enriched passing/rushing data 2025+ only.
- **Concentration**: one Patreon, one store, one Discord, one person's accounts; the LLC appears only in the Terms.

Sources: swarm lane `discord.md` (pinned rules, AFK, 2026-10-01 PPA thread, 429 thread) · `docs/CFBD_TIER3_REVIEW_2026-10-05.md`
§2.2 + Limitations · Patreon post 2021-12-03 · https://apinext.collegefootballdata.com/data-availability.

## 7. What Beat Vegas should copy, adapt and not copy

**Differentiation hypothesis.** Bill sells data and method and refuses, in his Terms and his
ratings posts, to be a betting system; his own picks were a free contest entry and his ATS was a
coin flip by his own account. Every product in his ecosystem is an INPUT. Beat Vegas's product is
the judged OUTPUT: a transparent, pre-registered (`docs/HYPOTHESES.md`), market-graded betting
system with a public ledger of every real ticket, its closing line and its interval — the one
thing nobody in the CFB data ecosystem sells, and the one thing a data vendor cannot sell without
becoming what he refuses to be. The test is prospective: if the registered rule keeps a public
record through H-STOP-2, the product exists; if not, the honest ledger is still the product.

**Copy**
- The Sunday deliverable: something lands every in-season Sunday, same hour, same format.
- Candour as the house style: outages, losses and limits in the first sentence, not a footnote.
- A public benchmark with the market beside every number (he put Vegas next to every 2019 pick).

**Adapt**
- Free-core / paid-headroom becomes free-ledger / paid-nothing for now: every rate with its
  interval, no dollars; "follow our picks" stays free until the registry says there is something.
- His project board becomes the registry: every proposed study is a public row before a script.
- His "not a forecast or betting system" becomes "a betting system that never places bets and
  states its own stopping rule" — the opposite claim, held to the same plainness.

**Do not copy**
- Selling inputs (data packs, API tiers): The Odds API and CFBD are our vendors, not our product.
- One-person ops with DM blindness: the board is the failure surface, `HEALTH.md` the contract; no Discord.
- Regenerating history silently: every frame names its fingerprint; every change is a HISTORY episode.

**Three practices to adopt this season**
1. Publish the model's MAE beside Hard Rock's every week on the public site (B-SERVE 9.03 vs
   8.39 is already measured in the weekly review; it is not yet public).
2. A public "what changed" changelog page fed from `docs/HISTORY.md` — one dated line per shipped
   PR, the thing CFBD lacks.
3. A season-rhythm deliverable: the graded ledger and H-STOP-2 clock reading posted every Sunday
   at a fixed hour, even when the week went 1-4.

**Three practices to avoid**
1. Selling picks (or a "premium" tier of picks) before the registered rule has a record.
2. Tiering the picks: no early-access or paid-first on BET-rated builds; everyone sees the card
   at the same time.
3. Hiding losses: no week unposted, no ticket leaves the ledger, no dollar dressed up as units.

## 8. Open questions for Tate

1. Is "follow our picks" a product at all, or is the public ledger the whole product this season?
   (Decides whether a changelog page and a Sunday post are enough, or a sign-up exists.)
2. Should the weekly MAE-vs-Hard-Rock number go public now, while it says the market is more
   accurate than the model? (The honest answer is the differentiator; it is also unflattering.)
3. Any channel other than the site? Bill's Discord is his support cost and retention engine at once.
4. Enter the CFBD Model Pick'em with the full-game reference margin (free, public, external
   validation; our first public number not graded by us)?
5. Does any paid rung ever exist? The only candidates consistent with §7 are infrastructure (the
   ledger CSV, the research docs), never the picks — confirm or strike.

### Could not source
@CFB_Data follower count (x.com 402; speakrj, socialblade, instalker 403) · Patreon's own patron
count and earnings (hidden to an anonymous read; "3,500+" is the site's claim) · newsletter
subscribers, YouTube views, a public page for the Workbench or Score Bot beyond their titles · any
podcast or conference appearance by Bill (none found in two searches).
