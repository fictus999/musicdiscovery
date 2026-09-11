"""ArtworkProvider: Cover Art Archive first (keyed by MusicBrainz release
MBID), falling back to whichever listening provider a recording resolved
against, if that provider exposes artwork (V2.2 audit gap — MusicBrainz's
core data carries no cover art itself).

Cover Art Archive's API (documented at musicbrainz.org/doc/Cover_Art_Archive/API)
is a genuinely public, unauthenticated JSON API — this implementation calls
it directly rather than stubbing it, but coverage/licensing still needs the
Phase 0 artwork audit (many releases have no art at all; a 404 here is a
normal, expected outcome, not a provider failure).
"""

import httpx

from provider_types import (
    ArtworkProvider,
    ProviderCapabilities,
    ProviderUnavailableError,
    ResolvedArtwork,
)


class CoverArtArchiveArtworkProvider(ArtworkProvider):
    def __init__(self, *, base_url: str, http_client: httpx.AsyncClient):
        self._base_url = base_url.rstrip("/")
        self._http = http_client

    @property
    def source_id(self) -> str:
        return "cover_art_archive"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(artwork=True)

    async def get_artwork_for_release(self, release_mbid: str) -> ResolvedArtwork | None:
        try:
            resp = await self._http.get(f"{self._base_url}/release/{release_mbid}")
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(self.source_id, str(exc)) from exc

        if resp.status_code == 404:
            return None  # no artwork for this release — expected, not an error
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailableError(self.source_id, str(exc)) from exc

        images = resp.json().get("images", [])
        front = next((img for img in images if img.get("front")), images[0] if images else None)
        if front is None:
            return None
        return ResolvedArtwork(
            source=self.source_id,
            image_url=front.get("image"),
            # Cover Art Archive's API returns image/thumbnail URLs, not
            # pixel dimensions, so width/height are left unset here.
            is_fallback=False,
        )

    async def get_fallback_artwork(
        self, *, provider: str, provider_track_id: str
    ) -> ResolvedArtwork | None:
        """Kept as a thin coordination point rather than baking a specific
        provider's artwork field into this class — call sites pass in
        whichever MusicProvider resolved successfully. Implemented once
        Phase 0 confirms which providers expose artwork fields to a Client
        Credentials caller (Spotify's track/album objects do; Apple's
        depend on the still-unverified MusicKit catalog response shape).
        """
        return None
