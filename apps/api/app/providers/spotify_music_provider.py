"""Spotify as a MusicProvider: catalog-lookup/link resolution only in
Phase 1. Client Credentials is the only auth mode actually exercised here
— Authorization Code exists as a feature-flagged skeleton (see
config.spotify_auth_code_enabled) per V2.1 §F, never assumed production-
scale.

Every live endpoint this class calls (`/api/token`, `/v1/search`) must be
re-confirmed against the actual Development Mode app during Phase 0 —
February 2026 changes already removed/changed fields and endpoints for
new apps (search limit capped at 10, popularity gone, batch endpoints
removed). Nothing here should be trusted as "verified working" until
Phase 0 says so; it's written against Spotify's documented Client
Credentials flow and search-by-ISRC pattern, tested here only against a
mocked transport, never a live call.
"""

import time

import httpx

from provider_types import (
    MusicProvider,
    ProviderCapabilities,
    ProviderCapabilityError,
    ProviderUnavailableError,
    ProviderLinkStatus,
    ResolvedTrackLink,
)

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE_URL = "https://api.spotify.com/v1"


class SpotifyMusicProvider(MusicProvider):
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        auth_code_enabled: bool,
        http_client: httpx.AsyncClient,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._auth_code_enabled = auth_code_enabled
        self._http = http_client
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def source_id(self) -> str:
        return "spotify"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            deep_links=True,
            client_credentials=True,
            # These stay False until Phase 0 confirms Authorization Code is
            # wired, tested, and within Development Mode's 5-user allowlist
            # — never inferred from auth_code_enabled alone.
            oauth_user=False,
            user_profile=False,
            user_playlists=False,
            playlist_items=False,
            library_read=False,
            library_write=False,
        )

    async def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        try:
            resp = await self._http.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("spotify", str(exc)) from exc
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.monotonic() + payload.get("expires_in", 3600) - 30
        return self._token

    async def resolve_provider_track(
        self, *, isrc: str | None, title: str, artist_names: list[str], length_ms: int | None
    ) -> ResolvedTrackLink:
        token = await self._get_token()
        query = f"isrc:{isrc}" if isrc else f"track:{title} artist:{artist_names[0] if artist_names else ''}"
        try:
            resp = await self._http.get(
                f"{API_BASE_URL}/search",
                params={"q": query, "type": "track", "limit": 10},  # limit capped at 10 (Feb 2026)
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # A resolution failure degrades to UNRESOLVED, not an
            # exception — V2.2 §8: provider failure must never break
            # discovery. FAILED is reserved for the ProviderUnavailableError
            # case a caller explicitly wants to distinguish (e.g. observability).
            return ResolvedTrackLink(
                status=ProviderLinkStatus.FAILED,
                provider=self.source_id,
                match_method="isrc" if isrc else "title_artist",
            )

        items = resp.json().get("tracks", {}).get("items", [])
        if not items:
            return ResolvedTrackLink(
                status=ProviderLinkStatus.UNRESOLVED,
                provider=self.source_id,
                match_method="isrc" if isrc else "title_artist",
            )
        track = items[0]
        return ResolvedTrackLink(
            status=ProviderLinkStatus.RESOLVED,
            provider=self.source_id,
            provider_track_id=track["id"],
            url=track.get("external_urls", {}).get("spotify"),
            match_method="isrc" if isrc else "title_artist",
            match_confidence=1.0 if isrc else 0.6,
        )

    async def get_track_link(self, provider_track_id: str) -> str:
        return f"https://open.spotify.com/track/{provider_track_id}"

    def _require_user_oauth(self, operation: str) -> None:
        if not self._auth_code_enabled or not self.capabilities.oauth_user:
            raise ProviderCapabilityError(self.source_id, operation)

    async def connect_user(self, user_id: str, authorization_code: str) -> None:
        self._require_user_oauth("connect_user")

    async def disconnect_user(self, user_id: str) -> None:
        self._require_user_oauth("disconnect_user")

    async def get_user_library(self, user_id: str) -> list[str]:
        self._require_user_oauth("get_user_library")
        return []

    async def get_user_playlists(self, user_id: str) -> list[dict]:
        self._require_user_oauth("get_user_playlists")
        return []

    async def import_playlist(self, user_id: str, provider_playlist_id: str) -> list[str]:
        self._require_user_oauth("import_playlist")
        return []

    async def save_to_library(self, user_id: str, provider_track_id: str) -> None:
        self._require_user_oauth("save_to_library")
