# The January 2027 review — templates (roadmap v2.1, written 2026-10-11)

Two reads decide the 2026 research season: **2026-12-07** (mid-point, no decisions) and
**2027-01-25** (final). Between them every arm, the judge (`cv1`) and the protocol (`p1.1`) run
unchanged (roadmap v2.0 decision 3). This file holds the templates for both reads, the one-page
Monday read, and the 2027 default Tate drafted on 2026-10-11 for January to confirm or change.
Every decision slot is blank until Tate fills it at the read.

## The one-page Monday read (every Monday from 2026-10-19)

One sitting of about 30 minutes. Tate opens the session; Claude brings the page. Order:

1. **Arms, one line each** (`protocol_position` from `study.yml`, the runner's numbers): readings
   so far, the SPRT position against both boundaries, the judge's mean EV with its interval,
   exclusions by reason. The six registered arms: H-ARM-1HU, H-ARM-1HO, H-ARM-FGU, H-ARM-WX1H,
   H-ARM-WXFG, H-ARM-HT1H.
2. **The judge's own reading** (the four side readings: Hard Rock vs the field, the close window
   fill rate, the share of picks excluded, the H-JUDGE slope when re-read).
3. **What broke** (`/api/health` verdicts, the card and grade contracts, any capture gap).
4. **Decisions needed** (normally none; a bug fix shown before/after; account-side items).

Not on the page: the personal ledger (Results shows it), the weekly report, model accuracy tables.

## 2026-12-07 — the mid-point read (no decisions)

- Every arm's position and its readings-to-date; which arms could still reach a boundary by the
  season's end at their weekly volume, which cannot.
- The H6 confirmatory look (`docs/WHEN_TO_BET.md`; the script refuses `--confirmatory` before this
  date). Its verdict is recorded; it licenses nothing.
- H-VENUE-1 development read: games with both venues inside the window, best-of-two EV, and whether
  the feed's Kalshi price includes the taker fee (the fee question must be answered before January).
- The capture dataset so far (book timestamps, event ids, Saturday density) and what the two
  structural arms (slots 4-5) could be designed on.
- Nothing is promoted, killed, changed or registered at this read.

## 2027-01-25 — the final read

### What is read
| Item | Source | Decision slot |
|---|---|---|
| Each arm's final SPRT position (PASS / KILL / timeout) | `protocol_position`, every completed week | promote to $10 live validation / end / carry into 2027 under new rules: ______ |
| The judge validated | H-JUDGE re-read on the full season; the four side readings | keep `cv1` / amend (own row): ______ |
| H-VENUE-1 registered read | `venue_check`, every week captured, fee-inclusive prices stated | Kalshi account: yes only if best-of-two beats Hard Rock alone by about 1 pt EV over 100+ games (CPA first): ______ |
| H-ARM-EVP, exploratory (value at Hard Rock's price, +2%) | the newest `arm_positions` row: mean `ev_cons` with its interval, exclusions, and the gap rule's readings over the same weeks | register a 2027 confirmatory arm (its own row, fresh alpha) / drop: ______ |
| The Hard Rock capture dataset | `odds_snapshots` with `event_id` / `book_updated_at` | design slots 4-5 for 2027: ______ |
| The personal ledger | Results, never evidence | continue / stop (Tate's own call): ______ |
| Research-year deliverables | this file, `docs/HISTORY.md` | written beside the promotion bar: ______ |

### The 2027 default (drafted 2026-10-11; January confirms or changes it)
- Edge target **+1.5%** EV against the consensus close (2026 ran at +3%).
- **Two-season clocks**: an arm registered for 2027 runs through 2028 before a verdict.
- **Capture-based arms first** (derivative consistency, stale lines, the venue question); model
  arms return only if one passes in 2026.
- A 2026 pass earns **$10 flat live validation only**, decided here; a second season is still
  required before any larger stake or any product work.
- If January reads "no +3% edge", 2027 runs the same way: paper arms, the judge, the ledger.
- The alpha ledger: ______ (K = 10 at 0.5% each in 2026, never recycled; 2027's own ledger to be set).

### 2026 success, stated before the read
The promotion bar stays: one arm passes its registered test. Whatever the arms do, the research
year delivers, and January reports on each: a clean reading on every arm; the Hard Rock capture
dataset; the judge validated; 2027 designed (this file filled in).

## Account-side calendar (Tate)
- 2026-11-06: CFBD to Tier 1 at the renewal. The Odds API stays on 20K. Actions cap $20.
- After 2026-10-19: one late GitHub cron per job (the retries go); post-mortem tables stop once
  the public accuracy number is re-sourced.
- Friends: one plain message (research season, paper ratings, nothing proven).
