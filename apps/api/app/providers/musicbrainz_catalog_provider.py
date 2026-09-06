"""CatalogProvider backed by our own ingested copy of MusicBrainz data
(database/migrations/002-003). Never calls the live MusicBrainz API — that
would reintroduce the 1 req/sec bottleneck this whole indexing strategy
exists to avoid (see jobs/musicbrainz_ingest/README.md).
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalog.normalize import normalize_artist_credit, normalize_title
from provider_types import (
    ArtistCredit,
    CatalogCandidate,
    CatalogProvider,
    CatalogSearchResult,
    ProviderCapabilities,
    ResolvedRecording,
)

_SEARCH_SQL = text(
    """
    select r.id as recording_id,
           r.title,
           r.length_ms,
           array_agg(a.name order by ra.credit_order) as artist_names,
           greatest(
               similarity(r.normalized_title, :nq),
               max(similarity(a.normalized_name, :nq))
           ) as score
    from recording r
    join recording_artists ra on ra.recording_id = r.id
    join artist a on a.id = ra.artist_id
    where r.normalized_title % :nq or a.normalized_name % :nq
    group by r.id, r.title, r.length_ms
    order by score desc
    limit :limit
    """
)

_ISRC_LOOKUP_SQL = text(
    """
    select r.id as recording_id, r.title, r.length_ms,
           array_agg(a.name order by ra.credit_order) as artist_names
    from recording_external_ids ext
    join recording r on r.id = ext.recording_id
    join recording_artists ra on ra.recording_id = r.id
    join artist a on a.id = ra.artist_id
    where ext.id_type = 'isrc' and ext.value = :isrc
    group by r.id, r.title, r.length_ms
    """
)

_METADATA_SQL = text(
    """
    select r.id as recording_id, r.normalized_title, r.length_ms,
           array_agg(a.name order by ra.credit_order) as artist_names
    from recording r
    join recording_artists ra on ra.recording_id = r.id
    join artist a on a.id = ra.artist_id
    where r.normalized_title % :nq
    group by r.id, r.normalized_title, r.length_ms
    limit 25
    """
)

_EXTERNAL_IDS_SQL = text(
    "select id_type, value from recording_external_ids where recording_id = :recording_id"
)


class MusicBrainzCatalogProvider(CatalogProvider):
    def __init__(self, session: Session):
        self._session = session

    @property
    def source_id(self) -> str:
        return "musicbrainz"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            catalog_search=True,
            catalog_track_lookup=True,
            isrc_lookup=True,
            client_credentials=False,  # not applicable — this is our own DB, not a remote API
        )

    async def search(self, query: str, *, limit: int = 20) -> CatalogSearchResult:
        nq = normalize_title(query)
        rows = self._session.execute(_SEARCH_SQL, {"nq": nq, "limit": limit}).mappings().all()
        candidates = [
            CatalogCandidate(
                source=self.source_id,
                source_id=str(row["recording_id"]),
                title=row["title"],
                artists=[ArtistCredit(name=name) for name in row["artist_names"]],
                length_ms=row["length_ms"],
            )
            for row in rows
        ]
        return CatalogSearchResult(query=query, candidates=candidates, source=self.source_id, truncated=False)

    async def resolve_identity(self, candidate: CatalogCandidate) -> ResolvedRecording | None:
        if candidate.source == self.source_id:
            # Already one of our own canonical recordings.
            row = self._session.execute(
                text("select id, title, length_ms from recording where id = :id"),
                {"id": candidate.source_id},
            ).mappings().first()
            if row is None:
                return None
            return ResolvedRecording(
                recording_id=str(row["id"]),
                title=row["title"],
                artists=candidate.artists,
                isrc=candidate.isrc,
                length_ms=row["length_ms"],
            )

        # A candidate from another catalog source: apply ISRC-first, then
        # normalized-metadata matching (app.catalog.identity), never a
        # title-only guess.
        from app.catalog.identity import ExistingRecording, resolve_recording

        def isrc_lookup(isrc: str) -> str | None:
            row = self._session.execute(_ISRC_LOOKUP_SQL, {"isrc": isrc}).mappings().first()
            return str(row["recording_id"]) if row else None

        def metadata_candidates_lookup() -> list[ExistingRecording]:
            nq = normalize_title(candidate.title)
            rows = self._session.execute(_METADATA_SQL, {"nq": nq}).mappings().all()
            return [
                ExistingRecording(
                    recording_id=str(row["recording_id"]),
                    normalized_title=row["normalized_title"],
                    normalized_artist_credit=normalize_artist_credit(
                        [a for a in row["artist_names"]]
                    ),
                    length_ms=row["length_ms"],
                )
                for row in rows
            ]

        match = resolve_recording(
            title=candidate.title,
            artist_names=[a.name for a in candidate.artists],
            length_ms=candidate.length_ms,
            isrc=candidate.isrc,
            isrc_lookup=isrc_lookup,
            metadata_candidates_lookup=metadata_candidates_lookup,
        )
        if match is None:
            return None
        return ResolvedRecording(
            recording_id=match.recording_id,
            title=candidate.title,
            artists=candidate.artists,
            isrc=candidate.isrc,
            length_ms=candidate.length_ms,
        )

    async def get_recording_metadata(self, source_id: str) -> CatalogCandidate | None:
        row = self._session.execute(
            text(
                "select r.id, r.title, r.length_ms, array_agg(a.name order by ra.credit_order) as artist_names "
                "from recording r "
                "join recording_artists ra on ra.recording_id = r.id "
                "join artist a on a.id = ra.artist_id "
                "where r.id = :id group by r.id, r.title, r.length_ms"
            ),
            {"id": source_id},
        ).mappings().first()
        if row is None:
            return None
        return CatalogCandidate(
            source=self.source_id,
            source_id=str(row["id"]),
            title=row["title"],
            artists=[ArtistCredit(name=name) for name in row["artist_names"]],
            length_ms=row["length_ms"],
        )

    async def lookup_isrc(self, isrc: str) -> list[CatalogCandidate]:
        rows = self._session.execute(_ISRC_LOOKUP_SQL, {"isrc": isrc}).mappings().all()
        return [
            CatalogCandidate(
                source=self.source_id,
                source_id=str(row["recording_id"]),
                title=row["title"],
                artists=[ArtistCredit(name=name) for name in row["artist_names"]],
                length_ms=row["length_ms"],
                isrc=isrc,
            )
            for row in rows
        ]

    async def lookup_external_ids(self, source_id: str) -> dict[str, str]:
        rows = self._session.execute(_EXTERNAL_IDS_SQL, {"recording_id": source_id}).mappings().all()
        return {row["id_type"]: row["value"] for row in rows}
