"""sunday.yml builds the historical feature frame twice per run -- once to
score, once inside post_derived_lines.py via historical_references() for the
board tint anchors -- a ~4.6 MB Neon read each. weekly_update.py can now write
the references it already has and post_derived_lines.py reads them back."""

from __future__ import annotations

from beatvegas.factors.board import load_references, save_references


def test_round_trip_keeps_tuples(tmp_path):
    refs = {"wx_wind": (7.0, 3.5), "combined_sec_play": (26.2, 2.1)}
    p = tmp_path / "sub" / "refs.json"  # parent created on the way
    save_references(refs, p)
    back = load_references(p)
    assert back == refs
    assert all(isinstance(v, tuple) for v in back.values())


def test_missing_empty_or_garbage_file_means_fall_back(tmp_path):
    assert load_references(tmp_path / "nope.json") is None
    (tmp_path / "empty.json").write_text("{}")
    assert load_references(tmp_path / "empty.json") is None
    (tmp_path / "bad.json").write_text("not json")
    assert load_references(tmp_path / "bad.json") is None
    (tmp_path / "shape.json").write_text('{"a": [1]}')  # wrong arity -> nothing usable
    assert load_references(tmp_path / "shape.json") is None
