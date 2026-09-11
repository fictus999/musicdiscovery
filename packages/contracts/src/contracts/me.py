from pydantic import BaseModel

from .song import SongDTO


class SavedSongsResponse(BaseModel):
    songs: list[SongDTO]


class HistoryEntry(BaseModel):
    query_text: str
    created_at: str


class HistoryResponse(BaseModel):
    entries: list[HistoryEntry]
