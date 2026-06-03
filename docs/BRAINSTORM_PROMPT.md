# Brainstorm prompt — paste into the claude.ai Project to start the conversation

> Copy everything below the line into a new chat in the Beat Vegas Project (with
> `PROJECT_BRIEF.md`, `BV_LINE.md`, `GLOSSARY.md`, `README.md` loaded as knowledge).

---

You have the Beat Vegas knowledge files. Quick state of the world so we start from the
frontier, not from scratch:

- It's a **research-only** system for college-football **first-half (1H) unders**. Free
  data only (CFBD, TeamRankings tempo, Open-Meteo, The Odds API for live `totals_h1`).
- The honest reality: **no free historical 1H lines**, so backtests are proxy-graded
  (0.52× full total) — directional, not proof. Blanket 1H unders ≈ breakeven; any edge
  is in **selection**. Pace + weather carry what little signal there is; rest/travel/
  returning were flat. The edge is **small and decaying** (≈57–59% in 2018–21 → ≈50%
  in 2023–25). The "1H is a soft market" thesis was **refuted**.
- The current flagship is the **BV line**: a **market-blind** regressor (no Vegas number
  feeds it, by rule) that projects an independent 1H total; we rank games by the **gap**
  to the real Vegas line. But the BV line is **noisy (σ ≈ 12 pts)**, so most single-game
  gaps are within noise — it ships an 80% band and reports gaps in σ. The verdict on the
  whole method is **CLV** (do the biggest gaps see the line move toward us by close?),
  **not win rate**. The gap does **not** drive the 0–100 score yet.
- Already shipped recently: market-blind rule + guard, the prediction interval, a
  near-kickoff poll for trustworthy closing lines / CLV, and a forward-only QB-out flag.

**My question: what would make this meaningfully better?** I want your best thinking on
where to spend effort next. Cover these angles, but rank ruthlessly — most ideas won't
beat noise:

1. **Signals / features** that could plausibly improve *first-half* scoring prediction
   on free data (e.g. garbage-time-free or early-down 1H efficiency, opponent-adjusted
   pace / expected possessions, 1Q-only splits, coordinator/scheme or tempo-identity
   changes, weather refinements). For each: the hypothesis, the free data that powers it,
   and how we'd test it **leak-free, walk-forward**.
2. **The QB problem.** Confirmed QB-outs matter but we have no historical injury data to
   train on. Is deriving a historical "backup-QB-started" feature from CFBD box scores
   worth it, or is the forward-only flag enough? What else is in this bucket?
3. **Methodology / honesty.** Should we calibrate the classifier's probabilities? Make
   the BV interval per-segment/conformal? Find *where* (if anywhere) the gap→CLV
   relationship actually holds (by total range, conference, tempo, era)?
4. **Lines / CLV.** Better closing-line capture, no-vig fair lines, book dispersion as a
   signal, or whether a **paid historical 1H-line feed** is worth buying to finally
   validate the proxy.
5. **Charts / UX** that would make the honest signal (and its absence) clearer.

For your top picks, give me: the hypothesis, expected effort (S/M/L), the single biggest
way it could be fooling us, and how we'd know it worked. Be skeptical — including of my
framing. Then propose the **2–3 highest-leverage things to build next** and why.
