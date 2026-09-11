"""In-memory CatalogProvider for tests and local dev without a database."""

from provider_types import (
    CatalogCandidate,
    CatalogProvider,
    CatalogSearchResult,
    ProviderCapabilities,
    ResolvedRecording,
)


class MockCatalogProvider(CatalogProvider):
    def __init__(self, seed_candidates: list[CatalogCandidate] | None = None):
        self._candidates = list(seed_candidates or [])

    @property
    def source_id(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(catalog_search=True, catalog_track_lookup=True, isrc_lookup=True)

    async def search(self, query: str, *, limit: int = 20) -> CatalogSearchResult:
        q = query.lower()
        matches = [
            c
            for c in self._candidates
            if q in c.title.lower() or any(q in a.name.lower() for a in c.artists)
        ][:limit]
        return CatalogSearchResult(query=query, candidates=matches, source=self.source_id)

    async def resolve_identity(self, candidate: CatalogCandidate) -> ResolvedRecording | None:
        for existing in self._candidates:
            if existing.isrc and existing.isrc == candidate.isrc:
                return ResolvedRecording(
                    recording_id=existing.source_id,
                    title=existing.title,
                    artists=existing.artists,
                    isrc=existing.isrc,
                    length_ms=existing.length_ms,
                )
        return None

    async def get_recording_metadata(self, source_id: str) -> CatalogCandidate | None:
        return next((c for c in self._candidates if c.source_id == source_id), None)

    async def lookup_isrc(self, isrc: str) -> list[CatalogCandidate]:
        return [c for c in self._candidates if c.isrc == isrc]

    async def lookup_external_ids(self, source_id: str) -> dict[str, str]:
        candidate = next((c for c in self._candidates if c.source_id == source_id), None)
        if candidate is None or candidate.isrc is None:
            return {}
        return {"isrc": candidate.isrc}
