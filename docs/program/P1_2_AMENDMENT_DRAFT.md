# Protocol amendment p1.2 — DRAFT for Tate's approval (not in force)

Status: **draft, 2026-10-14.** Nothing here changes `beatvegas/protocol.py`,
`scripts/protocol_position.py`, grading or any arm until Tate approves this text. Programme
step 9 (`~/.claude/plans/pasted-content-id-a68f…`, Part 10 §4). On approval the text below is
copied into `docs/PROTOCOL_2026.md` as p1.2 and into each arm's registry row, then the reader
changes land in their own PR.

## Why it is needed

1. **A week is read before it is over.** `protocol_position.completed()` admits a week once every
   row logged *so far* is graded. A Tuesday pick that grades Wednesday makes the week "complete"
   with one reading; the Friday and Saturday picks then reopen it. Harmless only while reads run on
   Mondays (they do: `pricing_monday.yml`, 12Z).
2. **The bowls collapse into one reading.** CFBD files every postseason game as `week 1`
   (`games.season_type = 'postseason'`): 2023 bowls ran 12-16 → 01-09, 2024 12-15 → 01-21, 2025
   12-14 → 01-20 (query G6). Keyed by (season, week), a whole bowl season would be one observation,
   read only after the title game.
3. **One ungradable pick freezes its week for good.** A pick whose game has no final, or a 0-0 first
   half without proof, never grades; its week never completes, and every later week waits behind it.

## The rules (exact text proposed)

**R1 — the reading unit.** A regular-season pick belongs to the reading week (season, CFBD week).
A postseason pick (`games.season_type = 'postseason'`) belongs to (season, `post`, ISO year, ISO
week of its kickoff in UTC). ISO weeks run Monday–Sunday and are defined across New Year
(2026-12-28 → 2027-01-03 is 2026-W53), so a 12-30 bowl and a 01-02 bowl share one reading while the
season stays 2026. Conference-championship games keep their regular-season week. Readings enter the
SPRT in reading-week order.

**R2 — when a reading week is complete.** A reading week enters only when (a) every pick logged in
it is graded or permanently excluded (R3), **and** (b) the read runs at or after 12:00 UTC on the
first Monday after the latest kickoff among its picks. Before both hold, the week is `pending`. The
read's clock is the Monday workflow's own run time.

**R3 — the seven-day exclusion.** At a read run ≥ 7 days (168 h) after a pick's kickoff, a pick whose
game still has no final score, or (for a first-half pick) no trusted first-half total
(`grading.trusted_first_half_total` is None), becomes an exclusion with reason `ungradable`:
counted beside the arm's readings, never an observation. **It stays an exclusion even if the data
arrives later**, so a week already read can never change. A grading outage with the data present
leaves the pick `pending`; only missing data excludes.

## How R3 is made permanent without touching grading

The exclusion is recorded in a new additive table `arm_exclusions (hypothesis, pick_table,
pick_id, reason, decided_at, run_id)`, written only by `protocol_position.py --write` in the Monday
workflow. The reader treats a pick listed there as excluded forever, whatever grading later writes.
Grading, `ev_cons`, the judge and the pick rows are untouched.

## Why seven days, and why permanent

- Grading lands within two days for 275 of 326 played 2026 games; the only late cluster (50 records
  graded 2026-09-15) was the one-off backfill when `game_records` was introduced (queries G1, G8).
  Seven days gives play-by-play proof a full week and still closes the week before the next Monday.
- Permanent, because a late grade re-entering would change a week's mean and the LLR path after
  they were read, and a STOP or PROMOTE already reported could flip.
- PBP proof was needed for 2–3 games a season in 2023-25 (query G3).

## Impact on the data as of 2026-10-14 (measured)

| Rule | What would change today |
|---|---|
| R1 | Nothing: no postseason row exists yet |
| R2 | Nothing: no forward week is complete; H-ARM-1HO's week 7 reads `pending` either way |
| R3 | Nothing: 0 of the season's arm and paper picks and 0 of 26 real tickets are ungradable at 7 days (G2, G9); 2023-25 had 37–45 games a season with a final and no half total, **none** in the Hard-Rock-priced universe (G4, G7) |

No reading, exclusion or position changes on approval. The App State–Old Dominion half (10-10, a
0-0 line score with a 3-10 final, Q14) is not an arm pick.

## Decision for Tate

- Approve R1, R2 and R3 as written, or change the seven days, or keep R3's exclusion reversible.
- On approval: one PR — `docs/PROTOCOL_2026.md` p1.2, the registry rows, `arm_exclusions` (additive,
  `migrate.yml`), the reader change with fixtures for a mid-week read, a bowl season across New
  Year, and an ungradable pick that later grades.
