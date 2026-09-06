import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import httpx
import pytest

from app.providers.spotify_music_provider import SpotifyMusicProvider
from provider_types import ProviderCapabilityError, ProviderLinkStatus


def _make_provider(handler, *, auth_code_enabled: bool = False) -> SpotifyMusicProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return SpotifyMusicProvider(
        client_id="test-id",
        client_secret="test-secret",
        auth_code_enabled=auth_code_enabled,
        http_client=client,
    )


async def test_resolve_provider_track_prefers_isrc_and_reports_resolved():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert "isrc:USRC17607839" in request.url.params["q"]
        return httpx.Response(
            200,
            json={
                "tracks": {
                    "items": [
                        {"id": "spotify-track-1", "external_urls": {"spotify": "https://open.spotify.com/track/x"}}
                    ]
                }
            },
        )

    provider = _make_provider(handler)
    link = await provider.resolve_provider_track(
        isrc="USRC17607839", title="Nights", artist_names=["Frank Ocean"], length_ms=307000
    )

    assert link.status == ProviderLinkStatus.RESOLVED
    assert link.provider_track_id == "spotify-track-1"
    assert link.match_method == "isrc"
    assert link.match_confidence == 1.0


async def test_resolve_provider_track_no_match_is_unresolved_not_an_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, json={"tracks": {"items": []}})

    provider = _make_provider(handler)
    link = await provider.resolve_provider_track(
        isrc="USRC00000000", title="Nonexistent", artist_names=["Nobody"], length_ms=None
    )

    assert link.status == ProviderLinkStatus.UNRESOLVED


async def test_resolve_provider_track_degrades_on_network_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        raise httpx.ConnectError("connection refused", request=request)

    provider = _make_provider(handler)
    link = await provider.resolve_provider_track(
        isrc="USRC17607839", title="Nights", artist_names=["Frank Ocean"], length_ms=307000
    )

    # A downed Spotify must degrade the listening link, never raise into
    # the caller and break discovery (V2.2 §8).
    assert link.status == ProviderLinkStatus.FAILED


async def test_user_oauth_operations_are_capability_gated_by_default():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover — never called
        raise AssertionError("no HTTP call expected for a capability-gated operation")

    provider = _make_provider(handler, auth_code_enabled=False)

    with pytest.raises(ProviderCapabilityError):
        await provider.get_user_playlists("user-1")
    with pytest.raises(ProviderCapabilityError):
        await provider.save_to_library("user-1", "spotify-track-1")


async def test_capabilities_never_claim_oauth_even_when_flag_enabled():
    """auth_code_enabled=True turns on the *attempt*, not a verified
    capability — capabilities.oauth_user must stay False until Phase 0
    actually confirms Authorization Code works for this app.
    """

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("unused in this test")

    provider = _make_provider(handler, auth_code_enabled=True)
    assert provider.capabilities.oauth_user is False
