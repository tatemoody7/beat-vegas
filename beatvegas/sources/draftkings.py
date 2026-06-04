"""Free, high-frequency capture of DraftKings NCAAF lines via their undocumented
JSON API.

WHY: The Odds API free tier (500 credits/mo) is too thin to poll often enough to
catch genuine openers, and it doesn't carry the originator (Circa). DraftKings'
hidden "sportscontent" endpoint costs no credits and updates near-instantly, so
the *first observed* line is a real opener. Full-game totals + spreads open Sunday
(1H totals post later); we capture the full-game opener and derive a 1H number.

UNOFFICIAL — like ESPN/TeamRankings (see CLAUDE.md "Gotchas"): the endpoint, the
operator key (`dkusoh`), and the league id drift, and DK actively blocks requests
without browser-like headers (HTTP 403). Every call therefore FAILS SILENT
(returns []/{}), so a block degrades the pipeline gracefully to the Odds-API path
rather than crashing it.

Schema (leagues/{id}): {events:[{id,name,startEventDate,participants:[{name,
venueRole}]}], markets:[{id,eventId,name,main}], selections:[{marketId,label,
points,outcomeType,displayOdds:{american}}]}.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

# DraftKings NCAAF league. The host, operator key (dkusoh) and league id (87637)
# drift; if capture goes empty mid-season, re-discover from the live sportsbook
# (DevTools → the leagues/{id} XHR) and update here.
_HOST = "https://sportsbook-nash.draftkings.com"
_PATH = "/sites/US-SB/api/sportscontent/dkusoh/v1/leagues/87637"
# DK returns 403 to non-browser clients; these headers get a 200.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://sportsbook.draftkings.com/",
    "Origin": "https://sportsbook.draftkings.com",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

_HALF_QTR = ("half", "quarter", "1q", "2q", "3q", "4q", "1st half", "2nd half")


class DraftKingsClient:
    def __init__(self, path: str = _PATH, timeout: int = 20):
        self.url = f"{_HOST}{path}"
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def fetch_ncaaf(self) -> Dict[str, Any]:
        """Raw league JSON, or {} on any error/empty (offseason, 403 block)."""
        try:
            r = self._session.get(self.url, timeout=self.timeout)
            if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                return r.json() or {}
        except (requests.RequestException, ValueError):
            pass
        return {}


def _amer(raw: Any) -> Optional[int]:
    """DK american odds ('−110' with unicode minus, '+120') -> int, or None."""
    if raw is None:
        return None
    try:
        return int(str(raw).replace("−", "-").replace("+", "").strip())
    except (ValueError, TypeError):
        return None


def _num(raw: Any) -> Optional[float]:
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _events_map(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """eventId -> {home, away, commence_time} from participant venueRole."""
    out: Dict[str, Dict[str, Any]] = {}
    for ev in (payload or {}).get("events", []) or []:
        eid = ev.get("id")
        if eid is None:
            continue
        home = away = None
        for p in ev.get("participants", []) or []:
            role = (p.get("venueRole") or "").lower()
            if role == "home":
                home = p.get("name")
            elif role == "away":
                away = p.get("name")
        out[str(eid)] = {
            "home_team": home,
            "away_team": away,
            "commence_time": ev.get("startEventDate") or ev.get("startDate"),
        }
    return out


def _market_name(m: Dict[str, Any]) -> str:
    return (m.get("name") or (m.get("marketType") or {}).get("name") or "").lower()


def _pick_markets(payload: Dict[str, Any], keyword: str) -> Dict[str, str]:
    """eventId -> marketId for full-game markets whose name matches `keyword`,
    preferring the `main` market and excluding half/quarter derivatives."""
    out: Dict[str, str] = {}
    main_seen: set = set()
    for m in (payload or {}).get("markets", []) or []:
        name = _market_name(m)
        eid = m.get("eventId")
        if eid is None or keyword not in name:
            continue
        if any(h in name for h in _HALF_QTR):
            continue
        eid = str(eid)
        if m.get("main"):
            out[eid] = m["id"]
            main_seen.add(eid)
        elif eid not in main_seen:
            out.setdefault(eid, m["id"])
    return out


def _selections_by_market(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for sel in (payload or {}).get("selections", []) or []:
        mid = sel.get("marketId")
        if mid is not None:
            out.setdefault(str(mid), []).append(sel)
    return out


def _total_from_selections(sels: List[Dict[str, Any]]):
    """(line, over_price, under_price) from a Total market's selections."""
    line = over_p = under_p = None
    for s in sels:
        ot = (s.get("outcomeType") or s.get("label") or "").lower()
        odds = (s.get("displayOdds") or {}).get("american")
        if ot.startswith("o"):
            over_p, line = _amer(odds), _num(s.get("points"))
        elif ot.startswith("u"):
            under_p, ln = _amer(odds), _num(s.get("points"))
            line = line if line is not None else ln
    return line, over_p, under_p


def _home_spread_from_selections(sels: List[Dict[str, Any]]) -> Optional[float]:
    """Home-relative signed spread (negative = home favored). Only |spread| is
    used downstream, so a mislabeled side just flips the sign."""
    home = away = None
    for s in sels:
        pts = _num(s.get("points"))
        ot = (s.get("outcomeType") or "").lower()
        if pts is None:
            continue
        if ot == "home":
            home = pts
        elif ot == "away":
            away = pts
    if home is not None:
        return home
    if away is not None:
        return -away
    return None


def normalize_full_game(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten DK league JSON into one full-game row per event: total + spread.

    Row: event_id, commence_time, home_team, away_team, book, line (total),
    spread (home-relative), over_price, under_price, last_update."""
    events = _events_map(payload)
    sbm = _selections_by_market(payload)
    total_mkt = _pick_markets(payload, "total")
    spread_mkt = _pick_markets(payload, "spread")
    rows: List[Dict[str, Any]] = []
    for eid, mid in total_mkt.items():
        if eid not in events:
            continue
        line, ov, un = _total_from_selections(sbm.get(mid, []))
        if line is None:
            continue
        spread = None
        smid = spread_mkt.get(eid)
        if smid is not None:
            spread = _home_spread_from_selections(sbm.get(smid, []))
        ev = events[eid]
        rows.append(
            {
                "event_id": eid,
                "commence_time": ev.get("commence_time"),
                "home_team": ev.get("home_team"),
                "away_team": ev.get("away_team"),
                "book": "draftkings",
                "line": float(line),
                "spread": spread,
                "over_price": ov,
                "under_price": un,
                "last_update": None,
            }
        )
    return rows


def normalize_first_half(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """1H-total rows in the SAME shape as sources.odds.normalize_first_half.

    The default league payload carries only main (full-game) markets, so this is
    usually empty; DK exposes 1H totals via a subcategory query closer to kickoff.
    Kept so 1H lines drop into the existing path the moment they appear."""
    events = _events_map(payload)
    sbm = _selections_by_market(payload)
    rows: List[Dict[str, Any]] = []
    for m in (payload or {}).get("markets", []) or []:
        name = _market_name(m)
        eid = m.get("eventId")
        if eid is None or "total" not in name:
            continue
        if not ("1st half" in name or "first half" in name):
            continue
        eid = str(eid)
        if eid not in events:
            continue
        line, ov, un = _total_from_selections(sbm.get(str(m.get("id")), []))
        if line is None:
            continue
        ev = events[eid]
        rows.append(
            {
                "event_id": eid,
                "commence_time": ev.get("commence_time"),
                "home_team": ev.get("home_team"),
                "away_team": ev.get("away_team"),
                "book": "draftkings",
                "line": float(line),
                "over_price": ov,
                "under_price": un,
                "last_update": None,
            }
        )
    return rows
