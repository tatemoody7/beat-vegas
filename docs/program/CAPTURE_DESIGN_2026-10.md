# Hard Rock off-market capture: the design note (2026-10-11)

**Tate's calls (2026-10-11, the October review, roadmap v2.0 decision 6):** the next build is the
Hard Rock off-market capture, scoped to *columns plus denser Saturday polls*, landing this week
after Tuesday's card (PR Wednesday, first denser Saturday 2026-10-17). Nothing in this note changes
an arm, the judge (`docs/CONSENSUS.md`: the 2-hour window, the book set, the median) or the
protocol; it changes what the feed's rows keep and how often the Saturday close poll looks.

## Why

The review (`docs/program/REVIEW_2026-10.md` §C4) found the one Hard-Rock-specific edge nobody has
tested ("Hard Rock is off the market inside hours") has no data behind it: Hard Rock's 1H history
begins 2026, its close is a point or more off the retail median in about one game in three, and
the capture reaches about 85 judgeable games in six weeks. Two facts of the capture make the
question unanswerable today (REVIEW §B2, the strategic review's data audit):

1. **The book's own update time is discarded.** The Odds API sends `last_update` per market and
   per bookmaker; `sources/odds.py::_rows_for_market` keeps it in the row dict, and
   `scripts/poll_lines.py` / `scripts/poll_full_game.py` drop it when they build the
   `OddsSnapshot`. "Fresh" therefore means *we saw the number again* (`last_seen_at`), so a book
   frozen for a day counts as a fresh close, and the lead/lag between Hard Rock and the other
   books cannot be measured.
2. **The event id is discarded.** Every poll re-matches on team names (`etl/match.py`), where a
   prefix scores 1.0 ("Texas" against "Texas Tech") and ties go to the first game scanned; an
   unmatched event is printed, not stored.
3. **Saturday polls are too coarse for the drift.** The close poll looks only 120 minutes ahead
   (`CLOSE_LOOKAHEAD_MIN`), once per UTC hour from Vercel (GitHub's 30-minute crons are the
   unreliable backup), so a game gets about two reads inside the window and nothing between the
   8am sweep and 2 hours out, while Hard Rock's main-line share falls from 97% beyond 48 h to
   31% inside 2 h (`docs/HISTORY.md` 2026-10-01).

## The change

### Schema (additive; `migrate.yml` before the deploy, the usual order)

Two nullable columns on `odds_snapshots` (`beatvegas/db/models.py::OddsSnapshot` and the
`_MIGRATIONS["odds_snapshots"]` map in `beatvegas/db/store.py`):

| column | type | meaning |
|---|---|---|
| `event_id` | VARCHAR | The Odds API's event id for the row (the feed's own key) |
| `feed_updated_at` | TIMESTAMP (naive UTC) | the feed's `last_update` for that market at FIRST capture of this price state; never overwritten |
| `feed_reseen_at` | TIMESTAMP (naive UTC) | the newest feed `last_update` seen while the price stayed unchanged, when it differs from the first |

**Correction (Tate, 2026-10-11, before implementation):** the note first called the column
`book_updated_at`. The Odds API's `last_update` is when the PROVIDER last observed the
bookmaker's odds, not when the bookmaker changed them, so the column is named for what it is.
Three stamps, three meanings, and a fourth fact no column holds:

| stamp | set by | means | does not mean |
|---|---|---|---|
| `feed_updated_at` | the provider | its last observation of the quote, at our first capture | when Hard Rock posted the price |
| `captured_at` | us | our first poll that saw this price state | when the price appeared |
| `last_seen_at` | us | our last poll that still saw it unchanged | that it stood continuously in between |
| the Florida app | Tate | a screenshot or a ticket | — |

Two polls seeing the same price prove it was quoted at both instants, not that it was available
between them; the reader owns that distinction. A missing or unparseable stamp is NULL, never
invented (`beatvegas/sources/odds.py::parse_feed_stamp`); a stamp more than ten minutes ahead of
our own clock is reported in the run log and kept. Rows written before the columns existed keep
`feed_updated_at` NULL for good: it means "at first capture" or nothing; stamps seen on later
re-sightings of those rows go to `feed_reseen_at`. The shared logic is
`beatvegas/snapshots_provenance.py`.

Rows written before the change stay NULL; nothing reads the columns on the site, so
`web/prisma/schema.prisma` is untouched (the app reads `odds_snapshots` by raw SQL, and only the
columns it names).

### Writers (one line each)

- `scripts/poll_lines.py` (1H): the `OddsSnapshot(...)` at the end of the match loop gains
  `event_id` and `feed_updated_at`; the re-sighting branch (`prev.last_seen_at = ...`) calls
  `note_reseen`, which leaves the first stamp alone and records a newer one in `feed_reseen_at`.
- `scripts/poll_full_game.py` (three `OddsSnapshot(...)` sites: totals, spreads, moneylines):
  the same two fields.
- `parse_feed_stamp` (`beatvegas/sources/odds.py`) parses the feed's ISO-8601 stamp to a naive UTC
  `datetime` (the project's convention) or None.
- The two history backfills (`backfill_1h_history.py`, `backfill_fg_history.py`) are not touched:
  their source rows carry no update stamp.

### The Saturday poll

`CLOSE_LOOKAHEAD_MIN` 120 → **360** for the Saturday ticks only: the workflow's resolve step picks
`CLOSE_LOOKAHEAD_MIN_SAT` for a tick inside Saturday's window (14Z Saturday to 05Z Sunday) and both
the precheck and the poll read that one step output, so they cannot disagree. Each Vercel tick (one per UTC hour, 14Z–04Z, 15 entries) then polls
every Hard Rock-priced game kicking off in the next 6 hours, so a game is read about six times
inside its last six hours instead of about twice inside two. Weeknight ticks keep 120: the
weeknight slate is one or two games and the question is a Saturday one.

**Credits.** A per-event 1H call costs 1 credit with the ten named books. Saturday today: about
45 games × ~2 reads ≈ 90 credits; after: about 45 × ~6 ≈ 270, i.e. **about +180 a Saturday,
+800 a month**, against ~3,300 a month in use and the 20K plan (`docs/OPS_ACCOUNTS.md`).
`poll_lines.py --max-credits` stays as the cap; the precheck's "events kicking off in the next N
minutes" line prints the count every tick.

**Not changed.** The judge's close window stays 2 hours (`consensus.CLOSE_WINDOW_H`); the
arms read `ev_cons`; no reading of any arm moves because more rows exist earlier. Vercel Hobby
cannot tick more than hourly, so "every 30 minutes" is not on offer; the wider lookahead is the
honest version of "denser".

### Parity edits the PR must carry

- `tests/test_workflows.py:832-835` pins `CLOSE_LOOKAHEAD_MIN == 120` and the precheck wording:
  it becomes a per-weekday assertion (Saturday 360, weeknight 120).
- `docs/HEALTH.md:161` and `:278` and `beatvegas/health.py:928` name the 120-minute window
  (`test_docs_parity.py` regenerates the rendered block): both say "6 h on Saturday, 2 h on
  weeknights".
- `web/lib/cronJobs.ts:132,157` comments; `CLAUDE.md`'s decision calendar row for `lines-close`.
- `tests/test_pick_columns_parity.py` does not read `odds_snapshots`; `test_e2e_schema_parity.py`
  reads `web/e2e/fixture/schema.sql`, which `scripts/dump_e2e_schema.py` regenerates after the
  model change.

## What it enables (each its own registry row, later)

- **The lead/lag read**: with `book_updated_at`, when Hard Rock's 1H line is off the median,
  whether it moved first or last, and how long the gap lasts (the strategic review's "untested
  place", REVIEW Part 1 topic 2). The early/stale-lines arm (ledger slot 5) is designed on this
  read, never before it.
- **Derivative consistency** (slot 4): Hard Rock's 1H total against the fair 1H implied by the
  consensus full-game total and spread, sampled six times a game instead of twice.
- **The off-market frequency** by hour before kickoff, which §A of the review could only read at
  the close (n 85).

## Rollout and verification

1. PR: model + `_MIGRATIONS` + writers + `_naive_utc` + the Saturday lookahead + the parity
   edits; unit tests for `_naive_utc` and for the writer carrying both fields (synthetic feed
   row → `OddsSnapshot`); `tests/test_workflows.py` green.
2. `migrate.yml` dispatched on main after the merge (additive; `init_db` ALTERs the two columns);
   `/api/health` ok.
3. The next `lines_watch.yml` tick writes rows with both fields: one SELECT on Neon shows
   `book_updated_at IS NOT NULL` on the newest rows and `event_id` matching the feed.
4. Saturday 2026-10-17: the precheck line shows the 6-hour count each tick; the credits line
   per tick stays under the cap; `close_coverage_pct` unchanged (1.000 on 10-10).
5. One `study.yml` read the following Monday (a development read, no row): rows per game inside
   6 h, before and after.

## Implemented 2026-10-11 (Step 1 of the pricing-inefficiency programme)

Shipped as one PR with the corrections above, plus `scripts/probe_hr_keys.py`: a by-hand probe
that asks the feed for `hardrockbet` and `hardrockbet_fl` together with the keys left as spelled
(the capture folds every state key into `hardrockbet`; the Odds API's bookmaker table calls that
key the Indiana book, "currently same odds as several other states"). One matching slate proves
nothing beyond that slate; any Florida-specific research must cite verified Florida data. The
scheduler fact, checked on 2026-10-11 over the last 40 `lines_watch` runs: 28 were Vercel
`workflow_dispatch` ticks (`lines-close` / `close-weeknight`) and 12 were GitHub `schedule`
runs, so both schedulers write rows; the resolve step chooses the look-ahead from the clock, not
the trigger, so a tick from either reads the same window. Verification steps and the probe's table: `docs/HISTORY.md` 2026-10-11.
