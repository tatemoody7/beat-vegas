# Board alignment — four behaviour changes for Tate's decision (none applied)

Status: **memo, 2026-10-14.** Programme step 15. Each item below could change which games the Board
lights green or how a ticket is judged, so each needs its own yes. The display-only Board fixes
(price age, the server's verdict in the reply) shipped in step 14. Measured on cards 17–28 (weeks
4–6, the scheduled builds); week 7's Saturday has not happened, so it is left out.

| # | Change | Measured impact, weeks 4–6 | Recommendation |
|---|---|---|---|
| B1 | Build the Board's bar from **upcoming** games only, as the card does | 0–3 upcoming games a Saturday checkpoint would read a different tier (below) | **Approve** |
| B2b | The server refuses the empty-slate fallback bar (1.75) and judges from the newest **scheduled** card | 0 occurrences: one manual card in weeks 4–7 (card 18), slate n 49, no empty slate | **Approve** (a guard; changes nothing that happened) |
| B4 | One QB-out source: the Board reads the newest card's fresh QB-out instead of Sunday's flag | 1 disagreement in weeks 4–7; it touched no game at or above the bar | Approve or leave; low stakes either way |
| B3 | Build the "Held" section: when a card is degraded, its BETs show under Held and the server honours the hold, as `BETTING_POLICY.md` says | 0 degraded cards in weeks 4–7 (13 cards) | **Approve** (it only matters on a bad day) |

## B1 — the bar, in detail

The Board computes its bar over every game of the week, including games already kicked off (their
last pre-kick quote); the card computes it over upcoming games only. After the week's first
kickoffs the two bars differ, so the Board can light a game the card (and the server) do not, or the
reverse. Using each game's last build-time gap:

| Saturday | Board bar | Card bar | Upcoming games whose tier differs |
|---|---|---|---|
| Wk 4, noon ET | 5.00 | 5.54 | 2 (Central Michigan @ Miami, Arizona @ Washington State) |
| Wk 4, 3pm ET | 5.00 | 5.78 | 3 (+ Oregon @ USC) |
| Wk 4, 7pm ET | 5.00 | 5.54 | 1 |
| Wk 5, noon / 3pm ET | 2.13 | 2.54 | 1 (Temple @ South Florida) |
| Wk 5, 7pm ET | 2.13 | 2.13 | 0 |
| Wk 6, noon ET | 1.13 | 0.59 | 2 (Coastal Carolina @ Marshall, Buffalo @ Toledo) |
| Wk 6, 3pm ET | 1.13 | 0.57 | 3 (+ Houston @ Kansas State) |
| Wk 6, 7pm ET | 1.13 | 0.35 | 1 (Boise State @ Fresno State) |

The direction varies: in weeks 4–5 the Board's bar was lower than the card's (the Board lit games
the server would judge Watch); in week 6 it was higher (the Board withheld games the card rated
Bet). Approving B1 makes the Board, the card, the paper arm and the server read one bar. What
friends see changes only after Saturday's first kickoffs, on those 0–3 games.

## B2b, B4, B3 — what would change

- **B2b:** only a hand-run `manual` card with an empty slate carries the 1.75 fallback; the server
  would honour it for a ticket. It has not happened; the guard makes it impossible.
- **B4:** the Board's Sunday QB flags come from one Rotowire read (an empty response wrote "not
  out"); the card refreshes per build. Approving makes the Board read the card's fresh flag.
- **B3:** the policy says a degraded card holds its BETs; only the card does. Approving makes the
  Board show a "Held" group and the server refuse a ticket on a held game, until the next clean
  build. Rejecting instead amends `BETTING_POLICY.md` to describe the current behaviour.

## Decision for Tate

Approve or decline each of B1, B2b, B4, B3. Each approved item is its own PR, verified with a
before/after on the fixture and a production check, and named `[behaviour]` in its title.
