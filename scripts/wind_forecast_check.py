#!/usr/bin/env python
"""H-WX-ICON-BIAS (docs/HYPOTHESES.md; exploratory, one look): does ICON's
sustained 10 m wind forecast at the kickoff hour run low against observed wind?

Tate, 2026-10-17: the game page's wind (ICON via `build_forecasts`) often reads
lower than the NWS point forecast (Arkansas State @ Southern Miss: 8.6 mph on the
page, NWS 13-15 sustained, gusts agreeing). The weather arms H-ARM-WX1H /
H-ARM-WXFG freeze ICON's sustained wind at the kickoff UTC hour, 10.0+ mph, so a
forecast that runs low shrinks their universe. NWS keeps no history in these
tables, so the truth here is observed wind at the same hour.

Forecasts (all `icon_seamless`, the kickoff UTC hour):
- `weather_obs` leads 24 and 72, `decision_safe`, the newest fetch per game;
  2024-25 is the primary read, 2026's played games are shown beside it;
- `build_forecasts` 2026, each game's newest row fetched before kickoff (what the
  page and the arms read).
Truths, side by side and never blended (`weather_actuals`, hour_offset 0):
- ERA5 (`open_meteo_era5_archive`): a reanalysis, itself a model, hourly at the
  same UTC hour;
- CFBD `/games/weather`: station-like, whole-number wind, provider and hour not
  stated.
Universe: FBS-vs-FBS, outdoor (venue not a dome, the forecast row not a dome,
CFBD not indoors), forecast and truth both present.

Per forecast x truth: mean bias (forecast minus observed; 95% interval resampling
whole kickoff dates, since one weather system moves a day's games together),
median bias, MAE, and the share of games where the forecast is under 10 mph but
the observation is 10+ ("missed windy") and the reverse ("false windy"); split by
local kickoff hour (day < 16:00, evening 16:00-18:59, night 19:00+), observed
wind band and the forecast's own gust / sustained ratio. n in every cell.

Exploratory: counts and intervals only; it licenses nothing. READ-ONLY (no
init_db, no write); writes reports/wind_forecast_check_<UTC>.{md,json}. Runs
through study.yml.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from beatvegas.backtest.early_close import bootstrap_mean_ci  # noqa: E402
from beatvegas.etl.situational import kickoff_local_hour  # noqa: E402

WIND_MIN_MPH = 10.0  # the arms' threshold, frozen 2026-10-09 (wx_paper.WIND_MIN_MPH)
ICON = "icon_seamless"
ERA5 = "open_meteo_era5_archive"
CFBD = "cfbd_games_weather"
TRUTHS = {ERA5: "ERA5", CFBD: "CFBD"}
PRIMARY_SEASONS = (2024, 2025)
LIVE_SEASON = 2026
LEADS = (24, 72)

# The venue's IANA zone comes from `venues.timezone` (CFBD /venues). Where it is
# empty, a state wholly inside one zone gives it exactly; Texas and Nevada are
# exact by city (El Paso and Hudspeth counties are the only Mountain part of
# Texas, West Wendover the only Mountain part of Nevada). Every other venue is
# left out of the hour split and counted.
SINGLE_ZONE_STATES = {
    **dict.fromkeys(
        ("CT", "DC", "DE", "GA", "MA", "MD", "ME", "NC", "NH", "NJ", "NY", "OH", "PA", "RI"),
        "America/New_York",
    ),
    **dict.fromkeys(("SC", "VA", "VT", "WV"), "America/New_York"),
    **dict.fromkeys(
        ("AL", "AR", "IA", "IL", "LA", "MN", "MO", "MS", "OK", "WI"), "America/Chicago"
    ),
    **dict.fromkeys(("CO", "MT", "NM", "UT", "WY"), "America/Denver"),
    "AZ": "America/Phoenix",
    **dict.fromkeys(("CA", "WA"), "America/Los_Angeles"),
    "HI": "Pacific/Honolulu",
}

HOUR_BANDS = ("day", "evening", "night")
OBS_BANDS = ((0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, None))
RATIO_BANDS = ((0.0, 1.5), (1.5, 2.0), (2.0, None))


def venue_zone(stored: Optional[str], state: Optional[str], city: Optional[str]) -> Optional[str]:
    """The venue's IANA zone: the stored one, else an exact state / city rule."""
    if stored and str(stored).strip():
        return str(stored).strip()
    st = (state or "").strip().upper()
    c = (city or "").strip().lower()
    if st == "TX":
        return (
            "America/Denver"
            if c in ("el paso", "fort hancock", "sierra blanca")
            else ("America/Chicago" if c else None)
        )
    if st == "NV":
        return "America/Denver" if c == "west wendover" else ("America/Los_Angeles" if c else None)
    return SINGLE_ZONE_STATES.get(st)


def hour_band(local_hour: Optional[float]) -> Optional[str]:
    """day < 16:00, evening 16:00-18:59, night 19:00+ (local wall clock)."""
    if local_hour is None:
        return None
    if local_hour < 16.0:
        return "day"
    if local_hour < 19.0:
        return "evening"
    return "night"


def _band(x: float, bands: Sequence[Tuple[float, Optional[float]]]) -> str:
    for lo, hi in bands:
        if x >= lo and (hi is None or x < hi):
            return f"{lo:g}+" if hi is None else f"{lo:g}-{hi:g}"
    return "?"


def obs_band(observed: float) -> str:
    return _band(observed, OBS_BANDS)


def ratio_band(wind: Optional[float], gust: Optional[float]) -> Optional[str]:
    """The forecast's own gust / sustained ratio, a decision-time quantity."""
    if wind is None or gust is None or wind <= 0:
        return None
    return _band(gust / wind, RATIO_BANDS)


def pair(forecasts: Dict[int, dict], truths: Dict[int, dict], games: Dict[int, dict]) -> List[dict]:
    """One row per game with both a forecast and an observation (outdoor only)."""
    out = []
    for gid, f in forecasts.items():
        g, t = games.get(gid), truths.get(gid)
        if g is None or t is None or f.get("wind") is None or t.get("wind") is None:
            continue
        if f.get("dome") or g.get("dome") or t.get("indoors"):
            continue
        out.append(
            {
                "game_id": gid,
                "date": g["kickoff"].strftime("%Y-%m-%d"),
                "forecast": float(f["wind"]),
                "gust": None if f.get("gust") is None else float(f["gust"]),
                "observed": float(t["wind"]),
                "local_hour": g.get("local_hour"),
            }
        )
    return out


def summarize(rows: List[dict]) -> dict:
    """Bias (forecast minus observed), MAE and the 10 mph crossings for a group."""
    n = len(rows)
    if not n:
        return {"n": 0}
    diffs = [r["forecast"] - r["observed"] for r in rows]
    by_date: Dict[str, List[float]] = defaultdict(list)
    for r, d in zip(rows, diffs):
        by_date[r["date"]].append(d)
    missed = sum(1 for r in rows if r["forecast"] < WIND_MIN_MPH <= r["observed"])
    false = sum(1 for r in rows if r["observed"] < WIND_MIN_MPH <= r["forecast"])
    return {
        "n": n,
        "dates": len(by_date),
        "forecast_mean": sum(r["forecast"] for r in rows) / n,
        "observed_mean": sum(r["observed"] for r in rows) / n,
        "bias_mean": sum(diffs) / n,
        "bias_ci95": bootstrap_mean_ci(list(by_date.values())),
        "bias_median": statistics.median(diffs),
        "mae": sum(abs(d) for d in diffs) / n,
        "obs_windy": sum(1 for r in rows if r["observed"] >= WIND_MIN_MPH),
        "fc_windy": sum(1 for r in rows if r["forecast"] >= WIND_MIN_MPH),
        "missed_windy": missed,
        "false_windy": false,
    }


def splits(rows: List[dict]) -> Dict[str, dict]:
    """Overall, then by local kickoff hour, observed band and forecast gust ratio."""
    groups: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        groups["all"].append(r)
        hb = hour_band(r["local_hour"])
        groups[f"kickoff {hb}" if hb else "kickoff zone unknown"].append(r)
        groups[f"observed {obs_band(r['observed'])} mph"].append(r)
        rb = ratio_band(r["forecast"], r["gust"])
        groups[f"gust ratio {rb}" if rb else "gust ratio n/a"].append(r)
    order = (
        ["all"]
        + [f"kickoff {b}" for b in HOUR_BANDS]
        + ["kickoff zone unknown"]
        + [f"observed {_band(lo, OBS_BANDS)} mph" for lo, _ in OBS_BANDS]
        + [f"gust ratio {_band(lo, RATIO_BANDS)}" for lo, _ in RATIO_BANDS]
        + ["gust ratio n/a"]
    )
    return {k: summarize(groups[k]) for k in order if groups.get(k)}


# ------------------------------------------------------------------ database reads


def load_games(session, seasons: Iterable[int]) -> Dict[int, dict]:
    """FBS-vs-FBS games of the seasons, with dome, kickoff and local kickoff hour."""
    from beatvegas.db.models import Game, Venue
    from beatvegas.etl.fbs import load_fbs_teams

    fbs = load_fbs_teams()
    q = (
        session.query(
            Game.id,
            Game.season,
            Game.start_date,
            Game.home_team,
            Game.away_team,
            Venue.dome,
            Venue.timezone,
            Venue.state,
            Venue.city,
        )
        .outerjoin(Venue, Venue.id == Game.venue_id)
        .filter(Game.season.in_(list(seasons)))
    )
    out: Dict[int, dict] = {}
    for gid, season, kick, home, away, dome, tz, state, city in q.all():
        teams = fbs.get(int(season))
        if teams is None or home not in teams or away not in teams or kick is None:
            continue
        zone = venue_zone(tz, state, city)
        out[int(gid)] = {
            "season": int(season),
            "kickoff": kick,
            "dome": bool(dome),
            "zone": zone,
            "zone_stored": bool(tz and str(tz).strip()),
            "local_hour": kickoff_local_hour(kick, zone) if zone else None,
        }
    return out


def load_truths(session, game_ids: Iterable[int]) -> Dict[str, Dict[int, dict]]:
    """source -> game_id -> the newest hour_offset-0 reading."""
    from beatvegas.db.models import WeatherActual

    ids = set(game_ids)
    rows = (
        session.query(WeatherActual)
        .filter(WeatherActual.hour_offset == 0, WeatherActual.source.in_(list(TRUTHS)))
        .order_by(WeatherActual.retrieved_at.asc(), WeatherActual.id.asc())
        .all()
    )
    out: Dict[str, Dict[int, dict]] = {s: {} for s in TRUTHS}
    for r in rows:  # ascending, so the newest wins
        if int(r.game_id) in ids:
            out[r.source][int(r.game_id)] = {
                "wind": r.wind_mph,
                "indoors": bool(r.game_indoors),
            }
    return out


def load_obs_forecasts(session, game_ids: Iterable[int], lead: int) -> Dict[int, dict]:
    """game_id -> the newest decision-safe ICON forecast at that lead."""
    from beatvegas.db.models import WeatherObs

    ids = set(game_ids)
    rows = (
        session.query(WeatherObs)
        .filter(
            WeatherObs.lead_hours == lead,
            WeatherObs.decision_safe.is_(True),
            WeatherObs.weather_model == ICON,
        )
        .order_by(WeatherObs.retrieved_at.asc(), WeatherObs.id.asc())
        .all()
    )
    out: Dict[int, dict] = {}
    for r in rows:
        if int(r.game_id) in ids:
            out[int(r.game_id)] = {"wind": r.wind_mph, "gust": r.wind_gust_mph, "dome": r.dome}
    return out


def load_build_forecasts(session, games: Dict[int, dict]) -> Dict[int, dict]:
    """game_id -> the newest ICON build-time forecast fetched before kickoff."""
    from beatvegas.db.models import BuildForecast

    rows = (
        session.query(BuildForecast)
        .filter(BuildForecast.weather_model == ICON)
        .order_by(BuildForecast.fetched_at.asc(), BuildForecast.id.asc())
        .all()
    )
    out: Dict[int, dict] = {}
    for r in rows:
        g = games.get(int(r.game_id))
        if g is None or r.fetched_at is None or r.fetched_at >= g["kickoff"]:
            continue
        out[int(r.game_id)] = {
            "wind": r.wind_mph,
            "gust": r.wind_gust_mph,
            "dome": r.dome,
            "lead_hours": r.lead_hours,
        }
    return out


# ------------------------------------------------------------------ report


def _f(x: Optional[float], signed: bool = False) -> str:
    if x is None:
        return "—"
    return f"{x:+.2f}" if signed else f"{x:.2f}"


def _share(k: int, n: int) -> str:
    return f"{k} ({100 * k / n:.1f}%)" if n else "—"


def render(result: dict, meta: dict, stamp: str) -> str:
    L = [
        f"# H-WX-ICON-BIAS, wind forecast check ({stamp})",
        "",
        "FBS-vs-FBS outdoor games; forecast = ICON (`icon_seamless`) sustained 10 m wind at the "
        "kickoff UTC hour; truth = `weather_actuals` hour_offset 0 (ERA5 reanalysis, or CFBD's "
        "station-like whole-number reading). Bias = forecast minus observed, mph (negative = the "
        "forecast runs LOW); 95% interval resamples whole kickoff dates. Missed windy = forecast "
        f"< {WIND_MIN_MPH:g} but observed >= {WIND_MIN_MPH:g}; false windy = the reverse; both as "
        "a share of n. Exploratory: nothing is adopted from it.",
        "",
        f"Run: {meta['run']}.",
        "",
        "## Summary (every forecast x truth, all games)",
        "",
        "| forecast | truth | n | dates | forecast mean | observed mean | mean bias (95% CI) "
        "| median bias | MAE | observed 10+ | forecast 10+ | missed windy | false windy |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for block in result.values():
        a = block["splits"].get("all", {"n": 0})
        if not a["n"]:
            L.append(f"| {block['forecast']} | {block['truth']} | 0 | | | | | | | | | | |")
            continue
        L.append(_row(block["forecast"], block["truth"], a))
    for block in result.values():
        L += [
            "",
            f"## {block['forecast']} vs {block['truth']}",
            "",
            "| group | n | dates | forecast mean | observed mean | mean bias (95% CI) | median bias "
            "| MAE | observed 10+ | forecast 10+ | missed windy | false windy |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for name, s in block["splits"].items():
            L.append(_row(name, None, s))
    L += ["", "## Notes", ""]
    for k, v in meta["notes"].items():
        L.append(f"- {k}: {v}")
    return "\n".join(L) + "\n"


def _row(first: str, second: Optional[str], s: dict) -> str:
    ci = s["bias_ci95"]
    ci_s = "—" if ci is None else f"{ci[0]:+.2f} to {ci[1]:+.2f}"
    lead = f"| {first} | {second} " if second is not None else f"| {first} "
    return (
        f"{lead}| {s['n']} | {s['dates']} | {_f(s['forecast_mean'])} | {_f(s['observed_mean'])} "
        f"| {_f(s['bias_mean'], True)} ({ci_s}) | {_f(s['bias_median'], True)} | {_f(s['mae'])} "
        f"| {_share(s['obs_windy'], s['n'])} | {_share(s['fc_windy'], s['n'])} "
        f"| {_share(s['missed_windy'], s['n'])} | {_share(s['false_windy'], s['n'])} |"
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports")
    args = ap.parse_args(argv)

    import os

    from beatvegas.db.store import get_engine, session_scope, wait_for_db

    try:
        wait_for_db(get_engine())
    except Exception as e:  # noqa: BLE001 - one clear line, not a traceback
        print(f"database unreachable: {e}")
        return 1

    result: Dict[str, dict] = {}
    with session_scope() as s:
        games = load_games(s, PRIMARY_SEASONS + (LIVE_SEASON,))
        truths = load_truths(s, games)
        sets: List[Tuple[str, Dict[int, dict]]] = []
        for lead in LEADS:
            fc = load_obs_forecasts(s, games, lead)
            for label, seasons in (
                (f"weather_obs {lead} h, 2024-25", PRIMARY_SEASONS),
                (f"weather_obs {lead} h, 2026", (LIVE_SEASON,)),
            ):
                sets.append((label, {g: f for g, f in fc.items() if games[g]["season"] in seasons}))
        build = load_build_forecasts(s, games)
        sets.append(("build_forecasts newest pre-kickoff, 2026", build))
        for label, fc in sets:
            for src, tname in TRUTHS.items():
                rows = pair(fc, truths[src], games)
                result[f"{label} | {tname}"] = {
                    "forecast": label,
                    "truth": tname,
                    "splits": splits(rows),
                }

    leads = sorted(f["lead_hours"] for f in build.values() if f.get("lead_hours") is not None)
    cfbd_vals = [t["wind"] for t in truths[CFBD].values() if t.get("wind") is not None]
    meta = {
        "run": (
            f"GITHUB_RUN_ID {os.environ.get('GITHUB_RUN_ID', '-')}, "
            f"GITHUB_SHA {os.environ.get('GITHUB_SHA', '-')[:7]}"
        ),
        "notes": {
            "FBS-vs-FBS games loaded (2024-26)": len(games),
            "venue zone stored in venues.timezone": sum(
                1 for g in games.values() if g["zone_stored"]
            ),
            "venue zone from the state / city rule": sum(
                1 for g in games.values() if g["zone"] and not g["zone_stored"]
            ),
            "venue zone unknown (left out of the hour split)": sum(
                1 for g in games.values() if not g["zone"]
            ),
            "ERA5 readings on these games": len(truths[ERA5]),
            "CFBD readings on these games": len(truths[CFBD]),
            "CFBD readings of exactly 0 mph (calm or unreported; kept)": sum(
                1 for v in cfbd_vals if v == 0
            ),
            "build_forecasts games (newest pre-kickoff row)": len(build),
            "build_forecasts lead hours, median": (
                f"{statistics.median(leads):.1f}" if leads else "—"
            ),
        },
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md = render(result, meta, stamp)
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"wind_forecast_check_{stamp}.md").write_text(md)
    (outdir / f"wind_forecast_check_{stamp}.json").write_text(
        json.dumps({"meta": meta, "result": result}, indent=1, default=str)
    )
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
