"""College-football injury report from Rotowire's public table endpoint.

DISPLAY CONTEXT ONLY — never a model feature (no historical injury data exists to
train on). UNOFFICIAL: an undocumented JSON endpoint behind Rotowire's college
injury-report page; it can change without notice, so every call fails silent
(returns empty) and callers must say so out loud. Chosen 2026-09-02 after ESPN's
college injury feeds proved dead: `site.api.espn.com` is Akamai-blocked from every
network we run on and `sports.core.api.espn.com` returns 0 injuries for every FBS
team (it works for the NFL). Rotowire aggregates the conference availability
reports (SEC / ACC / Big Ten) plus beat reporting, and its table is current.

One call returns the whole current report (~7 rows on a Tuesday, more by Friday):
    {"player","team","RotoSchoolName","IR","position","injury_type","ReturnDate",
     "game_datetime",...}   with IR in {"Out","Doubtful","Questionable","Probable",...}
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import requests

from ..etl.match import name_score

_URL = "https://www.rotowire.com/cfootball/tables/injury-report.php"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.rotowire.com/cfootball/injury-report.php?league=college",
}

# Statuses that mean the player is not expected to play.
OUT_STATUSES = ("out", "doubtful", "suspended", "injured reserve", "season")


def fetch_injury_report(timeout: int = 15) -> List[dict]:
    """Raw report rows, or [] on any failure (unofficial source — never raise)."""
    try:
        r = requests.get(_URL, params={"league": "college"}, headers=_HEADERS, timeout=timeout)
        if r.status_code != 200:
            return []
        data = r.json()
        return data if isinstance(data, list) else []
    except (requests.RequestException, ValueError):
        return []


def format_entry(row: dict) -> str:
    """'QB Name — Out (Knee)' — the same shape the preview page and QB-out
    heuristic have always consumed."""
    pos = (row.get("position") or "").strip()
    name = (row.get("player") or "").strip() or "Player"
    status = (row.get("IR") or "").strip()
    inj = (row.get("injury_type") or "").strip()
    label = f"{pos + ' ' if pos else ''}{name}"
    tail = status + (f" ({inj})" if inj and inj.lower() != "undisclosed" else "")
    return f"{label} — {tail}" if tail else label


def by_school(
    rows: Iterable[dict], schools: List[str], min_score: float = 0.8
) -> Dict[str, List[dict]]:
    """Group report rows by OUR school name (CFBD `Team.school`), fuzzy-matching
    Rotowire's team label. Unmatched rows are dropped (a wrong team is worse than
    a missing one on a real-money screen)."""
    out: Dict[str, List[dict]] = {}
    cache: Dict[str, Optional[str]] = {}
    for row in rows:
        label = (row.get("RotoSchoolName") or row.get("team") or "").strip()
        if not label:
            continue
        if label not in cache:
            best, best_s = None, 0.0
            for s in schools:
                # Rotowire label FIRST on purpose: name_score's "leading chars"
                # rule would otherwise score "Michigan" a perfect match against
                # "Michigan St." (school is a prefix of the label).
                sc = name_score(label, s)
                if sc > best_s:
                    best, best_s = s, sc
            cache[label] = best if best_s >= min_score else None
        school = cache[label]
        if school:
            out.setdefault(school, []).append(row)
    return out


def qb_out_detail(rows: Iterable[dict]) -> Optional[str]:
    """Formatted entry for a QB listed Out/Doubtful/Suspended, else None."""
    for row in rows:
        if (row.get("position") or "").strip().upper() != "QB":
            continue
        if any(st in (row.get("IR") or "").lower() for st in OUT_STATUSES):
            return format_entry(row)
    return None
