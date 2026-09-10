"""scripts/fetch_team_logos.py: CFBD /teams rows -> web/public/logos + the index."""

import json

import pytest


def _row(team_id, school, classification="fbs", logos=True):
    return {
        "id": team_id,
        "school": school,
        "classification": classification,
        "logos": ["https://cdn.example/x.png"] if logos else None,
    }


def _fbs_filler(n, start=900):
    return [_row(start + i, f"Filler {i}") for i in range(n)]


def test_wanted_teams_keeps_fbs_and_fcs_with_artwork(load_script):
    mod = load_script("fetch_team_logos")
    rows = [
        _row(333, "Alabama"),
        _row(2306, "Kansas State"),
        _row(2000, "Some FCS", classification="fcs"),
        _row(2500, "A D2 School", classification="ii"),
        _row(2600, "A D3 School", classification="iii"),
        _row(349, "No Artwork", logos=False),
    ]
    out = mod.wanted_teams(rows, min_fbs=1)
    assert out == [(333, "Alabama"), (2000, "Some FCS"), (2306, "Kansas State")]


def test_wanted_teams_refuses_an_implausibly_thin_response(load_script):
    mod = load_script("fetch_team_logos")
    with pytest.raises(ValueError, match="only 2 FBS"):
        mod.wanted_teams([_row(333, "Alabama"), _row(61, "Georgia")])


def test_wanted_teams_accepts_a_full_slate(load_script):
    mod = load_script("fetch_team_logos")
    assert len(mod.wanted_teams(_fbs_filler(mod.MIN_PLAUSIBLE_FBS_LOGOS))) == (
        mod.MIN_PLAUSIBLE_FBS_LOGOS
    )


def test_download_logos_writes_a_file_per_team_and_skips_failures(load_script, tmp_path):
    mod = load_script("fetch_team_logos")
    asked = []

    def fetch(url):
        asked.append(url)
        if "61" in url:
            raise RuntimeError("404")
        return b"PNGBYTES"

    written = mod.download_logos([(333, "Alabama"), (61, "Georgia")], tmp_path, fetch=fetch)

    assert written == [(333, "Alabama")]
    assert (tmp_path / "333.png").read_bytes() == b"PNGBYTES"
    assert not (tmp_path / "61.png").exists()
    # The dark-background variant is the one the navy canvas needs.
    assert all("logos-dark/64/" in u for u in asked)


def test_write_index_maps_id_to_school(load_script, tmp_path):
    mod = load_script("fetch_team_logos")
    p = tmp_path / "team_logos.json"
    mod.write_index([(2306, "Kansas State"), (333, "Alabama")], p)
    assert json.loads(p.read_text()) == {"333": "Alabama", "2306": "Kansas State"}
    assert p.read_text().endswith("\n")


def test_low_contrast_flags_a_mark_that_vanishes_into_the_background(load_script, tmp_path):
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    mod = load_script("fetch_team_logos")

    def _write(team_id, rgb):
        px = np.zeros((8, 8, 4), dtype=np.uint8)
        px[:, :, :3] = rgb
        px[:, :, 3] = 255
        Image.fromarray(px).save(tmp_path / f"{team_id}.png")

    _write(1, mod.SITE_BG)  # a navy blob on a navy card
    _write(2, (255, 255, 255))  # a white mark

    flagged = mod.low_contrast_marks([(1, "Invisible"), (2, "Legible")], tmp_path)
    assert [f[:2] for f in flagged] == [(1, "Invisible")]
