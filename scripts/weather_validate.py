#!/usr/bin/env python
"""Read this before promoting a weather backfill. It is a report, not a gate.

    PYTHONPATH=. python scripts/weather_validate.py [--staging PATH] [--from-db]

Six checks, each aimed at a way this has already gone wrong or could:

  1. GROUND TRUTH. Two kickoffs whose true conditions were established by hand
     against the ERA5 archive. The old table stored 63.2F for an LA Coliseum
     game that was 78.1F -- if either of these still reads like the old value,
     the clock is still wrong and nothing else in this report matters.
  2. COVERAGE by season and lead, against the modelled set.
  3. ENVELOPES. Gusts at or above the mean wind, non-negative precipitation,
     domes carrying no weather, temperatures inside a seasonal band.
  4. LEAD MONOTONICITY. A 72-hour forecast must sit FURTHER from the
     near-kickoff value than a 24-hour one. If that inverts, the lead variables
     are mislabelled and every decision-safe row is suspect.
  5. DECISION SAFETY. No lead-0 row may ever be flagged decision_safe.
  6. OLD VS NEW. How far the legacy `weather` rows were from the repaired ones,
     which is the measure of what the bug cost.
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from beatvegas.db.models import Weather, WeatherObs
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.sources.weather import SOURCE_ACTUAL, fetch_weather

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGING = REPO_ROOT / "data" / "cache" / "weather_staging.jsonl"

# (game_id, venue, lat, lon, kickoff UTC, the WRONG value the old table stored)
GROUND_TRUTH = [
    (401523986, "Los Angeles Memorial Coliseum", 34.014167, -118.287778, "2023-08-27T00", 63.2),
    (401540199, "Cramton Bowl", 32.37949, -86.293002, "2023-08-26T19", 93.6),
]

# A first-half college football kickoff is never below this or above that.
TEMP_BAND = (-30.0, 130.0)

# A gust below the mean wind is physically impossible, but TWO different things
# produce it and only one is a defect.
#
# Open-Meteo works in m/s and converts, so on a calm hour where gust == wind the
# rounding can invert them by a tenth. Measured on the near-kickoff series: 15 of
# 4,227 rows (0.35%), every deficit 0.1-0.3 mph, every case under 7.5 mph of wind.
#
# The real failure looks nothing like that. `gfs_seamless` at 48h+ fills gust and
# mean wind from different model runs: 32% of samples inverted, deficits to
# 2.7 mph. So neither magnitude nor count alone discriminates -- the RATE does,
# and the two thresholds below are set between the measured populations.
GUST_TOLERANCE_MPH = 0.5
GUST_INVERSION_RATE_MAX = 0.01


def _load_staging(path: Path) -> List[dict]:
    rows = []
    for ln in path.read_text().splitlines():
        if ln.strip():
            rows.append(json.loads(ln))
    latest = {(r["game_id"], r["lead_hours"]): r for r in rows}
    return list(latest.values())


def _load_db() -> List[dict]:
    with session_scope() as s:
        return [
            {
                "game_id": w.game_id,
                "lead_hours": w.lead_hours,
                "valid_time": w.valid_time.isoformat() if w.valid_time else None,
                "decision_safe": w.decision_safe,
                "temperature_f": w.temperature_f,
                "wind_mph": w.wind_mph,
                "wind_gust_mph": w.wind_gust_mph,
                "precipitation": w.precipitation,
                "dome": w.dome,
                "source": w.source,
            }
            for w in s.query(WeatherObs).all()
        ]


def _by_lead(rows: List[dict]) -> Dict[int, List[dict]]:
    out = defaultdict(list)
    for r in rows:
        out[r["lead_hours"]].append(r)
    return out


def check_ground_truth(rows: List[dict]) -> bool:
    print("\n1. GROUND TRUTH")
    idx = {(r["game_id"], r["lead_hours"]): r for r in rows}
    ok = True
    for gid, name, lat, lon, kick, old_wrong in GROUND_TRUTH:
        r = idx.get((gid, 0))
        if r is None:
            print(f"   {name}: NOT STAGED (cannot check)")
            continue
        actual = fetch_weather(
            lat, lon, datetime.strptime(kick, "%Y-%m-%dT%H"), source=SOURCE_ACTUAL
        )
        truth = actual["temperature_f"] if actual else None
        got = r["temperature_f"]
        near_old = got is not None and abs(got - old_wrong) < 1.0
        near_truth = truth is not None and got is not None and abs(got - truth) < 6.0
        verdict = "STILL WRONG" if near_old else ("ok" if near_truth else "CHECK")
        ok = ok and not near_old and near_truth
        print(
            f"   {name:<30} stored={got}  ERA5 actual={truth}  old(wrong)={old_wrong}  -> {verdict}"
        )
    return ok


def check_coverage(rows: List[dict]) -> None:
    print("\n2. COVERAGE (rows by season and lead)")
    seasons = defaultdict(lambda: defaultdict(int))
    for r in rows:
        vt = r.get("valid_time") or ""
        yr = vt[:4]
        # a season runs Aug-Jan, so January belongs to the previous season
        season = int(yr) - 1 if vt[5:7] == "01" else int(yr) if yr else 0
        seasons[season][r["lead_hours"]] += 1
    leads = sorted({r["lead_hours"] for r in rows})
    print("   season  " + "  ".join(f"lead{lead:>4}" for lead in leads))
    for season in sorted(seasons):
        print(f"   {season}    " + "  ".join(f"{seasons[season][x]:>8}" for x in leads))


def check_envelopes(rows: List[dict]) -> bool:
    print("\n3. ENVELOPES")
    ok = True
    for lead, rs in sorted(_by_lead(rows).items()):
        out = [r for r in rs if not r["dome"]]
        gusted = [r for r in out if r["wind_gust_mph"] is not None and r["wind_mph"] is not None]
        deficits = [
            r["wind_mph"] - r["wind_gust_mph"] for r in gusted if r["wind_gust_mph"] < r["wind_mph"]
        ]
        gust_rate = (len(deficits) / len(gusted)) if gusted else 0.0
        gust_bad = [d for d in deficits if d > GUST_TOLERANCE_MPH]
        if gust_rate > GUST_INVERSION_RATE_MAX:
            # Rate, not magnitude, is what separates unit rounding from two
            # variables arriving out of different model runs.
            gust_bad = gust_bad or deficits
        precip_bad = [r for r in out if (r["precipitation"] or 0) < 0]
        temp_bad = [
            r
            for r in out
            if r["temperature_f"] is not None
            and not (TEMP_BAND[0] <= r["temperature_f"] <= TEMP_BAND[1])
        ]
        dome_dirty = [
            r
            for r in rs
            if r["dome"] and any(r[k] is not None for k in ("temperature_f", "wind_mph"))
        ]
        bad = len(gust_bad) + len(precip_bad) + len(temp_bad) + len(dome_dirty)
        ok = ok and bad == 0
        worst = max(deficits) if deficits else 0.0
        print(
            f"   lead {lead:>3}: {len(rs):>6} rows  gust<wind={len(deficits)} "
            f"({gust_rate:.2%}, worst {worst:.1f}mph)  precip<0={len(precip_bad)}  "
            f"temp out of band={len(temp_bad)}  dome with weather={len(dome_dirty)}  "
            f"{'ok' if bad == 0 else '*** PROBLEM ***'}"
        )
        if deficits and not gust_bad:
            print(
                f"          (inversions are within {GUST_TOLERANCE_MPH}mph on "
                f"<{GUST_INVERSION_RATE_MAX:.0%} of rows -- unit rounding on calm hours, not a defect)"
            )
    return ok


def check_lead_monotonicity(rows: List[dict]) -> bool:
    print("\n4. LEAD MONOTONICITY (distance from the near-kickoff value)")
    by_lead = _by_lead(rows)
    base = {r["game_id"]: r for r in by_lead.get(0, [])}
    if not base:
        print("   no lead-0 rows staged -- cannot compare")
        return True
    means = {}
    for lead in sorted(x for x in by_lead if x > 0):
        d = [
            abs(r["temperature_f"] - base[r["game_id"]]["temperature_f"])
            for r in by_lead[lead]
            if r["game_id"] in base
            and r["temperature_f"] is not None
            and base[r["game_id"]]["temperature_f"] is not None
        ]
        if d:
            means[lead] = st.mean(d)
            print(
                f"   lead {lead:>3}h: mean |temp - near_kickoff| = {means[lead]:.2f}F  (n={len(d)})"
            )
    ordered = [means[k] for k in sorted(means)]
    ok = ordered == sorted(ordered)
    print(
        f"   {'ok - longer leads sit further out' if ok else '*** NOT MONOTONE - leads may be mislabelled ***'}"
    )
    return ok


def check_decision_safety(rows: List[dict]) -> bool:
    print("\n5. DECISION SAFETY")
    leaks = [r for r in rows if r["lead_hours"] == 0 and r["decision_safe"]]
    safe = sum(1 for r in rows if r["decision_safe"])
    print(f"   {safe} decision-safe rows; {len(leaks)} lead-0 rows wrongly flagged")
    print(
        "   " + ("ok" if not leaks else "*** LOOK-AHEAD BIAS: lead-0 rows marked decision_safe ***")
    )
    return not leaks


def check_old_vs_new(rows: List[dict]) -> None:
    print("\n6. OLD VS NEW (what the clock bug cost)")
    new = {r["game_id"]: r for r in rows if r["lead_hours"] == 0 and not r["dome"]}
    with session_scope() as s:
        old = [
            (w.game_id, w.temperature_f, w.wind_mph)
            for w in s.query(Weather).filter(Weather.temperature_f.isnot(None)).all()
        ]
    dt, dw = [], []
    for gid, t, wind in old:
        r = new.get(gid)
        if not r:
            continue
        if t is not None and r["temperature_f"] is not None:
            dt.append(abs(t - r["temperature_f"]))
        if wind is not None and r["wind_mph"] is not None:
            dw.append(abs(wind - r["wind_mph"]))
    if not dt:
        print("   no overlap with the legacy table yet")
        return
    dt.sort()
    print(f"   {len(dt)} games overlap the legacy table")
    print(
        f"   |temp old-new|: mean {st.mean(dt):.2f}F  median {st.median(dt):.2f}F  p90 {dt[int(0.9 * len(dt))]:.2f}F  max {dt[-1]:.2f}F"
    )
    if dw:
        print(f"   |wind old-new|: mean {st.mean(dw):.2f}mph  median {st.median(dw):.2f}mph")
    print(f"   share off by more than 5F: {100 * sum(1 for x in dt if x > 5) / len(dt):.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--staging", type=Path, default=STAGING)
    ap.add_argument(
        "--from-db", action="store_true", help="validate weather_obs instead of the file"
    )
    args = ap.parse_args()
    if not try_init_db():
        return
    rows: Optional[List[dict]] = _load_db() if args.from_db else _load_staging(args.staging)
    print(
        f"== weather validation: {len(rows)} rows from "
        f"{'weather_obs' if args.from_db else args.staging} =="
    )
    passed = [
        check_ground_truth(rows),
        check_envelopes(rows),
        check_lead_monotonicity(rows),
        check_decision_safety(rows),
    ]
    check_coverage(rows)
    check_old_vs_new(rows)
    print(f"\n== {sum(passed)}/{len(passed)} hard checks passed ==")


if __name__ == "__main__":
    main()
