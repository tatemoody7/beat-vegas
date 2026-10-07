# The program-wide false-positive budget: three ways to split it

**Written 2026-10-07 for Tate's decision. Nothing changes from this document.** Whichever
option is chosen lands as its own registry PR (`docs/HYPOTHESES.md` amended before any row it
touches reads a new number).

## The decision

You approved one false-positive budget for the whole program on 2026-10-06 and left the split
open. Today every registry row spends its own 5%, so the more rows run at once, the likelier it
is that one of them "passes" on luck alone. With the six confirmatory rows now live or waiting,
that chance is about **1 in 4** for the season.

**My recommendation is Option 2:** tighten only the rows whose pass can move something toward
the champion, and leave the rows whose pass is a labelled finding at 5%. It costs those three
rows about 13 more picks each, and leaves the money path's own clock alone. The other two
options are stated with their costs so you can choose.

## What counts, and what does not

A false positive matters only where a pass unlocks something. The rows sort into three groups:

| row | what a pass unlocks | in the budget? |
|---|---|---|
| H-PCT-TIE (margin above the bar, 2 paper arms) | a paper promotion decision for you | yes |
| H-SHADOW-F, H-INSEASON-T (shadow engines) | a registered promotion decision that would supersede H-STOP-2 | yes |
| H-NEGGAP-P (paper overs, 3 arms) | nothing at real money: a finding | finding |
| H-FG-P (paper full-game unders) | nothing at real money: a finding | finding |
| H6 (when to bet, one look on 2026-12-07) | "best build" wording, or no build preferred | finding |
| H-STOP-2 (the champion's clock) | a success changes nothing; only its failure boundary acts, and that is the 20% "missed edge" side, not this budget | no |
| H-TIMING, H-CLOSE-W | measurement and sensitivity reads, no test | no |
| H-HIST, H-ELO-F, H-WEPA-F | already decided; their 5% is spent and stays on the record | spent |

Two rows are already collecting (H-NEGGAP-P since 2026-10-02, H-FG-P from the 10-08 build).
Changing their thresholds mid-test is a protocol change, so every option below leaves running
rows as registered unless it says otherwise, and applies to rows that have not read an
observation yet (H-PCT-TIE, H-SHADOW-F, H-INSEASON-T have no collector or engine yet; H6 has
not had its look).

## The three options

The cost of a tighter threshold is time: an arm with a real edge needs more picks before its
clock can pass. The table uses the line-value clock (μ₁ +0.50 pts, σ 1.371, power 80%, the
frozen H-STOP-2 shape every paper arm shares); "picks" is the expected count to a pass when the
edge is real (Wald's approximation, `stopping.sprt_expected_n`). H-STOP-2's own clock took 9
line-value picks in its first week, so roughly ten picks is a week.

| | Option 1: one 10% cap, equal per row | Option 2: tighten what unlocks (recommended) | Option 3: keep 5% each, count it honestly |
|---|---|---|---|
| The rule | 10% for the whole program, split evenly over the 6 confirmatory rows (1.67% each), then over each row's arms and clocks | The three rows whose pass unlocks a promotion share 5% (1.67% each); the three finding rows keep 5% each and every pass of theirs is reported as "a finding, licenses nothing" | No threshold changes. The registry gains a running count of live rows, and every pass is reported beside the program-wide chance of at least one fluke (26% at six rows); a promotion also needs a repeat the next season |
| H-PCT-TIE, per clock | 0.42% → about **58** picks | 0.42% → about **58** picks | 1.25% → about 45 picks (today) |
| H-SHADOW-F / H-INSEASON-T | 1.67% across their comparisons | 1.67% across their comparisons | 5% (today) |
| H-NEGGAP-P, per clock | 0.28% → about **63** picks (a mid-test change) | 0.83% → about 50 picks (unchanged) | unchanged |
| H-FG-P, per clock | 0.83% → about **50** picks (a mid-test change) | 2.5% → about 37 picks (unchanged) | unchanged |
| H6 (12-07) | Holm at 1.67% across its 6 pairs | 5% (unchanged; a finding) | unchanged |
| Chance of ≥ 1 fluke pass, program-wide | about 10% | about 5% on the rows that unlock anything; findings stay labelled | about 26% |
| What it costs | Every row slows; two running rows change mid-test | Three not-yet-started rows slow by about 13 picks (~1 week) each | Nothing now; the protection moves to "repeat next season", which costs a season |

### What I could not settle from the data

- The shadow-engine rows (H-SHADOW-F, H-INSEASON-T) are not built. Their comparisons mix an
  accuracy test with two clocks, so the per-comparison split inside their 1.67% is written in
  their own PRs, before the engines log anything.
- The 26% assumes the rows' errors are independent. They are not fully: every paper arm shares
  the champion's model and the same weeks, so the true chance is somewhat lower. It is not
  measurable from one season.

## If you pick one

- **Option 1 or 2:** one registry PR amends the affected rows' criteria (dated, "amended before
  any observation", or for Option 1 a stated mid-test change on H-NEGGAP-P and H-FG-P), adds a
  "Program budget" section to `docs/HYPOTHESES.md` with the live allocation, and a registry test
  that the allocations of live confirmatory rows sum to no more than the cap.
- **Option 3:** one registry PR adds the live-row count and the replication rule; no row's
  numbers change.
