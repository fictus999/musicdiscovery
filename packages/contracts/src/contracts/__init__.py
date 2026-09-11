from .song import ProviderLink, SongDTO
from .search import SearchRequest, SearchResponse
from .recommendations import RecommendationRequest, RecommendationResponse, RecommendationResult
from .me import SavedSongsResponse, HistoryEntry, HistoryResponse

__all__ = [
    "SongDTO",
    "ProviderLink",
    "SearchRequest",
    "SearchResponse",
    "RecommendationRequest",
    "RecommendationResponse",
    "RecommendationResult",
    "SavedSongsResponse",
    "HistoryEntry",
    "HistoryResponse",
]
