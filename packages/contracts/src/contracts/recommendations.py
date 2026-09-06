from pydantic import BaseModel

from .song import SongDTO


class RecommendationRequest(BaseModel):
    """Mirrors the V2 §14 backend API contract."""

    track_id: str  # canonical recording_id
    mode: str = "overall"
    limit: int = 20
    adventurousness: float = 0.5
    exclude_same_artist: bool = False


class RecommendationResult(BaseModel):
    song: SongDTO
    score: float
    dimension_scores: dict[str, float]
    reason_codes: list[str]


class RecommendationResponse(BaseModel):
    reference: SongDTO
    mode: str
    results: list[RecommendationResult]
    model_version: str
