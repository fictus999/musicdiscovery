from sqlalchemy import text

from app.catalog.normalize import normalize_artist, normalize_title
from app.providers.musicbrainz_catalog_provider import MusicBrainzCatalogProvider
from provider_types import CatalogCandidate, ArtistCredit


def _seed_recording(session, *, title: str, artist_name: str, length_ms: int, isrc: str | None = None):
    artist_id = session.execute(
        text(
            "insert into artist (name, normalized_name) values (:name, :norm) returning id"
        ),
        {"name": artist_name, "norm": normalize_artist(artist_name)},
    ).scalar_one()
    artist_credit_id = session.execute(
        text("insert into artist_credit (name) values (:name) returning id"),
        {"name": artist_name},
    ).scalar_one()
    session.execute(
        text(
            "insert into artist_credit_name (artist_credit_id, position, artist_id, name) "
            "values (:acid, 0, :aid, :name)"
        ),
        {"acid": artist_credit_id, "aid": artist_id, "name": artist_name},
    )
    recording_id = session.execute(
        text(
            "insert into recording (artist_credit_id, title, normalized_title, length_ms) "
            "values (:acid, :title, :norm, :length_ms) returning id"
        ),
        {"acid": artist_credit_id, "title": title, "norm": normalize_title(title), "length_ms": length_ms},
    ).scalar_one()
    if isrc:
        session.execute(
            text(
                "insert into recording_external_ids (recording_id, id_type, value, verified) "
                "values (:rid, 'isrc', :isrc, true)"
            ),
            {"rid": recording_id, "isrc": isrc},
        )
    session.commit()
    return str(recording_id)


async def test_search_matches_on_title_and_artist(db_session):
    _seed_recording(db_session, title="Nights", artist_name="Frank Ocean", length_ms=307000)
    _seed_recording(db_session, title="Solo", artist_name="Frank Ocean", length_ms=257000)
    _seed_recording(db_session, title="Nightcall", artist_name="Kavinsky", length_ms=257000)

    provider = MusicBrainzCatalogProvider(db_session)
    result = await provider.search("nights")

    titles = {c.title for c in result.candidates}
    assert "Nights" in titles
    # "Nightcall" is trigram-similar to "nights" too — that's expected/fine,
    # what matters is the exact match ranks and isn't silently dropped.
    assert result.candidates[0].title == "Nights"


async def test_search_matches_on_artist_name(db_session):
    _seed_recording(db_session, title="Pyramids", artist_name="Frank Ocean", length_ms=600000)

    provider = MusicBrainzCatalogProvider(db_session)
    result = await provider.search("frank ocean")

    assert any(c.title == "Pyramids" for c in result.candidates)


async def test_lookup_isrc_finds_verified_recording(db_session):
    recording_id = _seed_recording(
        db_session, title="Nights", artist_name="Frank Ocean", length_ms=307000, isrc="USRC17607839"
    )

    provider = MusicBrainzCatalogProvider(db_session)
    candidates = await provider.lookup_isrc("USRC17607839")

    assert len(candidates) == 1
    assert candidates[0].source_id == recording_id


async def test_resolve_identity_prefers_isrc_over_metadata(db_session):
    recording_id = _seed_recording(
        db_session, title="Nights", artist_name="Frank Ocean", length_ms=307000, isrc="USRC17607839"
    )
    # Seed a decoy with near-identical metadata but no ISRC, to prove ISRC
    # match wins rather than an accidental metadata-fallback hit.
    _seed_recording(db_session, title="Nights", artist_name="Someone Else", length_ms=307000)

    provider = MusicBrainzCatalogProvider(db_session)
    candidate = CatalogCandidate(
        source="spotify",
        source_id="spotify-track-xyz",
        title="Nights",
        artists=[ArtistCredit(name="Frank Ocean")],
        length_ms=307000,
        isrc="USRC17607839",
    )
    resolved = await provider.resolve_identity(candidate)

    assert resolved is not None
    assert resolved.recording_id == recording_id


async def test_resolve_identity_returns_none_for_unmatched_candidate(db_session):
    _seed_recording(db_session, title="Nights", artist_name="Frank Ocean", length_ms=307000)

    provider = MusicBrainzCatalogProvider(db_session)
    candidate = CatalogCandidate(
        source="spotify",
        source_id="spotify-track-unrelated",
        title="A Completely Different Song",
        artists=[ArtistCredit(name="Nobody Related")],
        length_ms=123000,
    )
    resolved = await provider.resolve_identity(candidate)

    assert resolved is None


async def test_lookup_external_ids_returns_isrc(db_session):
    recording_id = _seed_recording(
        db_session, title="Nights", artist_name="Frank Ocean", length_ms=307000, isrc="USRC17607839"
    )

    provider = MusicBrainzCatalogProvider(db_session)
    ids = await provider.lookup_external_ids(recording_id)

    assert ids == {"isrc": "USRC17607839"}
