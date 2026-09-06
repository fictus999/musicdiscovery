from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_optional_user_id
from app.db.repository import (
    get_or_create_model_version,
    get_song_dto,
    persist_recommendation,
    persist_recommendation_results,
)
from app.db.session import get_session
from app.recommendation.service import recommend
from contracts import RecommendationRequest, RecommendationResponse, RecommendationResult

router = APIRouter()

MODEL_VERSION_TAG = "baseline-v1"


@router.post("/recommendations", response_model=RecommendationResponse)
async def create_recommendation(
    payload: RecommendationRequest,
    session: Session = Depends(get_session),
    user_id: str | None = Depends(get_optional_user_id),
) -> RecommendationResponse:
    reference = get_song_dto(session, payload.track_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="reference track not found")

    scored = recommend(
        session,
        reference_recording_id=payload.track_id,
        limit=payload.limit,
        exclude_same_artist=payload.exclude_same_artist,
    )
    if scored is None:
        raise HTTPException(status_code=404, detail="reference track not found")

    model_version_id = get_or_create_model_version(session, family="ranker", version_tag=MODEL_VERSION_TAG)
    recommendation_id = persist_recommendation(
        session,
        reference_recording_id=payload.track_id,
        mode=payload.mode,
        params=payload.model_dump(exclude={"track_id", "mode"}),
        model_version_id=model_version_id,
        requested_by_user_id=user_id,
    )
    persist_recommendation_results(session, recommendation_id=recommendation_id, scored_candidates=scored)

    results = [
        RecommendationResult(
            song=get_song_dto(session, c.recording_id),
            score=c.score,
            dimension_scores=c.dimension_scores,
            reason_codes=c.reason_codes,
        )
        for c in scored
    ]
    return RecommendationResponse(
        reference=reference, mode=payload.mode, results=results, model_version=MODEL_VERSION_TAG
    )


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: str, session: Session = Depends(get_session)
) -> RecommendationResponse:
    header = session.execute(
        text(
            "select rec.reference_recording_id, rec.mode, mv.version_tag "
            "from recommendations rec join model_versions mv on mv.id = rec.model_version_id "
            "where rec.id = :id"
        ),
        {"id": recommendation_id},
    ).mappings().first()
    if header is None:
        raise HTTPException(status_code=404, detail="recommendation not found")

    rows = session.execute(
        text(
            "select recording_id, score, dimension_scores, reason_codes "
            "from recommendation_results where recommendation_id = :id order by rank"
        ),
        {"id": recommendation_id},
    ).mappings().all()

    reference = get_song_dto(session, str(header["reference_recording_id"]))
    results = [
        RecommendationResult(
            song=get_song_dto(session, str(row["recording_id"])),
            score=float(row["score"]),
            dimension_scores=row["dimension_scores"],
            reason_codes=row["reason_codes"],
        )
        for row in rows
    ]
    return RecommendationResponse(
        reference=reference, mode=header["mode"], results=results, model_version=header["version_tag"]
    )
