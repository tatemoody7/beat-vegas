# CFBD Starter Pack — walkthrough notes (2026-10-07)

**Verdict: a good teaching pack with five defects that would mislead an analysis, two findings that
matter for Beat Vegas, and nothing that changes the system.** All 14 notebooks run as shipped. The
two findings: (1) on 2025, early-season first-half scoring barely predicts later first-half totals
(correlation 0.14, 410 games), and opponent adjustment adds nothing to it — a sobering prior for the
proposed H-RIDGE-F; (2) explosiveness is the one common efficiency stat nearly independent of the
others, and the champion does not carry it (H-SHADOW-F does). Two proposed rows, none registered.
The pack's PPA is on CFBD's pre-September scale and must never be mixed with live frames.

**Defects found** (each checked in a scratchpad copy; the pack is unmodified): the data dictionary
mislabels explosiveness (00); 05's model predicts a home win for every game; 07 reads field position
from the home team's end and carries 116 impossible drive totals; 04's radar chart rescales across
only the teams drawn; 10's least-squares system is mis-specified (harmless on 2025: rankings agree
0.99 with a correct fit).

**How it was run.** Pack: CFBD Starter Pack, 2026 preseason edition (files dated 2026-06-15/16),
personal licence, gitignored at `research/cfbd_pack/`; its own venv (`research/cfbd_pack/.venv`,
Python 3.14, pandas 3.0.6). Notebooks executed headless as shipped (2025 season); every check
beyond the notebooks ran on scratchpad copies, Mac-side, on the pack's own files — these are not
runner numbers about the live model and are never quoted as such. Notes are in our own words; no
pack data or code is copied here. Proposed rows are proposals only.

## 00 Data dictionary
- **What it does:** previews each file: teams/conferences, `games.csv` (1869-2025 + 2026 schedule),
  box and advanced stats per season and per game, drives, plays (one file per week, 2003-2025).
- **Relation to Beat Vegas:** the shared key is CFBD's game id, the same id as our `games.id`, so
  the pack joins to our tables directly. Our engine pulls the same families live (CFBD games,
  advanced season stats, play-by-play), and `history_load.yml` already loaded 2003-22 FBS games
  and pregame Elo from the API.
- **Two cautions found while running it:**
  1. **The pack's PPA is on the old scale.** Mean FBS offense PPA in the pack: 2023 0.181,
     2024 0.183, 2025 0.168. CFBD rewrote PPA history in Sept 2026; the live post-fix 2025 figure
     is 0.112. Any PPA, success or explosiveness number from the pack must not be mixed with our
     live frames.
  2. **The notebook's definition of explosiveness is wrong.** It calls it a share of big plays;
     the values (FBS mean 1.25, range 1.05-1.50) are CFBD's average PPA on successful plays.
- **What the pack has that could save API calls:** every FBS-vs-FBS game 2003-2025 carries
  quarter line scores and pregame Elo (100% coverage every season), and every play has its
  period — the raw material for first-half box stats (the H-FHBOX idea) without ~2,400 calls,
  subject to the PPA-scale caution and the licence.
- **Proposed rows:** none.

## 01 Intro to data
- **What it does:** picks one game (Notre Dame @ Miami, 2025 week 1), pulls its 168 play rows and
  23 drives by game id, charts plays per drive, averages yards per drive by team.
- **Relation to Beat Vegas:** the pack's quarter scores give that game's first half as Miami 14,
  Notre Dame 7 — our `games` row agrees exactly (14 / 7 / 21, `first_half_source = linescores`).
  Same game id, same answer.
- **Cautions:** (1) "plays" in the pack's play files include kickoffs, timeouts, penalties and
  end-of-quarter rows, so plays-per-drive is not snaps; anything pace-related must filter play
  types first. (2) Play rows are not stored in game order; sort by drive and play number.
  (3) `games.csv` gains lower-division games from 2021 (≈1,500 → ≈3,700 a season); always filter
  to FBS-vs-FBS, as `etl/fbs.py` does.
- **Proposed rows:** none.

## 02 Simple rankings
- **What it does:** scales each team's full-season offense and defense PPA (then also success
  rate) to 0-1, averages them with hand-picked weights, ranks the 136 FBS teams, and shows how
  the top moves under offense-heavy and defense-heavy weights. 2025 top three: Ohio State,
  Indiana, Texas Tech.
- **Relation to Beat Vegas:** (1) A ranking is offense *minus* what the defense allows — a
  strength gap, which is what predicts a **margin** (H-MARGIN's question). A first-half **total**
  needs the opposite combination: both offenses' production *plus* what both defenses allow.
  Our model already carries that (`combined_off_ppa`, `combined_def_ppa`, `combined_fh_offense`,
  `combined_fh_defense`). (2) The notebook uses full-season numbers, which know the future; our
  features are season-to-date as of kickoff. (3) Our regressor learns its weights instead of
  picking them. (4) Of its four inputs the champion has three: off/def PPA for both sides and
  offensive success; it has **no defensive success rate and no explosiveness** (58 inputs) —
  both are already in the registered H-SHADOW-F input list (pre-registered, engine not built).
- **Cautions:** unadjusted for opponents (09/10 cover that); min-max scaling lets one extreme
  team set the scale; old PPA scale (see 00).
- **Proposed rows:** none (the gap it exposes is already H-SHADOW-F).

## 03 Metrics comparison
- **What it does:** correlates team-season efficiency stats (2025, 136 FBS teams) and flags
  "boom-or-bust" offenses: top 15% in explosiveness, bottom 40% in success rate (12 teams, e.g.
  UTEP, Wake Forest, Colorado, Kansas State, Texas).
- **Findings worth keeping:** offensive EPA per play is mostly success rate (r 0.91);
  explosiveness is almost independent of success (r −0.08) and only loosely tied to EPA (0.28).
  On defense, success rate allowed tracks pass and rush EPA allowed (0.75 / 0.70); front-seven
  havoc runs opposite to all of them (−0.44 to −0.63); defensive explosiveness allowed is close
  to independent of everything (|r| ≤ 0.27).
- **Relation to Beat Vegas:** the champion carries EPA and offensive success, which by this table
  largely duplicate each other, and no explosiveness, the one input that carries different
  information. That supports H-SHADOW-F's input list. The 2026 factor screen (87 comparisons)
  screened the live inputs only, so explosiveness has never been read against the first-half
  residual.
- **Cautions:** one season of full-season numbers; explosiveness is an average over successful
  plays only, so it is noisier for low-success teams — exactly the boom-or-bust corner. Old PPA
  scale (00).
- **Proposed row (proposal only):** H-BOOM-R — see the list at the end.

## 04 Team similarity
- **What it does:** standardises 12 season stats per team (offense/defense EPA, success,
  explosiveness, line yards, second-level yards, points per scoring opportunity) and finds each
  team's nearest neighbours by straight-line distance. Alabama 2025: TCU (1.42), then Virginia,
  New Mexico, Iowa State, SMU (2.07-2.54).
- **Relation to Beat Vegas:** none direct. A "find comparable past games and see where their first
  half landed against the line" idea is a cruder version of what the gradient-boosted model
  already does (it splits on the same kind of profile); not worth its own row.
- **Cautions:** the radar chart rescales every spoke across only the four teams drawn, so one team
  is always at 0 and one at 1 — near neighbours look wildly different. Every stat gets equal
  weight in the distance, and EPA/success are near-duplicates (03), so "efficiency" counts
  roughly twice. Full-season numbers; old PPA scale.
- **Proposed rows:** none.

## 05 Matchup predictor
- **What it does:** predicts "did the home team win" for 2025 FBS-vs-FBS games (784 with stats)
  from four differences built on 2024 full-season PPA and success rate, logistic regression,
  random 80/20 split, then a one-matchup probability helper.
- **What it actually does:** predicts a home win for **all 157 test games**. Its 59.2% accuracy is
  exactly the home-win rate (the majority-class baseline it prints beside it). Re-checked in a
  scratchpad copy: standardising the four inputs does not help (58.6%, still 99% home); the four
  differences are built offense-against-defense-allowed in a way that partly cancels, and every
  coefficient comes out negative. One correctly-signed net rating — (home offense − home defense)
  − (away offense − away defense), prior-season PPA — gets 61.1% and predicts home 74% of the
  time; it correlates 0.39 with the final margin. (157 test games: ±4 points of noise either way.)
- **Relation to Beat Vegas:** H-MARGIN (`docs/MARGIN.md`, run 37670166376) is the grown-up version:
  `bv_margin_v1` picked 2025 winners 70.1% of the time against Vegas's 72.8% (790 games) —
  different test sets, so read side by side, not as a contest. Its random split leaks little here
  because every input is prior-season; with in-season inputs it would, which is why our harness
  always trains on seasons before the target.
- **Cautions:** accuracy hides a do-nothing model; always print what share of predictions each
  class gets. Prior-season inputs only. Old PPA scale.
- **Proposed rows:** none.

## 06 Custom rankings
- **What it does:** 02 with a configurable list of (stat, weight, higher-is-better); default is
  EPA 30% / success 15% / explosiveness 5% on each side of the ball. Lists every numeric column
  available (≈80) for building your own.
- **Finding:** the default top ten is the same ten teams as 02's first two-stat ranking, only
  reordered (Ohio State, Indiana, Notre Dame, Texas Tech, Toledo, Oregon, Utah, Washington, James
  Madison, Vanderbilt). Hand-tuned weights move little when EPA carries most of the weight and
  success rate largely duplicates it (03).
- **Relation to Beat Vegas:** none new beyond 02; useful only as the column catalogue for the
  advanced-season file.
- **Proposed rows:** none.

## 07 Drive efficiency
- **What it does:** 2025 FBS-vs-FBS drives (18,758): points per drive by offense and allowed by
  defense, how drives end, and points per drive by starting field position.
- **Two bugs, both checked in a scratchpad copy:**
  1. **Field position is read from the home team's end.** `startYardline` is the absolute yard
     line (home offense mean 30, away 71); `startYardsToGoal` is the offense's own. Binned as
     shipped, red-zone starts score *least* (1.64 per drive) and the notebook says the chart
     confirms the pattern. Corrected: 1.78 / 2.26 / 3.06 / 3.99 from own 0-25 to opponent 25-0.
  2. **116 drives in 77 games carry impossible point totals** (up to 52 on one drive) because the
     drive's starting score resets to 0 mid-game; resets that land at 8 or fewer points are
     invisible. North Texas's 4.27 points per drive becomes 3.55 with the impossible rows removed
     (still first).
- **Relation to Beat Vegas:** a first-half total is first-half drives × points per drive. On 2025
  FBS games: 11.8 first-half drives per game (sd 2.4), 2.11 points per first-half drive, and the
  drive count correlates only 0.23 with first-half points — scoring efficiency, not the number of
  possessions, carries most of the variation. Our live model has no pace or drive input since
  B-SERVE removed the first-half play-by-play family (`mm_pace` among them) for a join defect, not
  for lack of value; H-FHBOX (decided 2026-10-05, not yet registered) is where they come back.
- **Cautions:** never bin on `startYardline`; screen drive points for >8 or <0; old data
  conventions may differ by season (check before pooling 2003+).
- **Proposed row (proposal only):** H-FHDRIVE — see the list at the end.

## 08 Offense vs defense
- **What it does:** lines one offense up against one defense (default Indiana's offense vs
  Georgia's defense, 2025 full season) on seven paired stats — EPA, success, explosiveness,
  standard- and passing-down EPA, line yards, stuff rate — each placed 0-1 against all FBS teams
  with direction flipped so longer always means the better unit. Correctly done (scaled over the
  whole league, unlike 04's radar).
- **Relation to Beat Vegas:** this is the unit-against-unit idea behind the five matchup columns
  B-SERVE removed with the first-half play-by-play family (`mm_epa_edge`, `mm_success_edge`,
  `mm_explosive_edge`, `mm_pace`, `mm_havoc`). For a total, a game is two of these matchups
  added together (home offense vs away defense, and the reverse). Line yards and stuff rate are
  not in our inputs; nothing suggests they matter for totals beyond what EPA carries.
- **Cautions:** full-season, unadjusted for opponents; old PPA scale.
- **Proposed rows:** none (the matchup columns return through H-FHBOX if anywhere).

## 09 Opponent adjustments
- **What it does:** a one-pass schedule adjustment on 2025 game-level EPA: each game's offense EPA
  minus what that opponent allowed on average (and the mirror for defense), averaged per team.
  Biggest movers up: UCLA (+40 places), Kentucky, Wisconsin, Florida — losing teams with brutal
  schedules.
- **Cautions:** the opponent's average includes the very game being adjusted, and the opponent's
  own number is unadjusted (one pass). 10 does it properly.
- **Proposed rows:** none (see 10).

## 10 SRS-adjusted metrics
- **What it does:** solves every team's offense and defense rating at once by least squares
  (an SRS), net = offense − defense. 2025 top five: Indiana, Ohio State, Notre Dame, Oregon, Miami.
- **A flaw that turns out small:** as written, each system rates a team's offense against its
  opponents' *offense* ratings (one unknown vector serves both sides), not their defenses. Checked
  against a correct joint ridge fit (offense EPA = league mean + team offense + opponent defense):
  full-season rankings agree 0.99, and fitted on weeks 1-7 both predict week 8+ margins about
  equally (correlation 0.567 as shipped, 0.583 joint ridge, 0.562 with no adjustment at all, 410
  games).
- **The finding that matters for H-RIDGE-F (2025 only, scratchpad):** fitted on weeks 1-7
  first-half points (from quarter scores) and tested on 410 week 8+ games, season-to-date
  first-half points for/against correlate **0.14** with the later first-half total, and a ridge
  opponent adjustment adds nothing (0.137-0.139 across penalties 1-50). Its error improves only
  with heavy shrinkage (8.59 at penalty 20) — about the same as predicting the test-set mean for
  every game (8.63, a flattering benchmark). For margins, opponent adjustment helps a little; for
  first-half totals, on this evidence, it does not. Context: the champion's and Hard Rock's
  average first-half miss on 2026 is about 8.3 / 8.2 points (213 games) — everyone works close to
  that floor.
- **Proposed rows:** none new. This is a prior for the existing proposal H-RIDGE-F
  (`docs/KNOWLEDGE.md`): one season says expect little; it would need its own registered test
  before anyone builds it.

## 11 Metric distribution explorer
- **What it does:** one stat, one team, placed on a histogram, a boxplot and a percentile
  (default: Indiana's defense EPA allowed, better than 95% of FBS). Correct, including the flipped
  direction for defensive stats.
- **Relation to Beat Vegas:** none. **Proposed rows:** none.

## 12 Efficiency dashboards
- **What it does:** a one-team profile (default Michigan): 14 stats with percentile and FBS rank,
  plus single- and two-team radar charts scaled across all FBS teams (correct, unlike 04).
  Michigan 2025: 8th in avoiding stuffed runs and in big plays allowed; 96th on passing-down
  offense, 117th on passing-down defense, 129th in offensive explosiveness.
- **Relation to Beat Vegas:** a possible format for a game page's "team profile" someday; nothing
  for the model. **Proposed rows:** none.

## 13 Weekly team trajectory
- **What it does:** week-by-week EPA for one team (default Texas), a 4-game rolling average,
  last-four-games vs season form for every team, most improved/declined, and volatility (spread
  of weekly offense EPA; most volatile Louisiana Tech, Boise State, USC; most consistent Eastern
  Michigan).
- **Its central claim, tested:** the notebook says late-season form is often the best predictor.
  Walk-forward on 2025 (474 games, weeks 6+, both teams with 4+ prior games, only earlier games
  used): for **margins**, the full season-to-date average beats the last four games (0.55 vs
  0.49) and a decaying weight sits between (0.51). For **first-half totals**, recent form reads
  slightly higher (0.16 vs 0.13) — inside the noise for 474 games (about ±0.05).
- **Relation to Beat Vegas:** the Texas chart is the picture of why "the model cannot learn
  in-season" is less costly than it sounds: a team's weekly EPA swings far more than its true level
  moves. The decaying-weight arm is already noted for H-RIDGE-F in `docs/KNOWLEDGE.md`.
- **Cautions:** "volatility" from 11-12 unadjusted games is mostly schedule and noise.
- **Proposed rows:** none.

## Proposed rows (proposals only; none registered — Tate decides)
- **H-BOOM-R** (from 03): does a matchup's combined boom-or-bust profile (season-to-date
  explosiveness high and success rate low, both offenses) predict the first-half residual against
  Hard Rock's real close? Measurement only, prospective 2026 games (2023-25 is spent for rule
  selection); a pass licenses a paper arm at most. Distinct from H-SHADOW-F, which adds
  explosiveness to the model for accuracy; this asks about direction against the market.
- **H-FHDRIVE** (from 07): season-to-date first-half drives per game and points per first-half
  drive (offense and defense, both teams) as shadow-engine inputs, inside or beside H-FHBOX;
  judged like H-SHADOW-F (paired error against the champion on 2026 games). History could come
  from the pack's drive files (2001-2025) subject to the licence and the two drive-data defects.

## Open question for Tate
- **The licence**: personal use only, no redistribution. Using pack data inside the engine is
  arguably personal use, but what reaches Neon also feeds the public site. Learning-only, or a
  data source? Undecided.
