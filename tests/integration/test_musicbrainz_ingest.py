"""Validates the ingestion transform end-to-end against small synthetic
staging data, standing in for a real `COPY`-loaded MusicBrainz dump (which
this sandbox has neither the network access nor the disk budget to
download). This is the load-bearing test for jobs/musicbrainz_ingest —
if the FK-resolution-via-id_map and normalization logic has a bug, it
shows up here, not three transform steps later against real data.
"""

import uuid

import pytest
from sqlalchemy import text

from app.db.repository import get_ranking_features, get_song_dto
from jobs.musicbrainz_ingest.staging import ensure_staging_schema
from jobs.musicbrainz_ingest.transform import transform_all
from jobs.musicbrainz_ingest.config import IngestConfig

TEST_DSN = "postgresql://postgres:postgres@localhost:5432/musicdiscovery_test"


@pytest.fixture(autouse=True)
def clean_staging_schema(db_session):
    # mb_staging is created/populated through a separate psycopg connection
    # (ensure_staging_schema, copy_table_from_file), not the SQLAlchemy
    # session conftest.py's db_session fixture cleans up — so it needs its
    # own teardown rather than relying on the shared truncate list.
    db_session.execute(text("drop schema if exists mb_staging cascade"))
    db_session.commit()
    yield


def _seed_staging(session):
    artist_gid = uuid.uuid4()
    artist_credit_gid = uuid.uuid4()
    release_group_gid = uuid.uuid4()
    release_gid = uuid.uuid4()
    medium_gid = uuid.uuid4()
    recording_gid = uuid.uuid4()
    track_gid = uuid.uuid4()
    work_gid = uuid.uuid4()

    session.execute(
        text(
            "insert into mb_staging.artist (id, gid, name, sort_name, comment) "
            "values (1, :gid, 'Frank Ocean', 'Ocean, Frank', '')"
        ),
        {"gid": artist_gid},
    )
    session.execute(
        text("insert into mb_staging.artist_credit (id, gid, name) values (1, :gid, 'Frank Ocean')"),
        {"gid": artist_credit_gid},
    )
    session.execute(
        text(
            "insert into mb_staging.artist_credit_name "
            "(artist_credit, position, artist, name, join_phrase) "
            "values (1, 0, 1, 'Frank Ocean', '')"
        )
    )
    session.execute(text("insert into mb_staging.release_group_primary_type (id, name) values (1, 'Album')"))
    session.execute(
        text(
            "insert into mb_staging.release_group (id, gid, name, artist_credit, type, comment) "
            "values (1, :gid, 'Blonde', 1, 1, '')"
        ),
        {"gid": release_group_gid},
    )
    session.execute(
        text(
            "insert into mb_staging.release_group_meta "
            "(id, release_count, first_release_date_year, first_release_date_month, first_release_date_day) "
            "values (1, 1, 2016, 8, 20)"
        )
    )
    session.execute(text("insert into mb_staging.release_status (id, name) values (1, 'Official')"))
    session.execute(
        text("insert into mb_staging.language (id, iso_code_3, name) values (1, 'eng', 'English')")
    )
    session.execute(
        text(
            "insert into mb_staging.release "
            "(id, gid, name, artist_credit, release_group, status, language, barcode, comment) "
            "values (1, :gid, 'Blonde', 1, 1, 1, 1, null, '')"
        ),
        {"gid": release_gid},
    )
    session.execute(
        text(
            "insert into mb_staging.medium (id, gid, release, position, track_count, name) "
            "values (1, :gid, 1, 1, 1, '')"
        ),
        {"gid": medium_gid},
    )
    session.execute(
        text(
            "insert into mb_staging.recording (id, gid, name, artist_credit, length, video, comment) "
            "values (1, :gid, 'Nights', 1, 307000, false, '')"
        ),
        {"gid": recording_gid},
    )
    session.execute(
        text(
            "insert into mb_staging.track "
            "(id, gid, recording, medium, position, number, name, artist_credit, length) "
            "values (1, :gid, 1, 1, 1, '1', 'Nights', 1, 307000)"
        ),
        {"gid": track_gid},
    )
    session.execute(
        text("insert into mb_staging.work (id, gid, name, comment) values (1, :gid, 'Nights', '')"),
        {"gid": work_gid},
    )
    session.execute(text("insert into mb_staging.isrc (id, recording, isrc) values (1, 1, 'USRC17607839')"))
    session.execute(text("insert into mb_staging.iswc (id, work, iswc) values (1, 1, 'T-000000001-0')"))
    session.execute(
        text("insert into mb_staging.l_recording_work (id, link, entity0, entity1) values (1, 1, 1, 1)")
    )
    session.commit()


def test_transform_all_populates_canonical_tables_correctly(engine, db_session):
    ensure_staging_schema(TEST_DSN, IngestConfig())
    _seed_staging(db_session)

    with engine.begin() as conn:
        counts = transform_all(conn, "mb_staging")

    assert counts["artist"] == 1
    assert counts["recording"] == 1
    assert counts["track"] == 1

    recording_id = db_session.execute(text("select id from recording where title = 'Nights'")).scalar_one()

    song = get_song_dto(db_session, str(recording_id))
    assert song is not None
    assert song.artist_names == ["Frank Ocean"]

    features = get_ranking_features(db_session, str(recording_id))
    assert features is not None
    assert features.release_year == 2016
    assert features.language == "eng"
    assert len(features.artist_ids) == 1

    isrc_row = db_session.execute(
        text("select value from recording_external_ids where recording_id = :id and id_type = 'isrc'"),
        {"id": recording_id},
    ).first()
    assert isrc_row[0] == "USRC17607839"

    iswc_row = db_session.execute(
        text(
            "select we.value from work_external_ids we "
            "join work w on w.id = we.work_id where w.title = 'Nights' and we.id_type = 'iswc'"
        )
    ).first()
    assert iswc_row[0] == "T-000000001-0"

    recording_work_count = db_session.execute(
        text(
            "select count(*) from recording_works rw "
            "join recording r on r.id = rw.recording_id where r.title = 'Nights'"
        )
    ).scalar_one()
    assert recording_work_count == 1

    release_group_row = db_session.execute(
        text("select primary_type, first_release_date_year from release_group where title = 'Blonde'")
    ).first()
    assert release_group_row == ("Album", 2016)

    release_row = db_session.execute(
        text("select status, language from release where title = 'Blonde'")
    ).first()
    assert release_row == ("Official", "eng")


def test_transform_is_idempotent_on_rerun(engine, db_session):
    ensure_staging_schema(TEST_DSN, IngestConfig())
    _seed_staging(db_session)

    with engine.begin() as conn:
        transform_all(conn, "mb_staging")
    with engine.begin() as conn:
        counts = transform_all(conn, "mb_staging")

    # Re-running against the same staging data must upsert, not duplicate.
    assert counts["artist"] == 1
    total_artists = db_session.execute(text("select count(*) from artist")).scalar_one()
    assert total_artists == 1
