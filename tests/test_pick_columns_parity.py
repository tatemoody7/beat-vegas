"""The manual_picks ledger has ONE writer: beatvegas/picks.py::add_pick (the card
build). The site's writer, web/lib/picks.ts::createPick, left on 2026-10-18 with
the owner log path (final-2026 plan, decision D2): the site is a read-only
research record, and the 30 real tickets it wrote stay in the table untouched.

Until then this file pinned the two writers' column sets together (that is how
the web lane once went a season without writing `book` or `price_provenance`).
Now it refuses the second writer outright: no INSERT into manual_picks may
appear anywhere under web/app or web/lib, and the Python writer must still
exist. The Hard Rock book key the site reads is still mirrored from Python."""

from __future__ import annotations

import re
from pathlib import Path

from beatvegas import picks
from beatvegas.hardrock import HR_BOOK_KEY

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
BOOKS_TS = WEB / "lib" / "books.ts"
# The site's code, not its test fixture: web/e2e/fixture/seed.mjs seeds a
# synthetic ledger into the local sandbox and is the e2e lane's business.
SITE_FOLDERS = ("app", "lib", "middleware.ts")

_INSERT = re.compile(r"INSERT\s+INTO\s+manual_picks", re.I)


def _site_files():
    for rel in SITE_FOLDERS:
        p = WEB / rel
        if p.is_file():
            yield p
        elif p.is_dir():
            yield from (f for f in p.rglob("*") if f.suffix in (".ts", ".tsx", ".js", ".mjs"))


def test_the_site_never_inserts_a_manual_pick():
    offenders = [
        str(f.relative_to(ROOT))
        for f in _site_files()
        if _INSERT.search(f.read_text(errors="ignore"))
    ]
    assert offenders == [], f"the site writes manual_picks again: {offenders}"


def test_the_site_has_no_pick_write_route():
    """The routes and modules the log path was made of are gone, not disabled."""
    for rel in (
        "app/api/picks",
        "app/api/price-refresh",
        "app/api/bets",
        "app/api/login",
        "app/api/logout",
        "app/login",
        "lib/ticketPolicy.ts",
        "lib/pickRules.ts",
        "lib/priceRefresh.ts",
        "lib/auth.ts",
        "lib/session.ts",
    ):
        assert not (WEB / rel).exists(), f"web/{rel} is back"
    picks_ts = (WEB / "lib" / "picks.ts").read_text()
    for name in ("createPick", "updatePick", "deletePick", "getEditablePick"):
        assert f"function {name}" not in picks_ts, f"web/lib/picks.ts grew {name} back"


def test_the_python_writer_is_the_one_left():
    assert callable(getattr(picks, "add_pick", None)), (
        "beatvegas/picks.py::add_pick is the ledger's one writer"
    )


def test_web_hard_rock_key_matches_python():
    m = re.search(r'export\s+const\s+HR_BOOK_KEY\s*=\s*"([a-z_]+)"\s*;', BOOKS_TS.read_text())
    assert m, "web/lib/books.ts must export HR_BOOK_KEY"
    assert m.group(1) == HR_BOOK_KEY
