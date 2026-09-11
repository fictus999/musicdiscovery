"""Apple Music / MusicKit stub. Every capability is False and every method
raises ProviderCapabilityError until Phase 0 validates MusicKit entitlement,
developer-token generation (Apple's server-to-server auth uses a JWT signed
with an Apple Developer Program private key, not a Client Credentials
grant — a different shape from Spotify's, still unverified from this
environment), and catalog/library capabilities (V2.1 §F, V2.2 §6).

This exists so the provider registry and capability-routing code have a
real, type-correct implementation to wire against now, without inventing
behavior for an integration nobody has confirmed works yet.
"""

from provider_types import (
    MusicProvider,
    ProviderCapabilities,
    ProviderCapabilityError,
    ResolvedTrackLink,
)


class AppleMusicProvider(MusicProvider):
    def __init__(self, *, musickit_enabled: bool):
        self._musickit_enabled = musickit_enabled

    @property
    def source_id(self) -> str:
        return "apple_music"

    @property
    def capabilities(self) -> ProviderCapabilities:
        # Deliberately all-False regardless of musickit_enabled: that flag
        # only gates whether we *attempt* Apple calls at all, it is not
        # itself proof Phase 0 has verified what those calls can do.
        return ProviderCapabilities()

    def _not_yet_verified(self, operation: str) -> ProviderCapabilityError:
        return ProviderCapabilityError(self.source_id, operation)

    async def resolve_provider_track(
        self, *, isrc: str | None, title: str, artist_names: list[str], length_ms: int | None
    ) -> ResolvedTrackLink:
        raise self._not_yet_verified("resolve_provider_track")

    async def get_track_link(self, provider_track_id: str) -> str:
        raise self._not_yet_verified("get_track_link")

    async def connect_user(self, user_id: str, authorization_code: str) -> None:
        raise self._not_yet_verified("connect_user")

    async def disconnect_user(self, user_id: str) -> None:
        raise self._not_yet_verified("disconnect_user")

    async def get_user_library(self, user_id: str) -> list[str]:
        raise self._not_yet_verified("get_user_library")

    async def get_user_playlists(self, user_id: str) -> list[dict]:
        raise self._not_yet_verified("get_user_playlists")

    async def import_playlist(self, user_id: str, provider_playlist_id: str) -> list[str]:
        raise self._not_yet_verified("import_playlist")

    async def save_to_library(self, user_id: str, provider_track_id: str) -> None:
        raise self._not_yet_verified("save_to_library")
