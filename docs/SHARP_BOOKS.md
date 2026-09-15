# Sharp books and first-half totals — does a sharper reference line exist?

**Finding (descriptive, no criterion): a sharp book does post CFB first-half totals
through the Odds API, but on 2-3 of 75 events.** Probe only — no bookmaker key changed,
no swap. Run **Tuesday 2026-09-15, 21:13 UTC** with `scripts/sharp_book_probe.py --live`
(64 credits, 55,037 → 54,973); pure pieces pinned by `tests/test_sharp_book_probe.py`.
Registry row **H5** in `docs/HYPOTHESES.md`.

## Why it was run

Every "market" number the system compares Hard Rock to — the off-market test, the fair
price behind the kill line, the consensus close behind line value — is a **retail
median** over nine books. A sharp book (Pinnacle, Circa, BookMaker, BetOnline) would be a
better "true line", and the lead/lag question would become the one professionals ask: does
Hard Rock trail Pinnacle. The per-event 1H call bills ten bookmaker keys as one region, so
a sharp key can only enter by displacing a retail one. Before spending a slot, find out
who posts.

## What was done

1. `list_events` (free): 75 upcoming events.
2. **Discovery:** the first 3 events, `markets=totals_h1`, regions **us, us2, eu** (3
   credits each) — every bookmaker key posting a first-half total, retail or sharp.
3. **Coverage:** every key found outside our ten, plus `hardrockbet`, as a bookmakers list
   (1 credit per event) across all 75 events: posted or not, line, prices, update time, and
   Hard Rock's line in the same response.

Budget cap 120 credits; the API bills nothing for an event with no odds posted.

## What it found

- **Discovery, 3 events:** thirteen keys post a 1H total — our ten, plus **betonlineag
  (3 of 3), betus (3 of 3), pinnacle (1 of 3)**. No `circasports`, `bookmaker`, `lowvig` or
  `betcris` anywhere.
- **Coverage, 75 events, Hard Rock posted on 52:** **Pinnacle posted on 2**, **BetOnline
  on 3**, both only on events Hard Rock had also priced. **BetUS posted on 55** — a retail
  offshore book, not a sharp one — 0.31 points from Hard Rock on average and never updated
  after it.
- **Where both posted, the sharp lines sat above Hard Rock:** Pinnacle +1.00 (n 2),
  BetOnline +0.67 (n 3). Two and three games; a direction, not a finding.
- **Update timing:** neither sharp key's `last_update` was later than Hard Rock's on any
  shared event. With n ≤ 3 this says nothing about who leads.

### Coverage of the sharp keys across the slate

75 events called; Hard Rock posted a 1H total on 52.

| key | posted | where HR posted too | HR posted, sharp absent | mean abs diff vs HR | mean signed (sharp − HR) | updated after HR |
|---|---|---|---|---|---|---|
| betonlineag (BetOnline) | 3 | 3 | 49 | 0.67 | +0.67 | 0 |
| betus (betus) | 55 | 52 | 0 | 0.31 | -0.04 | 0 |
| pinnacle (Pinnacle) | 2 | 2 | 50 | 1.00 | +1.00 | 0 |

## What this licenses, and what it does not

**It does not license a swap.** A reference line that exists on 2-3 of 52 Hard-Rock-priced
games cannot anchor an off-market test, a fair price or a line-value basis; the retail
median stays. It does not rule one out either: this was a **Tuesday** probe, and Hard Rock
itself posts 31% of its 1H lines by Tuesday and 97% by Saturday morning
(`CLAUDE.md`, week 2). Whether Pinnacle's first-half coverage widens toward kickoff is
unknown from this run. A Friday-evening or Saturday-morning repeat (≈ 80 credits) would
answer it; that is Tate's call, not this row's.

BetUS is worth one sentence: it posted on more events than any of our nine retail keys
did in discovery, tracks Hard Rock within a third of a point, and is not sharp. It could
widen the consensus; it would not sharpen it.

## Reproduce

```
PYTHONPATH=. python scripts/sharp_book_probe.py                       # dry run, free
PYTHONPATH=. python scripts/sharp_book_probe.py --live --max-credits 120
```

Writes `reports/sharp_books_<UTC>.{md,json}` (gitignored); exits 0. Reads nothing from
Neon; touches no config.
