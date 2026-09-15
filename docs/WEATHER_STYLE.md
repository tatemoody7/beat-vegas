# Weather × offensive style — does decision-time gust predict market error?

**Verdict (pre-registered rule): NO FINDING.** Measurement only. Weather stays out
of the model (`WEATHER_OBS_LEAD_HOURS = None`) regardless of this result; activation
is a separate promotion test (`WEATHER.md`). Run 2026-09-15 with
`scripts/weather_style_study.py --lead 24 --n-boot 2000`; arithmetic and the rule in
`beatvegas/backtest/weather_style.py`, pinned by `tests/test_weather_style.py`.

## The question, and why it is phrased this way

The book prices wind. So the question is not "does wind lower first-half scoring"
but, after conditioning on the book's own de-vigged P(under) at its closing number,
**does the forecast gust that existed 24 hours before kickoff still predict the
under — and does it do so differently for pass-heavy offences?** That interaction is
the sharper hypothesis Tate asked to have hunted, and the one an external review
named as a candidate core layer.

Every input is decision-safe by construction: `weather_obs` rows with `lead_hours =
24` and `decision_safe = true` (the Previous Runs forecast a day out, never the
near-kickoff series), and each offence's 1H pass rate / explosiveness as the mean of
its **prior** games that season. Fixed-lead wind and gusts begin with the 2024
season, so the sample is **2024–25**.

## The rule, written before the numbers were read

A weather × style signal is claimed only when **all three** hold:

1. the interaction coefficient's bootstrap CI excludes zero;
2. it carries the same sign in every season;
3. the implied swing in P(under) for a pass-heavy game across the 10th–90th
   percentile of gust exceeds the **2.38 pp** vig hurdle.

The main gust effect is reported but is not the claim — the book prices wind.

## What it found

**1,220 decided outdoor FBS games** (2024: 611, 2025: 609) with a real 1H close, a
centred de-vigged closing price and a decision-safe lead-24 forecast. Pass-heavy =
top third of the two offences' mean as-of 1H pass rate (cut 0.535).

Logistic of *under* on the book's logit (offset, coefficient 1) + gust/5 + pass-heavy
+ gust/5 × pass-heavy, 2,000 bootstrap resamples:

| term | coefficient | 95% CI |
|---|---|---|
| gust per 5 mph | +0.013 | −0.084 to +0.106 |
| pass-heavy | +0.271 | −0.254 to +0.793 |
| **gust × pass-heavy** | **−0.066** | **−0.229 to +0.101** |

- **The book prices wind.** After the price control, gust alone is +0.013 per 5 mph
  with a CI that spans zero comfortably. There is no residual wind-under effect to
  take.
- **The interaction is not there.** −0.066 with a CI from −0.23 to +0.10 (criterion
  1 fails). Same sign in both seasons (−0.006 / −0.095), but that is two small
  negatives, not a finding.
- **The swing points the wrong way and is noise.** For a pass-heavy game, moving
  gust from 5.6 to 23.9 mph shifts P(under) by **−4.9 pp** — *fewer* unders in wind
  for passing teams, the opposite of the hypothesis — with the whole CI of the
  coefficient behind it spanning zero.
- **Lead 72 says the same** (robustness run, 1,000 resamples): gust +0.026 [−0.067,
  +0.121], interaction −0.076 [−0.236, +0.084], swing −4.6 pp.

By bucket (realized under minus implied, pp; every Wilson interval spans the implied):

| style | gust < 10 | 10–15 | 15–20 | 20–25 | 25+ |
|---|---|---|---|---|---|
| pass-heavy (n) | −0.1 (122) | +6.0 (111) | +4.1 (94) | −4.7 (46) | −5.6 (38) |
| other (n) | −0.2 (237) | −1.0 (203) | +0.4 (200) | −2.8 (114) | +0.8 (55) |

The pass-heavy 10–20 mph cells lean under by 4–6 pp and the 20+ cells lean over by
about the same — non-monotone, each on ~100 or fewer games, each interval spanning
the implied. That is the shape noise takes.

## What this means

- The 2024 Salaga & Howley result (weather variables predict totals outcomes and
  the market under-reacts) does **not** reproduce on first-half totals at a
  decision-safe 24-hour lead, once the book's own probability is the control. Either
  the effect lives in the full game, or in a different weather variable, or the 1H
  market has absorbed it. This study cannot tell which; it can say the specific
  pass-heavy × gust pocket is not there at n=1,220.
- The earlier "weather helped" model read was measured on mis-timed values
  (`WEATHER.md`) and is withdrawn; this is the first weather test on correct,
  decision-safe data, and it is null.
- **Nothing changes.** `weather_obs` stays as research data; `wx_*` features keep
  reading the legacy table until a promotion test exists; no gate, card or bet moves.

## Not tested here, and would need its own pre-registration

Temperature and precipitation as main effects; wind (not gust) direction relative to
the field, which needs stadium orientation we do not hold; kickers rather than
passers; full-game totals. Each is a separate study, not an extension of this one.

## Reproduce

```bash
PYTHONPATH=. python scripts/weather_style_study.py --out reports/weather_style --n-boot 2000 --lead 24
PYTHONPATH=. python scripts/weather_style_study.py --out reports/weather_style72 --n-boot 1000 --lead 72
```
Reads `postmortem_games`, `odds_snapshots` (closing price via the censoring loader),
`weather_obs`, `fh_team_game`, `games`. Writes under `reports/` (gitignored); this
file is the finding.
