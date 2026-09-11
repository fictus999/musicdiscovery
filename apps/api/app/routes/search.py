from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_optional_user_id
from app.db.repository import record_search
from app.db.session import get_session
from app.providers.musicbrainz_catalog_provider import MusicBrainzCatalogProvider
from contracts import SearchResponse, SongDTO

router = APIRouter()


@router.get("/music/search", response_model=SearchResponse)
async def search_music(
    q: str,
    limit: int = 20,
    session: Session = Depends(get_session),
    user_id: str | None = Depends(get_optional_user_id),
) -> SearchResponse:
    provider = MusicBrainzCatalogProvider(session)
    result = await provider.search(q, limit=limit)
    songs = [
        SongDTO(
            recording_id=c.source_id,
            title=c.title,
            artist_names=[a.name for a in c.artists],
            length_ms=c.length_ms,
            # Provider deep-links (Spotify/Apple) are resolved lazily, not
            # inline per search keystroke — see app/routes/songs.py and
            # the Phase 0 note in spotify_music_provider.py. Empty here is
            # a scope boundary, not a bug.
            provider_links=[],
        )
        for c in result.candidates
    ]
    # Only logged for authenticated users — anonymous search history would
    # need a client-generated session_id (search_history.session_id exists
    # for that) which the frontend doesn't produce yet; not invented here.
    if user_id is not None:
        record_search(session, user_id=user_id, query_text=q)
    return SearchResponse(query=q, results=songs)
