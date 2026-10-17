# Wind forecast check (H-WX-ICON-BIAS)

**Verdict (exploratory, 2026-10-17): it depends on which observation you trust. Against ERA5,
ICON runs only slightly low. Against CFBD's station-like readings it runs low by about 1.3 mph
and calls about half as many 10+ mph games as CFBD records.** The two "truths" are about 1 mph
apart from each other, so this check cannot say on its own which is right.

- **Against ERA5**, ICON's 24-hour forecast reads about a third of a mile per hour low on average
  (−0.32 mph, 95% interval −0.47 to −0.19, 1,467 games). It calls 10+ mph about as often as ERA5
  sees it (14.8% of games against 15.5%).
- **Against CFBD**, the same forecast reads −1.28 mph (−1.51 to −0.99, 1,447 games). It calls
  10+ mph on 14.8% of games, where CFBD records 10+ on 25.5%.
- **Night kickoffs (7pm local or later) are the one place both truths agree.** ICON runs about
  1 mph low there: −0.98 against ERA5 (260 games), −1.16 against CFBD (259 games).
- **The game page's own forecasts cannot be checked yet.** Every build-time forecast
  (`build_forecasts`, from 2026-10-13) is newer than the newest observed game in
  `weather_actuals` (kickoff 2026-10-07 23:30Z), so that comparison has 0 games.
- **The Arkansas State @ Southern Miss gap does not look like this bias.** The page read 8.6 mph
  where NWS read 13-15. A 4-6 mph gap is two to three times the typical miss (average absolute
  error 1.6 mph against ERA5, 2.9 against CFBD). It sits in the group whose gusts run 2+ times
  the sustained wind, where ICON reads −0.50 (ERA5) or −1.51 (CFBD).

Nothing here changes an arm, a threshold, the source or a page (registry row H-WX-ICON-BIAS:
exploratory, licenses nothing). Any change to the arms' wind source is a protocol amendment and
Tate's call.

## How it was measured

- **Run:** `study.yml` run 39053121873 (2026-10-17 17:20 UTC, branch `claude/wind-forecast-check`
  at a243715), `scripts/wind_forecast_check.py`. The full report is the appendix below.
- **Universe:** FBS-vs-FBS games, outdoor (venue not a dome, the forecast row not a dome, CFBD not
  indoors), with both a forecast and an observation (2,368 FBS-vs-FBS games loaded for 2024-26).
- **Forecast:** ICON (`icon_seamless`) sustained 10 m wind at the kickoff UTC hour, the number the
  weather arms freeze. Taken from `weather_obs` leads 24 and 72, `decision_safe`, the newest fetch
  per game.
- **Truth:** `weather_actuals`, hour_offset 0, the same UTC hour (both tables key on the hour the
  game kicks off in, checked by hand). Two sources, never blended:
  - ERA5 (`open_meteo_era5_archive`): a reanalysis on a roughly 30 km grid, so itself a model,
    and it smooths local wind.
  - CFBD `/games/weather`: station-like, whole-number wind. Its provider is not named and the hour
    it describes is not stated. 213 of 1,846 readings are exactly 0 mph (calm or unreported), and
    all are kept.
- **Sign:** bias = forecast minus observed, so **negative means ICON reads LOW**. Hand check from
  the summary row: 6.10 − 6.42 = −0.32. The 95% intervals resample whole kickoff dates, because one
  weather system moves a whole day's games together.
- **Missed windy** = ICON under 10 mph, observed 10+. **False windy** = the reverse. Both are shares
  of n.

## Main read: 2024-25, every comparison

| forecast | truth | n | ICON mean | observed mean | mean bias (95% CI) | MAE | observed 10+ | ICON 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|
| 24 h | ERA5 | 1,467 | 6.10 | 6.42 | −0.32 (−0.47 to −0.19) | 1.62 | 15.5% | 14.8% | 4.8% (70) | 4.0% (59) |
| 24 h | CFBD | 1,447 | 6.09 | 7.36 | −1.28 (−1.51 to −0.99) | 2.85 | 25.5% | 14.8% | 14.0% (202) | 3.2% (47) |
| 72 h | ERA5 | 1,467 | 6.11 | 6.42 | −0.31 (−0.52 to −0.13) | 1.90 | 15.5% | 14.2% | 6.1% (89) | 4.8% (70) |
| 72 h | CFBD | 1,447 | 6.10 | 7.36 | −1.26 (−1.50 to −0.97) | 2.99 | 25.5% | 14.2% | 15.1% (218) | 3.8% (55) |

The 24-hour and 72-hour forecasts carry the same bias. The longer lead only adds noise (MAE 1.62
to 1.90 against ERA5).

## Splits (24-hour forecast, 2024-25; run 39053121873)

| group | n (ERA5) | bias vs ERA5 (95% CI) | n (CFBD) | bias vs CFBD (95% CI) |
|---|---|---|---|---|
| kickoff day (before 4pm local) | 597 | −0.04 (−0.21 to +0.13) | 589 | −1.40 (−1.76 to −1.03) |
| kickoff evening (4-6:59pm) | 286 | −0.21 (−0.51 to +0.07) | 285 | −1.51 (−1.99 to −1.03) |
| kickoff night (7pm or later) | 260 | −0.98 (−1.26 to −0.69) | 259 | −1.16 (−1.59 to −0.72) |
| kickoff zone unknown | 324 | −0.39 (−0.67 to −0.15) | 314 | −0.93 (−1.38 to −0.49) |
| ICON gust / sustained under 1.5 | 28 | −1.40 (−2.05 to −0.74) | 28 | −0.02 (−1.09 to +1.07) |
| ICON gust / sustained 1.5-2 | 235 | +0.76 (+0.37 to +1.12) | 234 | −0.25 (−0.72 to +0.23) |
| ICON gust / sustained 2+ | 1,204 | −0.50 (−0.65 to −0.38) | 1,185 | −1.51 (−1.76 to −1.25) |
| observed 0-5 mph | 581 | +0.27 | 463 | +1.17 |
| observed 5-10 mph | 658 | −0.45 | 615 | −1.37 |
| observed 10-15 mph | 195 | −1.30 (misses 35%) | 271 | −3.33 (misses 64%) |
| observed 15+ mph | 33 | −2.34 | 98 | −6.56 |

**Read the observed-wind rows with care.** They group games by the truth, and any noisy forecast
looks low against high observations and high against low ones (regression to the mean), even when
it has no bias at all. The fair test of "does ICON under-call windy games" is the frequency
comparison in the main table: against ERA5 ICON calls 10+ about as often as it happens (217
against 228 games); against CFBD it calls 214 where CFBD records 369.

**How the local kickoff hour was found.** `venues.timezone` is still empty in Neon (0 of 852
venues): it was added on 2026-10-17, and grade.yml's venue refresh fills it. Until then a state
that lies wholly in one zone gives the zone exactly, and Texas and Nevada are decided by city.
That covers 1,839 of 2,368 games; the other 529 are in the "zone unknown" row, never guessed. A
re-run after the venue refresh would fill most of that row.

## 2026 so far (development look, small)

The same leads on 2026 games already observed: 96 games over 9 dates. Against ERA5 the bias is
−0.06 (−0.60 to +0.18) at 24 h. Against CFBD it is **+1.10** (−0.74 to +1.68), which is the
opposite sign to 2024-25. The interval crosses zero, and only 2 of the 96 CFBD readings were 10+
mph. Too few windy games to say anything.

## What would settle it

- **Re-run after the next `weather_actuals` fetch** (it runs Monday to Wednesday, roadmap v2.1).
  That covers games from 2026-10-13 on, so the build-time forecasts the page actually shows get
  their own row. Nothing in the script changes.
- **A station truth that names its station and hour.** One option is the nearest airport's
  hourly report (ASOS/METAR, through the Iowa Environmental Mesonet archive). That would break the
  ERA5 / CFBD tie. It would be a new data source, so it is Tate's call.
- **NWS keeps no history in these tables.** Comparing NWS with ICON head to head would mean
  capturing the NWS point forecast at build time from now on. That is also a new source and Tate's
  call.

## Appendix: the full report (run 39053121873, verbatim)

### H-WX-ICON-BIAS, wind forecast check (20261017T172000Z)

FBS-vs-FBS outdoor games; forecast = ICON (`icon_seamless`) sustained 10 m wind at the kickoff UTC hour; truth = `weather_actuals` hour_offset 0 (ERA5 reanalysis, or CFBD's station-like whole-number reading). Bias = forecast minus observed, mph (negative = the forecast runs LOW); 95% interval resamples whole kickoff dates. Missed windy = forecast < 10 but observed >= 10; false windy = the reverse; both as a share of n. Exploratory: nothing is adopted from it.

Run: GITHUB_RUN_ID 39053121873, GITHUB_SHA a243715.

#### Summary (every forecast x truth, all games)

| forecast | truth | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| weather_obs 24 h, 2024-25 | ERA5 | 1467 | 139 | 6.10 | 6.42 | -0.32 (-0.47 to -0.19) | -0.30 | 1.62 | 228 (15.5%) | 217 (14.8%) | 70 (4.8%) | 59 (4.0%) |
| weather_obs 24 h, 2024-25 | CFBD | 1447 | 138 | 6.09 | 7.36 | -1.28 (-1.51 to -0.99) | -1.20 | 2.85 | 369 (25.5%) | 214 (14.8%) | 202 (14.0%) | 47 (3.2%) |
| weather_obs 24 h, 2026 | ERA5 | 96 | 9 | 5.42 | 5.48 | -0.06 (-0.60 to +0.18) | +0.10 | 1.78 | 6 (6.2%) | 7 (7.3%) | 3 (3.1%) | 4 (4.2%) |
| weather_obs 24 h, 2026 | CFBD | 96 | 9 | 5.42 | 4.32 | +1.10 (-0.74 to +1.68) | +0.95 | 2.50 | 2 (2.1%) | 7 (7.3%) | 1 (1.0%) | 6 (6.2%) |
| weather_obs 72 h, 2024-25 | ERA5 | 1467 | 139 | 6.11 | 6.42 | -0.31 (-0.52 to -0.13) | -0.30 | 1.90 | 228 (15.5%) | 209 (14.2%) | 89 (6.1%) | 70 (4.8%) |
| weather_obs 72 h, 2024-25 | CFBD | 1447 | 138 | 6.10 | 7.36 | -1.26 (-1.50 to -0.97) | -1.10 | 2.99 | 369 (25.5%) | 206 (14.2%) | 218 (15.1%) | 55 (3.8%) |
| weather_obs 72 h, 2026 | ERA5 | 96 | 9 | 5.47 | 5.48 | -0.01 (-0.46 to +0.78) | -0.30 | 2.09 | 6 (6.2%) | 8 (8.3%) | 3 (3.1%) | 5 (5.2%) |
| weather_obs 72 h, 2026 | CFBD | 96 | 9 | 5.47 | 4.32 | +1.15 (-0.25 to +1.76) | +1.00 | 2.63 | 2 (2.1%) | 8 (8.3%) | 1 (1.0%) | 7 (7.3%) |
| build_forecasts newest pre-kickoff, 2026 | ERA5 | 0 | | | | | | | | | | |
| build_forecasts newest pre-kickoff, 2026 | CFBD | 0 | | | | | | | | | | |

#### weather_obs 24 h, 2024-25 vs ERA5

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 1467 | 139 | 6.10 | 6.42 | -0.32 (-0.47 to -0.19) | -0.30 | 1.62 | 228 (15.5%) | 217 (14.8%) | 70 (4.8%) | 59 (4.0%) |
| kickoff day | 597 | 33 | 6.82 | 6.86 | -0.04 (-0.21 to +0.13) | -0.10 | 1.45 | 121 (20.3%) | 112 (18.8%) | 32 (5.4%) | 23 (3.9%) |
| kickoff evening | 286 | 79 | 6.02 | 6.23 | -0.21 (-0.51 to +0.07) | -0.30 | 1.87 | 33 (11.5%) | 39 (13.6%) | 12 (4.2%) | 18 (6.3%) |
| kickoff night | 260 | 108 | 4.45 | 5.43 | -0.98 (-1.26 to -0.69) | -1.10 | 1.82 | 22 (8.5%) | 16 (6.2%) | 10 (3.8%) | 4 (1.5%) |
| kickoff zone unknown | 324 | 78 | 6.18 | 6.57 | -0.39 (-0.67 to -0.15) | -0.30 | 1.57 | 52 (16.0%) | 50 (15.4%) | 16 (4.9%) | 14 (4.3%) |
| observed 0-5 mph | 581 | 101 | 3.41 | 3.14 | +0.27 (+0.11 to +0.42) | +0.20 | 1.37 | 0 (0.0%) | 1 (0.2%) | 0 (0.0%) | 1 (0.2%) |
| observed 5-10 mph | 658 | 105 | 6.70 | 7.15 | -0.45 (-0.65 to -0.26) | -0.50 | 1.60 | 0 (0.0%) | 58 (8.8%) | 0 (0.0%) | 58 (8.8%) |
| observed 10-15 mph | 195 | 56 | 10.63 | 11.93 | -1.30 (-1.61 to -1.03) | -1.40 | 2.09 | 195 (100.0%) | 127 (65.1%) | 68 (34.9%) | 0 (0.0%) |
| observed 15+ mph | 33 | 23 | 14.94 | 17.27 | -2.34 (-3.70 to -1.06) | -3.20 | 3.83 | 33 (100.0%) | 31 (93.9%) | 2 (6.1%) | 0 (0.0%) |
| gust ratio 0-1.5 | 28 | 21 | 2.21 | 3.62 | -1.40 (-2.05 to -0.74) | -1.85 | 2.10 | 0 (0.0%) | 1 (3.6%) | 0 (0.0%) | 1 (3.6%) |
| gust ratio 1.5-2 | 235 | 71 | 8.90 | 8.14 | +0.76 (+0.37 to +1.12) | +0.80 | 2.19 | 67 (28.5%) | 93 (39.6%) | 14 (6.0%) | 40 (17.0%) |
| gust ratio 2+ | 1204 | 132 | 5.65 | 6.15 | -0.50 (-0.65 to -0.38) | -0.40 | 1.50 | 161 (13.4%) | 123 (10.2%) | 56 (4.7%) | 18 (1.5%) |

#### weather_obs 24 h, 2024-25 vs CFBD

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 1447 | 138 | 6.09 | 7.36 | -1.28 (-1.51 to -0.99) | -1.20 | 2.85 | 369 (25.5%) | 214 (14.8%) | 202 (14.0%) | 47 (3.2%) |
| kickoff day | 589 | 33 | 6.80 | 8.20 | -1.40 (-1.76 to -1.03) | -1.30 | 2.88 | 179 (30.4%) | 110 (18.7%) | 93 (15.8%) | 24 (4.1%) |
| kickoff evening | 285 | 79 | 6.02 | 7.53 | -1.51 (-1.99 to -1.03) | -1.20 | 2.99 | 80 (28.1%) | 39 (13.7%) | 49 (17.2%) | 8 (2.8%) |
| kickoff night | 259 | 108 | 4.43 | 5.59 | -1.16 (-1.59 to -0.72) | -1.10 | 2.78 | 33 (12.7%) | 16 (6.2%) | 22 (8.5%) | 5 (1.9%) |
| kickoff zone unknown | 314 | 75 | 6.16 | 7.09 | -0.93 (-1.38 to -0.49) | -1.10 | 2.74 | 77 (24.5%) | 49 (15.6%) | 38 (12.1%) | 10 (3.2%) |
| observed 0-5 mph | 463 | 98 | 3.66 | 2.49 | +1.17 (+0.85 to +1.48) | +1.10 | 2.21 | 0 (0.0%) | 5 (1.1%) | 0 (0.0%) | 5 (1.1%) |
| observed 5-10 mph | 615 | 102 | 5.91 | 7.27 | -1.37 (-1.69 to -1.06) | -1.40 | 2.39 | 0 (0.0%) | 42 (6.8%) | 0 (0.0%) | 42 (6.8%) |
| observed 10-15 mph | 271 | 64 | 8.57 | 11.91 | -3.33 (-3.70 to -3.00) | -3.40 | 3.57 | 271 (100.0%) | 98 (36.2%) | 173 (63.8%) | 0 (0.0%) |
| observed 15+ mph | 98 | 45 | 11.81 | 18.37 | -6.56 (-7.38 to -5.76) | -6.65 | 6.79 | 98 (100.0%) | 69 (70.4%) | 29 (29.6%) | 0 (0.0%) |
| gust ratio 0-1.5 | 28 | 21 | 2.21 | 2.24 | -0.02 (-1.09 to +1.07) | +1.50 | 2.72 | 0 (0.0%) | 1 (3.6%) | 0 (0.0%) | 1 (3.6%) |
| gust ratio 1.5-2 | 234 | 71 | 8.91 | 9.16 | -0.25 (-0.72 to +0.23) | -0.30 | 2.83 | 93 (39.7%) | 93 (39.7%) | 24 (10.3%) | 24 (10.3%) |
| gust ratio 2+ | 1185 | 130 | 5.62 | 7.13 | -1.51 (-1.76 to -1.25) | -1.30 | 2.86 | 276 (23.3%) | 120 (10.1%) | 178 (15.0%) | 22 (1.9%) |

#### weather_obs 24 h, 2026 vs ERA5

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 96 | 9 | 5.42 | 5.48 | -0.06 (-0.60 to +0.18) | +0.10 | 1.78 | 6 (6.2%) | 7 (7.3%) | 3 (3.1%) | 4 (4.2%) |
| kickoff day | 32 | 4 | 5.67 | 5.36 | +0.31 (-0.15 to +0.87) | +0.45 | 1.72 | 1 (3.1%) | 3 (9.4%) | 0 (0.0%) | 2 (6.2%) |
| kickoff evening | 21 | 6 | 5.86 | 7.19 | -1.33 (-2.76 to -0.19) | -0.70 | 2.53 | 3 (14.3%) | 2 (9.5%) | 2 (9.5%) | 1 (4.8%) |
| kickoff night | 16 | 7 | 4.25 | 4.59 | -0.34 (-1.31 to +0.31) | -0.35 | 1.16 | 1 (6.2%) | 1 (6.2%) | 0 (0.0%) | 0 (0.0%) |
| kickoff zone unknown | 27 | 6 | 5.48 | 4.81 | +0.67 (+0.40 to +1.20) | +0.10 | 1.63 | 1 (3.7%) | 1 (3.7%) | 1 (3.7%) | 1 (3.7%) |
| observed 0-5 mph | 48 | 8 | 4.01 | 3.26 | +0.75 (+0.41 to +1.06) | +0.40 | 1.43 | 0 (0.0%) | 1 (2.1%) | 0 (0.0%) | 1 (2.1%) |
| observed 5-10 mph | 42 | 6 | 6.52 | 6.95 | -0.43 (-0.92 to -0.04) | -0.30 | 1.85 | 0 (0.0%) | 3 (7.1%) | 0 (0.0%) | 3 (7.1%) |
| observed 10-15 mph | 5 | 3 | 8.42 | 11.66 | -3.24 (-4.60 to -1.30) | -4.60 | 3.48 | 5 (100.0%) | 2 (40.0%) | 3 (60.0%) | 0 (0.0%) |
| observed 15+ mph | 1 | 1 | 12.10 | 19.30 | -7.20 (—) | -7.20 | 7.20 | 1 (100.0%) | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| gust ratio 1.5-2 | 19 | 5 | 7.92 | 6.76 | +1.16 (-0.25 to +1.82) | +1.10 | 2.73 | 2 (10.5%) | 5 (26.3%) | 1 (5.3%) | 4 (21.1%) |
| gust ratio 2+ | 77 | 9 | 4.81 | 5.16 | -0.36 (-0.79 to +0.12) | +0.10 | 1.54 | 4 (5.2%) | 2 (2.6%) | 2 (2.6%) | 0 (0.0%) |

#### weather_obs 24 h, 2026 vs CFBD

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 96 | 9 | 5.42 | 4.32 | +1.10 (-0.74 to +1.68) | +0.95 | 2.50 | 2 (2.1%) | 7 (7.3%) | 1 (1.0%) | 6 (6.2%) |
| kickoff day | 32 | 4 | 5.67 | 3.42 | +2.25 (+1.43 to +2.75) | +1.95 | 2.67 | 0 (0.0%) | 3 (9.4%) | 0 (0.0%) | 3 (9.4%) |
| kickoff evening | 21 | 6 | 5.86 | 5.43 | +0.43 (-2.50 to +1.70) | -0.50 | 3.06 | 2 (9.5%) | 2 (9.5%) | 1 (4.8%) | 1 (4.8%) |
| kickoff night | 16 | 7 | 4.25 | 4.62 | -0.37 (-1.69 to +1.10) | -1.00 | 2.23 | 0 (0.0%) | 1 (6.2%) | 0 (0.0%) | 1 (6.2%) |
| kickoff zone unknown | 27 | 6 | 5.48 | 4.35 | +1.13 (+0.04 to +1.81) | +0.50 | 2.01 | 0 (0.0%) | 1 (3.7%) | 0 (0.0%) | 1 (3.7%) |
| observed 0-5 mph | 59 | 8 | 4.69 | 2.49 | +2.19 (+1.78 to +2.69) | +1.70 | 2.66 | 0 (0.0%) | 3 (5.1%) | 0 (0.0%) | 3 (5.1%) |
| observed 5-10 mph | 35 | 7 | 6.38 | 6.62 | -0.24 (-1.59 to +0.74) | -0.60 | 1.93 | 0 (0.0%) | 3 (8.6%) | 0 (0.0%) | 3 (8.6%) |
| observed 15+ mph | 2 | 2 | 10.40 | 18.00 | -7.60 (-8.90 to -6.30) | -7.60 | 7.60 | 2 (100.0%) | 1 (50.0%) | 1 (50.0%) | 0 (0.0%) |
| gust ratio 1.5-2 | 19 | 5 | 7.92 | 4.71 | +3.22 (+0.63 to +3.88) | +2.60 | 3.58 | 0 (0.0%) | 5 (26.3%) | 0 (0.0%) | 5 (26.3%) |
| gust ratio 2+ | 77 | 9 | 4.81 | 4.23 | +0.58 (-1.09 to +1.13) | +0.40 | 2.23 | 2 (2.6%) | 2 (2.6%) | 1 (1.3%) | 1 (1.3%) |

#### weather_obs 72 h, 2024-25 vs ERA5

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 1467 | 139 | 6.11 | 6.42 | -0.31 (-0.52 to -0.13) | -0.30 | 1.90 | 228 (15.5%) | 209 (14.2%) | 89 (6.1%) | 70 (4.8%) |
| kickoff day | 597 | 33 | 6.68 | 6.86 | -0.19 (-0.46 to +0.13) | -0.10 | 1.85 | 121 (20.3%) | 105 (17.6%) | 51 (8.5%) | 35 (5.9%) |
| kickoff evening | 286 | 79 | 6.06 | 6.23 | -0.17 (-0.52 to +0.17) | -0.30 | 1.86 | 33 (11.5%) | 42 (14.7%) | 8 (2.8%) | 17 (5.9%) |
| kickoff night | 260 | 108 | 4.59 | 5.43 | -0.84 (-1.20 to -0.49) | -1.00 | 2.09 | 22 (8.5%) | 16 (6.2%) | 12 (4.6%) | 6 (2.3%) |
| kickoff zone unknown | 324 | 78 | 6.32 | 6.57 | -0.25 (-0.55 to +0.05) | -0.30 | 1.85 | 52 (16.0%) | 46 (14.2%) | 18 (5.6%) | 12 (3.7%) |
| observed 0-5 mph | 581 | 101 | 3.72 | 3.14 | +0.59 (+0.37 to +0.78) | +0.40 | 1.61 | 0 (0.0%) | 6 (1.0%) | 0 (0.0%) | 6 (1.0%) |
| observed 5-10 mph | 658 | 105 | 6.56 | 7.15 | -0.59 (-0.81 to -0.38) | -0.70 | 1.88 | 0 (0.0%) | 64 (9.7%) | 0 (0.0%) | 64 (9.7%) |
| observed 10-15 mph | 195 | 56 | 10.31 | 11.93 | -1.62 (-2.14 to -1.19) | -1.50 | 2.51 | 195 (100.0%) | 109 (55.9%) | 86 (44.1%) | 0 (0.0%) |
| observed 15+ mph | 33 | 23 | 14.39 | 17.27 | -2.88 (-3.84 to -1.92) | -3.10 | 3.56 | 33 (100.0%) | 30 (90.9%) | 3 (9.1%) | 0 (0.0%) |
| gust ratio 0-1.5 | 14 | 11 | 2.19 | 3.38 | -1.19 (-2.19 to -0.22) | -2.00 | 2.09 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| gust ratio 1.5-2 | 239 | 65 | 8.93 | 8.12 | +0.81 (+0.35 to +1.28) | +0.60 | 2.38 | 67 (28.0%) | 94 (39.3%) | 14 (5.9%) | 41 (17.2%) |
| gust ratio 2+ | 1214 | 135 | 5.60 | 6.12 | -0.52 (-0.75 to -0.34) | -0.40 | 1.80 | 161 (13.3%) | 115 (9.5%) | 75 (6.2%) | 29 (2.4%) |

#### weather_obs 72 h, 2024-25 vs CFBD

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 1447 | 138 | 6.10 | 7.36 | -1.26 (-1.50 to -0.97) | -1.10 | 2.99 | 369 (25.5%) | 206 (14.2%) | 218 (15.1%) | 55 (3.8%) |
| kickoff day | 589 | 33 | 6.67 | 8.20 | -1.53 (-1.89 to -1.15) | -1.50 | 3.14 | 179 (30.4%) | 104 (17.7%) | 102 (17.3%) | 27 (4.6%) |
| kickoff evening | 285 | 79 | 6.07 | 7.53 | -1.46 (-1.94 to -0.98) | -1.20 | 3.21 | 80 (28.1%) | 42 (14.7%) | 51 (17.9%) | 13 (4.6%) |
| kickoff night | 259 | 108 | 4.57 | 5.59 | -1.02 (-1.48 to -0.55) | -0.80 | 2.84 | 33 (12.7%) | 16 (6.2%) | 25 (9.7%) | 8 (3.1%) |
| kickoff zone unknown | 314 | 75 | 6.31 | 7.09 | -0.79 (-1.20 to -0.36) | -0.70 | 2.61 | 77 (24.5%) | 44 (14.0%) | 40 (12.7%) | 7 (2.2%) |
| observed 0-5 mph | 463 | 98 | 3.84 | 2.49 | +1.35 (+1.03 to +1.67) | +1.10 | 2.29 | 0 (0.0%) | 12 (2.6%) | 0 (0.0%) | 12 (2.6%) |
| observed 5-10 mph | 615 | 102 | 5.91 | 7.27 | -1.37 (-1.65 to -1.08) | -1.60 | 2.48 | 0 (0.0%) | 43 (7.0%) | 0 (0.0%) | 43 (7.0%) |
| observed 10-15 mph | 271 | 64 | 8.33 | 11.91 | -3.58 (-3.99 to -3.21) | -3.50 | 4.01 | 271 (100.0%) | 80 (29.5%) | 191 (70.5%) | 0 (0.0%) |
| observed 15+ mph | 98 | 45 | 11.81 | 18.37 | -6.56 (-7.32 to -5.76) | -6.45 | 6.67 | 98 (100.0%) | 71 (72.4%) | 27 (27.6%) | 0 (0.0%) |
| gust ratio 0-1.5 | 14 | 11 | 2.19 | 1.54 | +0.65 (-0.42 to +1.78) | +1.80 | 2.05 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| gust ratio 1.5-2 | 237 | 65 | 8.94 | 9.04 | -0.09 (-0.70 to +0.50) | -0.20 | 3.15 | 96 (40.5%) | 94 (39.7%) | 31 (13.1%) | 29 (12.2%) |
| gust ratio 2+ | 1196 | 133 | 5.58 | 7.10 | -1.52 (-1.74 to -1.27) | -1.35 | 2.97 | 273 (22.8%) | 112 (9.4%) | 187 (15.6%) | 26 (2.2%) |

#### weather_obs 72 h, 2026 vs ERA5

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 96 | 9 | 5.47 | 5.48 | -0.01 (-0.46 to +0.78) | -0.30 | 2.09 | 6 (6.2%) | 8 (8.3%) | 3 (3.1%) | 5 (5.2%) |
| kickoff day | 32 | 4 | 5.11 | 5.36 | -0.25 (-0.46 to -0.08) | -0.15 | 1.96 | 1 (3.1%) | 2 (6.2%) | 1 (3.1%) | 2 (6.2%) |
| kickoff evening | 21 | 6 | 5.93 | 7.19 | -1.26 (-2.12 to -0.24) | -1.00 | 2.11 | 3 (14.3%) | 1 (4.8%) | 2 (9.5%) | 0 (0.0%) |
| kickoff night | 16 | 7 | 4.97 | 4.59 | +0.38 (-1.28 to +2.11) | -0.30 | 2.02 | 1 (6.2%) | 3 (18.8%) | 0 (0.0%) | 2 (12.5%) |
| kickoff zone unknown | 27 | 6 | 5.84 | 4.81 | +1.02 (+0.09 to +1.82) | +0.60 | 2.26 | 1 (3.7%) | 2 (7.4%) | 0 (0.0%) | 1 (3.7%) |
| observed 0-5 mph | 48 | 8 | 3.90 | 3.26 | +0.64 (+0.39 to +0.83) | +0.55 | 1.80 | 0 (0.0%) | 1 (2.1%) | 0 (0.0%) | 1 (2.1%) |
| observed 5-10 mph | 42 | 6 | 6.55 | 6.95 | -0.39 (-1.07 to +1.88) | -0.50 | 2.19 | 0 (0.0%) | 4 (9.5%) | 0 (0.0%) | 4 (9.5%) |
| observed 10-15 mph | 5 | 3 | 9.86 | 11.66 | -1.80 (-3.40 to -1.20) | -2.00 | 3.20 | 5 (100.0%) | 2 (40.0%) | 3 (60.0%) | 0 (0.0%) |
| observed 15+ mph | 1 | 1 | 13.50 | 19.30 | -5.80 (—) | -5.80 | 5.80 | 1 (100.0%) | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| gust ratio 1.5-2 | 18 | 5 | 8.43 | 6.30 | +2.13 (-0.58 to +3.67) | +2.25 | 3.13 | 2 (11.1%) | 6 (33.3%) | 0 (0.0%) | 4 (22.2%) |
| gust ratio 2+ | 78 | 9 | 4.79 | 5.29 | -0.50 (-0.95 to +0.51) | -0.35 | 1.85 | 4 (5.1%) | 2 (2.6%) | 3 (3.8%) | 1 (1.3%) |

#### weather_obs 72 h, 2026 vs CFBD

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 96 | 9 | 5.47 | 4.32 | +1.15 (-0.25 to +1.76) | +1.00 | 2.63 | 2 (2.1%) | 8 (8.3%) | 1 (1.0%) | 7 (7.3%) |
| kickoff day | 32 | 4 | 5.11 | 3.42 | +1.69 (+0.53 to +1.93) | +1.25 | 2.35 | 0 (0.0%) | 2 (6.2%) | 0 (0.0%) | 2 (6.2%) |
| kickoff evening | 21 | 6 | 5.93 | 5.43 | +0.50 (-1.73 to +1.48) | +0.20 | 2.55 | 2 (9.5%) | 1 (4.8%) | 1 (4.8%) | 0 (0.0%) |
| kickoff night | 16 | 7 | 4.97 | 4.62 | +0.34 (-1.66 to +2.60) | -0.45 | 2.93 | 0 (0.0%) | 3 (18.8%) | 0 (0.0%) | 3 (18.8%) |
| kickoff zone unknown | 27 | 6 | 5.84 | 4.35 | +1.49 (-0.28 to +2.68) | +1.90 | 2.85 | 0 (0.0%) | 2 (7.4%) | 0 (0.0%) | 2 (7.4%) |
| observed 0-5 mph | 59 | 8 | 4.70 | 2.49 | +2.21 (+1.65 to +3.09) | +2.10 | 2.73 | 0 (0.0%) | 4 (6.8%) | 0 (0.0%) | 4 (6.8%) |
| observed 5-10 mph | 35 | 7 | 6.41 | 6.62 | -0.21 (-1.21 to +0.54) | -0.70 | 2.25 | 0 (0.0%) | 3 (8.6%) | 0 (0.0%) | 3 (8.6%) |
| observed 15+ mph | 2 | 2 | 11.70 | 18.00 | -6.30 (-7.50 to -5.10) | -6.30 | 6.30 | 2 (100.0%) | 1 (50.0%) | 1 (50.0%) | 0 (0.0%) |
| gust ratio 1.5-2 | 18 | 5 | 8.43 | 4.83 | +3.59 (+0.11 to +4.96) | +3.15 | 4.21 | 0 (0.0%) | 6 (33.3%) | 0 (0.0%) | 6 (33.3%) |
| gust ratio 2+ | 78 | 9 | 4.79 | 4.21 | +0.58 (-0.44 to +1.02) | +0.55 | 2.27 | 2 (2.6%) | 2 (2.6%) | 1 (1.3%) | 1 (1.3%) |

#### build_forecasts newest pre-kickoff, 2026 vs ERA5

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|

#### build_forecasts newest pre-kickoff, 2026 vs CFBD

| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |
|---|---|---|---|---|---|---|---|---|---|---|---|

#### Notes

- FBS-vs-FBS games loaded (2024-26): 2368
- venue zone stored in venues.timezone: 0
- venue zone from the state / city rule: 1839
- venue zone unknown (left out of the hour split): 529
- ERA5 readings on these games: 1764
- CFBD readings on these games: 1846
- CFBD readings of exactly 0 mph (calm or unreported; kept): 213
- build_forecasts games (newest pre-kickoff row): 58
- build_forecasts lead hours, median: 7.4
