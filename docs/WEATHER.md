# Weather

Two findings sit behind this document. The first is that the weather table was
**wrong**, not merely thin. The second is that "the weather at kickoff" and "the
weather forecast we could have acted on" are different datasets, and treating
them as one is look-ahead bias.

## 1. The clock was wrong for three years

Both writers asked Open-Meteo for `timezone=auto` and then indexed the resulting
**local** hourly array at the **UTC** kickoff hour. `Game.start_date` is naive UTC
(`scripts/backfill.py::_parse_dt` parses the offset, then strips tzinfo), so every
stored reading was displaced by the venue's UTC offset — 4 to 10 hours for US
venues — and a late kickoff landed on the wrong calendar day entirely.

| Game | Stored | Truth at kickoff | Error |
|---|---|---|---|
| LA Coliseum, `2023-08-27 00:00Z` (5pm PDT) | 63.2°F | 78.1°F | 14.9°, read local midnight |
| Cramton Bowl, `2023-08-26 19:30Z` (2:30pm CDT) | 93.6°F | 99.8°F | 6.2°, hit the `T19` fallback |

`scripts/backfill_enrichment.py` made it worse by falling back to a blind
`T19` string-replace when the UTC key missed the local series, so a noon kickoff
was silently recorded as 7pm conditions.

This is almost certainly why `docs/POST_MORTEM.md` classifies `wx_temp` and
`wx_wind` as **noise in every row** while `beatvegas/factors/registry.py` still
labels them tier 1. The feature was never measured — it was measured wrong.

**The fix is `timezone=UTC` on every request**, which makes the hourly index equal
the UTC hour, which is what `Game.start_date` already stores. Verified: the
UTC-keyed ERA5 lookup returns exactly 78.1 and 99.8 for the two games above.
`tests/test_weather_source.py` pins it. Do not reintroduce `timezone=auto` — a
local-time series cannot be keyed by a UTC timestamp.

The old module also had **no retries**, and returned `{}` for both "rate limited"
and "no data". That is why `data/backfill_weather_full.log` holds **647 `empty`
venues** including Soldier Field and Stanford Stadium, and why coverage stalled at
21%. Exhausted retries now raise `WeatherUnavailable`.

## 2. Near-kickoff is not decision-time

Open-Meteo's **Historical Forecast API** builds a continuous series by stitching
the first hours of successive model runs, so it tracks what actually happened. It
is not "the forecast we would have had". Measured over 12 real Oct/Nov 2024-25
kickoffs, mean absolute difference against the ERA5 actual:

| Source | Temp | Wind |
|---|---|---|
| Historical Forecast API | **1.82°F** | **1.55 mph** |
| Previous Runs, 1-day lead | 2.30°F | 1.67 mph |
| Previous Runs, 3-day lead | 3.55°F | 2.26 mph |

Monotone in lead time, with the Historical Forecast API sitting at lead ≈ 0.

**How far back it goes (measured 2026-09-15, LA Coliseum, hourly temperature,
wind, gusts, precipitation):** every field is **null through 2017-10-01** and
**populated from 2018-01-01**. An earlier probe only checked the HTTP status,
which is 200 either way. Nothing before 2018 is available from this API; the
backfill covers 2023+ and is unaffected.

So `weather_obs` keys on `lead_hours` and stores `decision_safe`:

- **`lead_hours = 0`** — near-kickoff. Good for modelling and data quality.
  `decision_safe = false`. **Never** the basis of a market-edge claim.
- **`lead_hours ∈ {24, 72}`** — the **Previous Runs API**, the forecast that
  genuinely existed that far ahead. `decision_safe = true`. Every market-edge
  query filters on this column.

`decision_safe` is derivable from `source` + `lead_hours` and is stored anyway:
the censoring study showed how easily two populations get conflated, and this
makes the guard one token instead of a remembered convention.

### Hard limits of the Previous Runs API

- **Fixed-lead wind, gusts and precipitation begin with the 2024 season.** Probed
  null at 2023-11-01 and 2024-01-15, populated from 2024-03-01. **2023 is
  temperature-only**, so any decision-time study is a **2024-2026** study.
- **Maximum lead is 7 days** — `previous_day8` returns empty.

### The model is pinned to `icon_seamless`, and this is not a preference

The default blend (`gfs_seamless`) returns **gusts below the mean wind** from 48
hours out — physically impossible, so the two variables are not coming from one
model run. Measured over 18 venue-hours, count of `gust < wind`:

| Lead | 24h | 48h | 72h | 96h | 120h | 144h | 168h |
|---|---|---|---|---|---|---|---|
| `gfs_seamless` (default) | 0/18 | **7/18** | **8/18** | **9/18** | **4/18** | **4/18** | **3/18** |
| `icon_seamless` | 0/18 | 0/18 | 0/18 | 0/18 | 0/18 | 0/18 | n/a |
| `ecmwf_ifs025` | no data at any lead | | | | | | |

`icon_seamless` has full coverage on all four variables across 2024, 2025 and
2026, and sits close to the default at 24h (1.18°F, 1.07 mph, 0.00in mean
absolute difference).

**Not every inversion is that defect, though.** The near-kickoff series inverts
too — 15 of 4,227 rows (0.35%), every deficit 0.1–0.3 mph, every case under
7.5 mph of wind. That is unit rounding: Open-Meteo works in m/s and converts, so
on a calm hour where gust equals wind the conversion can flip them by a tenth.
The two populations **overlap in magnitude** (gfs deficits start at 0.1 mph too),
so a tolerance alone cannot separate them. The **rate** can:

| source | inverted | worst deficit |
|---|---|---|
| `icon_seamless`, leads 24-144h | 0% | — |
| near-kickoff (rounding) | 0.35% | 0.3 mph |
| `gfs_seamless`, leads 48h+ | **32%** | **2.7 mph** |

So `scripts/weather_validate.py` fails on either a deficit above 0.5 mph or an
inversion rate above 1%, and `tests/test_weather_validate.py` pins that the
loosened check still rejects the gfs population. A check relaxed without a test
proving it still catches the thing it was built for is worse than the strict one.

## 3. Repairing the data does not activate it

Two separate decisions, deliberately kept apart:

1. **The data repair** writes `weather_obs`, a table **nothing reads**. Safe to
   run at any time, including mid-season with real money live.
2. **Model activation** is `etl/features.py::WEATHER_OBS_LEAD_HOURS`, which ships
   as `None` — reproducing the legacy frame exactly, so the incumbent is an *arm*
   of the experiment rather than a separate code path, the same shape as
   `PRIOR_SEASON_WEIGHT = 0` (`docs/LEVEL_ANCHOR.md`). Adding `wx_gust` to
   `FEATURE_COLS` is part of activation too.

**Do not judge activation on whether bv_line MAE improves.** MAE is near-blind to
changes of this kind; that is the documented level-anchor lesson. The gate reports
the blast radius — bias by spread bucket, and games crossing `BET_GAP_PTS` — so
the question it answers is *when* the live model moves, not whether the repaired
values are correct. Correctness is settled against ground truth by
`scripts/weather_validate.py`, not by a backtest.

## 4. Venue coordinates come first

Collecting perfect weather for the wrong stadium is the failure that looks like
success all the way down. `backfill.py::backfill_venues` falls back to CFBD's
`location["x"]` / `location["y"]`, and in GeoJSON `x` is conventionally
*longitude* — so a swap is a live possibility.

Audited 2026-09-13: 720 venues used by 2023-26 games, lat 21.29 → 53.34, lon
−157.82 → −0.28, every extreme legitimate (Aloha Stadium, Aviva, Wembley), **zero
swaps**. `beatvegas/etl/venues.py::coord_problems` is the standing guard;
`scripts/backfill_weather.py` refuses to start if it finds one, and
`tests/test_venue_coords.py` pins 26 stadiums plus the bounds.

## 5. Running it

```bash
PYTHONPATH=. python scripts/backfill_weather.py --start 2023 --end 2026 --leads 0,24,72
PYTHONPATH=. python scripts/weather_validate.py        # read this before promoting
PYTHONPATH=. python scripts/backfill_weather.py --promote
```

Staging goes to `data/cache/weather_staging.jsonl` with a `.done` sidecar, so a
re-run resumes rather than refetching. ~55 venue-seasons/min locally. Wrap it in
`caffeinate -i -s` — this Mac sleeps after one minute on battery.

**The full 2023-2026 range at three leads does NOT fit in one day.** Open-Meteo's
free tier weights a request by variables × days, so a season-range call with four
variables counts as far more than one: measured 2026-09-14, **5,711 requests
exhausted the DAILY quota in about 2.3 hours**, at 86% of the 6,636 venue-season-
leads. The limit is per UTC day (`"Daily API request limit exceeded"`), so it
resets at 00:00 UTC, not on a rolling window — waiting an hour does nothing.

Plan for two days, or split the run by lead. Nothing is lost when it stops: the
`.done` sidecar means a re-run picks up where it left off, and
`MAX_CONSECUTIVE_FAILURES` (10) halts the run rather than grinding through
thousands of doomed calls. The remaining 925 units took ~16 minutes the next day. `.github/workflows/weather_backfill.yml`
is the cloud path, but `sunday.yml` records Open-Meteo rate-limiting GitHub's
shared runners, so the Mac is usually faster.

The forward path (`scripts/enrich_weather.py`, run weekly by `sunday.yml`) shares
the fixed `fetch_weather` and still writes the legacy `weather` table until
activation.

## 6. What this unblocks, and what it does not

The open question is **not** "does weather predict scoring" — the book prices
that. It is:

> Controlling for the book's de-vigged probability at its own number, does
> **decision-time** forecast wind / gusts / temperature / precipitation still
> predict market error?

and the sharper form:

> Does **weather × offensive style** predict market error — 20 mph gusts against a
> highly explosive passing offence — where flat wind does not?

That study is the censoring study's exact shape (`docs/CENSORING_STUDY.md`):
control for the price, test whether the candidate still carries signal, bootstrap
the CI, check sign stability by season, hold it against the vig hurdle. Reuse
`brier`, `log_loss`, `wilson` and `reliability` from
`beatvegas/backtest/censoring.py`. It runs on `decision_safe` rows only, and its
usable sample is **2024-2026**.
