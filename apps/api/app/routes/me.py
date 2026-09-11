from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.db.repository import get_saved_songs, get_search_history
from app.db.session import get_session
from contracts import HistoryEntry, HistoryResponse, SavedSongsResponse

router = APIRouter(prefix="/me")


@router.get("/saved-songs", response_model=SavedSongsResponse)
async def saved_songs(
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> SavedSongsResponse:
    return SavedSongsResponse(songs=get_saved_songs(session, user_id=user_id))


@router.get("/history", response_model=HistoryResponse)
async def history(
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> HistoryResponse:
    entries = get_search_history(session, user_id=user_id)
    return HistoryResponse(entries=[HistoryEntry(**entry) for entry in entries])
