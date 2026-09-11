"""Delta refresh / targeted lookups / backfills via the LIVE MusicBrainz
API — the only place in this codebase that should call it, and only for
this narrow purpose (V2.2 decision #3: 'MusicBrainz API is fallback/
maintenance only'). Bulk search must always run against our own indexed
copy (app/catalog/search.py), never this module.

Rate limiting is enforced here, not left to caller discipline, because a
single missed rate-limit check across a whole ingestion job risks getting
the app's IP/user-agent blocked.
"""

import logging
import time
from dataclasses import dataclass

import httpx

from .config import IngestConfig

logger = logging.getLogger(__name__)

MUSICBRAINZ_WS_BASE_URL = "https://musicbrainz.org/ws/2/"


@dataclass
class RateLimiter:
    min_interval_seconds: float
    _last_call_monotonic: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._last_call_monotonic is not None:
            elapsed = now - self._last_call_monotonic
            remaining = self.min_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_call_monotonic = time.monotonic()


class MusicBrainzRefreshClient:
    """Thin, rate-limited client for single-entity lookups. Not a search
    client — there is deliberately no `search()` method here; that would
    reintroduce the live-API-as-search-backend problem this pipeline
    exists to avoid.
    """

    def __init__(self, config: IngestConfig):
        self._config = config
        self._limiter = RateLimiter(min_interval_seconds=config.live_api_min_interval_seconds)
        self._client = httpx.Client(
            base_url=MUSICBRAINZ_WS_BASE_URL,
            headers={"User-Agent": config.user_agent, "Accept": "application/json"},
            timeout=15.0,
        )

    def get_recording(self, mbid: str) -> dict:
        self._limiter.wait()
        resp = self._client.get(f"recording/{mbid}", params={"inc": "isrcs+artist-credits+releases"})
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()
