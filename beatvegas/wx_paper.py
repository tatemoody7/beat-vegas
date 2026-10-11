"""H-ARM-WX1H / H-ARM-WXFG: the registered weather arms -- paper unders on windy forecasts.

Registry rows H-ARM-WX1H and H-ARM-WXFG (docs/HYPOTHESES.md; ledger slots 6 and
7 of the 2026 protocol, p1.1; roadmap v1.6). Tate's calls of 2026-10-09 (strategic review
topic 3): at every decision build, each OUTDOOR game whose NEWEST forecast,
fetched by that build, has a sustained 10 m wind of 10+ mph at the kickoff hour
logs one paper UNDER at Hard Rock's price -- the first-half arm on Hard Rock's
centred main first-half total, the full-game arm on its newest centred
full-game total. Every qualifier, uncapped; one observation per game, at the
first eligible build that saw it (the paper windows of beatvegas.ci). Neither
arm reads the model, so the leak-fix pause (p1.1) does not touch them.

`capture` fetches the forecast during the build and writes `build_forecasts`
(decision-safe by construction: the build's own clock precedes the kickoff it
describes), pinned to the same weather model as `weather_obs`'s history so the
2024-25 history look (H-WX-HIST) and these arms read the same kind of number. It
fetches only the games an arm can log (`arm_game_ids`) and runs on the build's
clock (2026-10-10): fetching every game of the week ran the card job out of time.

Every row here is PAPER, in `challenger_picks`, never `manual_picks`. There is
no real-money path through this file.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional

from .card import parse_kick
from .challenger_picks import add_challenger_pick
from .db.models import BuildForecast, ChallengerPick, Game, Venue
from .devig import is_centred_quote
from .fg_paper import _hr_quotes
from .hardrock import HR_BOOK_KEY
from .protocol import ARM_WX_1H, ARM_WX_FG
from .sources.weather import (
    FORECAST_HORIZON_DAYS,
    SOURCE_FORECAST,
    WeatherUnavailable,
    fetch_hourly_series,
)

WIND_MIN_MPH = 10.0  # frozen 2026-10-09: sustained 10 m wind at the kickoff hour
WEATHER_MODEL = "icon_seamless"  # scripts/backfill_weather.py::DECISION_MODEL

# The capture runs inside the card build, whose whole job has 30 minutes
# (card.yml). On 2026-10-10 it fetched every game of the week -- 254 games, 245
# venue calls on the full retry ladder -- and the sat_am build was cancelled at
# the limit with no card written. A build call is short, and no new call starts
# once the budget is spent.
BUILD_FETCH_TIMEOUT_S = 10  # seconds per Open-Meteo call
BUILD_FETCH_ATTEMPTS = 2  # the backfills keep sources/weather.py's four
BUILD_CAPTURE_BUDGET_S = 180.0  # the whole capture


def capture(
    session,
    game_ids: Iterable[int],
    now: datetime,
    slot: Optional[str] = None,
    fetch: Callable[..., Dict[str, dict]] = fetch_hourly_series,
    *,
    timeout: int = BUILD_FETCH_TIMEOUT_S,
    attempts: int = BUILD_FETCH_ATTEMPTS,
    budget_seconds: Optional[float] = BUILD_CAPTURE_BUDGET_S,
    clock: Callable[[], float] = time.monotonic,
) -> Dict[str, int]:
    """Fetch and store the kickoff-hour forecast of every listed game not yet
    kicked off, earliest kickoff first. One call per venue and UTC day; a dome
    stores a row with no weather and costs no call. A failed fetch is counted,
    never fatal.

    Each call gets `timeout` seconds and `attempts` tries. Once `budget_seconds`
    have passed no new call starts: the games still waiting count as failed, and
    as `over_budget`, a key present only when the budget ran out."""
    ids = [int(g) for g in game_ids]
    stats = {"stored": 0, "domes": 0, "no_venue": 0, "failed": 0}
    if not ids:
        return stats
    games = (
        session.query(Game.id, Game.start_date, Game.venue_id)
        .filter(Game.id.in_(ids), Game.start_date > now)
        .order_by(Game.start_date.asc(), Game.id.asc())
        .all()
    )
    started = clock()
    vids = {int(v) for _, _, v in games if v is not None}
    venues = {int(v.id): v for v in session.query(Venue).filter(Venue.id.in_(vids)).all()}
    series_by: Dict[tuple, Optional[Dict[str, dict]]] = {}
    for gid, kick, vid in games:
        v = venues.get(int(vid)) if vid is not None else None
        if v is None or v.latitude is None or v.longitude is None:
            stats["no_venue"] += 1
            continue
        if kick - now > timedelta(days=FORECAST_HORIZON_DAYS):
            continue
        dome = bool(v.dome)
        vals: Dict[str, Any] = {}
        if dome:
            stats["domes"] += 1
        else:
            day = kick.strftime("%Y-%m-%d")
            key = (int(vid), day)
            if key not in series_by:
                if budget_seconds is not None and clock() - started >= budget_seconds:
                    stats["failed"] += 1
                    stats["over_budget"] = stats.get("over_budget", 0) + 1
                    continue
                try:
                    series_by[key] = fetch(
                        v.latitude,
                        v.longitude,
                        day,
                        day,
                        source=SOURCE_FORECAST,
                        models=WEATHER_MODEL,
                        timeout=timeout,
                        attempts=attempts,
                    )
                except WeatherUnavailable as e:
                    print(f"[wx] forecast unavailable for venue {vid} {day}: {e}")
                    series_by[key] = None
            series = series_by[key]
            hour = None if series is None else series.get(kick.strftime("%Y-%m-%dT%H"))
            if hour is None:
                stats["failed"] += 1
                continue
            vals = hour
        session.add(
            BuildForecast(
                game_id=int(gid),
                fetched_at=now,
                kickoff=kick,
                lead_hours=round((kick - now).total_seconds() / 3600.0, 2),
                slot=slot,
                temperature_f=vals.get("temperature_f"),
                wind_mph=vals.get("wind_mph"),
                wind_gust_mph=vals.get("wind_gust_mph"),
                precipitation=vals.get("precipitation"),
                dome=dome,
                latitude=v.latitude,
                longitude=v.longitude,
                source=SOURCE_FORECAST,
                weather_model=WEATHER_MODEL,
            )
        )
        stats["stored"] += 1
    session.flush()
    # To stderr, unbuffered: a build killed later still leaves this line in its
    # log, and the card summary on stdout keeps its first lines.
    print(
        f"[wx] forecast capture: {len(series_by)} calls in {clock() - started:.0f} s, {stats}",
        file=sys.stderr,
        flush=True,
    )
    return stats


def newest(session, game_ids: Iterable[int], now: datetime) -> Dict[int, BuildForecast]:
    """Each game's newest forecast fetched at or before `now`."""
    ids = [int(g) for g in game_ids]
    if not ids:
        return {}
    rows = (
        session.query(BuildForecast)
        .filter(BuildForecast.game_id.in_(ids), BuildForecast.fetched_at <= now)
        .order_by(BuildForecast.fetched_at.asc(), BuildForecast.id.asc())
        .all()
    )
    out: Dict[int, BuildForecast] = {}
    for r in rows:  # ascending, so the newest wins
        out[int(r.game_id)] = r
    return out


def qualifies(fc: Optional[BuildForecast], wind_min: float = WIND_MIN_MPH) -> bool:
    """Outdoor, with a sustained kickoff-hour wind at or above the threshold."""
    return bool(
        fc is not None and not fc.dome and fc.wind_mph is not None and fc.wind_mph >= wind_min
    )


def frozen(fc: BuildForecast) -> str:
    """The forecast a pick was decided on, frozen beside the row."""
    return json.dumps(
        {
            "wind_mph": fc.wind_mph,
            "wind_gust_mph": fc.wind_gust_mph,
            "temperature_f": fc.temperature_f,
            "precipitation": fc.precipitation,
            "lead_hours": fc.lead_hours,
            "fetched_at": fc.fetched_at.isoformat() if fc.fetched_at else None,
            "source": fc.source,
            "weather_model": fc.weather_model,
            "wind_min_mph": WIND_MIN_MPH,
        },
        sort_keys=True,
    )


def _logged(session, arm: str) -> set:
    rows = session.query(ChallengerPick.game_id).filter(ChallengerPick.arm == arm).all()
    return {int(g) for (g,) in rows}


def _priced_first_half(it: Dict) -> bool:
    """A card item the first-half arm can log: Hard Rock's centred main line
    with an under price."""
    return bool(
        it.get("hr_centred") and it.get("hr_line") is not None and it.get("hr_price") is not None
    )


def _priced_full_game(session, season: int, week: int, now: datetime) -> List[tuple]:
    """(game, quote) for the week's games not yet kicked off whose newest Hard Rock
    full-game total is centred with a line and an under price: the full-game
    arm's universe (H-ARM-FGU's quote rule)."""
    games = (
        session.query(Game)
        .filter(Game.season == int(season), Game.week == int(week), Game.start_date > now)
        .all()
    )
    quotes = _hr_quotes(session, [int(g.id) for g in games], now)
    out = []
    for g in games:
        q = quotes.get(int(g.id))
        if q is None or q.line is None or q.under_price is None:
            continue
        if not is_centred_quote(q.over_price, q.under_price):
            continue
        out.append((g, q))
    return out


def arm_game_ids(session, card: Dict, season: int, week: int, now: datetime) -> List[int]:
    """The games either weather arm can log at this build -- the card's Hard Rock
    first-half items and the week's Hard Rock full-game totals -- and so the
    only games worth a forecast call. A forecast for any other game is one
    nothing reads, paid for out of the card's clock."""
    ids = {int(it["game_id"]) for it in card.get("items", []) if _priced_first_half(it)}
    ids.update(int(g.id) for g, _ in _priced_full_game(session, season, week, now))
    return sorted(ids)


def _in_window(kick: Optional[datetime], now: datetime, window_hours: Optional[float]) -> bool:
    if kick is None or kick <= now:
        return False
    return window_hours is None or kick - now <= timedelta(hours=window_hours)


def log_first_half(
    session,
    card: Dict,
    now: datetime,
    forecasts: Dict[int, BuildForecast],
    window_hours: Optional[float] = None,
) -> Dict[str, int]:
    """H-ARM-WX1H: a paper first-half UNDER at Hard Rock's centred main line and
    under price on every qualifying game in the build's window."""
    logged = _logged(session, ARM_WX_1H)
    added = windy = 0
    for it in card.get("items", []):
        gid = int(it["game_id"])
        if not _priced_first_half(it):
            continue
        fc = forecasts.get(gid)
        if not qualifies(fc):
            continue
        windy += 1
        if gid in logged or not _in_window(parse_kick(it.get("kick")), now, window_hours):
            continue
        add_challenger_pick(
            session,
            arm=ARM_WX_1H,
            game_id=gid,
            season=int(card["season"]),
            week=int(card["week"]),
            home_team=it["home"],
            away_team=it["away"],
            side="under",
            market="1H",
            line=float(it["hr_line"]),
            price=int(it["hr_price"]),
            book=HR_BOOK_KEY,
            slot=card.get("slot"),
            placed_at=now,
            factors_json_at_pick=frozen(fc),
        )
        logged.add(gid)
        added += 1
    return {"windy": windy, "added": added}


def log_full_game(
    session,
    season: int,
    week: int,
    now: datetime,
    forecasts: Dict[int, BuildForecast],
    window_hours: Optional[float] = None,
    slot: Optional[str] = None,
) -> Dict[str, int]:
    """H-ARM-WXFG: a paper full-game UNDER at Hard Rock's newest centred
    full-game total and under price on every qualifying game in the window."""
    logged = _logged(session, ARM_WX_FG)
    added = windy = 0
    for g, q in _priced_full_game(session, season, week, now):
        gid = int(g.id)
        fc = forecasts.get(gid)
        if not qualifies(fc):
            continue
        windy += 1
        if gid in logged or not _in_window(g.start_date, now, window_hours):
            continue
        add_challenger_pick(
            session,
            arm=ARM_WX_FG,
            game_id=gid,
            season=int(season),
            week=int(week),
            home_team=g.home_team,
            away_team=g.away_team,
            side="under",
            market="full",
            line=float(q.line),
            price=int(q.under_price),
            book=HR_BOOK_KEY,
            slot=slot,
            placed_at=now,
            factors_json_at_pick=frozen(fc),
        )
        logged.add(gid)
        added += 1
    return {"windy": windy, "added": added}


def summary_lines(stats: Optional[Dict[str, Any]]) -> List[str]:
    """The card summary's lines about the weather arms."""
    tag = f"  ARMS {ARM_WX_1H} / {ARM_WX_FG} (paper unders, forecast wind {WIND_MIN_MPH:g}+ mph)"
    if not stats:
        return [f"{tag}: not run"]
    c, h, f = stats.get("capture", {}), stats.get("1h", {}), stats.get("full", {})
    over = c.get("over_budget")
    cap = f", {over} past the {BUILD_CAPTURE_BUDGET_S:g} s cap" if over else ""
    return [
        f"{tag}: forecasts stored {c.get('stored', 0)} (domes {c.get('domes', 0)}, "
        f"failed {c.get('failed', 0)}{cap}); first half {h.get('windy', 0)} windy, "
        f"+{h.get('added', 0)} logged; full game {f.get('windy', 0)} windy, "
        f"+{f.get('added', 0)} logged"
    ]
