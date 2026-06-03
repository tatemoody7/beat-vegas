#!/usr/bin/env python
"""Targeted, ADDITIVE deploy of the new engine's data to Neon.

Pushes only what changed, never wiping live data (manual_picks, odds_snapshots,
results stay untouched):
  - schema: create fh_team_game + factor_scores, add venue elevation/grass/capacity
  - fh_team_game: replace (Neon has none) from local SQLite
  - venues: UPDATE the new metadata columns in place
  - weather: replace with the fuller local set (enrichment, re-derivable)

After this, re-score on Neon (weekly_update / score_slate) produces gap-ranked
predictions natively, matching local. Run with DATABASE_URL set to Neon.

    DATABASE_URL='postgresql://...' python scripts/deploy_neon.py
"""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from beatvegas.config import REPO_ROOT, database_url
from beatvegas.db.models import FhTeamGame, Venue, Weather
from beatvegas.db.store import try_init_db


def _maps(session, model, drop_id=True):
    for o in session.query(model).all():
        yield {c.name: getattr(o, c.name) for c in model.__table__.columns
               if not (drop_id and c.name == "id")}


def _resync(ds, table):
    ds.execute(text(
        f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
        f"COALESCE((SELECT MAX(id) FROM {table}), 1))"))


def _chunked_insert(ds, model, rows, chunk=500):
    """Insert in batches — one giant statement stalls the Neon pooler."""
    for i in range(0, len(rows), chunk):
        ds.bulk_insert_mappings(model, rows[i:i + chunk])
        ds.commit()


def main() -> None:
    target = database_url()
    if target.startswith("sqlite"):
        raise SystemExit("Set DATABASE_URL to the Neon Postgres URL first.")
    if not try_init_db():          # create new tables + venue column migration
        raise SystemExit("Neon unreachable from this network — run from a network "
                         "that can reach Neon (or via GitHub Actions).")

    src = create_engine(f"sqlite:///{REPO_ROOT / 'data' / 'beatvegas.db'}", future=True)
    dst = create_engine(target, future=True, pool_pre_ping=True)
    SrcS, DstS = sessionmaker(bind=src), sessionmaker(bind=dst)

    with SrcS() as ss, DstS() as ds:
        # fh_team_game (Neon empty) — replace from local.
        ds.query(FhTeamGame).delete(); ds.commit()
        rows = list(_maps(ss, FhTeamGame))
        _chunked_insert(ds, FhTeamGame, rows)
        _resync(ds, "fh_team_game"); ds.commit()
        print(f"fh_team_game: {len(rows)} rows")

        # venues — update the new metadata columns in place (preserve rows/coords).
        vparams = [{"e": v.elevation, "g": v.grass, "c": v.capacity, "id": v.id}
                   for v in ss.query(Venue).all()]
        ds.execute(text("UPDATE venues SET elevation=:e, grass=:g, capacity=:c "
                        "WHERE id=:id"), vparams)   # executemany
        ds.commit(); print(f"venues updated: {len(vparams)}")

        # weather — replace with the fuller local set (enrichment; PK = game_id).
        ds.query(Weather).delete(); ds.commit()
        wrows = list(_maps(ss, Weather, drop_id=False))
        _chunked_insert(ds, Weather, wrows)
        print(f"weather: {len(wrows)} rows")

    print("deploy data push complete — now re-score on Neon to refresh predictions")


if __name__ == "__main__":
    main()
