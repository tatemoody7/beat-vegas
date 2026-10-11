#!/usr/bin/env python
"""Freeze the named trophy games into data/trophy_games.json (run once, by hand).

Tate's call (2026-10-09): the model's `rivalry_game` input is "the pair plays for
a named trophy", read from Wikipedia's "List of NCAA college football rivalry
games" at ONE pinned revision so the list never moves under a backtest. The
parse and the name mapping live in `beatvegas/etl/trophy_games.py`; CFBD names
come from `data/fbs_teams.json` (every season). Names that do not map (FCS and
lower schools) are listed in the file, never guessed.

    PYTHONPATH=. python scripts/build_trophy_games.py            # the pinned revision
    PYTHONPATH=. python scripts/build_trophy_games.py --check    # parse + report, no write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from beatvegas.etl import trophy_games as T  # noqa: E402

REVID = 1379225783  # read 2026-10-09
FROZEN = "2026-10-09"
API = "https://en.wikipedia.org/w/api.php"
UA = "BeatVegasResearch/1.0 (research use; one fetch per freeze)"


def fetch(revid: int) -> str:
    r = requests.get(
        API,
        params={
            "action": "parse",
            "oldid": revid,
            "prop": "wikitext",
            "format": "json",
            "formatversion": 2,
        },
        headers={"User-Agent": UA},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["parse"]["wikitext"]


def fbs_schools() -> set:
    seasons = json.loads((T.DATA.parent / "fbs_teams.json").read_text())
    return {x if isinstance(x, str) else x.get("school") for ts in seasons.values() for x in ts}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--revid", type=int, default=REVID)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    rows = T.parse_wikitext(fetch(args.revid))
    pairs, unmapped = T.pairs_from_rows(rows, fbs_schools())
    print(f"revision {args.revid}: {len(rows)} trophy rows -> {len(pairs)} FBS pairs")
    print(f"unmapped (not FBS in any season on file): {', '.join(unmapped) or 'none'}")
    if args.check:
        return 0
    out = {
        "source": "Wikipedia, List of NCAA college football rivalry games",
        "revid": args.revid,
        "frozen": FROZEN,
        "decided_by": "Tate, 2026-10-09 (strategic review topic 3)",
        "rule": "a row counts when its Trophy cell is filled; multi-team trophies count "
        "every pair of their current teams",
        "unmapped": unmapped,
        "pairs": pairs,
    }
    T.DATA.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {T.DATA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
