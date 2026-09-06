import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import httpx

from app.providers.cover_art_artwork_provider import CoverArtArchiveArtworkProvider
from provider_types import ProviderUnavailableError
import pytest


def _make_provider(handler) -> CoverArtArchiveArtworkProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return CoverArtArchiveArtworkProvider(base_url="https://coverartarchive.org", http_client=client)


async def test_returns_front_image_when_present():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"images": [{"front": False, "image": "https://x/back.jpg"}, {"front": True, "image": "https://x/front.jpg"}]},
        )

    provider = _make_provider(handler)
    artwork = await provider.get_artwork_for_release("some-release-mbid")

    assert artwork is not None
    assert artwork.image_url == "https://x/front.jpg"
    assert artwork.is_fallback is False


async def test_404_is_a_normal_no_artwork_outcome_not_an_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    provider = _make_provider(handler)
    artwork = await provider.get_artwork_for_release("release-with-no-art")

    assert artwork is None


async def test_network_failure_raises_provider_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _make_provider(handler)
    with pytest.raises(ProviderUnavailableError):
        await provider.get_artwork_for_release("some-release-mbid")
