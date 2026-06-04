#!/usr/bin/env python
"""ADDITIVE push of games + Game.spread to Neon (never wipes live data).

Two operations only:
  1. UPDATE spread on games already on Neon (the new spread-adjusted-multiplier
     input; the column is added by init_db's migration first).
  2. INSERT games present locally but missing on Neon (e.g. the 2026 schedule),
     so the Sunday DK poll can match events and populate openers on Neon.

Existing Neon rows' scores/totals are left untouched. Chunked inserts (one big
statement stalls the Neon pooler — see CLAUDE.md).

    DATABASE_URL='postgresql://...' python scripts/deploy_neon_games.py
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from beatvegas.config import REPO_ROOT, database_url
from beatvegas.db.models import Game
from beatvegas.db.store import try_init_db


def _chunked_insert(ds, model, rows, chunk=500):
    for i in range(0, len(rows), chunk):
        ds.bulk_insert_mappings(model, rows[i : i + chunk])
        ds.commit()


def main() -> None:
    target = database_url()
    if target.startswith("sqlite"):
        raise SystemExit("Set DATABASE_URL to the Neon Postgres URL first.")
    if not try_init_db():  # adds games.spread / odds_snapshots.spread on Neon
        raise SystemExit(
            "Neon unreachable from this network — run from a network "
            "that can reach Neon (or via GitHub Actions)."
        )

    src = create_engine(f"sqlite:///{REPO_ROOT / 'data' / 'beatvegas.db'}", future=True)
    dst = create_engine(target, future=True, pool_pre_ping=True)
    SrcS, DstS = sessionmaker(bind=src), sessionmaker(bind=dst)
    cols = [c.name for c in Game.__table__.columns]

    with SrcS() as ss, DstS() as ds:
        existing = {gid for (gid,) in ds.query(Game.id).all()}
        local = ss.query(Game).all()

        # 1) UPDATE spread in place for games already on Neon.
        sp = [
            {"id": g.id, "sp": g.spread} for g in local if g.id in existing and g.spread is not None
        ]
        if sp:
            ds.execute(text("UPDATE games SET spread=:sp WHERE id=:id"), sp)
            ds.commit()
        print(f"spread updated on {len(sp)} existing Neon games")

        # 2) INSERT games missing on Neon (new schedule), full row.
        new = [{c: getattr(g, c) for c in cols} for g in local if g.id not in existing]
        _chunked_insert(ds, Game, new)
        print(f"inserted {len(new)} new games (e.g. 2026 schedule)")

    print("games + spread push complete (additive).")


if __name__ == "__main__":
    main()
