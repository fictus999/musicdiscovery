import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "apps" / "api"))

from jobs.musicbrainz_ingest.transform import (  # noqa: E402
    RawArtist,
    RawRecording,
    build_artist_row,
    build_recording_row,
)


def test_build_artist_row_normalizes_name():
    row = build_artist_row(RawArtist(mbid="abc-123", name="Sigur Rós"))
    assert row["mbid"] == "abc-123"
    assert row["normalized_name"] == "sigur ros"


def test_build_recording_row_carries_isrcs_as_external_ids():
    raw = RawRecording(
        mbid="rec-mbid-1",
        title="Nights",
        length_ms=307000,
        artist_mbids=["artist-mbid-1"],
        isrcs=["USRC17607839"],
    )
    row = build_recording_row(raw)
    assert row["normalized_title"] == "nights"
    assert row["external_ids"] == [{"id_type": "isrc", "value": "USRC17607839", "verified": True}]
    assert row["artist_mbids"] == ["artist-mbid-1"]


def test_build_recording_row_handles_no_isrc():
    raw = RawRecording(mbid="rec-mbid-2", title="Untitled", length_ms=None)
    row = build_recording_row(raw)
    assert row["external_ids"] == []
    assert row["length_ms"] is None
