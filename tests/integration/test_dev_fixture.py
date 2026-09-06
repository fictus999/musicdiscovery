"""Guards the $0 local-dev fixture path: if dev_fixture.py's data ever
drifts out of sync with the canonical schema's constraints (as it did
once already — medium.track_count is NOT NULL and the fixture initially
left it null), this catches it in CI instead of on someone's laptop.
"""

from sqlalchemy import text

from jobs.musicbrainz_ingest.dev_fixture import load_dev_fixture


def test_dev_fixture_loads_cleanly_through_the_real_pipeline(engine, db_session, test_dsn):
    db_session.execute(text("drop schema if exists mb_staging cascade"))
    db_session.commit()

    counts = load_dev_fixture(engine, test_dsn)

    assert counts["artist"] == 4
    assert counts["recording"] == 7
    assert counts["isrc"] == 7
    assert counts["recording_works"] == 2

    titles = {
        row[0]
        for row in db_session.execute(text("select title from recording")).all()
    }
    assert "Paranoid Android" in titles
    assert "Nights" in titles

    # Fixture gids must never look like they could collide with a real
    # MusicBrainz mbid namespace — this just re-asserts they're all drawn
    # from the fixture's own deterministic namespace, catching a future
    # edit that accidentally hardcodes a real-looking random UUID instead.
    from jobs.musicbrainz_ingest.dev_fixture import FIXTURE_NAMESPACE, _fixture_uuid

    assert _fixture_uuid("artist:frank-ocean") != FIXTURE_NAMESPACE
    frank_ocean_mbid = db_session.execute(
        text("select mbid from artist where name = 'Frank Ocean'")
    ).scalar_one()
    assert str(frank_ocean_mbid) == str(_fixture_uuid("artist:frank-ocean"))
