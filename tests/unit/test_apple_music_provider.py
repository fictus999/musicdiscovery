import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

import pytest

from app.providers.apple_music_provider import AppleMusicProvider
from provider_types import ProviderCapabilityError


async def test_every_capability_is_false_until_phase0_verifies_entitlements():
    provider = AppleMusicProvider(musickit_enabled=True)
    caps = provider.capabilities
    assert not any(
        [
            caps.catalog_search,
            caps.catalog_track_lookup,
            caps.user_playlists,
            caps.library_read,
            caps.library_write,
            caps.oauth_user,
        ]
    )


async def test_every_operation_raises_capability_error_not_silently_no_ops():
    provider = AppleMusicProvider(musickit_enabled=True)
    with pytest.raises(ProviderCapabilityError):
        await provider.resolve_provider_track(
            isrc="USRC17607839", title="Nights", artist_names=["Frank Ocean"], length_ms=307000
        )
    with pytest.raises(ProviderCapabilityError):
        await provider.get_user_playlists("user-1")
