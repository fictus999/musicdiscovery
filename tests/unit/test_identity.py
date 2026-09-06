import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from app.catalog.identity import (  # noqa: E402
    ExistingRecording,
    resolve_by_isrc,
    resolve_by_metadata,
    resolve_recording,
)
from app.catalog.normalize import normalize_artist_credit, normalize_title  # noqa: E402


def test_normalize_title_strips_diacritics_and_case():
    assert normalize_title("Café del Mar") == "cafe del mar"


def test_normalize_artist_credit_preserves_order():
    assert normalize_artist_credit(["Daft Punk", "Pharrell"]) != normalize_artist_credit(
        ["Pharrell", "Daft Punk"]
    )


def test_isrc_match_is_authoritative_and_full_confidence():
    match = resolve_by_isrc("USRC17607839", lambda isrc: "rec-1" if isrc == "USRC17607839" else None)
    assert match is not None
    assert match.recording_id == "rec-1"
    assert match.confidence == 1.0
    assert match.method == "isrc"


def test_isrc_miss_returns_none():
    assert resolve_by_isrc("USRC17607839", lambda isrc: None) is None
    assert resolve_by_isrc(None, lambda isrc: "rec-1") is None


def test_metadata_match_accepts_close_duration_and_exact_text():
    candidates = [
        ExistingRecording(
            recording_id="rec-2",
            normalized_title=normalize_title("Nights"),
            normalized_artist_credit=normalize_artist_credit(["Frank Ocean"]),
            length_ms=307000,
        )
    ]
    match = resolve_by_metadata(
        title="Nights", artist_names=["Frank Ocean"], length_ms=307500, candidates=candidates
    )
    assert match is not None
    assert match.recording_id == "rec-2"
    assert match.method == "title_artist_duration"


def test_metadata_match_rejects_same_title_different_artist():
    """Two different songs can share a title; that alone must never merge them."""
    candidates = [
        ExistingRecording(
            recording_id="rec-3",
            normalized_title=normalize_title("Nights"),
            normalized_artist_credit=normalize_artist_credit(["Some Other Artist"]),
            length_ms=307000,
        )
    ]
    match = resolve_by_metadata(
        title="Nights", artist_names=["Frank Ocean"], length_ms=307000, candidates=candidates
    )
    assert match is None


def test_metadata_match_rejects_wildly_different_duration():
    candidates = [
        ExistingRecording(
            recording_id="rec-4",
            normalized_title=normalize_title("Nights"),
            normalized_artist_credit=normalize_artist_credit(["Frank Ocean"]),
            length_ms=90_000,  # a 90s clip vs. a ~5min track
        )
    ]
    match = resolve_by_metadata(
        title="Nights", artist_names=["Frank Ocean"], length_ms=307000, candidates=candidates
    )
    assert match is None


def test_resolve_recording_prefers_isrc_over_metadata():
    match = resolve_recording(
        title="Nights",
        artist_names=["Frank Ocean"],
        length_ms=307000,
        isrc="USRC17607839",
        isrc_lookup=lambda isrc: "rec-isrc-hit",
        metadata_candidates_lookup=lambda: (_ for _ in ()).throw(
            AssertionError("metadata lookup must not run when ISRC resolves")
        ),
    )
    assert match is not None
    assert match.recording_id == "rec-isrc-hit"
    assert match.method == "isrc"


def test_resolve_recording_falls_back_to_metadata_when_isrc_absent():
    candidates = [
        ExistingRecording(
            recording_id="rec-5",
            normalized_title=normalize_title("Nights"),
            normalized_artist_credit=normalize_artist_credit(["Frank Ocean"]),
            length_ms=307000,
        )
    ]
    match = resolve_recording(
        title="Nights",
        artist_names=["Frank Ocean"],
        length_ms=307200,
        isrc=None,
        isrc_lookup=lambda isrc: None,
        metadata_candidates_lookup=lambda: candidates,
    )
    assert match is not None
    assert match.method == "title_artist_duration"
