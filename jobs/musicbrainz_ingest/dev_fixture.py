"""A small, hand-authored MusicBrainz-shaped dataset for $0 local
development — NOT a verified extract from live MusicBrainz.

Honesty note: `musicbrainz.org` (both its docs and its `/ws/2/` web
service API) is blocked by this environment's network egress policy, so
this fixture could not be pulled from the live API the way a real
ingestion would. It uses real, well-known, easily fact-checkable
artist/song/album names (chosen because they're unambiguous enough that
getting them right from general knowledge is low-risk), but:

- Every `gid` (the field that holds a real MusicBrainz mbid in production)
  is a **deterministic synthetic UUID** derived from `FIXTURE_NAMESPACE`,
  not a real MusicBrainz identifier — see `_fixture_uuid`. Never write
  code that assumes a fixture-loaded row's `mbid` came from MusicBrainz.
- ISRCs and the one ISWC below are **fabricated in valid format** using
  the `QZ`/reserved-for-example prefix pattern, not real registered codes.
- Release dates are year-only (no month/day) wherever this fixture isn't
  confident enough in a specific day to state one without verification.

This exists to exercise the real ingestion pipeline (`staging.py` +
`transform.py`) end-to-end against something more realistic than the 1-2
rows individual unit tests seed, not to stand in for a genuine MusicBrainz
sample. Replace it with a real small extract (pulled by someone with
actual network access to musicbrainz.org, respecting the ~1req/sec rate
limit) once that's practical — see docs/phase-0-checklist.md item 9.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine

FIXTURE_NAMESPACE = uuid.UUID("f6b5b8c0-6b1a-4b1a-9b1a-6b1a4b1a9b1a")


def _fixture_uuid(key: str) -> uuid.UUID:
    return uuid.uuid5(FIXTURE_NAMESPACE, key)


ARTISTS = [
    {"id": 1, "gid": _fixture_uuid("artist:frank-ocean"), "name": "Frank Ocean", "sort_name": "Ocean, Frank"},
    {"id": 2, "gid": _fixture_uuid("artist:radiohead"), "name": "Radiohead", "sort_name": "Radiohead"},
    {"id": 3, "gid": _fixture_uuid("artist:daft-punk"), "name": "Daft Punk", "sort_name": "Daft Punk"},
    {"id": 4, "gid": _fixture_uuid("artist:tame-impala"), "name": "Tame Impala", "sort_name": "Tame Impala"},
]

ARTIST_CREDITS = [
    {"id": i, "gid": _fixture_uuid(f"artist_credit:{a['name']}"), "name": a["name"]}
    for i, a in enumerate(ARTISTS, start=1)
]

ARTIST_CREDIT_NAMES = [
    {"artist_credit": i, "position": 0, "artist": i, "name": a["name"], "join_phrase": ""}
    for i, a in enumerate(ARTISTS, start=1)
]

RELEASE_GROUP_PRIMARY_TYPES = [{"id": 1, "name": "Album"}]

# (release_group id, title, artist_credit id, first_release_year)
_RELEASE_GROUPS = [
    (1, "Blonde", 1, 2016),
    (2, "OK Computer", 2, 1997),
    (3, "Discovery", 3, 2001),
    (4, "Currents", 4, 2015),
]

RELEASE_GROUPS = [
    {
        "id": rg_id,
        "gid": _fixture_uuid(f"release_group:{title}"),
        "name": title,
        "artist_credit": ac_id,
        "type": 1,
    }
    for rg_id, title, ac_id, _year in _RELEASE_GROUPS
]

RELEASE_GROUP_META = [
    {"id": rg_id, "release_count": 1, "first_release_date_year": year, "first_release_date_month": None, "first_release_date_day": None}
    for rg_id, _title, _ac_id, year in _RELEASE_GROUPS
]

RELEASE_STATUSES = [{"id": 1, "name": "Official"}]
LANGUAGES = [{"id": 1, "iso_code_3": "eng", "name": "English"}]

RELEASES = [
    {
        "id": rg_id,
        "gid": _fixture_uuid(f"release:{title}"),
        "name": title,
        "artist_credit": ac_id,
        "release_group": rg_id,
        "status": 1,
        "language": 1,
        "barcode": None,
    }
    for rg_id, title, ac_id, _year in _RELEASE_GROUPS
]

_TRACK_COUNT_BY_MEDIUM = {1: 2, 2: 2, 3: 2, 4: 1}

MEDIA = [
    {
        "id": rg_id,
        "gid": _fixture_uuid(f"medium:{title}"),
        "release": rg_id,
        "position": 1,
        "track_count": _TRACK_COUNT_BY_MEDIUM[rg_id],
    }
    for rg_id, title, _ac_id, _year in _RELEASE_GROUPS
]

# (recording id, title, artist_credit id, length_ms, medium id, track position)
_RECORDINGS = [
    (1, "Nights", 1, 307_000, 1, 1),
    (2, "Pink + White", 1, 185_000, 1, 2),
    (3, "Paranoid Android", 2, 387_000, 2, 1),
    (4, "Karma Police", 2, 261_000, 2, 2),
    (5, "One More Time", 3, 320_000, 3, 1),
    (6, "Digital Love", 3, 300_000, 3, 2),
    (7, "The Less I Know The Better", 4, 216_000, 4, 1),
]

RECORDINGS = [
    {
        "id": rec_id,
        "gid": _fixture_uuid(f"recording:{title}"),
        "name": title,
        "artist_credit": ac_id,
        "length": length_ms,
        "video": False,
    }
    for rec_id, title, ac_id, length_ms, _medium_id, _position in _RECORDINGS
]

TRACKS = [
    {
        "id": rec_id,
        "gid": _fixture_uuid(f"track:{title}"),
        "recording": rec_id,
        "medium": medium_id,
        "position": position,
        "number": str(position),
        "name": title,
        "artist_credit": ac_id,
        "length": length_ms,
    }
    for rec_id, title, ac_id, length_ms, medium_id, position in _RECORDINGS
]

# Only Nights and Paranoid Android get a linked work, to exercise
# recording_works/ISWC without claiming every recording has one on record.
WORKS = [
    {"id": 1, "gid": _fixture_uuid("work:nights"), "name": "Nights"},
    {"id": 2, "gid": _fixture_uuid("work:paranoid-android"), "name": "Paranoid Android"},
]

# Fabricated, valid-format, obviously-fake identifiers (QZ is ISO 3166's
# reserved-for-example/user-assigned range) — never real registered codes.
ISRCS = [
    {"id": 1, "recording": 1, "isrc": "QZFIX2600001"},
    {"id": 2, "recording": 2, "isrc": "QZFIX2600002"},
    {"id": 3, "recording": 3, "isrc": "QZFIX2600003"},
    {"id": 4, "recording": 4, "isrc": "QZFIX2600004"},
    {"id": 5, "recording": 5, "isrc": "QZFIX2600005"},
    {"id": 6, "recording": 6, "isrc": "QZFIX2600006"},
    {"id": 7, "recording": 7, "isrc": "QZFIX2600007"},
]

ISWCS = [{"id": 1, "work": 1, "iswc": "T-000000001-0"}]

RECORDING_WORKS = [
    {"id": 1, "link": 1, "entity0": 1, "entity1": 1},  # Nights (recording) -> Nights (work)
    {"id": 2, "link": 1, "entity0": 3, "entity1": 2},  # Paranoid Android (recording) -> (work)
]


def _insert_rows(conn, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in columns)
    conn.execute(
        text(f"insert into mb_staging.{table} ({', '.join(columns)}) values ({placeholders})"),
        rows,
    )


def stage_fixture(conn) -> None:
    """Populates mb_staging with the fixture data. Caller is responsible
    for ensure_staging_schema() having already run (see staging.py) and
    for the schema being empty of conflicting ids (fresh dev DB, or call
    this once).
    """
    _insert_rows(conn, "artist", ARTISTS)
    _insert_rows(conn, "artist_credit", ARTIST_CREDITS)
    _insert_rows(conn, "artist_credit_name", ARTIST_CREDIT_NAMES)
    _insert_rows(conn, "release_group_primary_type", RELEASE_GROUP_PRIMARY_TYPES)
    _insert_rows(conn, "release_group", RELEASE_GROUPS)
    _insert_rows(conn, "release_group_meta", RELEASE_GROUP_META)
    _insert_rows(conn, "release_status", RELEASE_STATUSES)
    _insert_rows(conn, "language", LANGUAGES)
    _insert_rows(conn, "release", RELEASES)
    _insert_rows(conn, "medium", MEDIA)
    _insert_rows(conn, "recording", RECORDINGS)
    _insert_rows(conn, "track", TRACKS)
    _insert_rows(conn, "work", WORKS)
    _insert_rows(conn, "isrc", ISRCS)
    _insert_rows(conn, "iswc", ISWCS)
    _insert_rows(conn, "l_recording_work", RECORDING_WORKS)


def load_dev_fixture(engine: Engine, dsn: str, staging_schema: str = "mb_staging") -> dict[str, int]:
    """Stages the fixture and runs it through the real transform pipeline
    (transform_all) — the same code path production ingestion uses, just
    pointed at ~30 hand-authored rows instead of a real dump. Returns the
    transform's row counts per table.

    `engine` is a SQLAlchemy engine (used for transform_all, which runs
    ORM-agnostic SQL through a Connection); `dsn` is a plain psycopg-style
    connection string (used by staging.ensure_staging_schema, which talks
    to psycopg directly for the schema/table DDL) — these are deliberately
    separate parameters rather than one derived from the other, because
    `str(engine.url)` masks the password and keeps SQLAlchemy's
    `+psycopg` dialect suffix, neither of which psycopg.connect() accepts.
    """
    from .staging import ensure_staging_schema
    from .transform import transform_all
    from .config import IngestConfig

    ensure_staging_schema(dsn, IngestConfig())
    with engine.begin() as conn:
        stage_fixture(conn)
        return transform_all(conn, staging_schema)


if __name__ == "__main__":
    import os
    from sqlalchemy import create_engine

    dsn = os.environ.get(
        "DATABASE_URL", "postgresql://musicdiscovery:musicdiscovery@localhost:5432/musicdiscovery"
    )
    engine = create_engine(
        f"postgresql+psycopg://{dsn.split('://', 1)[1]}",
        connect_args={"options": "-c search_path=music_catalog,app,public"},
    )
    counts = load_dev_fixture(engine, dsn)
    print(f"loaded dev fixture: {counts}")
