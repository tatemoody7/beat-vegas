#!/usr/bin/env python
"""Backfill free context data the feature frame now uses.

- Venue metadata (elevation, grass surface, capacity) from CFBD /venues into the
  `venues` table (the lat/lon rows already exist; this fills the new columns).
- Warms the talent + roster caches under data/cache/ so the next feature build
  is offline (build_feature_frame fetches them lazily and caches otherwise).

    python scripts/backfill_context.py                 # venues + cache warm
    python scripts/backfill_context.py --venues-only
"""
from __future__ import annotations

import argparse

from beatvegas.db.models import Venue
from beatvegas.db.store import init_db, session_scope
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.season_stats import roster_experience_frame, talent_frame


def _b(v):
    return None if v is None else bool(v)


def backfill_venues(client: CFBDClient) -> int:
    rows = client.venues()
    n = 0
    with session_scope() as s:
        for r in rows:
            vid = r.get("id")
            if vid is None:
                continue
            v = s.get(Venue, vid)
            if v is None:
                v = Venue(id=vid, name=r.get("name"))
                s.add(v)
            v.elevation = r.get("elevation")
            v.grass = _b(r.get("grass"))
            v.capacity = r.get("capacity")
            if v.latitude is None:
                v.latitude = r.get("latitude")
                v.longitude = r.get("longitude")
            if v.dome is None:
                v.dome = _b(r.get("dome"))
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venues-only", action="store_true")
    ap.add_argument("--seasons", default="2015-2025")
    args = ap.parse_args()
    init_db()
    client = CFBDClient()

    n = backfill_venues(client)
    print(f"venues updated: {n}")

    if not args.venues_only:
        a, b = (int(x) for x in args.seasons.split("-"))
        seasons = list(range(a, b + 1))
        tal = talent_frame(client, seasons)
        exp = roster_experience_frame(client, seasons)
        print(f"talent rows: {len(tal)} | roster-experience rows: {len(exp)} "
              f"(cached under data/cache/)")


if __name__ == "__main__":
    main()
