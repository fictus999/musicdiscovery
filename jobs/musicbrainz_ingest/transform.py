"""Staged MusicBrainz rows -> canonical tables.

Foreign-key resolution (MusicBrainz's internal integer ids -> our
canonical UUIDs) goes through `mb_staging.id_map`, a persistent SQL table,
not a Python dict — at MusicBrainz's real scale (~38.7M recordings as of
a May 2026 snapshot) an in-process id map for every entity type would be
multiple GB of Python object overhead for no reason when Postgres can just
join on it. Text normalization (normalized_title/normalized_name) reuses
the same tested functions the live search path uses
(app/catalog/normalize.py) rather than re-implementing it in SQL — a
second normalization implementation that could silently drift from the
first is worse than the extra round-trip through Python.

Transform order matters: each step's foreign keys must already be in
id_map before it runs. See transform_all() for the dependency order.
"""

import logging
from collections.abc import Iterator

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.catalog.normalize import normalize_artist, normalize_title

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 5000


def ensure_id_map_table(conn: Connection, staging_schema: str) -> None:
    conn.execute(
        text(
            f"create table if not exists {staging_schema}.id_map ("
            "entity_type text not null, source_id integer not null, "
            "canonical_id uuid not null, primary key (entity_type, source_id))"
        )
    )


def _iter_batches(conn: Connection, query: str, batch_size: int) -> Iterator[list[dict]]:
    # execution_options() goes on the *statement*, not the Connection —
    # Connection.execution_options() mutates the connection itself and
    # returns it (unlike Engine.execution_options(), which returns a new
    # object), so setting stream_results there would make every later
    # INSERT on this same connection try to open a server-side cursor too
    # (and Postgres can't DECLARE CURSOR FOR an INSERT).
    statement = text(query).execution_options(stream_results=True, yield_per=batch_size)
    result = conn.execute(statement)
    batch = []
    for row in result.mappings():
        batch.append(dict(row))
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _populate_id_map(conn: Connection, staging_schema: str, entity_type: str, staging_table: str) -> None:
    conn.execute(
        text(
            f"insert into {staging_schema}.id_map (entity_type, source_id, canonical_id) "
            f"select :entity_type, s.id, c.id "
            f"from {staging_schema}.{staging_table} s "
            f"join {entity_type} c on c.mbid = s.gid "
            f"on conflict (entity_type, source_id) do update set canonical_id = excluded.canonical_id"
        ),
        {"entity_type": entity_type},
    )


def transform_artists(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    total = 0
    for batch in _iter_batches(
        conn, f"select id, gid, name, sort_name, comment from {staging_schema}.artist", batch_size
    ):
        rows = [
            {
                "mbid": r["gid"],
                "name": r["name"],
                "sort_name": r["sort_name"],
                "normalized_name": normalize_artist(r["name"]),
                "disambiguation": r["comment"] or None,
            }
            for r in batch
        ]
        conn.execute(
            text(
                "insert into artist (mbid, name, sort_name, normalized_name, disambiguation) "
                "values (:mbid, :name, :sort_name, :normalized_name, :disambiguation) "
                "on conflict (mbid) do update set name = excluded.name, sort_name = excluded.sort_name, "
                "normalized_name = excluded.normalized_name, disambiguation = excluded.disambiguation, "
                "updated_at = now()"
            ),
            rows,
        )
        total += len(rows)
    _populate_id_map(conn, staging_schema, "artist", "artist")
    logger.info("transformed %s artists", total)
    return total


def transform_artist_credits(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    total = 0
    for batch in _iter_batches(conn, f"select id, gid, name from {staging_schema}.artist_credit", batch_size):
        rows = [{"mbid": r["gid"], "name": r["name"]} for r in batch]
        conn.execute(
            text(
                "insert into artist_credit (mbid, name) values (:mbid, :name) "
                "on conflict (mbid) do update set name = excluded.name"
            ),
            rows,
        )
        total += len(rows)
    _populate_id_map(conn, staging_schema, "artist_credit", "artist_credit")
    logger.info("transformed %s artist_credits", total)
    return total


def transform_artist_credit_names(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    total = 0
    for batch in _iter_batches(
        conn,
        f"""
        select acn.artist_credit, acn.position, acn.name, acn.join_phrase,
               ac_map.canonical_id as artist_credit_id,
               a_map.canonical_id as artist_id
        from {staging_schema}.artist_credit_name acn
        join {staging_schema}.id_map ac_map
          on ac_map.entity_type = 'artist_credit' and ac_map.source_id = acn.artist_credit
        join {staging_schema}.id_map a_map
          on a_map.entity_type = 'artist' and a_map.source_id = acn.artist
        """,
        batch_size,
    ):
        conn.execute(
            text(
                "insert into artist_credit_name (artist_credit_id, position, artist_id, name, join_phrase) "
                "values (:artist_credit_id, :position, :artist_id, :name, :join_phrase) "
                "on conflict (artist_credit_id, position) do update set "
                "artist_id = excluded.artist_id, name = excluded.name, join_phrase = excluded.join_phrase"
            ),
            batch,
        )
        total += len(batch)
    logger.info("transformed %s artist_credit_names", total)
    return total


def transform_release_groups(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    total = 0
    for batch in _iter_batches(
        conn,
        f"""
        select rg.id, rg.gid, rg.name, rgt.name as primary_type,
               ac_map.canonical_id as artist_credit_id,
               meta.first_release_date_year, meta.first_release_date_month, meta.first_release_date_day
        from {staging_schema}.release_group rg
        left join {staging_schema}.release_group_primary_type rgt on rgt.id = rg.type
        left join {staging_schema}.release_group_meta meta on meta.id = rg.id
        join {staging_schema}.id_map ac_map
          on ac_map.entity_type = 'artist_credit' and ac_map.source_id = rg.artist_credit
        """,
        batch_size,
    ):
        rows = [
            {
                "mbid": r["gid"],
                "artist_credit_id": r["artist_credit_id"],
                "title": r["name"],
                "normalized_title": normalize_title(r["name"]),
                "primary_type": r["primary_type"],
                "first_release_date_year": r["first_release_date_year"],
                "first_release_date_month": r["first_release_date_month"],
                "first_release_date_day": r["first_release_date_day"],
            }
            for r in batch
        ]
        conn.execute(
            text(
                "insert into release_group "
                "(mbid, artist_credit_id, title, normalized_title, primary_type, "
                " first_release_date_year, first_release_date_month, first_release_date_day) "
                "values (:mbid, :artist_credit_id, :title, :normalized_title, :primary_type, "
                " :first_release_date_year, :first_release_date_month, :first_release_date_day) "
                "on conflict (mbid) do update set title = excluded.title, "
                "normalized_title = excluded.normalized_title, primary_type = excluded.primary_type, "
                "first_release_date_year = excluded.first_release_date_year, "
                "first_release_date_month = excluded.first_release_date_month, "
                "first_release_date_day = excluded.first_release_date_day, updated_at = now()"
            ),
            rows,
        )
        total += len(rows)
    _populate_id_map(conn, staging_schema, "release_group", "release_group")
    logger.info("transformed %s release_groups", total)
    return total


def transform_releases(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    total = 0
    for batch in _iter_batches(
        conn,
        f"""
        select rel.id, rel.gid, rel.name, rel.barcode,
               rs.name as status, lang.iso_code_3 as language,
               ac_map.canonical_id as artist_credit_id,
               rg_map.canonical_id as release_group_id
        from {staging_schema}.release rel
        left join {staging_schema}.release_status rs on rs.id = rel.status
        left join {staging_schema}.language lang on lang.id = rel.language
        join {staging_schema}.id_map ac_map
          on ac_map.entity_type = 'artist_credit' and ac_map.source_id = rel.artist_credit
        join {staging_schema}.id_map rg_map
          on rg_map.entity_type = 'release_group' and rg_map.source_id = rel.release_group
        """,
        batch_size,
    ):
        rows = [
            {
                "mbid": r["gid"],
                "artist_credit_id": r["artist_credit_id"],
                "release_group_id": r["release_group_id"],
                "title": r["name"],
                "normalized_title": normalize_title(r["name"]),
                "status": r["status"],
                "language": r["language"],
                "barcode": r["barcode"],
            }
            for r in batch
        ]
        conn.execute(
            text(
                "insert into release "
                "(mbid, artist_credit_id, release_group_id, title, normalized_title, status, language, barcode) "
                "values (:mbid, :artist_credit_id, :release_group_id, :title, :normalized_title, "
                " :status, :language, :barcode) "
                "on conflict (mbid) do update set title = excluded.title, "
                "normalized_title = excluded.normalized_title, status = excluded.status, "
                "language = excluded.language, barcode = excluded.barcode, updated_at = now()"
            ),
            rows,
        )
        total += len(rows)
    _populate_id_map(conn, staging_schema, "release", "release")
    logger.info("transformed %s releases", total)
    return total


def transform_media(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    total = 0
    for batch in _iter_batches(
        conn,
        f"""
        select m.id, m.gid, m.position, m.track_count, rel_map.canonical_id as release_id
        from {staging_schema}.medium m
        join {staging_schema}.id_map rel_map
          on rel_map.entity_type = 'release' and rel_map.source_id = m.release
        """,
        batch_size,
    ):
        rows = [
            {
                "mbid": r["gid"],
                "release_id": r["release_id"],
                "position": r["position"],
                "track_count": r["track_count"],
            }
            for r in batch
        ]
        conn.execute(
            text(
                "insert into medium (mbid, release_id, position, track_count) "
                "values (:mbid, :release_id, :position, :track_count) "
                "on conflict (mbid) do update set position = excluded.position, "
                "track_count = excluded.track_count"
            ),
            rows,
        )
        total += len(rows)
    _populate_id_map(conn, staging_schema, "medium", "medium")
    logger.info("transformed %s media", total)
    return total


def transform_recordings(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    total = 0
    for batch in _iter_batches(
        conn,
        f"""
        select rec.id, rec.gid, rec.name, rec.length, rec.video,
               ac_map.canonical_id as artist_credit_id
        from {staging_schema}.recording rec
        join {staging_schema}.id_map ac_map
          on ac_map.entity_type = 'artist_credit' and ac_map.source_id = rec.artist_credit
        """,
        batch_size,
    ):
        rows = [
            {
                "mbid": r["gid"],
                "artist_credit_id": r["artist_credit_id"],
                "title": r["name"],
                "normalized_title": normalize_title(r["name"]),
                "length_ms": r["length"],
                "video": r["video"],
            }
            for r in batch
        ]
        conn.execute(
            text(
                "insert into recording (mbid, artist_credit_id, title, normalized_title, length_ms, video) "
                "values (:mbid, :artist_credit_id, :title, :normalized_title, :length_ms, :video) "
                "on conflict (mbid) do update set title = excluded.title, "
                "normalized_title = excluded.normalized_title, length_ms = excluded.length_ms, "
                "video = excluded.video, updated_at = now()"
            ),
            rows,
        )
        total += len(rows)
    _populate_id_map(conn, staging_schema, "recording", "recording")
    logger.info("transformed %s recordings", total)
    return total


def transform_tracks(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    total = 0
    for batch in _iter_batches(
        conn,
        f"""
        select t.id, t.gid, t.position, t.number, t.name, t.length,
               med_map.canonical_id as medium_id,
               rec_map.canonical_id as recording_id,
               ac_map.canonical_id as artist_credit_id
        from {staging_schema}.track t
        join {staging_schema}.id_map med_map
          on med_map.entity_type = 'medium' and med_map.source_id = t.medium
        join {staging_schema}.id_map rec_map
          on rec_map.entity_type = 'recording' and rec_map.source_id = t.recording
        join {staging_schema}.id_map ac_map
          on ac_map.entity_type = 'artist_credit' and ac_map.source_id = t.artist_credit
        """,
        batch_size,
    ):
        rows = [
            {
                "mbid": r["gid"],
                "medium_id": r["medium_id"],
                "recording_id": r["recording_id"],
                "position": r["position"],
                "number": r["number"],
                "title": r["name"],
                "artist_credit_id": r["artist_credit_id"],
                "length_ms": r["length"],
            }
            for r in batch
        ]
        conn.execute(
            text(
                "insert into track "
                "(mbid, medium_id, recording_id, position, number, title, artist_credit_id, length_ms) "
                "values "
                "(:mbid, :medium_id, :recording_id, :position, :number, :title, :artist_credit_id, :length_ms) "
                "on conflict (mbid) do update set position = excluded.position, "
                "title = excluded.title, length_ms = excluded.length_ms"
            ),
            rows,
        )
        total += len(rows)
    logger.info("loaded %s tracks", total)
    return total


def transform_works(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    total = 0
    for batch in _iter_batches(conn, f"select id, gid, name from {staging_schema}.work", batch_size):
        rows = [
            {"mbid": r["gid"], "title": r["name"], "normalized_title": normalize_title(r["name"])}
            for r in batch
        ]
        conn.execute(
            text(
                "insert into work (mbid, title, normalized_title) "
                "values (:mbid, :title, :normalized_title) "
                "on conflict (mbid) do update set title = excluded.title, "
                "normalized_title = excluded.normalized_title, updated_at = now()"
            ),
            rows,
        )
        total += len(rows)
    _populate_id_map(conn, staging_schema, "work", "work")
    logger.info("transformed %s works", total)
    return total


def transform_isrc(conn: Connection, staging_schema: str) -> int:
    result = conn.execute(
        text(
            f"insert into recording_external_ids (recording_id, id_type, value, verified) "
            f"select rec_map.canonical_id, 'isrc', i.isrc, true "
            f"from {staging_schema}.isrc i "
            f"join {staging_schema}.id_map rec_map "
            f"  on rec_map.entity_type = 'recording' and rec_map.source_id = i.recording "
            f"on conflict (id_type, value) do nothing"
        )
    )
    logger.info("loaded %s ISRCs", result.rowcount)
    return result.rowcount


def transform_iswc(conn: Connection, staging_schema: str) -> int:
    result = conn.execute(
        text(
            f"insert into work_external_ids (work_id, id_type, value, verified) "
            f"select work_map.canonical_id, 'iswc', i.iswc, true "
            f"from {staging_schema}.iswc i "
            f"join {staging_schema}.id_map work_map "
            f"  on work_map.entity_type = 'work' and work_map.source_id = i.work "
            f"where i.iswc is not null "
            f"on conflict (id_type, value) do nothing"
        )
    )
    logger.info("loaded %s ISWCs", result.rowcount)
    return result.rowcount


def transform_recording_works(conn: Connection, staging_schema: str) -> int:
    result = conn.execute(
        text(
            f"insert into recording_works (recording_id, work_id) "
            f"select distinct rec_map.canonical_id, work_map.canonical_id "
            f"from {staging_schema}.l_recording_work lrw "
            f"join {staging_schema}.id_map rec_map "
            f"  on rec_map.entity_type = 'recording' and rec_map.source_id = lrw.entity0 "
            f"join {staging_schema}.id_map work_map "
            f"  on work_map.entity_type = 'work' and work_map.source_id = lrw.entity1 "
            f"on conflict do nothing"
        )
    )
    logger.info("loaded %s recording-work relationships", result.rowcount)
    return result.rowcount


def transform_all(conn: Connection, staging_schema: str, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, int]:
    """Runs every transform step in dependency order. Each step's foreign
    keys must already be resolvable in id_map before it runs — this order
    is load-bearing, not arbitrary.
    """
    ensure_id_map_table(conn, staging_schema)
    counts = {}
    counts["artist"] = transform_artists(conn, staging_schema, batch_size)
    counts["artist_credit"] = transform_artist_credits(conn, staging_schema, batch_size)
    counts["artist_credit_name"] = transform_artist_credit_names(conn, staging_schema, batch_size)
    counts["release_group"] = transform_release_groups(conn, staging_schema, batch_size)
    counts["release"] = transform_releases(conn, staging_schema, batch_size)
    counts["medium"] = transform_media(conn, staging_schema, batch_size)
    counts["recording"] = transform_recordings(conn, staging_schema, batch_size)
    counts["track"] = transform_tracks(conn, staging_schema, batch_size)
    counts["work"] = transform_works(conn, staging_schema, batch_size)
    counts["isrc"] = transform_isrc(conn, staging_schema)
    counts["iswc"] = transform_iswc(conn, staging_schema)
    counts["recording_works"] = transform_recording_works(conn, staging_schema)
    return counts
