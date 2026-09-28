# H-NEGGAP-P — paper OVERS on the negative-gap band, prospectively

Registry row **H-NEGGAP-P** (`docs/HYPOTHESES.md`), written 2026-09-28 before any
observation. Measurement only on the real-money side: **nothing here licenses a real
bet on an over.** `docs/BETTING_POLICY.md` is first-half unders and this row does not
amend it.

> **STATUS 2026-09-28 — REGISTERED, NOT YET LOGGING.** The collection code lands in its
> own PR after this row; the first card build that logs an arm is recorded below, with
> its `cards.id`, before any result is read.

## What prompted it, stated so it is not mistaken for support

Live 2026: Hard-Rock-priced games whose first-half line sat BELOW our number went over
**23 of 26** in weeks 2–3 and then **3 of 12** in week 4 — 26 of 38 cumulative (Wilson
52.5–80.9%). Two things that count hides (`docs/TWO_SIDED.md`, live section):

1. **23 of the 38 were Hard Rock ALTERNATE lines** the feed served as the 1H total — 2–4
   points under the field with the over at −160..−325 — the defect H-PCT-U removed from the
   universe on 2026-09-25. A line three points under the market going over is the line.
2. **On main lines only it is 10 over of 15** (0 of 4 in week 4; Wilson 41.7–84.8%).

The 2023–25 real-close history says 52.4% over on 1,200 negative-gap games (row R07), and
the pre-registered two-sided test found NO over-side signal there. So this is a hypothesis
for a prospective test and nothing more; the history is the answer until the clocks say
otherwise.

## The arms — frozen

Three nested arms on `gap = hr_line − bv_line` (Hard Rock's MAIN line minus our number,
off the card item at the decision build):

| arm | logs a paper OVER when |
|---|---|
| `neggap_lt0` | gap < 0 |
| `neggap_le175` | gap ≤ −1.75 |
| `neggap_le3` | gap ≤ −3 |

A game at gap −4 logs one row in each arm (nested by construction — the question is
where, if anywhere, the value sits). Universe = **H-PCT-U's**: Hard-Rock-priced games whose
NEWEST Hard Rock quote is its main line (`hr_live`), with a model read and a Hard Rock OVER
price captured at that build; the Friday-anchored decision build with the champion's paper
windows (`ci.PAPER_WINDOW_HOURS`), one row per game per arm, deduplicated per arm. Rows go
to **`challenger_picks`** with `side='over'` and `arm` = the label — never `manual_picks`,
so no query feeding the bankroll, the cap, Results or H-STOP-2's observations can see them.
Price = Hard Rock's over price at the build (no fair-price or off-market gate: the arm is
judged at the price it would have paid).

## The clocks — the champion's, reused

Two SPRT clocks per arm, the H-STOP-2 shape (`docs/STOPPING_RULE.md`, Clock 2):

- **Profit**, priced picks: per-pick alternative `mu1_i = 0.04 / b_i`, `b_i` the break-even
  the OVER price implies (`stopping.mu1_for_price`: 0.0764 at −110, 0.0650 at −160, 0.0800
  at +100); observation = units won per 1u at that price.
- **Line value**: `+(closing − bet)` against the centred consensus close confirmed inside
  `REAL_1H_CLOSE_WINDOW_H` (2 h) of kickoff, H1 **+0.50 pts**; a pick without a close inside
  the window is excluded from this clock and counted. **The sign is the reverse of the
  under ledger**: stored `clv` is `closing − bet` for every row, and a RISING line is what
  favours an over.
- **Sigma known and frozen** at the champion's: profit **0.929**, line value **1.371**
  (H-STOP-2's, from the 55 graded 2026 paper picks as stored 2026-09-22). Tate's call
  2026-09-28: the arm is held to the champion's bar in the champion's units, not to a sigma
  estimated on 15 rows.
- **Budget**: total false-decision 5%, split /3 arms (Bonferroni, 1.667% per arm) then /2
  clocks = **0.833% per arm-clock**, power 80%; bounds **A = +4.5643**, **B = −1.6011**
  (`sprt_bounds(0.05/6, 0.20)`).
- **Decisions**: an arm PASSES only when BOTH clocks cross A; an arm is DROPPED when EITHER
  crosses B; otherwise it accrues and weekly reporting is descriptive. **If more than one
  arm passes no threshold is chosen here** — that choice needs its own registered row. A
  pass is a finding for Tate and licenses nothing at real money.
- **Secondary, reported never optimised**: hit rate, selection share, and the champion's
  under record on the same games.

Constants: `beatvegas/backtest/stopping.py::NEGGAP`; position:
`scripts/neggap_position.py` (lands with the collection code); `tests/test_stopping.py`
pins the numbers to this document.

## Touches nothing live

No real-money selection, no model edit, no change to `BET_GAP_PTS`, the slate bar, the
price gate or H-STOP-2. The collection is switched on by `NEGGAP_COLLECT=1` in `card.yml`
and off by unsetting it.

## Data note

- First logging build: _to be recorded_ (`cards.id`, slot, date), before any result is read.
- Weekly: per arm, n logged, n graded, hit rate, units at price, favourable line value,
  excluded-no-close share, both LLRs against A/B.

## Result

None yet.
