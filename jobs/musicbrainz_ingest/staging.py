"""Stages MusicBrainz dump files into `mb_staging`, a schema whose tables
match the REAL MusicBrainz column layout — verified against `mbdata`
(MetaBrainz's own SQLAlchemy schema mirror, pip package `mbdata==31.0.1`),
not assumed. This matters mechanically, not just for correctness: dump
files are raw `COPY`-format rows with no header, so a staging table's
column list must match the source table's real column order exactly, or
`COPY FROM` puts data in the wrong columns silently. Only the ~15 tables
Phase 1 needs are staged — this is a small slice of MusicBrainz's real
~300-table schema, not a full replica.

Two things are deliberately NOT staged, on purpose, not by oversight:
- MusicBrainz's tag/genre tables (`recording_tag`, `release_group_tag`,
  etc.) — that data is CC BY-NC-SA (non-commercial); ingesting it into a
  commercial product would violate the license. See docs/architecture.md.
- `release_country` (per-country release dates) — Phase 1's ranking only
  needs one approximate year, sourced from `release_group_meta` instead.
"""

import logging

import psycopg

from .config import IngestConfig

logger = logging.getLogger(__name__)

# table_name -> (full real column list in dump order, column type DDL)
# Column order and types verified against mbdata.models (see module docstring).
STAGING_TABLES: dict[str, str] = {
    "artist": """
        id integer primary key, gid uuid, name text, sort_name text,
        begin_date_year smallint, begin_date_month smallint, begin_date_day smallint,
        end_date_year smallint, end_date_month smallint, end_date_day smallint,
        type integer, area integer, gender integer, comment text,
        edits_pending integer, last_updated timestamptz, ended boolean,
        begin_area integer, end_area integer
    """,
    "artist_credit": """
        id integer primary key, name text, artist_count smallint,
        ref_count integer, created timestamptz, edits_pending integer, gid uuid
    """,
    "artist_credit_name": """
        artist_credit integer, position smallint, artist integer,
        name text, join_phrase text,
        primary key (artist_credit, position)
    """,
    "release_group_primary_type": """
        id integer primary key, name text, parent integer,
        child_order integer, description text, gid uuid
    """,
    "release_group": """
        id integer primary key, gid uuid, name text, artist_credit integer,
        type integer, comment text, edits_pending integer, last_updated timestamptz
    """,
    "release_group_meta": """
        id integer primary key, release_count integer,
        first_release_date_year smallint, first_release_date_month smallint,
        first_release_date_day smallint, rating smallint, rating_count integer
    """,
    "release_status": """
        id integer primary key, name text, parent integer,
        child_order integer, description text, gid uuid
    """,
    "language": """
        id integer primary key, iso_code_2t char(3), iso_code_2b char(3),
        iso_code_1 char(2), name text, frequency smallint, iso_code_3 char(3)
    """,
    "release": """
        id integer primary key, gid uuid, name text, artist_credit integer,
        release_group integer, status integer, packaging integer,
        language integer, script integer, barcode text, comment text,
        edits_pending integer, quality smallint, last_updated timestamptz
    """,
    "medium": """
        id integer primary key, release integer, position integer,
        format integer, name text, edits_pending integer,
        last_updated timestamptz, track_count integer, gid uuid
    """,
    "track": """
        id integer primary key, gid uuid, recording integer, medium integer,
        position integer, number text, name text, artist_credit integer,
        length integer, edits_pending integer, last_updated timestamptz,
        is_data_track boolean
    """,
    "recording": """
        id integer primary key, gid uuid, name text, artist_credit integer,
        length integer, comment text, edits_pending integer,
        last_updated timestamptz, video boolean
    """,
    "work": """
        id integer primary key, gid uuid, name text, type integer,
        comment text, edits_pending integer, last_updated timestamptz
    """,
    "work_language": """
        work integer, language integer, edits_pending integer, created timestamptz,
        primary key (work, language)
    """,
    "isrc": """
        id integer primary key, recording integer, isrc char(12),
        edits_pending integer, created timestamptz
    """,
    "iswc": """
        id integer primary key, work integer, iswc char(15),
        edits_pending integer, created timestamptz
    """,
    "l_recording_work": """
        id integer primary key, link integer, entity0 integer, entity1 integer,
        edits_pending integer, last_updated timestamptz, link_order integer,
        entity0_credit text, entity1_credit text
    """,
}


def ensure_staging_schema(dsn: str, config: IngestConfig) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(f"create schema if not exists {config.staging_schema}")
        for table, columns in STAGING_TABLES.items():
            conn.execute(f"create table if not exists {config.staging_schema}.{table} ({columns})")


def copy_table_from_file(dsn: str, config: IngestConfig, table: str, file_path: str) -> int:
    """Loads one dump file directly into its staging table via native
    `COPY FROM` — MusicBrainz's dump files are already in Postgres COPY
    text format, so this is the whole loading step; no per-row Python
    parsing. Returns the number of rows copied.
    """
    if table not in STAGING_TABLES:
        raise ValueError(f"no staging table declared for '{table}' — add it to STAGING_TABLES first")

    row_count = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            with cur.copy(f"COPY {config.staging_schema}.{table} FROM STDIN") as copy:
                with open(file_path, "rb") as f:
                    while chunk := f.read(1024 * 1024):
                        copy.write(chunk)
            row_count = cur.rowcount
        conn.commit()
    logger.info("staged %s rows into %s.%s", row_count, config.staging_schema, table)
    return row_count
