# MusicBrainz ingestion pipeline

Loads a MusicBrainz data dump into our own canonical catalog tables
(`database/migrations/002_catalog_core.sql`, `003_catalog_identity.sql`), so
Phase 1 search runs against our own indexed Postgres copy — never the live
MusicBrainz API per request (that API is rate-limited to roughly 1 req/sec
per IP, which is a bootstrapping/lookup tool, not a production search
backend for any real traffic volume).

Full architecture rationale: `docs/architecture.md` section B.

## Pipeline stages (`pipeline.py`)

1. **download** (`download.py`) — fetch the dump archive, verify its
   checksum against MusicBrainz's published checksum file.
2. **stage** (`staging.py`) — `COPY` each dump table file directly into a
   `mb_staging` schema whose tables mirror MusicBrainz's *real* column
   layout (verified against `mbdata==31.0.1`, MetaBrainz's own SQLAlchemy
   schema mirror — see module docstring for what was and wasn't
   independently confirmed). This is a native Postgres `COPY`, not a
   custom per-line parser — the dump files are already in COPY text
   format.
3. **transform** (`transform.py`) — SQL joins resolve MusicBrainz's
   internal integer ids to our canonical UUIDs via a persistent
   `mb_staging.id_map` table (not a Python dict — at MusicBrainz's real
   scale, ~38.7M recordings as of a May 2026 snapshot, an in-process id
   map would be multiple GB for no reason). Text normalization reuses
   `app/catalog/normalize.py`, the same functions the live search path
   uses, so there's exactly one normalization implementation, not two
   that could drift apart.
4. **index** — the canonical tables' trigram indexes exist as part of
   their DDL; this stage just `ANALYZE`s after a bulk load.
5. **validate** (`validate.py`) — row-count sanity checks, ISRC coverage
   percentage, orphan-reference checks. A load that fails validation must
   not be promoted — see `pipeline.py`'s `IngestionFailed`.

`refresh.py` is the *only* module that calls the live MusicBrainz API, and
only for delta refreshes / targeted lookups / backfills of specific
recordings — never bulk search traffic — rate-limited to comply with
MusicBrainz's request policy.

## What's deliberately not ingested

MusicBrainz's tag/genre tables (`recording_tag`, `release_group_tag`, etc.)
are **not staged or transformed at all**. That data is licensed
CC BY-NC-SA 3.0 (non-commercial) — confirmed via MusicBrainz's own data
license documentation — so ingesting it into a paid product would violate
the license. Genre/style similarity has no data source in this schema yet;
see `docs/phase-0-checklist.md` item 5.

## Integration boundary — needs Phase 0 verification

The staging table column layouts in `staging.py` and the dump-file-path
assumption in `pipeline.py`'s `DUMP_FILE_PATHS` (`mbdump/<table>`, one file
per table) were verified against `mbdata` (`pip install mbdata`, an
authoritative package maintained by MetaBrainz themselves, read directly
from the installed package on disk) rather than by fetching
`musicbrainz.org`'s docs directly — that domain is blocked by this
environment's egress proxy. Two things specifically still need a primary-
source check in Phase 0 (`docs/phase-0-checklist.md` item 9):
which dump tarball (`mbdump.tar.bz2` vs. a derived tarball) actually
carries `release_group_meta`, `isrc`, and `l_recording_work`, and whether
the extracted path is really `mbdump/<table>` for every table listed.

This pipeline has been validated end-to-end against small synthetic
staging data in this repository's test suite (`tests/integration/
test_musicbrainz_ingest.py`) — the transform SQL and FK resolution logic
work correctly — but has not been run against a real MusicBrainz dump.
