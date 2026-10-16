"""Publish the frozen analysis of every game one scheduled card rates (H-1H-SHORTLIST).

card.yml runs this after `build`, for the card the run just wrote:

    python scripts/publish_shortlist.py --season S --week W --slot SLOT --since RUN_STARTED_AT --write

and `shortlist_publish.yml` re-runs it by hand for a card that missed (recoverable):

    python scripts/publish_shortlist.py --card-id N --write

Rules (website plan PR D, adjustment 2):
- a `manual` card publishes nothing (it is a preview);
- a card publishes ONCE: if it already has rows this exits 0 with "already published" and writes
  nothing, so a duplicate run can never overwrite a frozen ranking (the unique key is the backstop);
- `--write` refuses a card built more than `--max-age-h` (24) hours ago, so a late recovery can
  never publish stale ranks as if on time; a dry run may read any card;
- `--as-of` (dry run only) replays a past publication time: snapshots captured later are dropped and
  `last_seen_at` is capped at it (a later re-confirmation cannot be undone, so the replay says how
  many games it touched).

Writes `reports/shortlist_<card>_<UTC>.json` (the publication) and prints each entry and its sha256.
Exits 0 unless something is broken; card.yml's step is continue-on-error and the health check
(`card.shortlist_published`) is what reports a missing publication.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from datetime import datetime
from pathlib import Path

from beatvegas import pricing as PR
from beatvegas import shortlist as S
from beatvegas.ci import SCHEDULED_SLOTS
from beatvegas.db.models import Card
from beatvegas.db.store import session_scope, try_init_db

ROOT = Path(__file__).resolve().parents[1]


def _find_card(s, args):
    if args.card_id is not None:
        row = s.get(Card, args.card_id)
        return None if row is None else S.card_dict(row)
    since = S.parse_ts(args.since)
    rows = (
        s.query(Card)
        .filter(Card.season == args.season, Card.week == args.week, Card.built_at >= since)
        .order_by(Card.built_at.desc(), Card.id.desc())
        .all()
    )
    for row in rows:
        c = S.card_dict(row)
        if c["slot"] == args.slot:
            return c
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--card-id", type=int)
    ap.add_argument("--season", type=int)
    ap.add_argument("--week", type=int)
    ap.add_argument("--slot")
    ap.add_argument("--since", help="RUN_STARTED_AT: the card this run built")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--max-age-h", type=float, default=24.0)
    ap.add_argument("--as-of", help="dry run only: replay this publication time (ISO, UTC)")
    args = ap.parse_args(argv)
    if args.card_id is None and None in (args.season, args.week, args.slot, args.since):
        ap.error("give --card-id, or --season --week --slot --since")
    if args.as_of and args.write:
        ap.error("--as-of is a dry-run replay; it never writes")

    now = S.parse_ts(args.as_of) if args.as_of else datetime.utcnow()
    # Only a write initialises the schema (it creates shortlist_entries the first time); a dry
    # run, e.g. study.yml, reads and changes nothing.
    if args.write and not try_init_db():
        return 1
    with session_scope() as s:
        card = _find_card(s, args)
        if card is None:
            print("no matching card: nothing to publish")
            return 0
        print(
            f"card {card['id']} {card['slot']} {card['season']} w{card['week']} built {card['built_at']}"
        )
        if card["slot"] not in SCHEDULED_SLOTS:
            print(f"slot {card['slot']!r} is not a scheduled slot: a preview publishes nothing")
            return 0
        if args.write:
            age_h = (now - S.parse_ts(card["built_at"])).total_seconds() / 3600
            if age_h > args.max_age_h:
                print(
                    f"refused: card built {age_h:.1f} h ago (> {args.max_age_h:g} h); a late run would publish stale ranks"
                )
                return 0
            if S.already_published(s, card["id"]):
                print(f"card {card['id']} already published: frozen, nothing written")
                return 0
        snaps, ctx, forecasts, previews = S.load_inputs(s, card, now)
        touched = 0
        if args.as_of:
            for gid, sn in list(snaps.items()):
                kept = []
                for x in sn:
                    if x.captured_at > now:
                        touched += 1
                        continue
                    if x.last_seen_at and x.last_seen_at > now:
                        touched += 1
                        x = dataclasses.replace(x, last_seen_at=now)
                    kept.append(x)
                snaps[gid] = kept
        pub = S.build_publication(
            card, snaps, ctx, S.load_reference(), forecasts, previews, PR.MassTable.load(), now
        )
        sha = S.publication_sha(pub)
        out = ROOT / "reports" / f"shortlist_{card['id']}_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(S.canonical(pub))
        print(f"pool {pub['pool']}; sha256 {sha}; wrote {out.relative_to(ROOT)}")
        if args.as_of:
            print(
                f"replay as of {args.as_of}: {touched} snapshot rows were captured or re-confirmed later"
            )
        for e in pub["entries"]:
            p = e["price"]
            ev = (
                "—"
                if p.get("ev_point") is None
                else f"{100 * p['ev_point']:+.1f}% [{100 * p['range_low']:+.1f},{100 * p['range_high']:+.1f}]"
            )
            print(
                f"{e['game_id']} {e['matchup']:40s} HR u{p['hr_line']} {p['hr_under'] if p['hr_under'] is not None else '—'}"
                f"  EV {ev}  {e['label']}  books {len(p.get('ref_books', []))}"
            )
        if not args.write:
            print("dry run: nothing written")
            return 0
        n = S.write_publication(s, pub)
        print(
            f"wrote {n} shortlist_entries rows for card {card['id']}"
            if n
            else "already published: nothing written"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
