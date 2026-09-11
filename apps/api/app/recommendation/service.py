"""Orchestrates Phase 1 recommendation: candidate generation (shared-artist
SQL prefilter — the 'first stage' of V2 §10.1's two-stage retrieval; the
second stage, vector search over embeddings, doesn't exist until Phase 2)
-> baseline scoring -> top-K.

Mode is accepted and recorded (recommendations.mode) but Phase 1 has only
one feature family (metadata), so every mode currently scores identically
via baseline_ranking — mode-specific weighting (V2 §9.3) requires audio/
lyrics/rhythm feature families that don't exist until Phase 2. This is a
scope limit, not a bug: encoding fake per-mode weights now, with nothing
behind them, would be exactly the "fabricated score" the spec forbids.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.repository import get_candidate_ids_by_shared_artist, get_ranking_features_bulk, get_ranking_features
from app.recommendation.baseline_ranking import score_candidate
from app.recommendation.topk import top_k

CANDIDATE_POOL_SIZE = 200


@dataclass(frozen=True)
class ScoredCandidate:
    recording_id: str
    score: float
    dimension_scores: dict[str, float]
    reason_codes: list[str]


def recommend(
    session: Session,
    *,
    reference_recording_id: str,
    limit: int = 20,
    exclude_same_artist: bool = False,
) -> list[ScoredCandidate] | None:
    """Returns None if the reference recording itself isn't known (caller
    should surface a 404), otherwise the top-`limit` scored candidates —
    possibly fewer, or empty, if the candidate pool is too small; that is
    a valid outcome for a thin Phase 1 seed catalog, not an error.
    """
    reference = get_ranking_features(session, reference_recording_id)
    if reference is None:
        return None

    candidate_ids = get_candidate_ids_by_shared_artist(
        session, reference_recording_id, limit=CANDIDATE_POOL_SIZE
    )
    candidate_features = get_ranking_features_bulk(session, candidate_ids)

    scored: list[tuple[float, ScoredCandidate]] = []
    for recording_id, features in candidate_features.items():
        if exclude_same_artist and reference.artist_ids & features.artist_ids:
            continue
        score, dims, reasons = score_candidate(reference, features)
        scored.append((score, ScoredCandidate(recording_id, score, dims, reasons)))

    return [candidate for _, candidate in top_k(scored, limit)]
