#!/usr/bin/env python
"""Read-only look at the persisted model fits (model_artifacts).

    python scripts/model_artifacts.py list --engine residual [--limit 10]

One line per refit, newest first: when it was fitted, the slate it scored,
how many rows it trained on, the last game date it saw, the feature hash and
the scikit-learn version. A moved n_rows / max_game_date / feature_hash between
two rows in the same week is a mid-season change to the training history.
"""

from __future__ import annotations

import argparse

from beatvegas.db.models import ModelArtifact
from beatvegas.db.store import session_scope, try_init_db


def _fmt(row: ModelArtifact) -> str:
    fitted = row.fitted_at.strftime("%Y-%m-%d %H:%M") if row.fitted_at else "?"
    week = f"wk{row.week}" if row.week is not None else "wk?"
    return (
        f"{fitted}  {row.season} {week}  n_rows={row.n_rows}  "
        f"max_game_date={row.max_game_date}  feature_hash={row.feature_hash}  "
        f"sklearn={row.sklearn_version}"
    )


def list_artifacts(engine: str, limit: int) -> None:
    with session_scope() as s:
        rows = (
            s.query(ModelArtifact)
            .filter(ModelArtifact.engine == engine)
            .order_by(ModelArtifact.fitted_at.desc(), ModelArtifact.id.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            print(f"no artifacts for engine {engine!r}")
            return
        print(f"{len(rows)} newest artifact(s) for engine {engine!r}:")
        for row in rows:
            print("  " + _fmt(row))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="the last N persisted fits for an engine")
    ls.add_argument("--engine", default="residual")
    ls.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    if not try_init_db():
        return
    if args.cmd == "list":
        list_artifacts(args.engine, args.limit)


if __name__ == "__main__":
    main()
