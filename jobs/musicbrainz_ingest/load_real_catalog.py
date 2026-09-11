"""Loads a JSON dataset produced by fetch_real_catalog.py — which must be
run separately, on a host with real network access to musicbrainz.org
(this sandbox's egress is blocked from reaching it; see that module's and
dev_fixture.py's docstrings) — through the real staging + transform
ingestion pipeline against a target Postgres database.

Usage: python -m jobs.musicbrainz_ingest.load_real_catalog path/to/demo_catalog.json
"""

import json
import os
import sys
import uuid

from sqlalchemy import create_engine

from .dev_fixture import load_dataset

_GID_KEY = "gid"


def _parse_gids(dataset: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """fetch_real_catalog.py writes gid values as plain strings (JSON has
    no UUID type) — the staging pipeline expects Python uuid.UUID objects
    for uuid-typed columns, matching how dev_fixture.py's ARTISTS etc.
    already populate `gid` (via uuid.uuid5(...), not str). Converting here
    keeps this on the same tested code path rather than relying on
    psycopg to coerce a bare string against a uuid column.
    """
    parsed: dict[str, list[dict]] = {}
    for table, rows in dataset.items():
        new_rows = []
        for row in rows:
            new_row = dict(row)
            if new_row.get(_GID_KEY) is not None:
                new_row[_GID_KEY] = uuid.UUID(str(new_row[_GID_KEY]))
            new_rows.append(new_row)
        parsed[table] = new_rows
    return parsed


def main() -> None:
    json_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CATALOG_JSON_PATH", "demo_catalog.json")
    with open(json_path) as f:
        raw_dataset = json.load(f)
    dataset = _parse_gids(raw_dataset)

    dsn = os.environ.get(
        "DATABASE_URL", "postgresql://musicdiscovery:musicdiscovery@localhost:5432/musicdiscovery"
    )
    engine = create_engine(
        f"postgresql+psycopg://{dsn.split('://', 1)[1]}",
        connect_args={"options": "-c search_path=music_catalog,app,public"},
    )
    counts = load_dataset(engine, dsn, dataset)
    print(f"loaded real demo catalog: {counts}")


if __name__ == "__main__":
    main()
