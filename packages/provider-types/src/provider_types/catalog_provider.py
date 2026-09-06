from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel

from .capabilities import ProviderCapabilities


class ArtistCredit(BaseModel):
    name: str
    mbid: str | None = None


class CatalogCandidate(BaseModel):
    """One raw match from a catalog source, before canonical-identity
    resolution has decided whether it's the same recording as something
    already in our database (that decision is made in
    apps/api/app/catalog/identity.py, not by the provider adapter).
    """

    source: str  # catalog_sources.id, e.g. "musicbrainz"
    source_id: str  # e.g. the MusicBrainz recording MBID
    title: str
    artists: list[ArtistCredit]
    album_title: str | None = None
    length_ms: int | None = None
    release_date: date | None = None
    isrc: str | None = None


class CatalogSearchResult(BaseModel):
    query: str
    candidates: list[CatalogCandidate]
    source: str
    truncated: bool = False


class ResolvedRecording(BaseModel):
    """A canonical recording as known to our own database — the shape
    identity.py deals in once resolution has happened.
    """

    recording_id: str  # our canonical uuid, not a provider id
    title: str
    artists: list[ArtistCredit]
    isrc: str | None = None
    length_ms: int | None = None


class CatalogProvider(ABC):
    """Source of catalog search, identity metadata, and ISRC/external-id
    lookups. In Phase 1 this is MusicBrainz-backed (against our own
    ingested copy — see MusicBrainzCatalogProvider), never a listening
    provider's search endpoint (V2.2 §3: 'do not route normal song-search
    traffic through Spotify').
    """

    @property
    @abstractmethod
    def source_id(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @abstractmethod
    async def search(self, query: str, *, limit: int = 20) -> CatalogSearchResult: ...

    @abstractmethod
    async def resolve_identity(self, candidate: CatalogCandidate) -> ResolvedRecording | None:
        """Given a raw candidate, return the canonical recording it matches,
        if any is already known. Returns None when nothing matches yet
        (the caller then decides whether to create a new canonical entity).
        """
        ...

    @abstractmethod
    async def get_recording_metadata(self, source_id: str) -> CatalogCandidate | None: ...

    @abstractmethod
    async def lookup_isrc(self, isrc: str) -> list[CatalogCandidate]: ...

    @abstractmethod
    async def lookup_external_ids(self, source_id: str) -> dict[str, str]:
        """id_type -> value, e.g. {'isrc': 'USRC17607839'}."""
        ...
