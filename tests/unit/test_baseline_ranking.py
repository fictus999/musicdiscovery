import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from app.recommendation.baseline_ranking import RankingFeatures, score_candidate
from app.recommendation.topk import top_k


def test_shared_artist_and_era_drive_up_score():
    reference = RankingFeatures(
        recording_id="ref", artist_ids=frozenset({"artist-1"}), release_year=2016, language="en"
    )
    same_artist = RankingFeatures(
        recording_id="cand-a", artist_ids=frozenset({"artist-1"}), release_year=2017, language="en"
    )
    unrelated = RankingFeatures(
        recording_id="cand-b", artist_ids=frozenset({"artist-9"}), release_year=1975, language="fr"
    )

    score_a, dims_a, reasons_a = score_candidate(reference, same_artist)
    score_b, _, _ = score_candidate(reference, unrelated)

    assert score_a > score_b
    assert "SAME_ARTIST" in reasons_a
    assert "SAME_LANGUAGE" in reasons_a


def test_missing_feature_family_renormalizes_instead_of_faking_zero():
    reference = RankingFeatures(recording_id="ref", artist_ids=frozenset({"a1"}), language=None)
    candidate = RankingFeatures(recording_id="cand", artist_ids=frozenset({"a1"}), language=None)

    score, dims, _ = score_candidate(reference, candidate)

    # Only artist_relationship (1.0) and metadata_quality_bonus (1.0) are
    # present; both are satisfied, so renormalizing must yield 1.0 — not a
    # penalized score for the missing language/genre/era dimensions.
    assert "language_similarity" not in dims
    assert "genre_tag_overlap" not in dims
    assert "release_period_similarity" not in dims
    assert score == 1.0


def test_top_k_orders_by_score_and_respects_k():
    scored = [(0.2, "low"), (0.9, "high"), (0.5, "mid"), (0.7, "mid-high")]
    result = top_k(scored, k=2)
    assert [item for _, item in result] == ["high", "mid-high"]
