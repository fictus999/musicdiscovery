"""Load parsed dump rows into a `mb_staging` schema before touching the
canonical tables, so a bad transform run can be replayed from staging
without re-downloading or re-parsing the dump.

Depends on transform.parse_dump_row, which is not yet implemented (see
README.md) — this module is the second half of that same integration
boundary, not an independent gap.
"""

from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .config import IngestConfig
from .transform import parse_dump_row

STAGING_TABLES = ("artist", "release_group", "release", "work", "recording")


def ensure_staging_schema(conn: Connection, config: IngestConfig) -> None:
    conn.execute(text(f"create schema if not exists {config.staging_schema}"))
    for table in STAGING_TABLES:
        conn.execute(
            text(
                f"create table if not exists {config.staging_schema}.{table} "
                "(mbid text primary key, payload jsonb not null, loaded_at timestamptz not null default now())"
            )
        )


def load_table(
    conn: Connection, config: IngestConfig, table_name: str, raw_lines: Iterable[str]
) -> int:
    """Parses and stages one dump table's rows in batches. Returns the
    number of rows staged. Raises whatever parse_dump_row raises (currently
    always NotImplementedError) rather than silently skipping unparseable
    rows.
    """
    batch: list[dict] = []
    staged = 0

    def flush():
        nonlocal batch, staged
        if not batch:
            return
        conn.execute(
            text(
                f"insert into {config.staging_schema}.{table_name} (mbid, payload) "
                "values (:mbid, :payload) on conflict (mbid) do update set payload = excluded.payload, "
                "loaded_at = now()"
            ),
            batch,
        )
        staged += len(batch)
        batch = []

    for line in raw_lines:
        parsed = parse_dump_row(table_name, line)
        batch.append({"mbid": parsed.mbid, "payload": parsed.__dict__})
        if len(batch) >= config.batch_size:
            flush()
    flush()
    return staged
