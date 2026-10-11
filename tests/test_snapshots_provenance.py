"""The three stamps on odds_snapshots keep their meanings (capture design note,
2026-10-11): the feed's `last_update` is the PROVIDER's observation, parsed to
naive UTC or NULL; the first-capture stamp is never overwritten; a re-sighting
under a newer stamp lands in feed_reseen_at; rows from before the column have no
first stamp and never get one."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from beatvegas.snapshots_provenance import FEED_AHEAD_WARN, feed_stamp_for, note_reseen
from beatvegas.sources.odds import parse_feed_stamp


def test_parse_feed_stamp_is_naive_utc_or_none():
    assert parse_feed_stamp("2026-10-10T15:04:05Z") == datetime(2026, 10, 10, 15, 4, 5)
    assert parse_feed_stamp("2026-10-10T11:04:05-04:00") == datetime(2026, 10, 10, 15, 4, 5)
    assert parse_feed_stamp("2026-10-10T15:04:05+00:00") == datetime(2026, 10, 10, 15, 4, 5)
    assert parse_feed_stamp(datetime(2026, 10, 10, 15, 4, 5)) == datetime(2026, 10, 10, 15, 4, 5)
    assert parse_feed_stamp(None) is None
    assert parse_feed_stamp("") is None
    assert parse_feed_stamp("yesterday") is None


def test_feed_stamp_for_never_invents_and_warns_when_ahead(capsys):
    cap = datetime(2026, 10, 10, 15, 0)
    assert feed_stamp_for({"last_update": None, "book": "x"}, cap) is None
    assert feed_stamp_for({"last_update": "2026-10-10T14:50:00Z"}, cap) == datetime(
        2026, 10, 10, 14, 50
    )
    ahead = (cap + FEED_AHEAD_WARN + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert (
        feed_stamp_for({"last_update": ahead, "book": "hardrockbet", "event_id": "e"}, cap)
        is not None
    )
    assert "ahead of our capture" in capsys.readouterr().out


def test_note_reseen_preserves_the_first_stamp_and_tracks_newer_ones_apart():
    first = datetime(2026, 10, 10, 14, 50)
    row = SimpleNamespace(feed_updated_at=first, feed_reseen_at=None)
    note_reseen(row, None)  # a re-sighting without a stamp changes nothing
    assert (row.feed_updated_at, row.feed_reseen_at) == (first, None)
    note_reseen(row, first)  # the same stamp again: the price was not re-observed
    assert (row.feed_updated_at, row.feed_reseen_at) == (first, None)
    note_reseen(row, first - timedelta(minutes=5))  # an older stamp cannot move anything
    assert (row.feed_updated_at, row.feed_reseen_at) == (first, None)
    later = first + timedelta(hours=1)
    note_reseen(row, later)
    assert (row.feed_updated_at, row.feed_reseen_at) == (first, later)
    note_reseen(
        row, later - timedelta(minutes=30)
    )  # newest wins, an older re-sighting does not regress it
    assert row.feed_reseen_at == later
    note_reseen(row, later + timedelta(hours=1))
    assert (row.feed_updated_at, row.feed_reseen_at) == (first, later + timedelta(hours=1))


def test_note_reseen_leaves_legacy_rows_without_a_first_stamp():
    row = SimpleNamespace(feed_updated_at=None, feed_reseen_at=None)
    stamp = datetime(2026, 10, 10, 14, 50)
    note_reseen(row, stamp)
    assert row.feed_updated_at is None  # "at first capture" or nothing
    assert row.feed_reseen_at == stamp
