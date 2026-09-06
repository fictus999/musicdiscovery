from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.db.repository import get_song_dto, save_song, unsave_song
from app.db.session import get_session

router = APIRouter()


@router.post("/songs/{recording_id}/save")
async def save(
    recording_id: str,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    if get_song_dto(session, recording_id) is None:
        raise HTTPException(status_code=404, detail="song not found")
    save_song(session, user_id=user_id, recording_id=recording_id)
    return {"status": "saved"}


@router.delete("/songs/{recording_id}/save")
async def unsave(
    recording_id: str,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    unsave_song(session, user_id=user_id, recording_id=recording_id)
    return {"status": "unsaved"}
