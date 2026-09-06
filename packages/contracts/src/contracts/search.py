from pydantic import BaseModel

from .song import SongDTO


class SearchRequest(BaseModel):
    q: str
    limit: int = 20


class SearchResponse(BaseModel):
    query: str
    results: list[SongDTO]
