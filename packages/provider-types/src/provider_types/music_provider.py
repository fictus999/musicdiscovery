from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel

from .capabilities import ProviderCapabilities


class ProviderLinkStatus(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    STALE = "stale"
    FAILED = "failed"


class ResolvedTrackLink(BaseModel):
    status: ProviderLinkStatus
    provider: str
    provider_track_id: str | None = None
    url: str | None = None
    match_method: str | None = None  # 'isrc' | 'title_artist_duration' | 'manual'
    match_confidence: float | None = None


class MusicProvider(ABC):
    """A listening/library integration (Spotify, Apple Music, ...). This
    interface answers 'where can the user listen to / save this song', and
    must never be a dependency of the recommendation engine or of catalog
    search (V2.2 §10 — the recommendation engine depends on canonical IDs
    and feature records only).

    Every method that touches a specific user's account requires
    AuthMode.USER_OAUTH and must not be called unless that user has
    connected this provider; get_track_link/resolve_provider_track are the
    only operations expected to run under AuthMode.CLIENT_CREDENTIALS.
    """

    @property
    @abstractmethod
    def source_id(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @abstractmethod
    async def resolve_provider_track(
        self, *, isrc: str | None, title: str, artist_names: list[str], length_ms: int | None
    ) -> ResolvedTrackLink:
        """Client-Credentials-eligible: given canonical identity, find this
        provider's track id/url. ISRC-first per V2.2 §4; falls back to
        title/artist matching when the provider supports it and no ISRC
        match is found. Must return status=UNRESOLVED/FAILED rather than
        raising when the provider can't find a match — that's a normal
        outcome (V2.2 §8), not an error.
        """
        ...

    @abstractmethod
    async def get_track_link(self, provider_track_id: str) -> str: ...

    # --- user-connected features: require AuthMode.USER_OAUTH ---

    @abstractmethod
    async def connect_user(self, user_id: str, authorization_code: str) -> None: ...

    @abstractmethod
    async def disconnect_user(self, user_id: str) -> None: ...

    @abstractmethod
    async def get_user_library(self, user_id: str) -> list[str]:
        """Returns provider track ids. Raises ProviderCapabilityError if
        capabilities.library_read is False.
        """
        ...

    @abstractmethod
    async def get_user_playlists(self, user_id: str) -> list[dict]: ...

    @abstractmethod
    async def import_playlist(self, user_id: str, provider_playlist_id: str) -> list[str]: ...

    @abstractmethod
    async def save_to_library(self, user_id: str, provider_track_id: str) -> None: ...
