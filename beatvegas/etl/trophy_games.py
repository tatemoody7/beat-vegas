"""Named trophy games: the frozen list behind the `rivalry_game` model input.

Tate's call (2026-10-09, strategic review topic 3): a rivalry is a pair of teams
that plays for a named trophy, read from Wikipedia's "List of NCAA college
football rivalry games" at one pinned revision and frozen into
`data/trophy_games.json` by `scripts/build_trophy_games.py`. The list is a
structural fact about the pair, so a game's flag never depends on meetings
after it -- the leak the old "met in 8+ distinct seasons across the dataset"
flag had. The same frozen list serves the Cox literature look.

A row counts only when its Trophy cell is filled. Multi-team trophies (the
Commander-in-Chief's Trophy, the Florida Cup) count every pair among their
current teams; a "(previously X)" team is dropped.
"""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

DATA = Path(__file__).resolve().parents[2] / "data" / "trophy_games.json"

# Wikipedia display name -> CFBD school, where the two differ.
WIKI_TO_CFBD = {
    "Miami (FL)": "Miami",
    "Miami (OH)": "Miami (OH)",
    "Hawaii": "Hawai'i",
    "San Jose State": "San José State",
    "Southern Miss": "Southern Miss",
    "UL Monroe": "UL Monroe",
    "Louisiana–Monroe": "UL Monroe",
    "Louisiana-Monroe": "UL Monroe",
    "UConn": "UConn",
    "Connecticut": "UConn",
    "UMass": "Massachusetts",
    "FIU": "Florida International",
    "Pitt": "Pittsburgh",
    "USF": "South Florida",
    "UCF": "UCF",
    "BYU": "BYU",
    "SMU": "SMU",
    "TCU": "TCU",
    "UTEP": "UTEP",
    "UTSA": "UTSA",
    "UNLV": "UNLV",
    "LSU": "LSU",
    "Ole Miss": "Ole Miss",
    "NC State": "NC State",
    "App State": "App State",
    "Appalachian State": "App State",
    "Sam Houston": "Sam Houston",
    "Sam Houston State": "Sam Houston",
}

_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_TEMPLATE = re.compile(r"\{\{Trophy game\|(.*?)\}\}", re.S)


def _cell_text(cell: str) -> str:
    """Display text of a wikitext cell: link labels kept, markup dropped."""
    text = _LINK.sub(lambda m: m.group(2) or m.group(1), cell)
    text = re.sub(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"\{\{[^}]*\}\}|'''?|<[^>]+>", "", text)
    return text.strip()


def _teams_in(cell: str) -> List[str]:
    """The team display names linked in a cell, minus any "(previously X)" team."""
    cell = re.sub(r"\(previously[^)]*\)", "", cell)
    return [(m.group(2) or m.group(1)).strip() for m in _LINK.finditer(cell)]


def parse_wikitext(wikitext: str) -> List[Dict[str, object]]:
    """Every trophy row in the FBS sections: {"trophy", "teams"}.

    Reads the FBS section (its two-team templates and its multi-team table) and
    the FBS-vs-FCS section; the FCS-only section and everything from the
    Division II heading on are dropped, as are HTML comments (the page's own
    template example sits in one). Rows with an empty Trophy cell are skipped."""
    wikitext = re.sub(r"<!--.*?-->", "", wikitext, flags=re.S)
    end = wikitext.find("==NCAA Division II==")
    body = wikitext if end < 0 else wikitext[:end]
    fcs = body.find("==NCAA Division I Football Championship Subdivision==")
    mixed = body.find("==Rivalries involving FBS and FCS teams==")
    if 0 <= fcs < mixed:  # drop the FCS-only section, keep FBS-vs-FCS
        body = body[:fcs] + body[mixed:]
    rows: List[Dict[str, object]] = []

    # multi-team tables: !Series !Trophy !Teams !First meeting
    for table in re.findall(r"\{\|.*?\n\|\}", body, flags=re.S):
        header = [h.strip() for h in re.findall(r"^!(.*)$", table, flags=re.M)]
        if "Trophy" not in header or "Teams" not in header:
            continue
        ti, mi = header.index("Trophy"), header.index("Teams")
        for block in table.split("\n|-")[1:]:
            cells = [c[1:] for c in block.strip().split("\n") if c.startswith("|") and c != "|}"]
            if len(cells) > max(ti, mi) and _cell_text(cells[ti]):
                teams = _teams_in(cells[mi])
                if len(teams) >= 2:
                    rows.append({"trophy": _cell_text(cells[ti]), "teams": teams})

    for m in _TEMPLATE.finditer(body):
        parts = _split_template(m.group(1))
        if len(parts) < 4 or not _cell_text(parts[1]):
            continue
        teams = [_cell_text(parts[2]), _cell_text(parts[3])]
        if all(teams):
            rows.append({"trophy": _cell_text(parts[1]), "teams": teams})
    return rows


def _split_template(inner: str) -> List[str]:
    """Split a template's arguments on top-level pipes (not inside [[...]])."""
    parts, depth, cur = [], 0, []
    i = 0
    while i < len(inner):
        two = inner[i : i + 2]
        if two in ("[[", "{{"):
            depth += 1
            cur.append(two)
            i += 2
            continue
        if two in ("]]", "}}"):
            depth -= 1
            cur.append(two)
            i += 2
            continue
        if inner[i] == "|" and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(inner[i])
        i += 1
    parts.append("".join(cur))
    return parts


def to_cfbd(name: str, schools: Iterable[str]) -> Optional[str]:
    """CFBD school for a Wikipedia display name, or None."""
    known = set(schools)
    cand = WIKI_TO_CFBD.get(name, name)
    return cand if cand in known else None


def pairs_from_rows(
    rows: Iterable[Dict[str, object]], schools: Iterable[str]
) -> Tuple[List[Dict[str, object]], List[str]]:
    """(the CFBD-named trophy pairs, the display names that did not map)."""
    known = set(schools)
    out: Dict[FrozenSet[str], Dict[str, object]] = {}
    unmapped: Set[str] = set()
    for r in rows:
        mapped = []
        for t in r["teams"]:  # type: ignore[union-attr]
            c = to_cfbd(str(t), known)
            if c is None:
                unmapped.add(str(t))
            else:
                mapped.append(c)
        for a, b in itertools.combinations(sorted(set(mapped)), 2):
            out.setdefault(frozenset((a, b)), {"teams": [a, b], "trophy": r["trophy"]})
    return sorted(out.values(), key=lambda p: p["teams"]), sorted(unmapped)


def load_pairs(path: Path = DATA) -> Set[FrozenSet[str]]:
    """The frozen trophy pairs, as order-free team pairs."""
    data = json.loads(path.read_text())
    return {frozenset(p["teams"]) for p in data["pairs"]}
