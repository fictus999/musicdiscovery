"""Phase 1 metadata-only baseline ranking (V2 §11.1). No embeddings, no
audio/lyrics features — this exists to validate identity, retrieval, UX,
links, and persistence, not to claim recommendation quality (the spec says
so explicitly, and the weight renormalization below is what makes that
honest: a missing feature family drops out of the score rather than being
faked as 0, which would silently bias every score downward).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RankingFeatures:
    recording_id: str
    artist_ids: frozenset[str]
    release_year: int | None = None
    language: str | None = None
    tag_ids: frozenset[str] = field(default_factory=frozenset)
    identity_confidence: float = 1.0


# Phase 1 weights (V2 §9.3: "these weights are placeholders... store
# model/weight versions so experiments are reproducible" — see
# model_versions / recommendations.model_version_id in the schema).
BASELINE_WEIGHTS = {
    "artist_relationship": 0.35,
    "genre_tag_overlap": 0.35,
    "release_period_similarity": 0.15,
    "language_similarity": 0.10,
    "metadata_quality_bonus": 0.05,
}

REASON_CODES = {
    "artist_relationship": "SAME_ARTIST",
    "genre_tag_overlap": "SIMILAR_GENRE",
    "release_period_similarity": "SIMILAR_ERA",
    "language_similarity": "SAME_LANGUAGE",
}

_YEAR_DECAY_HORIZON = 20  # years apart at which release-period similarity bottoms out at 0


def score_candidate(
    reference: RankingFeatures, candidate: RankingFeatures
) -> tuple[float, dict[str, float], list[str]]:
    """Returns (overall_score, dimension_scores, reason_codes). Only
    includes a dimension when both sides actually have that data — a
    missing feature family renormalizes the remaining weights rather than
    silently scoring as 0 (V2.2 §9.2).
    """
    components: dict[str, float] = {
        "artist_relationship": 1.0 if reference.artist_ids & candidate.artist_ids else 0.0,
        "metadata_quality_bonus": candidate.identity_confidence,
    }

    if reference.tag_ids and candidate.tag_ids:
        union = reference.tag_ids | candidate.tag_ids
        components["genre_tag_overlap"] = len(reference.tag_ids & candidate.tag_ids) / len(union)

    if reference.release_year is not None and candidate.release_year is not None:
        diff = abs(reference.release_year - candidate.release_year)
        components["release_period_similarity"] = max(0.0, 1.0 - diff / _YEAR_DECAY_HORIZON)

    if reference.language is not None and candidate.language is not None:
        components["language_similarity"] = 1.0 if reference.language == candidate.language else 0.0

    active_weights = {k: BASELINE_WEIGHTS[k] for k in components}
    total_weight = sum(active_weights.values())
    if total_weight == 0:
        return 0.0, {}, []

    overall = sum(components[k] * active_weights[k] for k in components) / total_weight

    reasons = [
        REASON_CODES[k]
        for k, v in components.items()
        if k in REASON_CODES and v >= 0.6  # meaningfully present, not just nonzero
    ]
    return overall, components, reasons
