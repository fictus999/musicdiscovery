from .capabilities import AuthMode, ProviderCapabilities
from .catalog_provider import ArtistCredit, CatalogCandidate, CatalogProvider, CatalogSearchResult, ResolvedRecording
from .music_provider import MusicProvider, ProviderLinkStatus, ResolvedTrackLink
from .artwork_provider import ArtworkProvider, ResolvedArtwork
from .errors import ProviderUnavailableError, ProviderCapabilityError
from .routing import select_auth_mode

__all__ = [
    "select_auth_mode",
    "AuthMode",
    "ProviderCapabilities",
    "ArtistCredit",
    "CatalogCandidate",
    "CatalogProvider",
    "CatalogSearchResult",
    "ResolvedRecording",
    "MusicProvider",
    "ProviderLinkStatus",
    "ResolvedTrackLink",
    "ArtworkProvider",
    "ResolvedArtwork",
    "ProviderUnavailableError",
    "ProviderCapabilityError",
]
