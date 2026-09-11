from abc import ABC, abstractmethod

from pydantic import BaseModel

from .capabilities import ProviderCapabilities


class ResolvedArtwork(BaseModel):
    source: str  # e.g. "cover_art_archive" | "spotify" | "apple_music"
    image_url: str
    width: int | None = None
    height: int | None = None
    is_fallback: bool = False


class ArtworkProvider(ABC):
    """Album art is its own concern, independent of catalog search and of
    listening-provider resolution (V2.2 audit gap: MusicBrainz carries no
    cover art itself). Phase 1 tries Cover Art Archive first, keyed by
    release, and falls back to whatever listening provider a recording
    successfully resolved against, if that provider exposes artwork.
    """

    @property
    @abstractmethod
    def source_id(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @abstractmethod
    async def get_artwork_for_release(self, release_mbid: str) -> ResolvedArtwork | None: ...

    @abstractmethod
    async def get_fallback_artwork(
        self, *, provider: str, provider_track_id: str
    ) -> ResolvedArtwork | None:
        """Fallback path when Cover Art Archive has nothing for this
        release — ask whichever listening provider resolved successfully.
        """
        ...
