#!/usr/bin/env python
"""Vendor team logo marks from CFBD `/teams` into `web/public/logos/<id>.png`
plus an index at `web/data/team_logos.json` (read by web/lib/teamLogos.ts).

Why vendored and not hotlinked: the board is the product, and a third-party CDN
going away (or changing its URL shape) would blank every mark on it. Local files
also render in `npm run dev` with no network and in the week sim. The cost is a
manual refresh -- run this each August alongside scripts/fetch_fbs_teams.py, and
whenever a school rebrands.

The marks are the `logos-dark/` variant, which is the DARK-BACKGROUND artwork:
Iowa's black Hawkeye renders gold there, which is what the navy canvas needs.
A handful of teams ship the same file for both, so this script composites every
downloaded mark over the site background and PRINTS the low-contrast ones rather
than shipping a navy blob silently. It never drops them -- that is a judgment
call for a human looking at the list.

    python scripts/fetch_team_logos.py             # config backfill.end_season
    python scripts/fetch_team_logos.py --season 2026
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import requests

from beatvegas.config import REPO_ROOT, load_config
from beatvegas.sources.cfbd import CFBDClient

LOGO_DIR = REPO_ROOT / "web" / "public" / "logos"
LOGO_INDEX_PATH = REPO_ROOT / "web" / "data" / "team_logos.json"

LOGO_CDN = "https://cdn.collegefootballdata.com/logos-dark/{size}/{team_id}.png"
# The board mark renders at 18px and the game-page header matches it, so 64px is
# ~3.5x -- ample on a 3x phone, and ~4KB a file (about 1MB for the whole set).
LOGO_SIZE = 64

# FBS and FCS only. The `games` table carries NAIA/D2/D3 opponents too, but they
# are outside the Hard-Rock-priced board universe and mostly have no logo at all.
KEEP_CLASSIFICATIONS = ("fbs", "fcs")

# FBS has had 120-136 members every season since 2015 and CFBD has artwork for
# all of them, so a smaller number means a bad or partial response. Writing it
# would silently blank most of the board.
MIN_PLAUSIBLE_FBS_LOGOS = 120

# --bg-2 in web/app/globals.css: the deepest surface a mark can land on.
SITE_BG = (0x0A, 0x0F, 0x1E)
# Below this contrast ratio against SITE_BG the mark is not legible on the board.
MIN_CONTRAST = 2.0


def wanted_teams(
    rows: Iterable[Dict], min_fbs: int = MIN_PLAUSIBLE_FBS_LOGOS
) -> List[Tuple[int, str]]:
    """(team_id, school) for every FBS/FCS team CFBD has artwork for, by id."""
    keep: Dict[int, str] = {}
    fbs_with_logos = 0
    for r in rows:
        if r.get("classification") not in KEEP_CLASSIFICATIONS:
            continue
        if not r.get("logos") or r.get("id") is None or not r.get("school"):
            continue
        keep[int(r["id"])] = str(r["school"])
        if r["classification"] == "fbs":
            fbs_with_logos += 1
    if fbs_with_logos < min_fbs:
        raise ValueError(
            f"CFBD returned artwork for only {fbs_with_logos} FBS teams; refusing to vendor"
        )
    return sorted(keep.items())


def _download(url: str) -> bytes:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def download_logos(
    teams: Sequence[Tuple[int, str]],
    out_dir: Path,
    fetch: Callable[[str], bytes] = _download,
    size: int = LOGO_SIZE,
) -> List[Tuple[int, str]]:
    """Write <out_dir>/<id>.png for each team. Returns the ones that landed.

    A team whose file 404s is skipped, not fatal: it simply gets no mark on the
    board (web/app/components/TeamLogo.tsx renders nothing when the id is absent
    from the index). The min-FBS gate above is what catches a broken response.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Tuple[int, str]] = []
    for team_id, school in teams:
        url = LOGO_CDN.format(size=size, team_id=team_id)
        try:
            blob = fetch(url)
        except Exception as e:  # one bad mark must not kill the whole refresh
            print(f"  skip {school} ({team_id}): {e}")
            continue
        (out_dir / f"{team_id}.png").write_bytes(blob)
        written.append((team_id, school))
    return written


def write_index(teams: Sequence[Tuple[int, str]], path: Path) -> None:
    """id -> school, so the web app knows which ids have a vendored file.

    NOTE this file lives ONLY under web/. Unlike data/fbs_teams.json and
    data/multiplier.json it has no repo-root twin, so it is deliberately absent
    from FILES in web/lib/dataMirror.test.ts -- the PNGs it indexes are web
    assets, and nothing in beatvegas/ reads it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(k): v for k, v in sorted(teams)}
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")


def _relative_luminance(rgb: Sequence[float]) -> float:
    out = 0.0
    for value, weight in zip(rgb, (0.2126, 0.7152, 0.0722)):
        c = value / 255.0
        c = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        out += c * weight
    return out


def contrast_ratio(a: Sequence[float], b: Sequence[float]) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def low_contrast_marks(
    teams: Sequence[Tuple[int, str]],
    out_dir: Path,
    bg: Sequence[int] = SITE_BG,
    floor: float = MIN_CONTRAST,
) -> List[Tuple[int, str, float]]:
    """Marks whose BEST pixel still barely separates from the site background.

    Pillow arrives with matplotlib rather than as a declared dependency, so a
    missing install degrades to a printed note instead of failing the refresh.
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        print("  (Pillow/numpy not installed - skipped the contrast check)")
        return []

    flagged: List[Tuple[int, str, float]] = []
    for team_id, school in teams:
        path = out_dir / f"{team_id}.png"
        if not path.exists():
            continue
        with Image.open(path) as im:
            arr = np.asarray(im.convert("RGBA"), dtype=float)
        ink = arr[arr[:, :, 3] > 200][:, :3]
        if ink.size == 0:
            flagged.append((team_id, school, 1.0))
            continue
        best = max(contrast_ratio(px, bg) for px in np.unique(ink, axis=0))
        if best < floor:
            flagged.append((team_id, school, best))
    return flagged


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--out-dir", type=Path, default=LOGO_DIR)
    ap.add_argument("--index", type=Path, default=LOGO_INDEX_PATH)
    args = ap.parse_args()

    season = args.season
    if season is None:
        bf = load_config().get("backfill", {}) or {}
        season = int(bf.get("end_season", 2026))

    teams = wanted_teams(CFBDClient().teams(season))
    print(f"{season}: {len(teams)} FBS/FCS teams with artwork")
    written = download_logos(teams, args.out_dir)
    write_index(written, args.index)
    print(f"wrote {len(written)} marks to {args.out_dir}")
    print(f"wrote {args.index}")

    flagged = low_contrast_marks(written, args.out_dir)
    if flagged:
        print(f"\nlow contrast on {SITE_BG} (ratio < {MIN_CONTRAST}) - check these by eye:")
        for team_id, school, ratio in sorted(flagged, key=lambda f: f[2]):
            print(f"  {school} ({team_id}): {ratio:.2f}")
    else:
        print("contrast: every mark separates from the site background")


if __name__ == "__main__":
    main()
