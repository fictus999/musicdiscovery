"""Canonical song identity resolution (V2 §8, V2.2 §9).

Prefer verified ISRC matching when available. Fall back to normalized
artist + title + duration with an explicit confidence score. Never assume
two recordings are identical solely because titles match.

This module is deliberately DB-free: callers inject the lookups it needs
(an ISRC index and a candidate-fetching function) so the matching logic
itself is unit-testable with plain fakes, with no database or event loop
required. The real DB-backed lookups live in apps/api/app/db/repository.py.
"""

from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher

from .normalize import normalize_artist_credit, normalize_title

# Below this confidence, treat the candidate as a new/distinct recording
# rather than a match — false positives (merging two different songs) are
# worse than false negatives (a duplicate canonical row later reconciled),
# so this threshold is intentionally conservative.
METADATA_MATCH_THRESHOLD = 0.85

DURATION_EXACT_TOLERANCE_MS = 2_000
DURATION_MAX_TOLERANCE_MS = 15_000


@dataclass(frozen=True)
class ExistingRecording:
    recording_id: str
    normalized_title: str
    normalized_artist_credit: str
    length_ms: int | None


@dataclass(frozen=True)
class IdentityMatch:
    recording_id: str
    confidence: float
    method: str  # 'isrc' | 'title_artist_duration'


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _duration_score(a_ms: int | None, b_ms: int | None) -> float:
    if a_ms is None or b_ms is None:
        return 0.5  # neutral — missing duration should not itself sink a match
    diff = abs(a_ms - b_ms)
    if diff <= DURATION_EXACT_TOLERANCE_MS:
        return 1.0
    if diff >= DURATION_MAX_TOLERANCE_MS:
        return 0.0
    span = DURATION_MAX_TOLERANCE_MS - DURATION_EXACT_TOLERANCE_MS
    return 1.0 - (diff - DURATION_EXACT_TOLERANCE_MS) / span


def score_metadata_match(
    *,
    title: str,
    artist_names: list[str],
    length_ms: int | None,
    candidate: ExistingRecording,
) -> float | None:
    """Returns None (hard reject) when both durations are known and wildly
    different — otherwise an exact title+artist match alone (weight 0.9)
    would always clear the threshold regardless of duration, making the
    duration signal decorative. A big duration gap is itself evidence of a
    different edition (radio edit, intro-only teaser, extended mix), which
    per V2 §8 must resolve to a distinct canonical recording, not a merge.
    """
    duration_score = _duration_score(length_ms, candidate.length_ms)
    if length_ms is not None and candidate.length_ms is not None and duration_score == 0.0:
        return None
    title_score = _similarity(normalize_title(title), candidate.normalized_title)
    artist_score = _similarity(normalize_artist_credit(artist_names), candidate.normalized_artist_credit)
    return title_score * 0.5 + artist_score * 0.4 + duration_score * 0.1


def resolve_by_isrc(isrc: str | None, isrc_lookup: Callable[[str], str | None]) -> IdentityMatch | None:
    if not isrc:
        return None
    recording_id = isrc_lookup(isrc)
    if recording_id is None:
        return None
    return IdentityMatch(recording_id=recording_id, confidence=1.0, method="isrc")


def resolve_by_metadata(
    *,
    title: str,
    artist_names: list[str],
    length_ms: int | None,
    candidates: list[ExistingRecording],
) -> IdentityMatch | None:
    best: IdentityMatch | None = None
    for candidate in candidates:
        confidence = score_metadata_match(
            title=title, artist_names=artist_names, length_ms=length_ms, candidate=candidate
        )
        if confidence is None:
            continue
        if confidence >= METADATA_MATCH_THRESHOLD and (best is None or confidence > best.confidence):
            best = IdentityMatch(
                recording_id=candidate.recording_id,
                confidence=confidence,
                method="title_artist_duration",
            )
    return best


def resolve_recording(
    *,
    title: str,
    artist_names: list[str],
    length_ms: int | None,
    isrc: str | None,
    isrc_lookup: Callable[[str], str | None],
    metadata_candidates_lookup: Callable[[], list[ExistingRecording]],
) -> IdentityMatch | None:
    """ISRC-first, per V2 §8. metadata_candidates_lookup is only called
    (and only needs to return a plausible short-list, e.g. via trigram
    pre-filtering) when no verified ISRC match exists.
    """
    isrc_match = resolve_by_isrc(isrc, isrc_lookup)
    if isrc_match is not None:
        return isrc_match
    return resolve_by_metadata(
        title=title,
        artist_names=artist_names,
        length_ms=length_ms,
        candidates=metadata_candidates_lookup(),
    )
