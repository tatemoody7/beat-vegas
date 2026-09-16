# /dataviz audit — four visuals, what I found and what I propose

Branch `dataviz-audit`, local only. Nothing merged, nothing pushed.
Every colour below was measured with the skill's validator against the real
chart surface `--bg-2 #0a0f1e`. ΔE is OKLab ×100; the series floor is 15.

---

## 1. MovementChart — the serious one. **Your call, three options rendered.**

### What is actually wrong

The brief expected six book colours shading into the grade language. It is worse
than that: **this game has twelve books and the palette has six colours**, so
`COLORS[i % 6]` paints six pairs of books identically. On UNLV @ Hawai'i the
legend shows Hard Rock, DraftKings and Bally Bet in the *same* cyan. Two cyan
lines are plotted and both move. You cannot find the only book you can bet.

On top of that, three of the six collide with the grade language:

| Book slot | Nearest grade token | ΔE | Reads as |
|---|---|---|---|
| `#fb7185` rose | `--bad` `#f87171` | **2.7** | lost |
| `#f59e0b` amber | `--warn` `#f0b04a` | **4.3** | watch |
| `#34d399` green | `--good` `#3ddc84` | **4.3** | bet / won |
| `#f472b6` pink | `#fb7185` rose *(its own neighbour)* | **7.1** | a duplicate |

Validator on the palette as it ships, dark, on `--bg-2`: lightness band FAIL
(all six sit at L 0.71–0.77, above the 0.48–0.67 dark band), CVD WARN adjacent
(6.6), CVD FAIL and normal-vision FAIL under `--pairs all` (4.6 / 7.1).

### The three options, all built and rendered

**Variant 1 — emphasise Hard Rock.** Hard Rock in `--accent` `#38bdf8` (8.91:1)
at 2.5px; every other book in `--border-strong` `#55688f` (3.42:1). ΔE 25.2
between them. No grade collision is possible, and it does not care whether four
books post or fourteen. Legend is two entries. Cost: you cannot tell BetMGM from
FanDuel in the plot — but the per-book table sits directly above it.

**Variant 2 — a categorical ramp built to be disjoint from the grades.**
`#7b6ee0 · #199e70 · #6366f1 · #b06a2c · #2a78d6 · #c43f70`. Passes all five
checks on the adjacent pairlist (worst CVD ΔE 16.7, normal-vision 26.0, all
≥3:1), and every slot sits ≥15 ΔE from `--good`, `--warn`, `--bad` and `--push`.
Hard Rock always takes slot 1; the other five go to the books that moved most;
the rest fold to grey rather than cycling.
**Honest caveat:** it FAILS `--pairs all` — blue↔violet collapse to ΔE 1.8 under
protanopia and indigo↔violet to 5.0 for full-colour vision. Movement lines cross,
so that is a real failure, which is why every slot also carries a dash pattern.
That is not decoration; it is the secondary encoding the failure obliges.

**Variant 3 — Hard Rock against the market.** A low–high band across the other
books with the median through it, Hard Rock in cyan on top. It answers the
question the page is asking. Two notes: the band needed a **forward-fill** (books
are sampled at different times, so a raw per-timestamp min/max walks a different
subset each step and draws noise — my first pass was visibly jagged); and the
band's low edge is set by whichever single book is furthest out, so on this game
it is really describing BetMGM. An interquartile band would be steadier, and
would be more work.

### Fixed in all three regardless

`COLORS[i % COLORS.length]` is gone from every variant.
I checked the `consensus` leak the plan flagged: `consensus` **never appears in
1H snapshots** (verified against Neon — zero rows). It is a full-game CFBD
artefact only, so there is nothing to fix there. Dropping that one.

---

## 2. Chart chrome — done, per your call

Two real tokens in `globals.css`, ratios measured and written into the comment:

```css
--grid: #1b2336;      /* 1.22:1 on --bg-2 — recessive by design, below --border */
--axis-rule: #243049; /* 1.45:1 — the baseline and the tooltip edge */
```

They are genuinely quieter than `--border` (2.16:1) on purpose, which is what
`/dataviz` wants of a gridline, so they became tokens rather than being snapped
to an existing one. All three charts now mirror them as named constants with the
token name beside each — `LineStudyView`'s existing pattern, applied everywhere.

Orphans retired: axis tick `#97a3bd` → `--text-muted` `#aab6cc` (7.54:1 → 9.34:1,
and now one axis ink across all three charts); grid `#1b2336` → `--grid`;
axis line and tooltip border `#243049` → `--axis-rule`; the bankroll's reference
line `#5e6c87` → `--border-strong` `#55688f` (3.61:1 → 3.42:1, visually identical).
The cyan money line is now `MONEY` with a comment saying why it is not green.

---

## 3. GapBar — a real defect, confirmed by measurement, fixed

Not the finding I expected. On desktop it is fine. **At 375px the two captions
overlap.** Measured on a real 375 viewport, gap 0.7 points: "our number"
101.5→170.7, "the line" 145.2→189.9 — **25.5px of overlap**, rendering as
`OUR NUMBEҼHE LINE`. Any gap under about 1.3 points does it, and `BET_GAP_PTS`
is 1.75, so most Watch and Pass games on a phone hit it.

Fix: each caption leans away from the other **only when they would collide**
(marks closer than 20% of the track), otherwise it stays centred. The
conditionality is what makes it safe — `PAD` holds a colliding pair between ~35%
and ~65% of the track, while a wide gap, which would push a leaning label off the
edge, never triggers it. My first pass leaned unconditionally and pushed labels
12–19px outside the container on wide-gap games; that is fixed.

Verified across 12 live games at 375: zero caption overlaps, zero value overlaps,
zero labels outside the box, no page overflow.

Otherwise GapBar is the best-behaved of the four and I changed nothing else.

---

## 4. LineStudyView — confirmed good, one small fix

Its green/red bars measure CVD ΔE **7.2**, inside the 6–8 band the skill allows
*only with secondary encoding*. It has it: the dashed break-even line encodes the
same fact by position, plus the ranked table and the caption. **Compliant as
built — I left the colour alone**, as instructed.

One real fix: the break-even label was set to `position: "right"`, which parks it
outside the plot where the container clipped it to a single character `5`. Moved
to `insideTopLeft`, where `52.4% break-even` reads in full.

---

## 5. BankrollCurve — and a thing worth knowing

**It has never rendered.** There are zero graded picks in the entire database
(`manual_picks`: 5 rows, season 2026 week 2, `graded = 0`), so `BankrollHero`
shows the empty line, not the chart. Real money starts tomorrow. I rendered it on
a synthetic 16-week season to audit it at all.

- `dot={{ r: 3 }}` at season length: **fine, no change proposed.** The curve is
  one point per graded week plus an anchor — about 16 points, not hundreds.
- `$` axis vs units and ROI: **fine, no change proposed.** The caption under it
  already says "at $10 a unit" and names the dashed line.
- New: the y-axis ticks come out as `$72 / $112 / $152 / $192 / $228` — the
  domain is `floor(lo-pad)` to `ceil(hi+pad)`, so the ticks land on arbitrary
  values. Rounding the domain to a multiple of 10 or 25 would give round ticks.
  Not fixed; small and cosmetic, and it wants your call.

---

## Text alternatives (finding D) — added

`role="img"` plus a summarising `aria-label` on all three Recharts wrappers,
naming the actual numbers. Each already has a text twin nearby (`BookTable`, the
ranked table, `BankrollHero`'s caption), so this is naming, not new content.

## Out of scope, raised not touched

`/dataviz` treats a display face on a hero figure, and `tabular-nums` on a large
standalone number, as anti-patterns. `BankrollHero` does both (Archivo at
`text-5xl` with `tabular-nums`). That is the house design system on purpose and
`BankrollHero` is not one of the four visuals.

## Verification

- `npm run lint` — clean.
- `npx vitest run` — **389 passed, 34 files**. Note the brief's baseline of 372
  is stale: it predates PR #98. I touched no `lib/` file and no test, so 389 was
  already the number on `d9f51ae`.
- Validator re-run on every palette proposed, both pair modes, against `#0a0f1e`.
- Every finding confirmed on a rendered page before acting on it.
- `app/dev-viz/` and `MovementChartV1/V2/V3.tsx` are the comparison harness.
  Whichever variant you pick, the other two and the harness get deleted.
