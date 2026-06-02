#!/usr/bin/env python
"""One-time copy of the local SQLite DB → a Postgres DB (e.g. Neon).

    DATABASE_URL='postgresql://user:pass@host/db' python scripts/migrate_to_postgres.py

Reads from the local SQLite file (default data/beatvegas.db) and inserts every
row into the target Postgres DB, preserving types via the ORM. Creates the schema
first. Tables are loaded in FK-dependency order. Re-runnable: pass --wipe to clear
the target tables before loading.
"""
from __future__ import annotations

import argparse
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from beatvegas.config import REPO_ROOT, database_url
from beatvegas.db.models import (Base, Game, ManualPick, ModelRun, OddsSnapshot,
                                 Prediction, Result, Team, TeamTempo,
                                 TeamWeekFeature, Venue, Weather)

# FK-dependency order: parents before children.
ORDER = [Team, Venue, Game, Weather, OddsSnapshot, Prediction, Result,
         ManualPick, TeamTempo, TeamWeekFeature, ModelRun]


def _rows(session, model):
    for obj in session.query(model).all():
        yield {c.name: getattr(obj, c.name) for c in model.__table__.columns}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", default=str(REPO_ROOT / "data" / "beatvegas.db"))
    ap.add_argument("--wipe", action="store_true",
                    help="delete target rows before loading")
    args = ap.parse_args()

    target = database_url()
    if target.startswith("sqlite"):
        raise SystemExit("Set DATABASE_URL to your Postgres URL before migrating.")

    src = create_engine(f"sqlite:///{args.sqlite}", future=True)
    dst = create_engine(target, future=True, pool_pre_ping=True)
    Base.metadata.create_all(dst)
    SrcS, DstS = sessionmaker(bind=src), sessionmaker(bind=dst)

    with SrcS() as ss, DstS() as ds:
        if args.wipe:
            for model in reversed(ORDER):
                ds.query(model).delete()
            ds.commit()
        for model in ORDER:
            rows = list(_rows(ss, model))
            ds.bulk_insert_mappings(model, rows)
            ds.commit()
            print(f"  {model.__tablename__}: {len(rows)} rows")
    print("migration complete")


if __name__ == "__main__":
    main()
